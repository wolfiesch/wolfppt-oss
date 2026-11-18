"""Table text run and paragraph font facade helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .dml.color import ColorTextAndTransforms, fill_color_element
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    language_id_value as _language_id_value,
)
from .facade_values import (
    normalize_language_id as _normalize_language_id,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .shape_xml import (
    HyperlinkColorSourceRefusal,
    _set_paragraph_font_properties,
    hyperlink_color_source_member,
    hyperlink_color_source_xml,
)
from .table_cell_fill_facade import A_NS, _saved_table_cell_element
from .table_facade_state import (
    _set_table_cell_text_frame_paragraph_font,
    _set_table_cell_text_frame_paragraph_run_font,
    _set_table_cell_text_frame_paragraph_run_hyperlink_address,
    _set_table_cell_text_frame_paragraph_run_hyperlink_color_source,
    _table_cell_property_payload,
    _table_cell_text_frame_paragraph_font_value,
    _table_cell_text_frame_paragraph_fonts,
    _table_cell_text_frame_paragraph_run_font_value,
    _table_cell_text_frame_paragraph_run_fonts,
    _table_cell_text_frame_paragraph_run_hyperlink_address,
    _table_cell_text_frame_paragraph_run_hyperlink_color_source,
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

    @property
    def color_source(self) -> Any:
        """Where the link text takes its color, stored as ``hlinkClr/@val``.

        A ``PP_HYPERLINK_COLOR_SOURCE`` member, or ``None`` when the hyperlink
        carries no color source. A malformed saved value raises
        ``HyperlinkColorSourceRefusal``.
        """
        return hyperlink_color_source_member(self._color_source_xml())

    @color_source.setter
    def color_source(self, value: Any) -> None:
        requested = hyperlink_color_source_xml(value)
        if self.address is None:
            raise HyperlinkColorSourceRefusal(
                "color_source requires a hyperlink address on the table cell run"
            )
        try:
            unchanged = requested == self._color_source_xml()
        except HyperlinkColorSourceRefusal:
            unchanged = False  # an explicit edit replaces a malformed saved value
        if not unchanged:
            _set_table_cell_text_frame_paragraph_run_hyperlink_color_source(
                self._run._paragraph._cell,
                self._run._paragraph._index,
                self._run._index,
                requested,
            )

    def _color_source_xml(self) -> str | None:
        return _table_cell_text_frame_paragraph_run_hyperlink_color_source(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
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
    def strike(self) -> bool | None:
        return self._value("strike")

    @strike.setter
    def strike(self, value: bool | None) -> None:
        self._set("strike", None if value is None else bool(value))

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
    def color(self) -> TableCellTextRunFontColorFormat:
        return TableCellTextRunFontColorFormat(self._run)

    @property
    def fill(self) -> TableCellTextRunFontFillFormat:
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
    def fore_color(self) -> TableCellTextRunFontColorFormat:
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


class TableCellTextRunFontColorFormat(ColorTextAndTransforms):
    def __init__(self, run: Any) -> None:
        self._run = run

    def _color_element(self) -> ET.Element | None:
        cell, paragraph, run = (
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
        )
        return _table_font_color_element(cell, paragraph, run)

    def _set_color_element(self, color: ET.Element) -> None:
        _set_table_font_color_element(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            color,
            self._run._index,
        )

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}srgbClr":
            return None
        return _rgb_value(color.get("val"))

    @rgb.setter
    def rgb(self, value: Any) -> None:
        _set_table_font_base_color(self, "srgbClr", _normalize_rgb(value))

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.get("val"))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        _set_table_font_base_color(self, "schemeClr", _normalize_theme_color(value))


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
    def strike(self) -> bool | None:
        return _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "strike",
        )

    @strike.setter
    def strike(self, value: bool | None) -> None:
        self._set("strike", None if value is None else bool(value))

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
    def color(self) -> TableCellTextParagraphFontColorFormat:
        return TableCellTextParagraphFontColorFormat(self._paragraph)

    @property
    def fill(self) -> TableCellTextParagraphFontFillFormat:
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
    def fore_color(self) -> TableCellTextParagraphFontColorFormat:
        return TableCellTextParagraphFontColorFormat(self._paragraph)


class TableCellTextParagraphFontColorFormat(ColorTextAndTransforms):
    def __init__(self, paragraph: Any) -> None:
        self._paragraph = paragraph

    def _color_element(self) -> ET.Element | None:
        return _table_font_color_element(self._paragraph._cell, self._paragraph._index)

    def _set_color_element(self, color: ET.Element) -> None:
        _set_table_font_color_element(self._paragraph._cell, self._paragraph._index, color)

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}srgbClr":
            return None
        return _rgb_value(color.get("val"))

    @rgb.setter
    def rgb(self, value: Any) -> None:
        _set_table_font_base_color(self, "srgbClr", _normalize_rgb(value))

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.get("val"))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        _set_table_font_base_color(self, "schemeClr", _normalize_theme_color(value))


def _table_font_color_element(
    cell: Any, paragraph_index: int, run_index: int | None = None
) -> ET.Element | None:
    return fill_color_element(_table_font_properties(cell, paragraph_index, run_index))


def _table_font_properties(
    cell: Any, paragraph_index: int, run_index: int | None = None
) -> ET.Element | None:
    saved = _saved_table_cell_element(cell)
    properties = None
    if saved is not None:
        paragraphs = saved.findall(f"{{{A_NS}}}txBody/{{{A_NS}}}p")
        if paragraph_index < len(paragraphs):
            paragraph = paragraphs[paragraph_index]
            if run_index is None:
                properties = paragraph.find(f"{{{A_NS}}}pPr/{{{A_NS}}}defRPr")
            else:
                runs = paragraph.findall(f"{{{A_NS}}}r")
                if run_index < len(runs):
                    properties = runs[run_index].find(f"{{{A_NS}}}rPr")
    table = cell._table
    presentation = table._slide._presentation
    key = (table._slide._index, table._table_index, cell._row_idx, cell._col_idx, paragraph_index)
    queue = (
        presentation._table_cell_text_frame_paragraph_font_edits
        if run_index is None
        else presentation._table_cell_text_frame_paragraph_run_font_edits
    )
    edits = queue.get(key if run_index is None else (*key, run_index))
    if edits:
        properties = ET.Element(f"{{{A_NS}}}rPr") if properties is None else deepcopy(properties)
        _set_paragraph_font_properties(properties, edits)
    return properties


def _set_table_font_base_color(format: ColorTextAndTransforms, tag: str, value: str) -> None:
    existing = format._color_element()
    if existing is not None and existing.tag == f"{{{A_NS}}}{tag}" and existing.get("val") == value:
        return
    color = ET.Element(f"{{{A_NS}}}{tag}") if existing is None else deepcopy(existing)
    color.tag = f"{{{A_NS}}}{tag}"
    color.attrib.clear()
    color.set("val", value)
    format._set_color_element(color)


def _set_table_font_color_element(
    cell: Any, paragraph_index: int, color: ET.Element, run_index: int | None = None
) -> None:
    # Scalar font caches remain scalar for every existing table-format caller.
    scheme = color.tag == f"{{{A_NS}}}schemeClr"
    rgb = color.tag == f"{{{A_NS}}}srgbClr"
    scalar = {
        "fill_type": "solid",
        "color": color.get("val") if rgb else None,
        "theme_color": color.get("val") if scheme else None,
    }
    table = cell._table
    presentation = table._slide._presentation
    key = (table._slide._index, table._table_index, cell._row_idx, cell._col_idx, paragraph_index)
    payload = {
        "fill_type": "solid",
        "color": {"type": "xml", "value": ET.tostring(color, encoding="unicode")},
    }
    properties = _table_font_properties(cell, paragraph_index, run_index)
    pattern = None if properties is None else properties.find(f"{{{A_NS}}}pattFill")
    if pattern is not None:
        fill = {"type": "patterned", "pattern": pattern.get("prst")}
        for role in ("fore", "back"):
            existing = fill_color_element(properties, role)
            if existing is not None:
                fill[f"pattern_{role}_color"] = existing
        fill["pattern_fore_color"] = deepcopy(color)
        payload = {"fill_type": fill}
        scalar = {"fill_type": "patterned", "color": None, "theme_color": None}
        queue = (
            presentation._table_cell_text_frame_paragraph_font_edits
            if run_index is None
            else presentation._table_cell_text_frame_paragraph_run_font_edits
        )
        queue.get(key if run_index is None else (*key, run_index), {}).pop("color", None)
    if run_index is None:
        fonts = _table_cell_text_frame_paragraph_fonts(cell)
        fonts[paragraph_index].update(scalar)
        _table_cell_property_payload(cell)["text_frame_paragraph_fonts"] = fonts
        presentation._queue_table_cell_text_frame_paragraph_font(*key, payload)
    else:
        fonts = _table_cell_text_frame_paragraph_run_fonts(cell)
        fonts[paragraph_index][run_index].update(scalar)
        _table_cell_property_payload(cell)["text_frame_paragraph_run_fonts"] = fonts
        presentation._queue_table_cell_text_frame_paragraph_run_font(*key, run_index, payload)
