"""Writable row and column formats, materialized through the cell editing API.

Use ``TableRowFormat(table.rows[0]).fill.solid("112233")`` or
``TableColumnFormat(table.columns[1]).text_format.apply(TableTextFormat(bold=True))``.
An operation applies to the cells currently in that scope; it is not an inherited
style for cells inserted later. At intersections the last applied property wins.
Unspecified text properties remain unchanged, including run-local properties.

All targets and values are checked before queuing any edit. Merged cells, Strict
DrawingML and pending grid mutations are refused until their bulk-edit contracts
are qualified. The existing per-cell APIs remain available independently.

For a true table background, save the deck first, then call
``set_table_fill(source, output, rgb="112233")``. This clones the selected table
style and changes only its background, leaving direct cell fills and other
tables using the original style unchanged. Read it with ``read_table_fill``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET

from .editions import commercial_module
from .facade_values import normalize_rgb
from .package_parts import copy_package_with_replacements
from .render_package import read_package
from .table_cell_border_edits import validate_target_cell
from .table_facade_layout_state import _table_is_unsaved
from .table_xml import A_NS, _table_xml_element

if TYPE_CHECKING:
    from .table_facade import TableCell, TableColumn, TableRow

__all__ = [
    "TableColumnFormat",
    "TableFormatRefusal",
    "TableRowFormat",
    "TableScopeFillFormat",
    "TableScopeTextFormat",
    "TableTextFormat",
    "read_table_fill",
    "set_table_fill",
]


class TableFormatRefusal(ValueError):
    """Unsupported scoped table formatting, before any edit is queued."""


@dataclass(frozen=True)
class TableTextFormat:
    """Text properties to apply to every paragraph default and existing run.

    ``None`` means leave that property unchanged. ``size`` is an integral EMU
    font size (as in the cell font API), from 1 to 4000 points, in hundredths
    of a point. Color accepts a six-digit RGB string or three integral channels.
    This is a patch, not a replacement of the cell's text or hyperlinks.
    """

    name: str | None = None
    size: int | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    color: Any = None

    def _validated(self) -> dict[str, Any]:
        values = {}
        for attr in ("bold", "italic", "underline", "strike"):
            value = getattr(self, attr)
            if value is not None:
                if not isinstance(value, bool):
                    raise TableFormatRefusal(f"{attr} must be bool or None")
                values[attr] = value
        if self.name is not None:
            if not isinstance(self.name, str) or not self.name.strip():
                raise TableFormatRefusal("font name must be a nonempty string")
            if any(ord(char) < 32 for char in self.name):
                raise TableFormatRefusal("font name must not contain control characters")
            values["name"] = self.name
        if self.size is not None:
            if (
                isinstance(self.size, bool)
                or not isinstance(self.size, int)
                or not 12700 <= self.size <= 50800000
                or self.size % 127
            ):
                raise TableFormatRefusal(
                    "font size must be integral EMU, 1..4000 points, in hundredths of a point"
                )
            values["size"] = self.size
        if self.color is not None:
            values["color"] = _rgb(self.color)
        return values


def _rgb(value: Any) -> str:
    if not isinstance(value, str):
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            raise TableFormatRefusal("RGB must be six hex digits or three integral channels")
        if any(isinstance(channel, bool) or not isinstance(channel, int) for channel in value):
            raise TableFormatRefusal("RGB channels must be integers")
    try:
        return normalize_rgb(value)
    except (TypeError, ValueError) as exc:
        raise TableFormatRefusal(str(exc)) from exc


class _ScopeFormat:
    def __init__(self, scope: TableRow | TableColumn) -> None:
        self._scope = scope

    @property
    def fill(self) -> TableScopeFillFormat:
        return TableScopeFillFormat(self)

    @property
    def text_format(self) -> TableScopeTextFormat:
        return TableScopeTextFormat(self)

    def _cells(self) -> tuple[TableCell, ...]:
        table = self._scope._table
        presentation = table._slide._presentation
        if (
            not _table_is_unsaved(table)
            and b"http://purl.oclc.org/ooxml/drawingml/main" in table.part.blob
        ):
            raise TableFormatRefusal("Strict DrawingML scoped table edits are unsupported")
        if any(
            edit.get("slide_index") == table._slide._index
            and edit.get("table_index") == table._table_index
            for edit in presentation._table_row_column_edits
        ):
            raise TableFormatRefusal(
                "scoped formatting after pending grid mutations is unsupported"
            )
        try:
            cells = tuple(self._scope)
            if not cells:
                raise TableFormatRefusal("cannot format an empty row or column")
            for cell in cells:
                validate_target_cell(cell)
                if cell.is_merge_origin or cell.is_spanned:
                    raise TableFormatRefusal("scoped formatting of merged cells is unsupported")
        except (IndexError, ValueError) as exc:
            raise TableFormatRefusal(str(exc)) from exc
        return cells


class TableRowFormat(_ScopeFormat):
    """Apply explicit cell fill and text properties to a live table row."""

    def __init__(self, row: TableRow) -> None:
        from .table_facade import TableRow

        if not isinstance(row, TableRow):
            raise TableFormatRefusal("TableRowFormat requires a WolfPPT table row")
        super().__init__(row)


class TableColumnFormat(_ScopeFormat):
    """Apply explicit cell fill and text properties to a live table column."""

    def __init__(self, column: TableColumn) -> None:
        from .table_facade import TableColumn

        if not isinstance(column, TableColumn):
            raise TableFormatRefusal("TableColumnFormat requires a WolfPPT table column")
        super().__init__(column)


class TableScopeFillFormat:
    """Solid RGB and no-fill operations over a row or column's cells."""

    def __init__(self, scope: _ScopeFormat) -> None:
        self._scope = scope

    def solid(self, rgb: Any) -> None:
        color = _rgb(rgb)
        cells = self._scope._cells()
        for cell in cells:
            cell.fill.solid()
            cell.fill.fore_color.rgb = color

    def background(self) -> None:
        """Write explicit no-fill, using the cell fill API's background operation."""
        cells = self._scope._cells()
        for cell in cells:
            cell.fill.background()

    @property
    def rgb(self) -> str | None:
        """Read a uniform direct solid RGB; refuse mixed or other fill kinds."""
        values = []
        for cell in self._scope._cells():
            from .table_facade_state import _table_cell_fill_type

            kind = _table_cell_fill_type(cell)
            if kind == "solid":
                value = cell.fill.fore_color.rgb
                values.append(None if value is None else str(value))
            elif kind in (None, "background"):
                values.append(None)
            else:
                raise TableFormatRefusal("scoped RGB read requires solid or absent fills")
        if any(value != values[0] for value in values):
            raise TableFormatRefusal("row or column has mixed direct fill colors")
        return values[0]


