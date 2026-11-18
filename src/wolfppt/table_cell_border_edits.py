"""Table cell border editing, inspection, and XML application for Presentation tables.

DrawingML schema is authoritative: a:lnL, a:lnR, a:lnT, a:lnB,
a:lnTlToBr, and a:lnBlToTr are direct ordered children of a:tcPr
(CT_TableCellProperties). There is NO w:tcBorders wrapper and no insideH/insideV
cell edge. Supported styling: bounded width (0..20116800 EMUs), solid RGB color,
and explicit noFill.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    no_fill_element as _no_fill_element,
)
from .dml_fill import (
    set_solid_fill_rgb as _set_solid_fill_rgb,
)
from .dml_fill import (
    solid_fill_element as _solid_fill_element,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
)
from .facade_values import (
    emu_value as _emu_value,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .table_facade_cell_state import (
    _table_cell_property_payload,
)
from .table_xml import (
    _table_cell_xml_element,
)
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

RECTANGULAR_EDGES = ("left", "right", "top", "bottom")
DIAGONAL_EDGES = ("diagonal_down", "diagonal_up")
VALID_EDGES = RECTANGULAR_EDGES + DIAGONAL_EDGES

EDGE_TO_TAG = {
    "left": "lnL",
    "right": "lnR",
    "top": "lnT",
    "bottom": "lnB",
    "diagonal_down": "lnTlToBr",
    "diagonal_up": "lnBlToTr",
}

TAG_TO_EDGE = {tag: edge for edge, tag in EDGE_TO_TAG.items()}

# DrawingML ST_LineWidth: minInclusive 0, maxInclusive 20116800 (~22 inches)
MIN_BORDER_WIDTH_EMU = 0
MAX_BORDER_WIDTH_EMU = 20116800

# Canonical child element order for a:tcPr per DrawingML schema:
# lnL -> lnR -> lnT -> lnB -> lnTlToBr -> lnBlToTr -> cell3D -> EG_FillProperties -> headers -> extLst
_TCPR_SCHEMA_ORDER: dict[str, int] = {
    "lnL": 1,
    "lnR": 2,
    "lnT": 3,
    "lnB": 4,
    "lnTlToBr": 5,
    "lnBlToTr": 6,
    "cell3D": 7,
    "noFill": 8,
    "solidFill": 8,
    "gradFill": 8,
    "blipFill": 8,
    "pattFill": 8,
    "grpFill": 8,
    "headers": 9,
    "extLst": 999,
}


def _register_namespaces() -> None:
    ET.register_namespace("p", P_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("r", R_NS)


def normalize_edge(edge: str) -> str:
    """Normalize and validate a DrawingML table-cell border name.

    Direct cell lines include the four rectangular edges and the two diagonals.
    Table-level or WordprocessingML edges such as 'insideH' or 'insideV' are rejected.
    """
    if not isinstance(edge, str):
        raise TypeError(f"edge must be a string, got {type(edge).__name__}")
    norm = edge.strip().lower()
    if norm in (
        "insideh",
        "insidev",
        "inside_h",
        "inside_v",
        "insidehorizontal",
        "insidevertical",
    ):
        raise ValueError(
            f"edge {edge!r} is not a valid DrawingML cell border; insideH/insideV cell edges are not supported"
        )
    if norm not in VALID_EDGES:
        raise ValueError(
            f"unsupported border edge: {edge!r}; expected one of {VALID_EDGES}"
        )
    return norm


def validate_border_width(value: Any) -> int:
    """Validate and coerce line width in EMUs.

    Enforces 0 <= width <= 20116800 EMUs. Rejects booleans and non-integral types.
    """
    if isinstance(value, bool):
        raise TypeError(f"border width must be an integer EMU value, got bool {value}")
    try:
        width = _coerce_emu(value, "border width")
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"border width must be an integer EMU value, got {type(value).__name__}"
        ) from exc
    if width < MIN_BORDER_WIDTH_EMU or width > MAX_BORDER_WIDTH_EMU:
        raise ValueError(
            f"border width must be between {MIN_BORDER_WIDTH_EMU} and {MAX_BORDER_WIDTH_EMU} EMUs, got {width}"
        )
    return width


def _resolve_owning_table_shape(table: Any) -> tuple[Any, int]:
    """Find the live shape on the slide that owns this table and return (shape, table_index).

    Uses object identity of the table payload rather than numeric table index alone,
    preventing retargeting after table deletions.
    """
    slide = getattr(table, "_slide", None)
    if slide is None:
        raise ValueError("cannot edit borders on a cell without a slide")

    table_payload = getattr(table, "_payload", None)
    presentation = getattr(slide, "_presentation", None)

    # 1. Search active shapes on slide
    shapes = getattr(slide, "shapes", None)
    if shapes is None:
        shapes = getattr(slide, "_shapes", None)

    owning_shape = None
    if shapes is not None:
        shape_list = getattr(shapes, "_shapes", shapes)
        if isinstance(shape_list, (list, tuple)):
            for s in shape_list:
                s_payload = getattr(s, "_payload", {})
                tables = s_payload.get("tables") or []
                if any(t is table_payload for t in tables):
                    owning_shape = s
                    break

    # 2. Fall back to table._shape if directly set
    if owning_shape is None:
        direct_shape = getattr(table, "_shape", None)
        if direct_shape is not None:
            owning_shape = direct_shape

    # 3. If no owning shape found on the slide:
    if owning_shape is None:
        raise ValueError("cannot edit borders on a deleted table")

    # 4. Check if owning shape was marked deleted
    if getattr(owning_shape, "_payload", {}).get("_deleted", False):
        raise ValueError("cannot edit borders on a deleted table")

    # 5. Check if slide has queued deletion for this shape
    if presentation is not None:
        shape_deletes = getattr(presentation, "_shape_deletes", set())
        slide_idx = getattr(slide, "_index", None)
        shape_idx = getattr(owning_shape, "_index", None)
        if (slide_idx, shape_idx) in shape_deletes:
            raise ValueError("cannot edit borders on a deleted table")

    # 6. Stable table index from canonical shape facade. Newly added (pending)
    # tables are valid targets: save materializes them before the border step
    # runs, as it does for sibling table-cell property edits.
    live_table_index = getattr(
        owning_shape, "_table_index", getattr(table, "_table_index", 0)
    )
    return owning_shape, live_table_index


def validate_target_cell(cell: Any) -> tuple[Any, int]:
    """Ensure target cell belongs to a live, non-deleted slide and table, and is not part of a pending merge.

    Newly added slides and tables, including those on an in-memory
    ``Presentation()``, are accepted; queued borders apply after save
    materializes them.

    Refuses:
    - Deleted targets (slide marked _deleted, shape or table marked _deleted, row/col out of bounds or deleted)
    - Pending merge targets (cell has h_merge/v_merge or is in presentation._table_cell_merge_edits)

    Returns (owning_shape, live_table_index).
    """
    table = getattr(cell, "_table", None)
    if table is None:
        raise ValueError("cannot edit borders on a detached cell")

    slide = getattr(table, "_slide", None)
    if slide is None:
        raise ValueError("cannot edit borders on a cell without a slide")

    # 1. Slide deleted checks
    if getattr(slide, "_deleted", False):
        raise ValueError("cannot edit borders on a deleted slide")

    # 2. Presentation linkage
    presentation = getattr(slide, "_presentation", None)
    if presentation is None:
        raise ValueError("cannot edit borders on a cell without a presentation")

    # 3. Resolve owning shape, stable table index, and verify shape lifecycle (deleted)
    owning_shape, live_table_index = _resolve_owning_table_shape(table)

    # 4. Check row and column bounds & deletions
    rows = getattr(table, "_rows", None)
    row_idx = getattr(cell, "_row_idx", -1)
    col_idx = getattr(cell, "_col_idx", -1)
    if rows is not None and (
        row_idx < 0
        or row_idx >= len(rows)
        or col_idx < 0
        or (rows and col_idx >= len(rows[0]))
    ):
        raise IndexError(
            "target cell row or column has been deleted or is out of bounds"
        )

    slide_idx = getattr(slide, "_index", None)
    for edit in getattr(presentation, "_table_row_column_edits", []):
        if (
            edit.get("slide_index") == slide_idx
            and edit.get("table_index") == live_table_index
        ):
            edit_type = edit.get("type")
            if edit_type == "delete_table_row":
                del_r = edit.get("row_index")
                if del_r is not None and (
                    del_r == row_idx or (rows and row_idx >= len(rows))
                ):
                    raise IndexError(
                        f"target cell row {row_idx} has been deleted or is out of bounds"
                    )
            elif edit_type == "delete_table_column":
                del_c = edit.get("col_index")
                if del_c is not None and (
                    del_c == col_idx or (rows and col_idx >= len(rows[0]))
                ):
                    raise IndexError(
                        f"target cell column {col_idx} has been deleted or is out of bounds"
                    )

    # 5. Pending merge checks
    cell_payload = _table_cell_property_payload(cell)
    if (
        cell_payload.get("h_merge")
        or cell_payload.get("v_merge")
        or getattr(cell, "is_spanned", False)
    ):
        raise ValueError(
            f"cannot edit borders on cell ({row_idx}, {col_idx}): cell is spanned by a merge"
        )

    if hasattr(presentation, "_table_cell_merge_edits"):
        for edit in presentation._table_cell_merge_edits:
            if (
                edit.get("slide_index") == slide_idx
                and edit.get("table_index") == live_table_index
                and edit.get("kind") == "merge"
            ):
                r_min = edit.get("row_min", 0)
                r_max = edit.get("row_max", 0)
                c_min = edit.get("col_min", 0)
                c_max = edit.get("col_max", 0)
                if r_min <= row_idx <= r_max and c_min <= col_idx <= c_max:
                    raise ValueError(
                        f"cannot edit borders on cell ({row_idx}, {col_idx}): target is part of a pending merge"
                    )

    return owning_shape, live_table_index


@dataclass
class TableCellBorderSpec:
    """Explicit border specification for one table cell edge."""

    width: int | None = None
    color: str | None = None
    no_fill: bool = False
    clear: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "color": self.color,
            "no_fill": self.no_fill,
            "clear": self.clear,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableCellBorderSpec:
        return cls(
            width=data.get("width"),
            color=data.get("color"),
            no_fill=bool(data.get("no_fill", False)),
            clear=bool(data.get("clear", False)),
        )


def read_cell_borders_from_xml(
    cell_element: ET.Element | None,
) -> dict[str, TableCellBorderSpec]:
    """Read explicit DrawingML borders from a table cell's XML element."""
    result: dict[str, TableCellBorderSpec] = {}
    if cell_element is None:
        return result
    tc_pr = cell_element.find(f"{{{A_NS}}}tcPr")
    if tc_pr is None:
        return result

    for edge, tag in EDGE_TO_TAG.items():
        ln = tc_pr.find(f"{{{A_NS}}}{tag}")
        if ln is None:
            continue
        width = None
        raw_w = ln.attrib.get("w")
        if raw_w is not None:
            try:
                width = int(raw_w)
            except ValueError:
                pass
        no_fill = ln.find(f"{{{A_NS}}}noFill") is not None
        color = None
        solid_fill = ln.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            srgb = solid_fill.find(f"{{{A_NS}}}srgbClr")
            if srgb is not None:
                color = srgb.attrib.get("val")
        result[edge] = TableCellBorderSpec(
            width=width,
            color=color,
            no_fill=no_fill,
            clear=False,
        )
    return result


