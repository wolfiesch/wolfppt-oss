"""Chart axis, gridline, tick label, and data label facades."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .chart_axis_xml import (
    CHART_AXIS_BUILT_IN_DISPLAY_UNITS as _CHART_AXIS_BUILT_IN_DISPLAY_UNITS,
)
from .chart_axis_xml import (
    axis_title_element as _axis_title_element,
)
from .chart_axis_xml import (
    chart_axis_display_units as _chart_axis_display_units,
)
from .chart_axis_xml import (
    chart_axis_position as _chart_axis_position,
)
from .chart_data_label_xml import (
    _chart_data_labels_element,
    _data_label_insert_index,
    _set_chart_data_label_property,
    chart_data_labels_payload,
)
from .chart_element_format_xml import (
    set_chart_element_format_properties as _set_chart_element_format_properties,
)
from .chart_element_format_xml import (
    set_chart_element_format_properties_in_order as _set_chart_element_format_properties_in_order,
)
from .chart_facade_helpers import (
    chart_axis_gridlines_element as _chart_axis_gridlines_element,
)
from .chart_facade_helpers import (
    chart_axis_payload as _chart_axis_payload,
)
from .chart_facade_helpers import (
    chart_axis_proxy_element as _chart_axis_proxy_element,
)
from .chart_facade_helpers import (
    chart_axis_text_default_run_properties as _chart_axis_text_default_run_properties,
)
from .chart_facade_helpers import (
    chart_category_paths as _chart_category_paths,
)
from .chart_facade_helpers import (
    chart_payload as _chart_payload,
)
from .chart_facade_helpers import (
    normalize_tick_label_offset as _normalize_tick_label_offset,
)
from .chart_facade_helpers import (
    prepare_chart_category_levels as _prepare_chart_category_levels,
)
from .chart_facade_helpers import (
    shape_chart_root as _shape_chart_root,
)
from .chart_font_format_facade import ChartTextFormat, chart_text_body, chart_text_xml
from .chart_format_facade import ChartFont, ChartFormat
from .chart_layout_facade import ElementLayout, axis_layout_elements
from .chart_point_facade_xml import (
    chart_series_data_labels_text_default_run_properties as _series_label_run_properties,
)
from .chart_point_facade_xml import (
    chart_series_element as _chart_series_element,
)
from .chart_title_text_facade import ChartTitleTextFrame
from .chart_title_text_xml import set_title_text as _set_title_text
from .chart_workbook import (
    category_chart_workbook_blob as _category_chart_workbook_blob,
)
from .chart_xml import chart_series_elements as _chart_series_elements
from .chart_xml import (
    replace_chart_root_data_preserving_series_layout as _replace_chart_categories_xml,
)
from .facade_values import (
    axis_crosses_value as _axis_crosses_value,
)
from .facade_values import (
    axis_tick_mark_value as _axis_tick_mark_value,
)
from .facade_values import (
    category_axis_type_value as _category_axis_type_value,
)
from .facade_values import (
    data_label_position_value as _data_label_position_value,
)
from .facade_values import (
    normalize_axis_crosses as _normalize_axis_crosses,
)
from .facade_values import (
    normalize_axis_tick_mark as _normalize_axis_tick_mark,
)
from .facade_values import (
    normalize_data_label_position as _normalize_data_label_position,
)
from .facade_values import (
    normalize_optional_float as _normalize_optional_float,
)
from .facade_values import (
    normalize_tick_label_position as _normalize_tick_label_position,
)
from .facade_values import (
    optional_float as _optional_float,
)
from .facade_values import (
    tick_label_position_value as _tick_label_position_value,
)

if TYPE_CHECKING:
    from .chart_facade import Chart, ChartPlot
from .chart_xml_utils import A_NS, C_NS
from .facade_chart_values import (
    normalize_category_axis_type as _normalize_category_axis_type,
)
from .facade_chart_values import (
    normalize_time_unit as _normalize_time_unit,
)
from .facade_chart_values import (
    time_unit_value as _time_unit_value,
)
from .package_parts import XmlElementProxy


class ChartAxis(ElementLayout):
    def __init__(self, chart: Chart, axis: str) -> None:
        self._chart = chart
        self._axis = axis

    _layout_is_axis = True

    @property
    def _layout_chart(self) -> Chart:
        return self._chart

    @property
    def _layout_key(self) -> str:
        return {"cat": "category_axis", "val": "value_axis", "val2": "secondary_value_axis"}[
            self._axis
        ]

    def _layout_element(self, create: bool) -> ET.Element:
        self._check_live()
        element = axis_layout_elements(_shape_chart_root(self._chart._shape)).get(self._layout_key)
        if element is None:
            raise ValueError("manual layout requires an existing chart axis")
        return element

    def _check_live(self) -> None:
        shape = getattr(self._chart, "_shape", None)
        if shape is None:
            raise ValueError("chart shape is unavailable")
        payload = getattr(shape, "_payload", {})
        if isinstance(payload, dict):
            if payload.get("_deleted"):
                raise ValueError("cannot edit or read axis of a deleted shape")
            if payload.get("_stale"):
                raise ValueError("cannot edit or read axis of a stale shape")
        if getattr(shape, "_deleted", False):
            raise ValueError("cannot edit or read axis of a deleted shape")
        slide = getattr(shape, "_slide", None)
        if slide is not None:
            if getattr(slide, "_deleted", False):
                raise ValueError("cannot edit or read axis on a deleted slide")
            prs = getattr(slide, "_presentation", None)
            if prs is not None:
                slides = getattr(prs, "_slides", None)
                if slides is not None and slide not in slides:
                    raise ValueError("cannot edit or read axis on a deleted slide")
                slide_deletions = getattr(prs, "_slide_deletions", None)
                if slide_deletions and getattr(slide, "partname", None) in slide_deletions:
                    raise ValueError("cannot edit or read axis on a deleted slide")
                shape_deletes = getattr(prs, "_shape_deletes", None)
                shape_index = getattr(shape, "_index", None)
                if (
                    shape_deletes
                    and getattr(slide, "partname", None) in shape_deletes
                    and shape_index is not None
                    and shape_index in shape_deletes[slide.partname]
                ):
                    raise ValueError("cannot edit or read axis of a deleted shape")

    @property
    def has_title(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("has_title"))

    @property
    def category_type(self) -> Any:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'category_type'")
        raw = _chart_axis_payload(self._chart._shape, self._axis).get("category_type")
        return _category_axis_type_value(raw)

    @category_type.setter
    def category_type(self, value: Any) -> None:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'category_type'")
        norm = _normalize_category_axis_type(value)
        self._set_property("category_type", norm)
        if norm == "catAx":
            for clean_attr in (
                "base_time_unit",
                "major_time_unit",
                "minor_time_unit",
                "major_unit",
                "minor_unit",
            ):
                self._set_property(clean_attr, None, force=True)

    @property
    def base_time_unit(self) -> Any:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'base_time_unit'")
        raw = _chart_axis_payload(self._chart._shape, self._axis).get("base_time_unit")
        return _time_unit_value(raw)

    @base_time_unit.setter
    def base_time_unit(self, value: Any) -> None:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'base_time_unit'")
        norm = None if value is None else _normalize_time_unit(value)
        self._set_property("base_time_unit", norm)

    @property
    def major_time_unit(self) -> Any:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'major_time_unit'")
        raw = _chart_axis_payload(self._chart._shape, self._axis).get("major_time_unit")
        return _time_unit_value(raw)

    @major_time_unit.setter
    def major_time_unit(self, value: Any) -> None:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'major_time_unit'")
        norm = None if value is None else _normalize_time_unit(value)
        self._set_property("major_time_unit", norm)

    @property
    def minor_time_unit(self) -> Any:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'minor_time_unit'")
        raw = _chart_axis_payload(self._chart._shape, self._axis).get("minor_time_unit")
        return _time_unit_value(raw)

    @minor_time_unit.setter
    def minor_time_unit(self, value: Any) -> None:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'minor_time_unit'")
        norm = None if value is None else _normalize_time_unit(value)
        self._set_property("minor_time_unit", norm)

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_axis_proxy_element(self._chart._shape, self._axis),
            self._queue_format,
        )

    @property
    def major_gridlines(self) -> MajorGridlines:
        return MajorGridlines(self)

    @property
    def minor_gridlines(self) -> MinorGridlines:
        return MinorGridlines(self)

    @property
    def tick_labels(self) -> TickLabels:
        return TickLabels(self)

    @has_title.setter
    def has_title(self, value: bool) -> None:
        payload = _chart_axis_payload(self._chart._shape, self._axis)
        has_title = bool(value)
        if has_title == bool(payload.get("has_title")):
            return
        payload["has_title"] = has_title
        if not has_title:
            payload["title_text"] = ""
        self._chart._shape._slide._presentation._queue_chart_axis_title(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            self._axis,
            {
                "has_title": has_title,
                "text": str(payload.get("title_text") or ""),
            },
        )

    @property
    def axis_title(self) -> ChartAxisTitle:
        return ChartAxisTitle(self)

    @property
    def visible(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("visible"))

    @visible.setter
    def visible(self, value: Any) -> None:
        self._set_property("visible", bool(value))

    @property
    def has_major_gridlines(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("has_major_gridlines"))

    @has_major_gridlines.setter
    def has_major_gridlines(self, value: Any) -> None:
        self._set_property("has_major_gridlines", bool(value))

    @property
    def has_minor_gridlines(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("has_minor_gridlines"))

    @has_minor_gridlines.setter
    def has_minor_gridlines(self, value: Any) -> None:
        self._set_property("has_minor_gridlines", bool(value))

    @property
    def major_tick_mark(self) -> Any:
        return _axis_tick_mark_value(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "major_tick_mark",
                "out",
            )
        )

    @major_tick_mark.setter
    def major_tick_mark(self, value: Any) -> None:
        self._set_property("major_tick_mark", _normalize_axis_tick_mark(value))

    @property
    def minor_tick_mark(self) -> Any:
        return _axis_tick_mark_value(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "minor_tick_mark",
                "none",
            )
        )

    @minor_tick_mark.setter
    def minor_tick_mark(self, value: Any) -> None:
        self._set_property("minor_tick_mark", _normalize_axis_tick_mark(value))

    @property
    def tick_label_position(self) -> Any:
        return _tick_label_position_value(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "tick_label_position",
                "nextTo",
            )
        )

    @tick_label_position.setter
    def tick_label_position(self, value: Any) -> None:
        self._set_property(
            "tick_label_position",
            _normalize_tick_label_position(value),
        )

    @property
    def reverse_order(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("reverse_order"))

    @reverse_order.setter
    def reverse_order(self, value: Any) -> None:
        self._set_property("reverse_order", bool(value))

    @property
    def minimum_scale(self) -> float | None:
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("minimum_scale")
        )

    @minimum_scale.setter
    def minimum_scale(self, value: Any) -> None:
        normalized = _normalize_optional_float(value)
        if (
            normalized is not None
            and self._axis in {"val", "val2"}
            and self.log_base is not None
            and normalized <= 0.0
        ):
            raise ValueError(
                "logarithmic axis requires minimum_scale to be strictly positive (> 0), "
                f"got {normalized}"
            )
        self._set_property("minimum_scale", normalized)

    @property
    def maximum_scale(self) -> float | None:
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("maximum_scale")
        )

    @maximum_scale.setter
    def maximum_scale(self, value: Any) -> None:
        normalized = _normalize_optional_float(value)
        if (
            normalized is not None
            and self._axis in {"val", "val2"}
            and self.log_base is not None
            and normalized <= 0.0
        ):
            raise ValueError(
                "logarithmic axis requires maximum_scale to be strictly positive (> 0), "
                f"got {normalized}"
            )
        self._set_property("maximum_scale", normalized)

    @property
    def log_base(self) -> float | None:
        """Read authored log bases; only value axes support assignment."""
        if self._axis not in {"val", "val2"}:
            return _optional_float(self._child_val("scaling/logBase"))
        self._check_live()
        return _optional_float(_chart_axis_payload(self._chart._shape, self._axis).get("log_base"))

    @log_base.setter
    def log_base(self, value: Any) -> None:
        if self._axis not in {"val", "val2"}:
            raise AttributeError("'CategoryAxis' object has no attribute 'log_base'")
        self._check_live()
        if value is None:
            self._set_property("log_base", None)
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"log_base must be a finite number between 2 and 1000, got {value!r}")
        val = float(value)
        if not math.isfinite(val) or val < 2.0 or val > 1000.0:
            raise ValueError(f"log_base must be a finite number between 2 and 1000, got {value!r}")
        min_scale = self.minimum_scale
        if min_scale is not None and min_scale <= 0.0:
            raise ValueError(
                "logarithmic axis requires minimum_scale to be strictly positive (> 0), "
                f"got {min_scale}"
            )
        max_scale = self.maximum_scale
        if max_scale is not None and max_scale <= 0.0:
            raise ValueError(
                "logarithmic axis requires maximum_scale to be strictly positive (> 0), "
                f"got {max_scale}"
            )
        self._set_property("log_base", val)

    @property
    def major_unit(self) -> float | None:
        if self._axis not in {"val", "val2"}:
            cat_type = _chart_axis_payload(self._chart._shape, self._axis).get("category_type")
            if cat_type != "dateAx":
                raise AttributeError("'CategoryAxis' object has no attribute 'major_unit'")
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("major_unit")
        )

    @major_unit.setter
    def major_unit(self, value: Any) -> None:
        if self._axis not in {"val", "val2"}:
            cat_type = _chart_axis_payload(self._chart._shape, self._axis).get("category_type")
            if cat_type != "dateAx":
                raise AttributeError("'CategoryAxis' object has no attribute 'major_unit'")
        self._set_property("major_unit", _normalize_optional_float(value))

    @property
    def minor_unit(self) -> float | None:
        if self._axis not in {"val", "val2"}:
            cat_type = _chart_axis_payload(self._chart._shape, self._axis).get("category_type")
            if cat_type != "dateAx":
                raise AttributeError("'CategoryAxis' object has no attribute 'minor_unit'")
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("minor_unit")
        )

    @minor_unit.setter
    def minor_unit(self, value: Any) -> None:
        if self._axis not in {"val", "val2"}:
            cat_type = _chart_axis_payload(self._chart._shape, self._axis).get("category_type")
            if cat_type != "dateAx":
                raise AttributeError("'CategoryAxis' object has no attribute 'minor_unit'")
        self._set_property("minor_unit", _normalize_optional_float(value))

    @property
    def crosses(self) -> Any:
        """Where the perpendicular axis crosses this axis.

        For category and value axes the setting lives on the perpendicular axis
        element (python-pptx semantics). A series axis exposes its own ``c:crosses``.
        """
        cross_axis = _chart_axis_payload(self._chart._shape, self._cross_axis_key())
        if cross_axis.get("crosses_at") is not None:
            return _axis_crosses_value(None)
        return _axis_crosses_value(cross_axis.get("crosses"))

    @crosses.setter
    def crosses(self, value: Any) -> None:
        crosses = _normalize_axis_crosses(value)
        if crosses is None:
            cross_axis = _chart_axis_payload(self._chart._shape, self._cross_axis_key())
            if cross_axis.get("crosses_at") is not None:
                return
            self._set_cross_axis_property("crosses_at", 0.0)
            return
        self._set_cross_axis_property("crosses", crosses)

    @property
    def crosses_at(self) -> float | None:
        if self._axis not in {"val", "val2"}:
            raise AttributeError("'CategoryAxis' object has no attribute 'crosses_at'")
        return _optional_float(_chart_axis_payload(self._chart._shape, "cat").get("crosses_at"))

    @crosses_at.setter
    def crosses_at(self, value: Any) -> None:
        if self._axis not in {"val", "val2"}:
            raise AttributeError("'CategoryAxis' object has no attribute 'crosses_at'")
        self._set_cross_axis_property("crosses_at", _normalize_optional_float(value))

    @property
    def position(self) -> str:
        """Axis side: ``"bottom"``, ``"left"``, ``"right"`` or ``"top"``."""
        token = self._xml_state("position", _chart_axis_position)
        if token is None:
            token = {"cat": "b", "val": "l", "val2": "r"}[self._axis]
        return _AXIS_POSITION_NAMES.get(str(token), str(token))

    @position.setter
    def position(self, value: Any) -> None:
        self._xml_state("position", _chart_axis_position)
        self._set_property("position", _normalize_axis_position(value))

    @property
    def display_unit(self) -> str | None:
        """Value display unit: a built-in unit name, ``"custom"`` or ``None``."""
        state = self._display_units_state("display_unit")
        return None if state is None else str(state["unit"])

    @display_unit.setter
    def display_unit(self, value: Any) -> None:
        state = self._display_units_state("display_unit")
        unit = _normalize_display_unit(value)
        if unit is None:
            self._set_property("display_units", None)
            return
        if unit == "custom":
            if state is None or state["unit"] != "custom":
                raise ValueError("assign custom_display_unit to choose a custom display unit")
            return
        self._set_property(
            "display_units",
            {**_new_display_units_state(state), "unit": unit, "custom_unit": None},
        )

    @property
    def custom_display_unit(self) -> float | None:
        """The divisor of a custom display unit, ``None`` for built-in units."""
        state = self._display_units_state("custom_display_unit")
        return None if state is None else state["custom_unit"]

    @custom_display_unit.setter
    def custom_display_unit(self, value: Any) -> None:
        state = self._display_units_state("custom_display_unit")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"custom_display_unit must be a positive finite number, got {value!r}")
        divisor = float(value)
        if not math.isfinite(divisor) or divisor <= 0.0:
            raise ValueError(f"custom_display_unit must be a positive finite number, got {value!r}")
        self._set_property(
            "display_units",
            {
                **_new_display_units_state(state),
                "unit": "custom",
                "custom_unit": divisor,
            },
        )

    @property
    def display_unit_label_visible(self) -> bool:
        """Whether the display-unit label (for example "Thousands") is shown."""
        state = self._display_units_state("display_unit_label_visible")
        return state is not None and bool(state["label_visible"])

    @display_unit_label_visible.setter
    def display_unit_label_visible(self, value: Any) -> None:
        state = self._require_display_units("display_unit_label_visible")
        visible = bool(value)
        self._set_property(
            "display_units",
            {
                **state,
                "label_visible": visible,
                "label_text": state["label_text"] if visible else None,
            },
        )

    @property
    def display_unit_label_text(self) -> str | None:
        """Custom display-unit label text; ``None`` keeps the generated label."""
        state = self._display_units_state("display_unit_label_text")
        return None if state is None else state["label_text"]

    @display_unit_label_text.setter
    def display_unit_label_text(self, value: str | None) -> None:
        state = self._require_display_units("display_unit_label_text")
        if value is None:
            self._set_property("display_units", {**state, "label_text": None})
            return
        if not isinstance(value, str):
            raise TypeError(f"display_unit_label_text must be a string, got {type(value).__name__}")
        self._set_property("display_units", {**state, "label_visible": True, "label_text": value})

    @property
    def categories(self) -> ChartCategories:
        """Category labels with their per-level grouping labels."""
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'categories'")
        self._check_live()
        return ChartCategories(self)

    def _cross_axis_key(self) -> str:
        if self._axis == "ser":
            return "ser"
        return "val" if self._axis == "cat" else "cat"

    def _xml_state(self, attr: str, reader: Callable[[ET.Element], Any]) -> Any:
        """Seed an XML-backed payload entry from the axis element on first use."""
        self._check_live()
        payload = _chart_axis_payload(self._chart._shape, self._axis)
        if attr not in payload:
            payload[attr] = reader(_chart_axis_proxy_element(self._chart._shape, self._axis))
        return payload[attr]

    def _display_units_state(self, name: str) -> dict[str, Any] | None:
        if self._axis not in {"val", "val2"}:
            raise AttributeError(f"'CategoryAxis' object has no attribute {name!r}")
        state = self._xml_state("display_units", _chart_axis_display_units)
        return None if state is None else dict(state)

    def _require_display_units(self, name: str) -> dict[str, Any]:
        state = self._display_units_state(name)
        if state is None:
            raise ValueError(
                f"{name} needs a display unit; assign display_unit or custom_display_unit first"
            )
        return state

    def _child_val(self, path: str) -> str | None:
        self._check_live()
        node = _chart_axis_proxy_element(self._chart._shape, self._axis).find(
            "/".join(f"{{{C_NS}}}{name}" for name in path.split("/"))
        )
        return None if node is None else node.get("val")

    @property
    def axis_position(self) -> str | None:
        """Read-only ``c:axPos`` value (``"b"``, ``"l"``, ``"r"`` or ``"t"``)."""
        return self._child_val("axPos")

    @property
    def cross_between(self) -> str | None:
        """Read-only ``c:crossBetween`` value (``"between"`` or ``"midCat"``)."""
        if self._axis not in {"val", "val2"}:
            raise AttributeError("'CategoryAxis' object has no attribute 'cross_between'")
        return self._child_val("crossBetween")

    @property
    def display_units(self) -> str | float | None:
        """Read-only ``c:dispUnits``: the built-in unit name or custom unit factor."""
        if self._axis not in {"val", "val2"}:
            raise AttributeError("'CategoryAxis' object has no attribute 'display_units'")
        built_in = self._child_val("dispUnits/builtInUnit")
        if built_in is not None:
            return built_in
        return _optional_float(self._child_val("dispUnits/custUnit"))

    def _set_property(self, attr: str, value: Any, *, force: bool = False) -> None:
        self._check_live()
        payload = _chart_axis_payload(self._chart._shape, self._axis)
        if not force and payload.get(attr) == value:
            return
        payload[attr] = value
        self._chart._shape._slide._presentation._queue_chart_axis_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            self._axis,
            attr,
            value,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        axis_element = _chart_axis_proxy_element(self._chart._shape, self._axis)
        _queue_axis_format(self, axis_element, "axis_", properties, {})

    def _set_cross_axis_property(self, attr: str, value: Any) -> None:
        cross_axis = self._cross_axis_key()
        payload = _chart_axis_payload(self._chart._shape, cross_axis)
        current_crosses = payload.get("crosses")
        current_crosses_at = payload.get("crosses_at")
        if attr == "crosses" and current_crosses == value and current_crosses_at is None:
            return
        if attr == "crosses_at" and current_crosses is None and current_crosses_at == value:
            return
        if attr == "crosses":
            payload["crosses"] = value
            payload["crosses_at"] = None
        elif attr == "crosses_at":
            payload["crosses"] = None
            payload["crosses_at"] = value
        self._chart._shape._slide._presentation._queue_chart_axis_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            cross_axis,
            attr,
            value,
        )


class ChartAxisTitle(ElementLayout):
    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    @property
    def _layout_chart(self) -> Chart:
        return self._axis._chart

    @property
    def _layout_key(self) -> str:
        return self._axis._layout_key + "_title"

    def _layout_element(self, create: bool) -> ET.Element:
        self._axis._layout_element(False)
        element = self._title_element(create)
        if create:
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis)["has_title"] = True
        return element

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(self._title_element(create=False))

    @property
    def has_text_frame(self) -> bool:
        return self._title_element(False).find(f"{{{C_NS}}}tx/{{{C_NS}}}rich") is not None

    @has_text_frame.setter
    def has_text_frame(self, value: bool) -> None:
        if not value:
            raise NotImplementedError(
                "removing an axis title text frame is not supported; "
                "set axis.has_title = False to remove the title"
            )
        title = self._title_element(True)
        if title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich") is None:
            _set_title_text(title, "")
            self._queue_text({"text": ""})

    @property
    def text_frame(self) -> ChartTitleTextFrame:
        return ChartTitleTextFrame(self._title_element, self._queue_text)

    @property
    def text_format(self) -> ChartTextFormat:
        return self.text_frame.text_format

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(self._element, self._queue_format)

    def _element(self) -> Any:
        if not self._axis.has_title:
            return ET.Element(f"{{{C_NS}}}title")
        axis_element = _chart_axis_proxy_element(
            self._axis._chart._shape,
            self._axis._axis,
        )
        title = axis_element.find(f"{{{C_NS}}}title")
        return title if title is not None else ET.Element(f"{{{C_NS}}}title")

    def _queue_format(self, properties: dict[str, Any]) -> None:
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        axis_element = _chart_axis_proxy_element(
            self._axis._chart._shape,
            self._axis._axis,
        )
        title = _axis_title_element(axis_element)
        _set_chart_element_format_properties(title, properties)
        payload["has_title"] = True
        self._axis._chart._shape._slide._presentation._queue_chart_axis_title(
            self._axis._chart._shape._slide._index,
            self._axis._chart._shape._index,
            self._axis._axis,
            {
                "has_title": True,
                "format": properties,
            },
        )

    def _title_element(self, create: bool) -> Any:
        if not create and not self._axis.has_title:
            return ET.Element(f"{{{C_NS}}}title")
        axis_element = _chart_axis_proxy_element(
            self._axis._chart._shape,
            self._axis._axis,
        )
        if not create:
            title = axis_element.find(f"{{{C_NS}}}title")
            return title if title is not None else ET.Element(f"{{{C_NS}}}title")
        return _axis_title_element(axis_element)

    def _queue_text(self, properties: dict[str, Any]) -> None:
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        payload["has_title"] = True
        properties = {
            **properties,
            "_text_xml": chart_text_xml(self._title_element(False)),
        }
        if "text" in properties:
            payload["title_text"] = str(properties["text"])
        elif "paragraphs" in properties:
            payload["title_text"] = "\n".join(
                str(paragraph) for paragraph in properties["paragraphs"]
            )
        elif "paragraph_runs" in properties:
            payload["title_text"] = "\n".join(
                "".join(str(run) for run in runs) for runs in properties["paragraph_runs"]
            )
        self._axis._chart._shape._slide._presentation._queue_chart_axis_title(
            self._axis._chart._shape._slide._index,
            self._axis._chart._shape._index,
            self._axis._axis,
            {"has_title": True, **properties},
        )


class DataLabels:
    def __init__(self, plot: ChartPlot) -> None:
        self._plot = plot

    @property
    def text_format(self) -> ChartTextFormat:
        """Portion, paragraph and block formatting of plot/series labels."""
        return ChartTextFormat(self._text_body, self._commit_text_format)

    def _plot_element(self) -> ET.Element:
        root = _shape_chart_root(self._plot._chart._shape)
        plot_area = root.find(f".//{{{C_NS}}}plotArea")
        if plot_area is None:
            raise AttributeError("chart plot area is unavailable")
        plots = [child for child in plot_area if child.tag.endswith("Chart")]
        return plots[self._plot._index]

    def _labels_element(self, create: bool) -> ET.Element:
        plot = self._plot_element()
        if create:
            return _chart_data_labels_element(plot)
        labels = plot.find(f"{{{C_NS}}}dLbls")
        return labels if labels is not None else ET.Element(f"{{{C_NS}}}dLbls")

    def _text_body(self, create: bool) -> ET.Element | None:
        return chart_text_body(self._labels_element(create), create, _data_label_insert_index)

    def _commit_text_format(self, scope: str, delta: dict[str, Any]) -> None:
        self._queue({"text_format_edits": [{"scope": scope, "delta": dict(delta)}]})

    def _label_child(self, name: str) -> ET.Element | None:
        return self._labels_element(False).find(f"{{{C_NS}}}{name}")

    @property
    def separator(self) -> str | None:
        separator = self._label_child("separator")
        return None if separator is None else separator.text or ""

    @separator.setter
    def separator(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError("separator must be a string or None")
        self._set_property("separator", value)

    @property
    def show_bubble_size(self) -> bool:
        child = self._label_child("showBubbleSize")
        return child is not None and child.get("val", "1") in {"1", "true"}

    @show_bubble_size.setter
    def show_bubble_size(self, value: Any) -> None:
        self._set_property("show_bubble_size", bool(value))

    @property
    def show_leader_lines(self) -> bool:
        child = self._label_child("showLeaderLines")
        return child is not None and child.get("val", "1") in {"1", "true"}

    @show_leader_lines.setter
    def show_leader_lines(self, value: Any) -> None:
        self._set_property("show_leader_lines", bool(value))

    def _payload(self) -> dict[str, Any]:
        return chart_data_labels_payload(self._plot_element())

    def _font_properties(self) -> ET.Element | None:
        body = self._text_body(False)
        return None if body is None else body.find(f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr")

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            self._font_properties,
            self._set_properties,
            lambda: self._payload().get("font_size"),
            lambda: self._payload().get("font_fill_type"),
            lambda: self._payload().get("font_pattern"),
            lambda: self._payload().get("font_gradient"),
        )

    @property
    def show_value(self) -> bool:
        return bool(self._payload()["show_value"])

    @show_value.setter
    def show_value(self, value: Any) -> None:
        self._set_property("show_value", bool(value))

    @property
    def show_category_name(self) -> bool:
        return bool(self._payload()["show_category_name"])

    @show_category_name.setter
    def show_category_name(self, value: Any) -> None:
        self._set_property("show_category_name", bool(value))

    @property
    def show_series_name(self) -> bool:
        return bool(self._payload()["show_series_name"])

    @show_series_name.setter
    def show_series_name(self, value: Any) -> None:
        self._set_property("show_series_name", bool(value))

    @property
    def show_percentage(self) -> bool:
        return bool(self._payload()["show_percentage"])

    @show_percentage.setter
    def show_percentage(self, value: Any) -> None:
        self._set_property("show_percentage", bool(value))

    @property
    def show_legend_key(self) -> bool:
        return bool(self._payload()["show_legend_key"])

    @show_legend_key.setter
    def show_legend_key(self, value: Any) -> None:
        self._set_property("show_legend_key", bool(value))

    @property
    def position(self) -> Any:
        return _data_label_position_value(self._payload().get("position"))

    @position.setter
    def position(self, value: Any) -> None:
        self._set_property("position", _normalize_data_label_position(value))

    @property
    def number_format(self) -> str:
        return str(
            self._payload().get(
                "number_format",
                "General",
            )
        )

    @number_format.setter
    def number_format(self, value: Any) -> None:
        number_format = str(value)
        payload = self._payload()
        if (
            payload.get("has_data_labels")
            and str(payload.get("number_format", "General")) == number_format
            and payload.get("number_format_is_linked") is False
        ):
            return
        payload["number_format"] = number_format
        payload["number_format_is_linked"] = False
        self._queue({"number_format": number_format})

    @property
    def number_format_is_linked(self) -> bool:
        return bool(
            self._payload().get(
                "number_format_is_linked",
                True,
            )
        )

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        self._set_property("number_format_is_linked", bool(value))

    def _set_property(self, attr: str, value: Any) -> None:
        payload = self._payload()
        if payload.get("has_data_labels") and payload.get(attr) == value:
            return
        payload[attr] = value
        self._queue({attr: value})

    def _set_properties(self, properties: dict[str, Any]) -> None:
        for attr, value in properties.items():
            self._set_property(attr, value)

    def _queue(self, data_labels: dict[str, Any]) -> None:
        data_labels.setdefault("has_data_labels", True)
        if data_labels["has_data_labels"]:
            element = self._labels_element(True)
            for attr, value in data_labels.items():
                if attr != "text_format_edits":
                    _set_chart_data_label_property(element, attr, value)
            data_labels["_text_xml"] = chart_text_xml(element)
        else:
            plot = self._plot_element()
            element = plot.find(f"{{{C_NS}}}dLbls")
            if element is not None:
                plot.remove(element)
        data_labels = {
            "plot_data_labels": [{"plot_index": self._plot._index, "properties": data_labels}]
        }
        self._plot._chart._shape._slide._presentation._queue_chart_data_labels(
            self._plot._chart._shape._slide._index,
            self._plot._chart._shape._index,
            data_labels,
        )


#: Series label properties that inherit from the plot's c:dLbls, by their own c:dLbls child.
_INHERITED_LABEL_CHILDREN = {
    "show_value": "showVal",
    "show_category_name": "showCatName",
    "show_series_name": "showSerName",
    "show_percentage": "showPercent",
    "show_legend_key": "showLegendKey",
    "position": "dLblPos",
    "number_format_is_linked": "numFmt",
}


class ChartSeriesDataLabels(DataLabels):
    def __init__(self, series: Any) -> None:
        self._series = series

    def _labels_element(self, create: bool) -> ET.Element:
        series = _chart_series_element(self._series._chart._shape, self._series.index)
        if series is None:
            raise AttributeError("chart series is unavailable")
        if create:
            # Do not seed explicit show flags: absent keys inherit from the plot.
            labels = series.find(f"{{{C_NS}}}dLbls")
            if labels is None:
                from .chart_point_xml import _chart_series_data_labels_insert_index

                labels = ET.Element(f"{{{C_NS}}}dLbls")
                series.insert(_chart_series_data_labels_insert_index(series), labels)
            return labels
        labels = series.find(f"{{{C_NS}}}dLbls")
        return labels if labels is not None else ET.Element(f"{{{C_NS}}}dLbls")

    def _parent_labels(self) -> DataLabels:
        series = _chart_series_element(self._series._chart._shape, self._series.index)
        root = _shape_chart_root(self._series._chart._shape)
        plot_area = root.find(f".//{{{C_NS}}}plotArea")
        if plot_area is not None:
            plots = [child for child in plot_area if child.tag.endswith("Chart")]
            for index, plot in enumerate(plots):
                if series in plot.findall(f"{{{C_NS}}}ser"):
                    return DataLabels(self._series._chart.plots[index])
        raise AttributeError("chart series plot is unavailable")

    def _label_child(self, name: str) -> ET.Element | None:
        child = super()._label_child(name)
        if child is not None:
            return child
        return self._parent_labels()._label_child(name)

    def _inherited_value(self, key: str, name: str) -> Any:
        own = self._labels_element(False)
        if own.find(f"{{{C_NS}}}{name}") is None:
            parent = self._parent_labels()._payload()
            if parent["has_data_labels"]:
                return parent[key]
        container = ET.Element(f"{{{C_NS}}}ser")
        container.append(own)
        return chart_data_labels_payload(container)[key]

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            lambda: _series_label_run_properties(
                self._series._chart._shape,
                self._series.index,
            ),
            self._set_properties,
            lambda: self._payload().get("font_size"),
            lambda: self._payload().get("font_fill_type"),
            lambda: self._payload().get("font_pattern"),
            lambda: self._payload().get("font_gradient"),
        )

    @property
    def show_value(self) -> bool:
        return bool(self._inherited_value("show_value", "showVal"))

    @show_value.setter
    def show_value(self, value: Any) -> None:
        self._set_property("show_value", bool(value))

    @property
    def show_category_name(self) -> bool:
        return bool(self._inherited_value("show_category_name", "showCatName"))

    @show_category_name.setter
    def show_category_name(self, value: Any) -> None:
        self._set_property("show_category_name", bool(value))

    @property
    def show_series_name(self) -> bool:
        return bool(self._inherited_value("show_series_name", "showSerName"))

    @show_series_name.setter
    def show_series_name(self, value: Any) -> None:
        self._set_property("show_series_name", bool(value))

    @property
    def show_percentage(self) -> bool:
        return bool(self._inherited_value("show_percentage", "showPercent"))

    @show_percentage.setter
    def show_percentage(self, value: Any) -> None:
        self._set_property("show_percentage", bool(value))

    @property
    def show_legend_key(self) -> bool:
        return bool(self._inherited_value("show_legend_key", "showLegendKey"))

    @show_legend_key.setter
    def show_legend_key(self, value: Any) -> None:
        self._set_property("show_legend_key", bool(value))

    @property
    def position(self) -> Any:
        return _data_label_position_value(self._inherited_value("position", "dLblPos"))

    @position.setter
    def position(self, value: Any) -> None:
        self._set_property("position", _normalize_data_label_position(value))

    @property
    def number_format(self) -> str:
        return str(self._inherited_value("number_format", "numFmt"))

    @number_format.setter
    def number_format(self, value: Any) -> None:
        number_format = str(value)
        payload = self._payload()
        if (
            payload.get("has_data_labels")
            and str(payload.get("number_format", "General")) == number_format
            and payload.get("number_format_is_linked") is False
        ):
            return
        payload["number_format"] = number_format
        payload["number_format_is_linked"] = False
        self._queue({"number_format": number_format})

    @property
    def number_format_is_linked(self) -> bool:
        return bool(self._inherited_value("number_format_is_linked", "numFmt"))

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        self._set_property("number_format_is_linked", bool(value))

    def _payload(self) -> dict[str, Any]:
        payload = self._series._payload.setdefault("data_labels", {})
        payload.setdefault("has_data_labels", False)
        payload.setdefault("show_value", False)
        payload.setdefault("show_category_name", False)
        payload.setdefault("show_series_name", False)
        payload.setdefault("show_percentage", False)
        payload.setdefault("show_legend_key", False)
        payload.setdefault("position", None)
        payload.setdefault("number_format", "General")
        payload.setdefault("number_format_is_linked", True)
        return payload

    def _set_property(self, attr: str, value: Any) -> None:
        payload = self._payload()
        name = _INHERITED_LABEL_CHILDREN.get(attr)
        if name is None:
            unchanged = payload.get("has_data_labels") and payload.get(attr) == value
        else:
            explicit = self._labels_element(False).find(f"{{{C_NS}}}{name}") is not None
            unchanged = explicit and self._inherited_value(attr, name) == value
        if unchanged:
            return
        payload["has_data_labels"] = True
        payload[attr] = value
        self._queue({attr: value})

    def _set_properties(self, properties: dict[str, Any]) -> None:
        for attr, value in properties.items():
            self._set_property(attr, value)

    def _queue(self, data_labels: dict[str, Any]) -> None:
        data_labels.setdefault("has_data_labels", True)
        element = self._labels_element(True)
        for attr, value in data_labels.items():
            if attr != "text_format_edits":
                _set_chart_data_label_property(element, attr, value)
        data_labels["_text_xml"] = chart_text_xml(element)
        self._payload()["has_data_labels"] = True
        self._series._chart._shape._slide._presentation._queue_chart_data_labels(
            self._series._chart._shape._slide._index,
            self._series._chart._shape._index,
            {
                "series_data_labels": [
                    {
                        "series_index": self._series.index,
                        "properties": data_labels,
                    }
                ]
            },
        )


class _Gridlines:
    _kind: str

    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(
            _chart_axis_proxy_element(self._axis._chart._shape, self._axis._axis)
        )

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_axis_gridlines_element(
                self._axis._chart._shape,
                self._axis._axis,
                self._kind,
            ),
            self._queue_format,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        flag = f"has_{self._kind}_gridlines"
        _chart_axis_payload(self._axis._chart._shape, self._axis._axis)[flag] = True
        gridlines = _chart_axis_gridlines_element(
            self._axis._chart._shape,
            self._axis._axis,
            self._kind,
            create=True,
        )
        _queue_axis_format(
            self._axis, gridlines, f"{self._kind}_gridlines_", properties, {flag: True}
        )


class MajorGridlines(_Gridlines):
    _kind = "major"


class MinorGridlines(_Gridlines):
    _kind = "minor"


def _queue_axis_format(
    axis: ChartAxis,
    element: ET.Element,
    prefix: str,
    properties: dict[str, Any],
    queued: dict[str, Any],
) -> None:
    """Apply a format edit to the axis proxy ``element`` and queue it as axis properties."""
    _set_chart_element_format_properties_in_order(element, properties, "axis")
    for attr, value in properties.items():
        # The gradient payload replaces the fill itself; a bare gradient type has no stops.
        if attr == "fill_type" and value == "gradient" and "fill_gradient" in properties:
            continue
        queued[prefix + attr] = value
    for attr, value in queued.items():
        axis._chart._shape._slide._presentation._queue_chart_axis_property(
            axis._chart._shape._slide._index,
            axis._chart._shape._index,
            axis._axis,
            attr,
            value,
        )


class TickLabels:
    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            lambda: _chart_axis_text_default_run_properties(
                self._axis._chart._shape,
                self._axis._axis,
            ),
            self._queue_font,
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_size"),
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_fill_type"),
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_pattern"),
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_gradient"),
        )

    @property
    def number_format(self) -> str:
        return str(
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis).get(
                "number_format",
                "General",
            )
        )

    @number_format.setter
    def number_format(self, value: Any) -> None:
        number_format = str(value)
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        if (
            str(payload.get("number_format", "General")) == number_format
            and payload.get("number_format_is_linked") is False
        ):
            return
        payload["number_format"] = number_format
        payload["number_format_is_linked"] = False
        self._axis._set_property("number_format", number_format, force=True)

    @property
    def number_format_is_linked(self) -> bool:
        return bool(
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis).get(
                "number_format_is_linked",
            )
        )

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        linked = bool(value)
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        if linked == bool(payload.get("number_format_is_linked")):
            return
        payload.setdefault("number_format", "General")
        self._axis._set_property("number_format_is_linked", linked)

    @property
    def offset(self) -> int:
        if self._axis._axis != "cat":
            raise AttributeError("'CT_ValAx' object has no attribute 'lblOffset'")
        return int(
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis).get(
                "tick_label_offset",
                100,
            )
        )

    @offset.setter
    def offset(self, value: Any) -> None:
        if self._axis._axis != "cat":
            raise ValueError("only a category axis has an offset")
        offset = _normalize_tick_label_offset(value)
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        if int(payload.get("tick_label_offset", 100)) == offset:
            return
        self._axis._set_property("tick_label_offset", offset)

    def _queue_font(self, properties: dict[str, Any]) -> None:
        mapping = {
            "font_bold": "tick_label_font_bold",
            "font_italic": "tick_label_font_italic",
            "font_underline": "tick_label_font_underline",
            "font_size": "tick_label_font_size",
            "font_fill_type": "tick_label_font_fill_type",
            "font_pattern": "tick_label_font_pattern",
            "font_pattern_fore_rgb": "tick_label_font_pattern_fore_rgb",
            "font_pattern_back_rgb": "tick_label_font_pattern_back_rgb",
            "font_gradient": "tick_label_font_gradient",
            "font_rgb": "tick_label_font_rgb",
            "font_name": "tick_label_font_name",
            "font_language_id": "tick_label_font_language_id",
        }
        for attr, value in properties.items():
            try:
                payload_attr = mapping[attr]
            except KeyError as exc:
                raise ValueError(
                    f"unsupported chart tick-label font property: {properties!r}"
                ) from exc
            self._axis._set_property(payload_attr, value)


class ChartCategories:
    """Category labels of a category chart, each with per-level grouping labels.

    Level 0 is a category's own label; level 1 is its innermost group, and so
    on outward.  Edits rewrite the series category caches and the embedded
    workbook together, so the chart data stays editable in the host application.
    """

    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    def __len__(self) -> int:
        return len(self._paths())

    def __iter__(self) -> Iterator[ChartCategory]:
        for index in range(len(self)):
            yield ChartCategory(self, index)

    def __getitem__(self, index: int) -> ChartCategory:
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"category index must be an int, got {index!r}")
        count = len(self)
        if index < 0:
            index += count
        if not 0 <= index < count:
            raise IndexError("category index out of range")
        return ChartCategory(self, index)

    @property
    def level_count(self) -> int:
        """Number of label levels, counting the category labels themselves."""
        paths = self._paths()
        return len(paths[0]) if paths else 0

    @property
    def labels(self) -> list[str]:
        return [path[-1] for path in self._paths()]

    def add_level(self, labels: Sequence[str]) -> None:
        """Add an outermost grouping level with one label per category.

        Consecutive categories with the same label share one group.
        """
        paths = self._paths()
        new_labels = list(labels)
        if len(new_labels) != len(paths):
            raise ValueError(f"add_level needs {len(paths)} labels, got {len(new_labels)}")
        for label in new_labels:
            _require_level_text(label)
        self._write([[label, *path] for label, path in zip(new_labels, paths, strict=True)])

    def _paths(self) -> list[list[str]]:
        self._axis._check_live()
        return _chart_category_paths(self._axis._chart._shape)[0]

    def _level_text(self, index: int, level: int) -> str:
        path = self._paths()[index]
        if isinstance(level, bool) or not isinstance(level, int):
            raise TypeError(f"level must be an int, got {level!r}")
        if not 0 <= level < len(path):
            raise IndexError("category level out of range")
        return path[len(path) - 1 - level]

    def _set_level(self, index: int, level: int, text: str) -> None:
        _require_level_text(text)
        paths = [list(path) for path in self._paths()]
        depth = len(paths[index])
        if isinstance(level, bool) or not isinstance(level, int):
            raise TypeError(f"level must be an int, got {level!r}")
        if level == depth:
            paths = [["", *path] for path in paths]
            paths[index][0] = text
        elif 0 <= level < depth:
            paths[index][depth - 1 - level] = text
        else:
            raise IndexError(f"category level must be in range 0 to {depth} inclusive, got {level}")
        self._write(paths)

    def _write(self, paths: list[list[str]]) -> None:
        shape = self._axis._chart._shape
        if not paths:
            raise ValueError("the chart has no categories")
        if not _chart_category_paths(shape)[1]:
            raise ValueError("numeric and date categories cannot carry grouping levels")
        payload = _chart_payload(shape)
        series = list(payload.get("series") or [])
        leaves = [path[-1] for path in paths]
        depth = len(paths[0])
        hierarchy = [list(path) for path in paths] if depth > 1 else []
        series_payloads: list[dict[str, Any]] = []
        for series_payload in series:
            values = list(series_payload.get("values") or [])
            if any(value is None for value in values):
                raise ValueError(
                    "category levels cannot be rewritten while a series has blank values"
                )
            series_payloads.append(
                {
                    "name": str(series_payload.get("name") or ""),
                    "categories": leaves,
                    "values": [float(value) for value in values],
                }
            )
        replacement = {
            "data_kind": "category",
            "category_kind": "string",
            "categories": leaves,
            "category_hierarchy": hierarchy,
            "series": series_payloads,
            "xlsx_blob": _category_chart_workbook_blob(
                leaves,
                series_payloads,
                category_hierarchy=hierarchy or None,
            ),
        }
        root = _shape_chart_root(shape)
        _prepare_chart_category_levels(root, _chart_series_elements(root), depth)
        chart_xml = _replace_chart_categories_xml(root, replacement)
        for series_payload in series:
            series_payload["categories"] = list(leaves)
        shape._slide._presentation._queue_chart_data_replace(
            shape._slide._index,
            shape._index,
            {
                **replacement,
                "_chart_part": str(payload.get("part") or ""),
                "_chart_xml": chart_xml,
            },
        )


class ChartCategory:
    """One category and its grouping levels."""

    def __init__(self, categories: ChartCategories, index: int) -> None:
        self._categories = categories
        self._index = index

    @property
    def label(self) -> str:
        return self._categories._level_text(self._index, 0)

    @label.setter
    def label(self, value: str) -> None:
        self._categories._set_level(self._index, 0, value)

    @property
    def levels(self) -> ChartCategoryLevels:
        return ChartCategoryLevels(self._categories, self._index)


class ChartCategoryLevels:
    """Per-level labels of one category; level 0 is the category label."""

    def __init__(self, categories: ChartCategories, index: int) -> None:
        self._categories = categories
        self._index = index

    def __len__(self) -> int:
        return self._categories.level_count

    def __getitem__(self, level: int) -> str:
        return self._categories._level_text(self._index, level)

    def __setitem__(self, level: int, text: str) -> None:
        self.set_level(level, text)

    def set_level(self, level: int, text: str) -> None:
        """Set this category's label at ``level``.

        ``level`` equal to the current level count adds a new outermost level,
        leaving the other categories' labels at that level empty.
        """
        self._categories._set_level(self._index, level, text)

    def add_level(self, text: str) -> None:
        """Add an outermost level labelled ``text`` for this category."""
        self._categories._set_level(self._index, len(self), text)


_AXIS_POSITION_NAMES = {"b": "bottom", "l": "left", "r": "right", "t": "top"}
_AXIS_POSITION_TOKENS = {
    **{token: token for token in _AXIS_POSITION_NAMES},
    **{name: token for token, name in _AXIS_POSITION_NAMES.items()},
}
_DISPLAY_UNIT_KEYS = {unit.lower(): unit for unit in _CHART_AXIS_BUILT_IN_DISPLAY_UNITS}


def _normalize_axis_position(value: Any) -> str:
    raw = getattr(value, "name", value)
    token = _AXIS_POSITION_TOKENS.get(str(raw).strip().lower())
    if token is None:
        raise ValueError(f"unsupported axis position: {value!r}")
    return token


def _normalize_display_unit(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "name", value)
    key = re.sub(r"[^a-z]", "", str(raw).lower())
    if key == "none":
        return None
    if key in {"custom", "customvalue"}:
        return "custom"
    unit = _DISPLAY_UNIT_KEYS.get(key)
    if unit is None:
        raise ValueError(f"unsupported axis display unit: {value!r}")
    return unit


def _new_display_units_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Return a display-units state to edit; new units show their label."""
    if state is not None:
        return dict(state)
    return {
        "unit": "thousands",
        "custom_unit": None,
        "label_visible": True,
        "label_text": None,
    }


def _require_level_text(text: Any) -> None:
    if not isinstance(text, str):
        raise TypeError(f"category level text must be a string, got {text!r}")
