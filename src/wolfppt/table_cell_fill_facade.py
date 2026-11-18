"""Table cell fill facade classes for python-pptx-compatible access."""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .dml.color import ColorTextAndTransforms, fill_color_element
from .dml_fill import (
    brightness_from_color_element as _brightness_from_color_element,
)
from .dml_fill import (
    color_element as _color_from_payload,
)
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
)
from .dml_fill import (
    gradient_stop_element as _gradient_stop_element,
)
from .dml_fill import (
    has_brightness_modifiers as _has_brightness_modifiers,
)
from .dml_fill import (
    set_color_brightness as _set_color_brightness,
)
from .facade_values import (
    color_type_value as _color_type_value,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    normalize_pattern_type as _normalize_pattern_type,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    pattern_type_value as _pattern_type_value,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .shape_format_facade import FillFormat
from .table_facade_layout_state import _table_is_unsaved
from .table_facade_state import (
    _table_cell_fill_pattern,
    _table_cell_fill_type,
    _table_cell_gradient_fill_payload,
    _table_cell_pattern_rgb,
    _table_cell_pattern_theme_color,
    _table_cell_property_payload,
    _table_cell_solid_rgb,
    _table_cell_solid_theme_color,
)
from .table_xml import _table_cell_xml_element

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class TableCellFillFormat:
    def __init__(self, cell: Any) -> None:
        self._cell = cell

    @classmethod
    def from_fill_parent(cls, eg_fillProperties_parent: Any) -> FillFormat:
        return FillFormat.from_fill_parent(eg_fillProperties_parent)

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        payload = _table_cell_property_payload(self._cell)
        payload["fill_type"] = "solid"
        payload.pop("fill_rgb", None)
        payload.pop("fill_theme_color", None)
        payload.pop("fill_pattern", None)
        payload.pop("fill_pattern_fore_rgb", None)
        payload.pop("fill_pattern_back_rgb", None)
        payload.pop("fill_pattern_fore_theme_color", None)
        payload.pop("fill_pattern_back_theme_color", None)
        payload.pop("fill_gradient", None)
        self._cell._table._slide._presentation._queue_table_cell_fill_solid(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
        )

    def background(self) -> None:
        payload = _table_cell_property_payload(self._cell)
        if self._fill_type() == "background":
            return
        payload["fill_type"] = "background"
        payload.pop("fill_rgb", None)
        payload.pop("fill_theme_color", None)
        payload.pop("fill_pattern", None)
        payload.pop("fill_pattern_fore_rgb", None)
        payload.pop("fill_pattern_back_rgb", None)
        payload.pop("fill_pattern_fore_theme_color", None)
        payload.pop("fill_pattern_back_theme_color", None)
        payload.pop("fill_gradient", None)
        self._cell._table._slide._presentation._queue_table_cell_fill_background(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        pattern = None
        payload = _table_cell_property_payload(self._cell)
        payload["fill_type"] = "patterned"
        payload.pop("fill_rgb", None)
        payload.pop("fill_theme_color", None)
        payload["fill_pattern"] = pattern
        payload.pop("fill_gradient", None)
        self._cell._table._slide._presentation._queue_table_cell_fill_patterned(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            pattern,
        )

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        gradient = _default_gradient_payload()
        payload = _table_cell_property_payload(self._cell)
        payload["fill_type"] = "gradient"
        payload.pop("fill_rgb", None)
        payload.pop("fill_theme_color", None)
        payload.pop("fill_pattern", None)
        payload.pop("fill_pattern_fore_rgb", None)
        payload.pop("fill_pattern_back_rgb", None)
        payload.pop("fill_pattern_fore_theme_color", None)
        payload.pop("fill_pattern_back_theme_color", None)
        payload["fill_gradient"] = gradient
        self._queue_gradient(gradient)

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> TableCellColorFormat:
        return TableCellColorFormat(self._cell, "fore")

    @property
    def back_color(self) -> TableCellColorFormat:
        return TableCellColorFormat(self._cell, "back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._pattern_raw())

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern == self._pattern_raw():
            return
        _table_cell_property_payload(self._cell)["fill_pattern"] = pattern
        self._cell._table._slide._presentation._queue_table_cell_fill_patterned(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            pattern,
        )

    @property
    def gradient_angle(self) -> float | None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return self._gradient_payload().get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        angle = float(value)
        if gradient.get("angle") == angle:
            return
        gradient["angle"] = angle
        self._queue_gradient(gradient)

    @property
    def gradient_stops(self) -> TableCellGradientStops:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return TableCellGradientStops(self)

    def _fill_type(self) -> str | None:
        return _table_cell_fill_type(self._cell)

    def _pattern_raw(self) -> str | None:
        return _table_cell_fill_pattern(self._cell)

    def _gradient_payload(self) -> dict[str, Any]:
        payload = _table_cell_property_payload(self._cell)
        gradient = payload.get("fill_gradient")
        if not isinstance(gradient, dict):
            gradient = _table_cell_gradient_fill_payload(self._cell)
            if gradient is None:
                gradient = _default_gradient_payload()
            payload["fill_gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        payload = _table_cell_property_payload(self._cell)
        payload["fill_type"] = "gradient"
        payload["fill_gradient"] = gradient
        self._cell._table._slide._presentation._queue_table_cell_fill_gradient(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            gradient,
        )


class TableCellGradientStops(Sequence):
    def __init__(self, fill: TableCellFillFormat) -> None:
        self._fill = fill

    def __getitem__(self, index: int) -> TableCellGradientStop:
        stops = self._stops()
        if index < 0:
            index += len(stops)
        if index < 0 or index >= len(stops):
            raise IndexError("gradient stop index out of range")
        return TableCellGradientStop(self._fill, index)

    def __len__(self) -> int:
        return len(self._stops())

    def _stops(self) -> list[dict[str, Any]]:
        return self._fill._gradient_payload().setdefault("stops", [])


class TableCellGradientStop:
    def __init__(self, fill: TableCellFillFormat, index: int) -> None:
        self._fill = fill
        self._index = index

    @property
    def color(self) -> TableCellGradientStopColorFormat:
        return TableCellGradientStopColorFormat(self)

    @property
    def element(self) -> Any:
        return _gradient_stop_element(self._stop())

    @property
    def position(self) -> float:
        return float(self._stop().get("position", 0.0))

    @position.setter
    def position(self, value: Any) -> None:
        position = float(value)
        if self.position == position:
            return
        self._stop()["position"] = position
        self._fill._queue_gradient(self._fill._gradient_payload())

    def _stop(self) -> dict[str, Any]:
        return self._fill._gradient_payload()["stops"][self._index]


class TableCellGradientStopColorFormat(ColorTextAndTransforms):
    def __init__(self, stop: TableCellGradientStop) -> None:
        self._stop = stop

    def _set_color_element(self, color: ET.Element) -> None:
        gradient = deepcopy(self._stop._fill._gradient_payload())
        gradient["stops"][self._stop._index]["color"] = deepcopy(color)
        self._stop._fill._queue_gradient(gradient)

    @property
    def brightness(self) -> float:
        return _brightness_from_color_element(self._color_element())

    @brightness.setter
    def brightness(self, value: Any) -> None:
        brightness = float(value)
        if not -1.0 <= brightness <= 1.0:
            raise ValueError("brightness must be between -1.0 and 1.0")
        color = self._color_element()
        if _brightness_from_color_element(color) == brightness and (
            brightness != 0.0 or not _has_brightness_modifiers(color)
        ):
            return
        _set_color_brightness(color, brightness)
        self._stop._stop()["color"] = color
        self._stop._fill._queue_gradient(self._stop._fill._gradient_payload())

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color.tag != f"{{{A_NS}}}srgbClr":
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        value = color.attrib.get("val")
        return None if value is None else _rgb_value(value.upper())

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}srgbClr" and color.attrib.get("val") == rgb:
            return
        color = ET.Element(f"{{{A_NS}}}srgbClr")
        color.set("val", rgb)
        self._stop._stop()["color"] = color
        self._stop._fill._queue_gradient(self._stop._fill._gradient_payload())

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.attrib.get("val", ""))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        xml_value = _normalize_theme_color(value)
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}schemeClr" and color.attrib.get("val") == xml_value:
            return
        color = ET.Element(f"{{{A_NS}}}schemeClr")
        color.set("val", xml_value)
        self._stop._stop()["color"] = color
        self._stop._fill._queue_gradient(self._stop._fill._gradient_payload())

    @property
    def type(self) -> Any:
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}srgbClr":
            return _color_type_value("rgb")
        if color.tag == f"{{{A_NS}}}schemeClr":
            return _color_type_value("scheme")
        return None

    def _color_element(self) -> Any:
        color = self._stop._stop().get("color")
        if isinstance(color, ET.Element):
            return color
        return ET.Element(f"{{{A_NS}}}schemeClr", {"val": "accent1"})