def _read_cell_borders_for_cell(cell: Any) -> dict[str, TableCellBorderSpec]:
    table = getattr(cell, "_table", None)
    if table is None:
        return {}
    slide = getattr(table, "_slide", None)
    if slide is None:
        return {}
    slide_part = getattr(slide, "partname", None)
    presentation = getattr(slide, "_presentation", None)
    pres_path = getattr(presentation, "path", None)
    if slide_part and pres_path:
        try:
            _, live_table_index = _resolve_owning_table_shape(table)
        except (ValueError, NotImplementedError):
            live_table_index = getattr(table, "_table_index", 0)
        try:
            with zipfile.ZipFile(pres_path) as package:
                root = ET.fromstring(package.read(slide_part))
            cell_el = _table_cell_xml_element(
                root,
                live_table_index,
                cell._row_idx,
                cell._col_idx,
            )
            return read_cell_borders_from_xml(cell_el)
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            pass
    return {}


def get_cell_border_spec(cell: Any, edge: str) -> TableCellBorderSpec | None:
    """Retrieve the current border spec for a cell edge, checking queues first then XML."""
    norm_edge = normalize_edge(edge)
    presentation = getattr(
        getattr(getattr(cell, "_table", None), "_slide", None), "_presentation", None
    )

    # 1. Check queued edits
    if presentation is not None and hasattr(presentation, "_table_cell_border_edits"):
        try:
            _, live_tbl_idx = _resolve_owning_table_shape(cell._table)
        except (ValueError, NotImplementedError):
            live_tbl_idx = cell._table._table_index
        key = (
            cell._table._slide._index,
            live_tbl_idx,
            cell._row_idx,
            cell._col_idx,
        )
        cell_edits = presentation._table_cell_border_edits.get(key)
        if cell_edits and norm_edge in cell_edits:
            spec_data = cell_edits[norm_edge]
            if isinstance(spec_data, TableCellBorderSpec):
                return None if spec_data.clear else spec_data
            if isinstance(spec_data, dict):
                return (
                    None
                    if spec_data.get("clear")
                    else TableCellBorderSpec.from_dict(spec_data)
                )

    # 2. Check cached payload or read from XML
    payload = _table_cell_property_payload(cell)
    borders_dict = payload.get("borders")
    if borders_dict is None:
        borders_dict = _read_cell_borders_for_cell(cell)
        payload["borders"] = borders_dict

    spec = borders_dict.get(norm_edge)
    if spec is not None and spec.clear:
        return None
    return spec


