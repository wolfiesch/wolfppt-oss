"""Per-shape facade objects for slides and masters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .chart_facade import Chart
from .facade_values import (
    coerce_emu as _coerce_emu,
    coerce_rotation_degrees as _coerce_rotation_degrees,
)
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
)
from .shape_connector_facade import (
    connect_connector_endpoint as _connect_connector_endpoint,
    connector_endpoint_value as _connector_endpoint_value,
)
from .shape_edit_refs import shape_edit_ref as _shape_edit_ref
from .shape_action_facade import (
    ActionSetting,
    AdjustmentCollection,
    PlaceholderFormat,
)
from .shape_master_facade import MasterShape
from .shape_ole_facade import OleFormat, _shape_related_partname
from .shape_format_facade import FillFormat, LineFormat, ShadowFormat
from .shape_group_text_queue import (
    queue_pending_group_child_text as _queue_pending_group_child_text,
)
from .shape_inspection import (
    MediaFormat,
    PictureImage,
    _picture_crop_value,
    _picture_image,
    _replace_picture_image,
    _set_picture_crop_value,
    _shape_media_format,
    _shape_media_type,
    _shape_poster_frame,
    _set_shape_transform_value,
    _shape_auto_shape_type_value,
    _shape_line_xml_element,
    _shape_type_value,
)
from .shape_payloads import (
    _shape_paragraph_runs,
    _shape_transform_value,
)
from .shape_xml import _shape_xml_element
from .table_facade import Table
from .text_facade import TextFrame, _shape_rotation

if TYPE_CHECKING:
    from .presentation_slides import Slide

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class Shape:
    def __init__(
        self,
        slide: Slide,
        index: int,
        payload: dict[str, Any],
        table_index: int = 0,
        run_start_index: int = 0,
    ) -> None:
        self._slide = slide
        self._index = index
        self._payload = dict(payload)
        self._table_index = table_index
        self._run_start_index = run_start_index
        paragraph_runs = _shape_paragraph_runs(self)
        self._existing_paragraph_count = len(paragraph_runs)
        self._existing_run_counts = [len(runs) for runs in paragraph_runs]

    @property
    def shape_id(self) -> int | str | None:
        raw = self._payload.get("id")
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return raw

    @property
    def shape_type(self) -> Any:
        return _shape_type_value(self)

    @property
    def auto_shape_type(self) -> Any:
        return _shape_auto_shape_type_value(self)

    @property
    def adjustments(self) -> "AdjustmentCollection":
        if self._payload.get("kind") not in {"shape", "freeform"}:
            raise AttributeError("'Shape' object has no attribute 'adjustments'")
        return AdjustmentCollection(self)

    @property
    def ln(self) -> XmlElementProxy | None:
        if self._payload.get("kind") not in {
            "connector",
            "shape",
            "picture",
            "freeform",
        }:
            raise AttributeError("'Shape' object has no attribute 'ln'")
        line = _shape_line_xml_element(self)
        return None if line is None else XmlElementProxy(line)

    def get_or_add_ln(self) -> XmlElementProxy:
        if self._payload.get("kind") not in {
            "connector",
            "shape",
            "picture",
            "freeform",
        }:
            raise AttributeError("'Shape' object has no attribute 'get_or_add_ln'")
        line = _shape_line_xml_element(self)
        if line is None:
            line = ET.Element(f"{{{A_NS}}}ln")
        self._payload["has_line_element"] = True
        self._slide._presentation._queue_shape_line_element(
            self._slide._index,
            _shape_edit_ref(self),
        )
        return XmlElementProxy(line)

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._slide._presentation.path,
            self._slide.partname,
        )
        return XmlElementProxy(_shape_xml_element(root._element, self._payload))

    @property
    def _element(self) -> XmlElementProxy:
        return self.element

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"value must be a string, got {type(value)!r}")
        if value == self.name:
            return
        self._payload["name"] = value
        self._slide._presentation._queue_shape_name(
            self._slide._index,
            _shape_edit_ref(self),
            value,
        )

    @property
    def left(self) -> int:
        return _shape_transform_value(self, "x")

    @left.setter
    def left(self, value: int) -> None:
        _set_shape_transform_value(self, "x", _coerce_emu(value, "left"))

    @property
    def top(self) -> int:
        return _shape_transform_value(self, "y")

    @top.setter
    def top(self, value: int) -> None:
        _set_shape_transform_value(self, "y", _coerce_emu(value, "top"))

    @property
    def width(self) -> int:
        return _shape_transform_value(self, "cx")

    @width.setter
    def width(self, value: int) -> None:
        _set_shape_transform_value(self, "cx", _coerce_emu(value, "width"))

    @property
    def height(self) -> int:
        return _shape_transform_value(self, "cy")

    @height.setter
    def height(self, value: int) -> None:
        _set_shape_transform_value(self, "cy", _coerce_emu(value, "height"))

    @property
    def begin_x(self) -> int:
        return _connector_endpoint_value(self, "begin", "x")

    @property
    def begin_y(self) -> int:
        return _connector_endpoint_value(self, "begin", "y")

    @property
    def end_x(self) -> int:
        return _connector_endpoint_value(self, "end", "x")

    @property
    def end_y(self) -> int:
        return _connector_endpoint_value(self, "end", "y")

    def begin_connect(self, shape: Any, cxn_pt_idx: int) -> None:
        _connect_connector_endpoint(self, "begin", shape, cxn_pt_idx)

    def end_connect(self, shape: Any, cxn_pt_idx: int) -> None:
        _connect_connector_endpoint(self, "end", shape, cxn_pt_idx)

    @property
    def rotation(self) -> float:
        raw = self._payload.get("rotation")
        if not isinstance(raw, (int, float)):
            raw = _shape_rotation(self)
            self._payload["rotation"] = raw
        return float(raw)

    @rotation.setter
    def rotation(self, value: float) -> None:
        rotation = _coerce_rotation_degrees(value)
        if rotation == self.rotation:
            return
        self._payload["rotation"] = rotation
        self._slide._presentation._queue_shape_rotation(
            self._slide._index,
            _shape_edit_ref(self),
            rotation,
        )

    @property
    def fill(self) -> "FillFormat":
        return FillFormat(self)

    @property
    def line(self) -> "LineFormat":
        return LineFormat(self)

    @property
    def shadow(self) -> "ShadowFormat":
        return ShadowFormat(self)

    @property
    def click_action(self) -> "ActionSetting":
        return ActionSetting(self)

    @property
    def has_text_frame(self) -> bool:
        return self._payload.get("kind") in {"shape", "freeform"}

    @property
    def has_picture(self) -> bool:
        return (
            bool(self._payload.get("has_picture"))
            or self._payload.get("kind") == "picture"
        )

    @property
    def image(self) -> PictureImage:
        return _picture_image(self)

    def replace_image(self, image_file: Any) -> PictureImage:
        return _replace_picture_image(self, image_file)

    @property
    def media_format(self) -> MediaFormat:
        return _shape_media_format(self)

    @property
    def media_type(self) -> Any:
        return _shape_media_type(self)

    @property
    def poster_frame(self) -> PictureImage:
        return _shape_poster_frame(self)

    @property
    def crop_left(self) -> float:
        return _picture_crop_value(self, "l")

    @crop_left.setter
    def crop_left(self, value: Any) -> None:
        _set_picture_crop_value(self, "l", value)

    @property
    def crop_right(self) -> float:
        return _picture_crop_value(self, "r")

    @crop_right.setter
    def crop_right(self, value: Any) -> None:
        _set_picture_crop_value(self, "r", value)

    @property
    def crop_top(self) -> float:
        return _picture_crop_value(self, "t")

    @crop_top.setter
    def crop_top(self, value: Any) -> None:
        _set_picture_crop_value(self, "t", value)

    @property
    def crop_bottom(self) -> float:
        return _picture_crop_value(self, "b")

    @crop_bottom.setter
    def crop_bottom(self, value: Any) -> None:
        _set_picture_crop_value(self, "b", value)

    @property
    def has_table(self) -> bool:
        return bool(self._payload.get("tables"))

    @property
    def has_chart(self) -> bool:
        return bool(self._payload.get("has_chart"))

    @property
    def is_placeholder(self) -> bool:
        return bool(self._payload.get("is_placeholder"))

    @property
    def placeholder_format(self) -> "PlaceholderFormat":
        if not self.is_placeholder:
            raise ValueError("shape is not a placeholder")
        return PlaceholderFormat(self)

    @property
    def table(self) -> "Table":
        tables = self._payload.get("tables") or []
        if not tables:
            raise AttributeError("shape does not have a table")
        return Table(self._slide, self._table_index, tables[0])

    @property
    def chart(self) -> "Chart":
        if not self.has_chart:
            raise AttributeError("shape does not have a chart")
        return Chart(self)

    @property
    def chart_part(self) -> PackagePart:
        if not self.has_chart:
            raise ValueError("this graphic frame does not contain a chart")
        partname = _shape_related_partname(self, "/chart")
        if partname is None:
            raise ValueError("this graphic frame does not contain a chart")
        return PackagePart(self._slide._presentation, partname, None)

    @property
    def ole_format(self) -> "OleFormat":
        if self._payload.get("kind") != "ole_object":
            raise ValueError("not an OLE-object shape")
        return OleFormat(self)

    @property
    def shapes(self) -> "GroupShapeCollection":
        if self._payload.get("kind") != "group":
            raise AttributeError("'Shape' object has no attribute 'shapes'")
        shapes = getattr(self, "_group_shapes", None)
        if shapes is None:
            from .shape_group_collection_facade import GroupShapeCollection

            shapes = GroupShapeCollection(self)
            self._group_shapes = shapes
        return shapes
    @property
    def text(self) -> str:
        return str(self._payload.get("text") or "")

    @text.setter
    def text(self, value: str) -> None:
        if not self.has_text_frame:
            raise AttributeError("shape does not have a text frame")
        text = str(value)
        paragraphs = text.split("\n") if text else [""]
        self._payload["text"] = text
        self._payload["paragraphs"] = paragraphs
        self._payload["paragraph_runs"] = [
            [paragraph] if paragraph else [] for paragraph in paragraphs
        ]
        self._payload["paragraph_line_breaks"] = [[] for _ in paragraphs]
        if _queue_pending_group_child_text(self, text):
            return
        self._slide._presentation._queue_shape_text_for_shape(self, text)

    @property
    def text_frame(self) -> "TextFrame":
        if not self.has_text_frame:
            raise AttributeError("shape does not have a text frame")
        return TextFrame(self)