class TableCellColorFormat(ColorTextAndTransforms):
    def __init__(self, cell: Any, role: str) -> None:
        self._cell = cell
        self._role = role

    def _color_element(self) -> ET.Element | None:
        table = self._cell._table
        presentation = table._slide._presentation
        if _table_cell_fill_type(self._cell) not in {"solid", "patterned"}:
            return None
        key = (table._slide._index, table._table_index, self._cell._row_idx, self._cell._col_idx)
        patterned = _table_cell_fill_type(self._cell) == "patterned"
        if self._role == "back" and not patterned:
            raise TypeError("fill is not patterned, call .patterned() first")
        queue = (
            presentation._table_cell_fill_pattern_back_color_edits
            if patterned and self._role == "back"
            else presentation._table_cell_fill_pattern_fore_color_edits
            if patterned
            else presentation._table_cell_fill_color_edits
        )
        if key in queue:
            value = queue[key]
            return _color_from_payload(
                {"type": "rgb", "value": value} if isinstance(value, str) else value
            )
        if key in presentation._table_cell_fill_solid_edits:
            return None
        element = _saved_table_cell_element(self._cell)
        parent = None if element is None else element.find(f"{{{A_NS}}}tcPr")
        saved_pattern = None if parent is None else parent.find(f"{{{A_NS}}}pattFill")
        color = (
            fill_color_element(parent, self._role)
            if parent is not None and patterned == (saved_pattern is not None)
            else None
        )
        if color is not None:
            return color
        theme = (
            _table_cell_pattern_theme_color(self._cell, self._role)
            if patterned
            else _table_cell_solid_theme_color(self._cell)
        )
        rgb = self._rgb_raw()
        if theme is not None:
            return _color_from_payload({"type": "scheme", "value": theme})
        return None if rgb is None else _color_from_payload({"type": "rgb", "value": rgb})

    def _set_color_element(self, color: ET.Element) -> None:
        value = {"type": "xml", "value": ET.tostring(color, encoding="unicode")}
        table = self._cell._table
        presentation = table._slide._presentation
        patterned = _table_cell_fill_type(self._cell) == "patterned"
        if self._role == "back" and not patterned:
            raise TypeError("fill is not patterned, call .patterned() first")
        queue = (
            presentation._queue_table_cell_fill_pattern_back_color
            if patterned and self._role == "back"
            else presentation._queue_table_cell_fill_pattern_fore_color
            if patterned
            else presentation._queue_table_cell_fill_color
        )
        queue(
            table._slide._index,
            table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            value,
        )
        payload = _table_cell_property_payload(self._cell)
        prefix = f"fill_pattern_{self._role}_" if patterned else "fill_"
        payload[prefix + "rgb"] = color.get("val") if color.tag == f"{{{A_NS}}}srgbClr" else None
        payload[prefix + "theme_color"] = (
            color.get("val") if color.tag == f"{{{A_NS}}}schemeClr" else None
        )
        if not patterned:
            payload["fill_type"] = "solid"

    @property
    def rgb(self) -> Any:
        if (
            self._role == "fore"
            and _table_cell_fill_type(self._cell) == "solid"
            and _table_cell_solid_theme_color(self._cell) is not None
        ):
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        if (
            _table_cell_fill_type(self._cell) == "patterned"
            and _table_cell_pattern_theme_color(self._cell, self._role) is not None
        ):
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        raw = self._rgb_raw()
        if raw is None:
            return None
        return _rgb_value(raw)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        payload = _table_cell_property_payload(self._cell)
        if self._role == "fore":
            if _table_cell_fill_type(self._cell) == "patterned":
                if (
                    _table_cell_pattern_theme_color(self._cell, "fore") is None
                    and _table_cell_pattern_rgb(self._cell, "fore", "000000") == rgb
                ):
                    return
                payload["fill_pattern_fore_rgb"] = rgb
                payload.pop("fill_pattern_fore_theme_color", None)
                self._cell._table._slide._presentation._queue_table_cell_fill_pattern_fore_color(
                    self._cell._table._slide._index,
                    self._cell._table._table_index,
                    self._cell._row_idx,
                    self._cell._col_idx,
                    rgb,
                )
                return
            if (
                _table_cell_fill_type(self._cell) == "solid"
                and _table_cell_solid_rgb(self._cell) == rgb
            ):
                return
            payload["fill_rgb"] = rgb
            payload.pop("fill_theme_color", None)
            payload["fill_type"] = "solid"
            payload.pop("fill_pattern", None)
            payload.pop("fill_pattern_fore_rgb", None)
            payload.pop("fill_pattern_back_rgb", None)
            payload.pop("fill_gradient", None)
            self._cell._table._slide._presentation._queue_table_cell_fill_color(
                self._cell._table._slide._index,
                self._cell._table._table_index,
                self._cell._row_idx,
                self._cell._col_idx,
                rgb,
            )
            return
        if _table_cell_fill_type(self._cell) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        if (
            _table_cell_pattern_theme_color(self._cell, "back") is None
            and _table_cell_pattern_rgb(self._cell, "back", "FFFFFF") == rgb
        ):
            return
        payload["fill_pattern_back_rgb"] = rgb
        payload.pop("fill_pattern_back_theme_color", None)
        self._cell._table._slide._presentation._queue_table_cell_fill_pattern_back_color(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            rgb,
        )

    @property
    def theme_color(self) -> Any:
        if _table_cell_fill_type(self._cell) == "patterned":
            value = _table_cell_pattern_theme_color(self._cell, self._role)
            return _theme_color_value("" if value is None else value)
        if self._role == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        value = _table_cell_solid_theme_color(self._cell)
        return _theme_color_value("" if value is None else value)

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        theme_color = _normalize_theme_color(value)
        if _table_cell_fill_type(self._cell) == "patterned":
            if _table_cell_pattern_theme_color(self._cell, self._role) == theme_color:
                return
            payload = _table_cell_property_payload(self._cell)
            payload[f"fill_pattern_{self._role}_theme_color"] = theme_color
            payload.pop(f"fill_pattern_{self._role}_rgb", None)
            presentation = self._cell._table._slide._presentation
            queue = (
                presentation._queue_table_cell_fill_pattern_back_color
                if self._role == "back"
                else presentation._queue_table_cell_fill_pattern_fore_color
            )
            queue(
                self._cell._table._slide._index,
                self._cell._table._table_index,
                self._cell._row_idx,
                self._cell._col_idx,
                {"type": "scheme", "value": theme_color},
            )
            return
        if self._role != "fore":
            raise TypeError("fill is not patterned, call .patterned() first")
        if (
            _table_cell_fill_type(self._cell) == "solid"
            and _table_cell_solid_theme_color(self._cell) == theme_color
        ):
            return
        payload = _table_cell_property_payload(self._cell)
        payload["fill_type"] = "solid"
        payload["fill_theme_color"] = theme_color
        payload.pop("fill_rgb", None)
        payload.pop("fill_pattern", None)
        payload.pop("fill_pattern_fore_rgb", None)
        payload.pop("fill_pattern_back_rgb", None)
        payload.pop("fill_pattern_fore_theme_color", None)
        payload.pop("fill_pattern_back_theme_color", None)
        payload.pop("fill_gradient", None)
        self._cell._table._slide._presentation._queue_table_cell_fill_color(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            {"type": "scheme", "value": theme_color},
        )

    def _rgb_raw(self) -> str | None:
        if self._role == "fore":
            if _table_cell_fill_type(self._cell) == "patterned":
                return _table_cell_pattern_rgb(self._cell, "fore", "000000")
            return _table_cell_solid_rgb(self._cell)
        if _table_cell_fill_type(self._cell) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _table_cell_pattern_rgb(self._cell, "back", "FFFFFF")

    @property
    def type(self) -> Any:
        if _table_cell_fill_type(self._cell) == "patterned":
            if _table_cell_pattern_theme_color(self._cell, self._role) is not None:
                return _color_type_value("scheme")
            return _color_type_value("rgb")
        if self._role == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        if _table_cell_solid_theme_color(self._cell) is not None:
            return _color_type_value("scheme")
        if _table_cell_solid_rgb(self._cell) is not None:
            return _color_type_value("rgb")
        return None


def _saved_table_cell_element(cell: Any) -> ET.Element | None:
    """Read the cell's saved owner without creating or modifying queued state."""
    table = cell._table
    partname = table._slide.partname
    if not partname or _table_is_unsaved(table):
        return None
    with zipfile.ZipFile(table._slide._presentation.path) as package:
        if partname.lstrip("/") not in package.namelist():
            return None
        root = ET.fromstring(package.read(partname.lstrip("/")))
    return _table_cell_xml_element(root, table._table_index, cell._row_idx, cell._col_idx)