def set_cell_border(
    cell: Any,
    edge: str,
    *,
    width: Any = None,
    color: Any = None,
    no_fill: bool = False,
) -> None:
    """Author explicit border properties on a table cell edge.

    Validates target cell before queue mutation. Overwrites any previous edit in the queue.
    """
    _, live_table_index = validate_target_cell(cell)
    norm_edge = normalize_edge(edge)

    if no_fill and color is not None:
        raise ValueError("cannot specify both color and no_fill=True")

    width_emu = validate_border_width(width) if width is not None else None
    color_hex = _normalize_rgb(color) if color is not None else None

    current = get_cell_border_spec(cell, norm_edge)
    new_width = (
        width_emu if width_emu is not None else (current.width if current else None)
    )

    if no_fill:
        new_color = None
        new_no_fill = True
    elif color_hex is not None:
        new_color = color_hex
        new_no_fill = False
    else:
        new_color = current.color if current else None
        new_no_fill = current.no_fill if current else False

    spec = TableCellBorderSpec(
        width=new_width,
        color=new_color,
        no_fill=new_no_fill,
        clear=False,
    )

    presentation = cell._table._slide._presentation
    if not hasattr(presentation, "_table_cell_border_edits"):
        presentation._table_cell_border_edits = {}

    key = (
        cell._table._slide._index,
        live_table_index,
        cell._row_idx,
        cell._col_idx,
    )
    presentation._table_cell_border_edits.setdefault(key, {})[norm_edge] = (
        spec.to_dict()
    )

    payload = _table_cell_property_payload(cell)
    payload.setdefault("borders", {})[norm_edge] = spec