class TableScopeTextFormat:
    """Apply a validated text patch without changing text, runs or hyperlinks."""

    def __init__(self, scope: _ScopeFormat) -> None:
        self._scope = scope

    def apply(self, formatting: TableTextFormat) -> None:
        if not isinstance(formatting, TableTextFormat):
            raise TableFormatRefusal("text formatting requires TableTextFormat")
        values = formatting._validated()
        cells = self._scope._cells()
        # Resolve every font before the first setter; malformed later cells must
        # not leave a prefix of the row/column with queued edits.
        fonts = []
        for cell in cells:
            for paragraph in cell.text_frame.paragraphs:
                fonts.append(paragraph.font)
                fonts.extend(run.font for run in paragraph.runs)
        for font in fonts:
            for attr, value in values.items():
                if attr == "color":
                    font.color.rgb = value
                else:
                    setattr(font, attr, value)


def _saved_table(source: Path, slide_index: int, table_index: int) -> tuple[Any, ...]:
    from .presentation import Presentation

    for index in (slide_index, table_index):
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise TableFormatRefusal("slide and table indices must be nonnegative integers")
    package = read_package(source)
    try:
        presentation = Presentation(source)
        slide_part = presentation.slides[slide_index].partname.lstrip("/")
        slide_root = package.xml(slide_part)
        table = _table_xml_element(slide_root, table_index)
    except (IndexError, ValueError) as exc:
        raise TableFormatRefusal(
            "selected saved table does not exist or uses Strict DrawingML"
        ) from exc
    properties = table.find(f"{{{A_NS}}}tblPr")
    if properties is None:
        raise TableFormatRefusal("table has no properties")
    style_id = properties.find(f"{{{A_NS}}}tableStyleId")
    if style_id is None or not style_id.text:
        raise TableFormatRefusal("table background requires a selected table style")
    presentation_part = package.related_part("", "officeDocument")
    if presentation_part is None:
        raise TableFormatRefusal("package has no presentation relationship")
    styles_part = package.related_part(presentation_part, "tableStyles")
    if styles_part is None:
        styles_part = presentation_part.rsplit("/", 1)[0] + "/tableStyles.xml"
        styles_root = (
            package.xml(styles_part)
            if package.read_optional(styles_part) is not None
            else ET.Element(f"{{{A_NS}}}tblStyleLst", {"def": style_id.text})
        )
    else:
        styles_root = package.xml(styles_part)
    style = next(
        (
            child
            for child in styles_root
            if child.tag == f"{{{A_NS}}}tblStyle" and child.get("styleId") == style_id.text
        ),
        None,
    )
    if style is None:
        renderer = commercial_module("render_table", "Resolving a built-in table style definition")
        style = renderer.built_in_table_style(style_id.text)
    if style is None:
        raise TableFormatRefusal("selected table style has no known definition")
    return package, slide_part, slide_root, properties, styles_part, styles_root, style


