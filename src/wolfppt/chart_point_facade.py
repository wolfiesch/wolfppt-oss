"""Chart series point and point data-label facade helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any
from xml.etree import ElementTree as ET

from .chart_data_label_xml import (
    _data_label_insert_index,
    _set_chart_data_label_property,
    chart_data_labels_payload,
)
from .chart_element_format_xml import (
    set_chart_element_format_properties_in_order as _set_chart_element_format_properties_in_order,
)
from .chart_font_format_facade import (
    ChartTextFormat,
    chart_text_body,
    order_chart_text_typefaces,
)
from .chart_format_facade import ChartFont, ChartFormat
from .chart_point_data_label_text_facade import DataLabelTextFrame
from .chart_point_data_label_xml import (
    point_data_label_position_xml as _point_data_label_position_xml,
)
from .chart_point_data_label_xml import (
    point_data_label_text_default_run_properties as _point_data_label_text_default_run_properties,
)
from .chart_point_data_label_xml import (
    set_point_data_label_position as _set_point_data_label_position,
)
from .chart_point_data_label_xml import (
    set_point_data_label_text_frame as _set_point_data_label_text_frame,
)
from .chart_point_data_label_xml import (
    set_point_data_label_text_properties as _set_point_data_label_text_properties,
)
from .chart_point_data_label_xml import (
    set_run_properties_font as _set_run_properties_font,
)
from .chart_point_facade_xml import (
    _chart_point_data_label_element,
    _chart_point_element,
    chart_series_element,
)
from .chart_point_marker_facade import Marker
from .chart_point_xml import CHART_POINT_SCALAR_PROPERTIES as _CHART_POINT_SCALAR_PROPERTIES
from .chart_point_xml import set_chart_point_scalar as _set_chart_point_scalar
from .facade_values import (
    data_label_position_value as _data_label_position_value,
)
from .facade_values import (
    normalize_data_label_position as _normalize_data_label_position,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"

#: Largest point explosion PowerPoint authors, as a percent of the pie radius.
MAX_POINT_EXPLOSION = 400


class ChartPointRefusal(ValueError):
    """An invalid data-point scalar edit was refused before changing the point."""


class ChartPointCollection(Sequence["ChartPoint"]):
    def __init__(self, series: Any) -> None:
        self._series = series

    def __getitem__(self, index: int | slice) -> ChartPoint | list[ChartPoint]:
        if isinstance(index, slice):
            return [ChartPoint(self._series, item) for item in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("chart point index out of range")
        return ChartPoint(self._series, index)

    def __iter__(self) -> Iterator[ChartPoint]:
        for index in range(len(self)):
            yield ChartPoint(self._series, index)

    def __len__(self) -> int:
        return len(self._series.values)


class ChartPoint:
    def __init__(self, series: Any, index: int) -> None:
        self._series = series
        self._index = index

    def set_picture_fill(
        self, image: Any, picture_type: str = "stretch", stack_unit: float = 1.0
    ) -> None:
        """Embed this point's picture with the chart series picture-fill API."""
        self._series.set_picture_fill(image, picture_type, stack_unit, point_index=self._index)

    def picture_fill(self) -> dict[str, Any] | None:
        """Read this point's embedded image and picture mode."""
        return self._series.picture_fill(point_index=self._index)

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_point_element(
                self._series._chart._shape,
                self._series.index,
                self._index,
            ),
            self._queue_format,
        )

    @property
    def data_label(self) -> DataLabel:
        return DataLabel(self)

    @property
    def marker(self) -> Marker:
        return Marker(self)

    @property
    def explosion(self) -> int | None:
        """This point's declared slice offset, a percent of the pie radius.

        ``None`` means the point declares none and the series explosion applies.
        Assign an int from 0 to 400, or ``None`` to remove the override.
        """
        value = self._scalar_val("explosion")
        return None if value is None else int(value)

    @explosion.setter
    def explosion(self, value: Any) -> None:
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= MAX_POINT_EXPLOSION
        ):
            raise ChartPointRefusal(
                f"point explosion must be an int from 0 to {MAX_POINT_EXPLOSION} or None, "
                f"got {value!r}"
            )
        self._set_scalar("explosion", value)

    @property
    def invert_if_negative(self) -> bool | None:
        """Whether a negative value draws this point inverted.

        ``None`` means the point declares no override and the series setting applies.
        """
        value = self._scalar_val("invert_if_negative")
        return None if value is None else value.strip().lower() in {"1", "true"}

    @invert_if_negative.setter
    def invert_if_negative(self, value: Any) -> None:
        if value is not None and not isinstance(value, bool):
            raise ChartPointRefusal(
                f"point invert_if_negative must be a bool or None, got {value!r}"
            )
        self._set_scalar("invert_if_negative", value)

    def _scalar_val(self, attr: str) -> str | None:
        point = _chart_point_element(self._series._chart._shape, self._series.index, self._index)
        child = point.find(f"{{{C_NS}}}{_CHART_POINT_SCALAR_PROPERTIES[attr]}")
        # CT_Boolean defaults to true; CT_UnsignedInt defaults to zero.
        return None if child is None else child.get("val", "0" if attr == "explosion" else "1")

    def _set_scalar(self, attr: str, value: Any) -> None:
        current = self._scalar_val(attr)
        if attr == "explosion":
            unchanged = (None if current is None else int(current)) == value
        else:
            unchanged = (
                None if current is None else current.strip().lower() in {"1", "true"}
            ) == value
        if unchanged:
            return
        element = _chart_point_element(
            self._series._chart._shape, self._series.index, self._index, create=True
        )
        _set_chart_point_scalar(element, attr, value)
        self._queue_point_properties({attr: value})

    def _queue_format(self, properties: dict[str, Any]) -> None:
        element = _chart_point_element(
            self._series._chart._shape,
            self._series.index,
            self._index,
            create=True,
        )
        _set_chart_element_format_properties_in_order(element, properties, "point")
        self._queue_point_properties(properties)

    def _queue_point_properties(self, properties: dict[str, Any]) -> None:
        chart = self._series._chart
        chart._shape._slide._presentation._queue_chart_data_labels(
            chart._shape._slide._index,
            chart._shape._index,
            {
                "point_formats": [
                    {
                        "series_index": self._series.index,
                        "point_index": self._index,
                        "properties": properties,
                    }
                ]
            },
        )