def clear_cell_border(cell: Any, edge: str) -> None:
    """Clear explicit border formatting on a table cell edge."""
    _, live_table_index = validate_target_cell(cell)
    norm_edge = normalize_edge(edge)

    presentation = cell._table._slide._presentation
    if not hasattr(presentation, "_table_cell_border_edits"):
        presentation._table_cell_border_edits = {}

    key = (
        cell._table._slide._index,
        live_table_index,
        cell._row_idx,
        cell._col_idx,
    )
    presentation._table_cell_border_edits.setdefault(key, {})[norm_edge] = {
        "width": None,
        "color": None,
        "no_fill": False,
        "clear": True,
    }

    payload = _table_cell_property_payload(cell)
    if "borders" in payload:
        payload["borders"].pop(norm_edge, None)


def clear_all_cell_borders(cell: Any) -> None:
    """Clear every explicit rectangular or diagonal border on a cell."""
    for edge in VALID_EDGES:
        clear_cell_border(cell, edge)


class TableCellBorder:
    """Facade for accessing and mutating a single table cell border edge."""

    def __init__(self, cell: Any, edge: str) -> None:
        self._cell = cell
        self._edge = normalize_edge(edge)

    @property
    def edge(self) -> str:
        return self._edge

    @property
    def is_explicit(self) -> bool:
        spec = get_cell_border_spec(self._cell, self._edge)
        return spec is not None and not spec.clear

    @property
    def width(self) -> Any:
        spec = get_cell_border_spec(self._cell, self._edge)
        if spec is None or spec.width is None:
            return None
        return _emu_value(spec.width)

    @width.setter
    def width(self, value: Any) -> None:
        set_cell_border(self._cell, self._edge, width=value)

    @property
    def color(self) -> Any:
        spec = get_cell_border_spec(self._cell, self._edge)
        if spec is None or spec.color is None:
            return None
        return _rgb_value(spec.color)

    @color.setter
    def color(self, value: Any) -> None:
        set_cell_border(self._cell, self._edge, color=value)

    @property
    def fill_type(self) -> str | None:
        spec = get_cell_border_spec(self._cell, self._edge)
        if spec is None:
            return None
        if spec.no_fill:
            return "no_fill"
        if spec.color is not None:
            return "solid"
        return None

    def solid(self, color: Any = None) -> None:
        """Set solid fill with optional color."""
        set_cell_border(self._cell, self._edge, color=color, no_fill=False)

    def no_fill(self) -> None:
        """Set explicit noFill on this border."""
        set_cell_border(self._cell, self._edge, no_fill=True)

    def clear(self) -> None:
        """Clear explicit border formatting from this edge."""
        clear_cell_border(self._cell, self._edge)