def set_table_fill(
    source: str | Path,
    output: str | Path,
    *,
    rgb: Any,
    slide_index: int = 0,
    table_index: int = 0,
) -> None:
    """Write a real table background without overwriting direct cell fills.

    Clone the selected table style with a new background fill reference, then
    assign the private style to this table only. Reuse an unmodified placeholder
    solid fill in the table's theme; refuse themes without one before writing.
    All other package members retain their original bytes. When the source has
    no tableStyles part, add one and register it in presentation relationships
    and content types. A selected known built-in or package style is required.
    """
    color = _rgb(rgb)
    source, output = Path(source), Path(output)
    package, slide_part, slide_root, properties, styles_part, styles_root, style = _saved_table(
        source, slide_index, table_index
    )
    # Resolve the selected slide's layout/master theme, not the first theme in
    # the package: decks may have several masters with different fill matrices.
    layout = package.related_part(slide_part, "slideLayout")
    master = None if layout is None else package.related_part(layout, "slideMaster")
    theme_part = None if master is None else package.related_part(master, "theme")
    if theme_part is None:
        raise TableFormatRefusal("table background requires the slide's master theme")
    theme = package.xml(theme_part)
    fills = theme.find(f".//{{{A_NS}}}fmtScheme/{{{A_NS}}}fillStyleLst")
    index = None
    for position, fill in enumerate(() if fills is None else fills, start=1):
        if fill.tag != f"{{{A_NS}}}solidFill" or len(fill) != 1:
            continue
        placeholder = fill[0]
        if (
            placeholder.tag == f"{{{A_NS}}}schemeClr"
            and placeholder.attrib == {"val": "phClr"}
            and len(placeholder) == 0
        ):
            index = position
            break
    if index is None:
        raise TableFormatRefusal("table background requires an unmodified solid theme placeholder")
    private_style = deepcopy(style)
    identifier = (
        "{"
        + str(
            uuid5(
                NAMESPACE_URL,
                f"wolfppt:table-fill:{package.digest}:{slide_part}:{table_index}:{color}",
            )
        ).upper()
        + "}"
    )
    private_style.set("styleId", identifier)
    private_style.set("styleName", f"Wolf table background {color}")
    for background in private_style.findall(f"{{{A_NS}}}tblBg"):
        private_style.remove(background)
    background = ET.Element(f"{{{A_NS}}}tblBg")
    reference = ET.SubElement(background, f"{{{A_NS}}}fillRef", {"idx": str(index)})
    ET.SubElement(reference, f"{{{A_NS}}}srgbClr", {"val": color})
    private_style.insert(0, background)
    styles_root.append(private_style)
    properties.find(f"{{{A_NS}}}tableStyleId").text = identifier
    replacements = {
        slide_part: ET.tostring(slide_root, encoding="utf-8", xml_declaration=True),
        styles_part: ET.tostring(styles_root, encoding="utf-8", xml_declaration=True),
    }
    presentation_part = package.related_part("", "officeDocument")
    if package.related_part(presentation_part, "tableStyles") is None:
        import posixpath

        rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        type_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        folder, name = posixpath.split(presentation_part)
        rels_part = posixpath.join(folder, "_rels", name + ".rels")
        rels = package.xml(rels_part)
        used_ids = {child.get("Id") for child in rels}
        suffix = 1
        while f"rIdWolfTableStyles{suffix}" in used_ids:
            suffix += 1
        ET.SubElement(
            rels,
            f"{{{rel_ns}}}Relationship",
            {
                "Id": f"rIdWolfTableStyles{suffix}",
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles",
                "Target": posixpath.relpath(styles_part, folder),
            },
        )
        types = package.xml("[Content_Types].xml")
        part_name = "/" + styles_part
        if not any(child.get("PartName") == part_name for child in types):
            ET.SubElement(
                types,
                f"{{{type_ns}}}Override",
                {
                    "PartName": part_name,
                    "ContentType": (
                        "application/vnd.openxmlformats-officedocument"
                        ".presentationml.tableStyles+xml"
                    ),
                },
            )
        replacements[rels_part] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)
        replacements["[Content_Types].xml"] = ET.tostring(
            types, encoding="utf-8", xml_declaration=True
        )
    copy_package_with_replacements(source, output, replacements)


def read_table_fill(
    source: str | Path, *, slide_index: int = 0, table_index: int = 0
) -> str | None:
    """Read the direct RGB background reference authored by ``set_table_fill``.

    An absent background returns None. Scheme or transformed backgrounds require
    effective formatting readback and are refused here rather than misreported.
    """
    *_, style = _saved_table(Path(source), slide_index, table_index)
    background = style.find(f"{{{A_NS}}}tblBg")
    if background is None:
        return None
    reference = background.find(f"{{{A_NS}}}fillRef")
    if reference is not None and len(reference) == 1:
        color = reference[0]
        if color.tag == f"{{{A_NS}}}srgbClr" and len(color) == 0:
            return _rgb(color.get("val"))
    raise TableFormatRefusal("table background is not a direct unmodified RGB fill reference")