class DataLabel:
    def __init__(self, point: ChartPoint) -> None:
        self._point = point

    def _element(self, create: bool = False) -> ET.Element:
        series = chart_series_element(self._point._series._chart._shape, self._point._series.index)
        labels = series.find(f"{{{C_NS}}}dLbls")
        if labels is None and create:
            labels = self._point._series.data_labels._labels_element(True)
        if labels is not None:
            for label in labels.findall(f"{{{C_NS}}}dLbl"):
                index = label.find(f"{{{C_NS}}}idx")
                if index is not None and index.get("val") == str(self._point._index):
                    return label
        label = ET.Element(f"{{{C_NS}}}dLbl")
        ET.SubElement(label, f"{{{C_NS}}}idx", {"val": str(self._point._index)})
        if create:
            assert labels is not None
            labels.insert(_data_label_insert_index(labels, "dLbl"), label)
        return label

    @property
    def text_format(self) -> ChartTextFormat:
        """Formatting of rich label text, or automatic label text in ``txPr``."""
        return ChartTextFormat(
            lambda create: chart_text_body(self._element(create), create, _data_label_insert_index),
            lambda scope, delta: self._queue(
                {"text_format_edits": [{"scope": scope, "delta": dict(delta)}]}
            ),
        )

    def _label_value(self, key: str) -> Any:
        label = self._element()
        tags = {
            "show_value": "showVal",
            "show_category_name": "showCatName",
            "show_series_name": "showSerName",
            "show_percentage": "showPercent",
            "show_legend_key": "showLegendKey",
            "show_bubble_size": "showBubbleSize",
            "show_leader_lines": "showLeaderLines",
            "separator": "separator",
            "number_format": "numFmt",
            "number_format_is_linked": "numFmt",
        }
        if label.find(f"{{{C_NS}}}{tags[key]}") is not None:
            return chart_data_labels_payload(_label_container(label))[key]
        labels = self._point._series.data_labels
        return getattr(labels, key)

    def _set_label_value(self, key: str, value: Any) -> None:
        _set_chart_data_label_property(self._element(True), key, value)
        self._queue({key: value})

    @property
    def separator(self) -> str | None:
        return self._label_value("separator")

    @separator.setter
    def separator(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError("separator must be a string or None")
        self._set_label_value("separator", value)

    @property
    def show_value(self) -> bool:
        return self._label_value("show_value")

    @show_value.setter
    def show_value(self, value: Any) -> None:
        self._set_label_value("show_value", bool(value))

    @property
    def show_category_name(self) -> bool:
        return self._label_value("show_category_name")

    @show_category_name.setter
    def show_category_name(self, value: Any) -> None:
        self._set_label_value("show_category_name", bool(value))

    @property
    def show_series_name(self) -> bool:
        return self._label_value("show_series_name")

    @show_series_name.setter
    def show_series_name(self, value: Any) -> None:
        self._set_label_value("show_series_name", bool(value))

    @property
    def show_percentage(self) -> bool:
        return self._label_value("show_percentage")

    @show_percentage.setter
    def show_percentage(self, value: Any) -> None:
        self._set_label_value("show_percentage", bool(value))

    @property
    def show_legend_key(self) -> bool:
        return self._label_value("show_legend_key")

    @show_legend_key.setter
    def show_legend_key(self, value: Any) -> None:
        self._set_label_value("show_legend_key", bool(value))

    @property
    def show_bubble_size(self) -> bool:
        return self._label_value("show_bubble_size")

    @show_bubble_size.setter
    def show_bubble_size(self, value: Any) -> None:
        self._set_label_value("show_bubble_size", bool(value))

    @property
    def show_leader_lines(self) -> bool:
        return self._label_value("show_leader_lines")

    @show_leader_lines.setter
    def show_leader_lines(self, value: Any) -> None:
        self._set_label_value("show_leader_lines", bool(value))

    @property
    def number_format(self) -> str:
        return self._label_value("number_format")

    @number_format.setter
    def number_format(self, value: Any) -> None:
        self._set_label_value("number_format", str(value))

    @property
    def number_format_is_linked(self) -> bool:
        return self._label_value("number_format_is_linked")

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        self._set_label_value("number_format_is_linked", bool(value))

    @property
    def has_text_frame(self) -> bool:
        element = self._element()
        return element.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich") is not None

    @has_text_frame.setter
    def has_text_frame(self, value: Any) -> None:
        enabled = bool(value)
        if enabled == self.has_text_frame:
            return
        element = self._element(True)
        _set_point_data_label_text_frame(element, enabled)
        self._queue({"has_text_frame": enabled})

    @property
    def text_frame(self) -> DataLabelTextFrame:
        return DataLabelTextFrame(self)

    @property
    def position(self) -> Any:
        element = self._element()
        position = element.find(f"{{{C_NS}}}dLblPos")
        return _data_label_position_value(None if position is None else position.attrib.get("val"))

    @position.setter
    def position(self, value: Any) -> None:
        position = _normalize_data_label_position(value)
        if (
            _point_data_label_position_xml(
                _chart_point_data_label_element(
                    self._point._series._chart._shape,
                    self._point._series.index,
                    self._point._index,
                )
            )
            == position
        ):
            return
        element = self._element(True)
        _set_point_data_label_text_properties(element)
        _set_point_data_label_position(element, position)
        self._queue({"position": position})

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            self._text_default_run_properties,
            self._queue_font,
        )

    def _text_default_run_properties(self) -> ET.Element | None:
        element = self._element()
        return element.find(f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr")

    def _queue_font(self, properties: dict[str, Any]) -> None:
        element = self._element(True)
        run_properties = _point_data_label_text_default_run_properties(element)
        font_properties: dict[str, Any] = {}
        for attr, value in properties.items():
            if attr == "font_bold":
                font_properties["bold"] = value
            elif attr == "font_italic":
                font_properties["italic"] = value
            elif attr == "font_underline":
                font_properties["underline"] = value
            elif attr == "font_size":
                font_properties["size"] = value
            elif attr == "font_fill_type":
                font_properties["fill_type"] = value
            elif attr == "font_pattern":
                font_properties["pattern"] = value
            elif attr == "font_pattern_fore_rgb":
                font_properties["pattern_fore_rgb"] = value
            elif attr == "font_pattern_back_rgb":
                font_properties["pattern_back_rgb"] = value
            elif attr == "font_gradient":
                font_properties["gradient"] = value
            elif attr == "font_rgb":
                font_properties["rgb"] = value
            elif attr == "font_name":
                font_properties["name"] = value
            elif attr == "font_language_id":
                font_properties["language_id"] = value
            else:
                raise AttributeError(f"unsupported chart data-label font property: {attr!r}")
        _set_run_properties_font(run_properties, font_properties)
        self._queue(properties)

    def _queue(self, properties: dict[str, Any]) -> None:
        chart = self._point._series._chart
        order_chart_text_typefaces(self._element())
        properties = {
            **properties,
            "_label_xml": ET.tostring(self._element(), encoding="utf-8"),
        }
        chart._shape._slide._presentation._queue_chart_data_labels(
            chart._shape._slide._index,
            chart._shape._index,
            {
                "point_labels": [
                    {
                        "series_index": self._point._series.index,
                        "point_index": self._point._index,
                        "properties": properties,
                    }
                ]
            },
        )


def _label_container(label: ET.Element) -> ET.Element:
    container = ET.Element(f"{{{C_NS}}}ser")
    labels = ET.SubElement(container, f"{{{C_NS}}}dLbls")
    for child in label:
        if child.tag != f"{{{C_NS}}}idx":
            labels.append(child)
    return container