class TableCellBorders:
    """Facade providing access to rectangular and diagonal table-cell borders."""

    def __init__(self, cell: Any) -> None:
        self._cell = cell

    @property
    def left(self) -> TableCellBorder:
        return TableCellBorder(self._cell, "left")

    @property
    def right(self) -> TableCellBorder:
        return TableCellBorder(self._cell, "right")

    @property
    def top(self) -> TableCellBorder:
        return TableCellBorder(self._cell, "top")

    @property
    def bottom(self) -> TableCellBorder:
        return TableCellBorder(self._cell, "bottom")

    @property
    def diagonal_down(self) -> TableCellBorder:
        """The top-left to bottom-right cell diagonal."""
        return TableCellBorder(self._cell, "diagonal_down")

    @property
    def diagonal_up(self) -> TableCellBorder:
        """The bottom-left to top-right cell diagonal."""
        return TableCellBorder(self._cell, "diagonal_up")

    def __getitem__(self, edge: str) -> TableCellBorder:
        return TableCellBorder(self._cell, edge)

    def set_all(
        self,
        *,
        width: Any = None,
        color: Any = None,
        no_fill: bool = False,
    ) -> None:
        """Apply uniform formatting to the four rectangular border edges."""
        for edge in RECTANGULAR_EDGES:
            set_cell_border(self._cell, edge, width=width, color=color, no_fill=no_fill)

    def clear_all(self) -> None:
        """Clear every explicit rectangular or diagonal cell border."""
        clear_all_cell_borders(self._cell)


def cell_borders(cell: Any) -> TableCellBorders:
    """Lightweight facade-access helper returning TableCellBorders for a TableCell."""
    return TableCellBorders(cell)


# --- XML Application ---


def _ensure_tc_pr(cell_element: ET.Element) -> ET.Element:
    """Find or create a:tcPr inside an a:tc element in DrawingML schema order."""
    tc_pr = cell_element.find(f"{{{A_NS}}}tcPr")
    if tc_pr is not None:
        return tc_pr

    tc_pr = ET.Element(f"{{{A_NS}}}tcPr")
    ext_lst = cell_element.find(f"{{{A_NS}}}extLst")
    if ext_lst is not None:
        idx = list(cell_element).index(ext_lst)
        cell_element.insert(idx, tc_pr)
    else:
        cell_element.append(tc_pr)
    return tc_pr


def reorder_tc_pr_children(tc_pr: ET.Element) -> None:
    """Ensure children of a:tcPr strictly adhere to DrawingML schema order.

    Order: lnL -> lnR -> lnT -> lnB -> lnTlToBr -> lnBlToTr -> cell3D -> EG_FillProperties -> headers -> extLst.
    Preserves original existing fill and relative order of unknown elements.
    """
    children = list(tc_pr)

    def _rank(child: ET.Element) -> int:
        local = _xml_local_name(child.tag)
        return _TCPR_SCHEMA_ORDER.get(local, 500)

    sorted_children = sorted(children, key=_rank)
    if sorted_children != children:
        for child in children:
            tc_pr.remove(child)
        for child in sorted_children:
            tc_pr.append(child)


def apply_border_spec_to_tc_pr(
    tc_pr: ET.Element,
    edge: str,
    spec: TableCellBorderSpec | dict[str, Any],
) -> None:
    """Apply an edge border specification to an a:tcPr XML element.

    Maintains correct DrawingML child order, preserves unrelated elements and attributes.
    """
    if isinstance(spec, dict):
        spec = TableCellBorderSpec.from_dict(spec)

    tag = EDGE_TO_TAG[normalize_edge(edge)]
    ln = tc_pr.find(f"{{{A_NS}}}{tag}")

    if spec.clear:
        if ln is not None:
            tc_pr.remove(ln)
        return

    if ln is None:
        ln = ET.Element(f"{{{A_NS}}}{tag}")
        tc_pr.append(ln)

    if spec.width is not None:
        ln.set("w", str(spec.width))

    if spec.no_fill:
        _no_fill_element(ln)
    elif spec.color is not None:
        solid = _solid_fill_element(ln)
        _set_solid_fill_rgb(solid, spec.color)

    reorder_tc_pr_children(tc_pr)


def apply_slide_cell_border_edits(
    slide_root: ET.Element,
    cell_edits: dict[tuple[int, int, int], dict[str, Any]],
) -> None:
    """Apply border edits for cells on a single slide XML tree."""
    for (table_index, row_index, col_index), edges in cell_edits.items():
        cell_el = _table_cell_xml_element(slide_root, table_index, row_index, col_index)
        tc_pr = _ensure_tc_pr(cell_el)
        for edge, spec in edges.items():
            apply_border_spec_to_tc_pr(tc_pr, edge, spec)


def apply_table_cell_border_edits(
    input_path: str | Path,
    output_path: str | Path,
    border_edits: (
        list[tuple[tuple[int, int, int, int], dict[str, Any]]]
        | dict[tuple[int, int, int, int], dict[str, Any]]
    ),
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    """Apply queued table cell border edits to a presentation package.

    Returns None, matching existing table edit apply return conventions.
    Preserves all unrelated package parts and namespaces.
    """
    input_p = Path(input_path)
    output_p = Path(output_path)

    if isinstance(border_edits, dict):
        items = list(border_edits.items())
    else:
        items = list(border_edits)

    edits_by_slide: dict[int, dict[tuple[int, int, int], dict[str, Any]]] = {}
    for (slide_index, table_index, row_index, col_index), edges in items:
        if not edges:
            continue
        slide_bucket = edits_by_slide.setdefault(slide_index, {})
        cell_bucket = slide_bucket.setdefault((table_index, row_index, col_index), {})
        cell_bucket.update(edges)

    if not edits_by_slide:
        _copy_package_with_replacements(input_p, output_p, {})
        return

    slides = (
        slide_payloads if slide_payloads is not None else _load_slide_payloads(input_p)
    )

    replacements: dict[str, bytes] = {}
    _register_namespaces()

    with zipfile.ZipFile(input_p) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            apply_slide_cell_border_edits(root, slide_edits)
            replacements[slide_part] = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )

    _copy_package_with_replacements(input_p, output_p, replacements)
