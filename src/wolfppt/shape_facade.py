"""Shape facade classes and shape XML readers."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .chart_edits import _normalize_chart_add_data
from .chart_facade import Chart
from .chart_xml import chart_type_payload_from_value as _chart_type_payload_from_value
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
    gradient_stop_element as _gradient_stop_element,
    set_shape_gradient_fill as _set_shape_gradient_fill,
    set_shape_no_fill as _set_shape_no_fill,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    set_shape_pattern_fill_color as _set_shape_pattern_fill_color,
    set_shape_solid_fill as _set_shape_solid_fill,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
    coerce_positive_int as _coerce_positive_int,
    coerce_rotation_degrees as _coerce_rotation_degrees,
    color_type_value as _color_type_value,
    emu_value as _emu_value,
    fill_type_value as _fill_type_value,
    line_dash_style_value as _line_dash_style_value,
    normalize_line_dash_style as _normalize_line_dash_style,
    normalize_pattern_type as _normalize_pattern_type,
    normalize_rgb as _normalize_rgb,
    normalize_theme_color as _normalize_theme_color,
    pattern_type_value as _pattern_type_value,
    rgb_value as _rgb_value,
    theme_color_value as _theme_color_value,
)
from .image_dimensions import picture_dimensions as _picture_dimensions
from .image_inputs import (
    binary_source_for_queue as _binary_source_for_queue,
    image_source_for_queue as _image_source_for_queue,
    movie_source_for_queue as _movie_source_for_queue,
    source_display_filename as _source_display_filename,
)
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
)
from .shape_action_facade import (
    ActionSetting,
    AdjustmentCollection,
    Hyperlink,
    PlaceholderFormat,
)
from .shape_inspection import (
    PictureImage,
    _auto_shape_preset_geometry,
    _cloneable_layout_placeholders,
    _connector_preset_geometry,
    _next_placeholder_name,
    _next_shape_id,
    _notes_placeholder_basename,
    _payload_string,
    _picture_crop,
    _picture_crop_value,
    _picture_image,
    _placeholder_basename,
    _placeholder_raw_value,
    _placeholder_type_value,
    _placeholder_type_xml,
    _set_picture_crop_value,
    _set_shape_transform_value,
    _shape_adjustment_actuals,
    _shape_adjustment_guides,
    _shape_auto_shape_preset_geometry,
    _shape_auto_shape_type_value,
    _shape_click_action_name,
    _shape_click_action_value,
    _shape_collection_table_count,
    _shape_hyperlink_address,
    _shape_hyperlink_click,
    _shape_is_text_box,
    _shape_line_xml_element,
    _shape_picture_crop,
    _shape_target_slide,
    _shape_type_value,
)
from .shape_format_facade import (
    ColorFormat,
    FillFormat,
    GradientStop,
    GradientStopColorFormat,
    GradientStops,
    LineFillFormat,
    LineFormat,
    ShadowFormat,
    _DetachedFillShape,
    _detached_fill_parent,
    _shape_fill_pattern,
    _shape_fill_type,
    _shape_gradient_fill_payload,
    _shape_line_dash_style,
    _shape_line_fill_pattern,
    _shape_line_fill_type,
    _shape_line_width,
    _shape_pattern_rgb,
    _shape_shadow_inherit,
    _shape_style_rgb,
    _supports_shape_line_style,
)
from .shape_freeform import FreeformBuilder
from .shape_payloads import (
    _shape_paragraph_runs,
    _shape_transform_value,
)
from .shape_placeholder_collections import (
    BaseShapePlaceholderCollection,
    MasterPlaceholderCollection,
    MasterShapeCollection,
    PlaceholderCollection,
)
from .shape_xml import (
    _shape_xml_element,
)
from .shape_core_facade import MasterShape, Shape
from .table_facade import Table
from .text_facade import TextFrame, _shape_rotation

if TYPE_CHECKING:
    from .presentation_slides import Slide

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _pending_shape_identity(shape_id: int) -> dict[str, Any]:
    return {"id": str(shape_id), "_pending_shape": True}


def _placeholder_queue_spec(
    spec: dict[str, str | bool | None],
) -> dict[str, str | None]:
    return {
        "placeholder_type": _payload_string(spec, "placeholder_type"),
        "placeholder_orient": _payload_string(spec, "placeholder_orient"),
        "placeholder_size": _payload_string(spec, "placeholder_size"),
        "placeholder_idx": _payload_string(spec, "placeholder_idx"),
    }


class ShapeCollection(Sequence["Shape"]):
    def __init__(self, slide: "Slide", shapes: list["Shape"]) -> None:
        self._slide = slide
        self._shapes = shapes
        self._turbo_add_enabled = False

    def __getitem__(self, index: int | slice) -> "Shape | list[Shape]":
        return self._shapes[index]

    def __iter__(self) -> Iterator["Shape"]:
        return iter(self._shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    def index(self, shape: "Shape") -> int:
        for index, candidate in enumerate(self._shapes):
            if candidate is shape:
                return index
        target = shape.element
        for index, candidate in enumerate(self._shapes):
            if (
                getattr(candidate, "_slide", None) is getattr(shape, "_slide", None)
                and getattr(candidate, "_index", None) == getattr(shape, "_index", None)
            ):
                return index
        raise ValueError(f"{target!r} is not in list")

    def remove(self, shape: "Shape") -> None:
        """Remove one existing shape from this slide or parent group."""
        if getattr(shape, "_payload", {}).get("_group_child"):
            raise NotImplementedError(
                "deleting shapes inside a group is not supported yet"
            )
        if getattr(shape, "_slide", None) is not self._slide:
            raise ValueError(f"{shape!r} is not in this shape collection")
        position = next(
            (index for index, candidate in enumerate(self._shapes) if candidate is shape),
            None,
        )
        if position is None:
            raise ValueError(f"{shape!r} is not in this shape collection")
        if not self._slide.partname or shape._payload.get("_pending_shape"):
            raise NotImplementedError("deleting an unsaved shape is not supported yet")

        self._slide._presentation._queue_shape_delete(
            self._slide._index,
            shape._index,
        )
        self._shapes.pop(position)
        self._slide._payload["shapes"].pop(position)
        shape._payload["_deleted"] = True
        placeholders = getattr(self._slide, "_placeholders", None)
        if placeholders is not None:
            placeholders._placeholders[:] = [
                placeholder
                for placeholder in placeholders._placeholders
                if placeholder is not shape
            ]

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def parent(self) -> "Slide":
        return self._slide

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._slide._presentation.path,
            self._slide.partname,
        )
        element = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if element is None:
            raise AttributeError("shape tree XML element is unavailable")
        return element

    @property
    def title(self) -> "Shape | None":
        for shape in self._shapes:
            if _placeholder_type_xml(shape) in {"title", "ctrTitle"}:
                return shape
        return None

    @property
    def placeholders(self) -> "PlaceholderCollection":
        return self._slide.placeholders

    @property
    def turbo_add_enabled(self) -> bool:
        return self._turbo_add_enabled

    @turbo_add_enabled.setter
    def turbo_add_enabled(self, value: Any) -> None:
        self._turbo_add_enabled = bool(value)

    def ph_basename(self, ph_type: Any) -> str:
        return _placeholder_basename(ph_type)

    def clone_layout_placeholders(self, slide_layout: Any) -> None:
        slide_part = str(self._slide._payload.get("part") or "")
        queue_layout_placeholders = (
            getattr(slide_layout, "_presentation", None) is self._slide._presentation
            and isinstance(getattr(slide_layout, "index", None), int)
            and hasattr(slide_layout, "_cloneable_placeholder_payloads")
        )
        queue_part_placeholders = (
            queue_layout_placeholders
            and bool(slide_part)
            and hasattr(slide_layout, "partname")
        )
        if hasattr(slide_layout, "_cloneable_placeholder_payloads"):
            specs = [
                self._append_placeholder_clone_payload(payload)
                for payload in slide_layout._cloneable_placeholder_payloads()
            ]
        else:
            specs = [
                self._append_placeholder_clone(placeholder)
                for placeholder in _cloneable_layout_placeholders(slide_layout)
            ]
        if specs:
            if queue_part_placeholders:
                for spec in specs:
                    self._slide._presentation._queue_part_placeholder_add(
                        slide_part,
                        spec,
                    )
            elif queue_layout_placeholders:
                self._slide._presentation._queue_layout_placeholders_add(
                    self._slide._index,
                    slide_layout.index,
                )
            else:
                self._slide._presentation._queue_placeholder_shapes_add(
                    self._slide._index,
                    [_placeholder_queue_spec(spec) for spec in specs],
                )

    def clone_placeholder(self, placeholder: Any) -> None:
        spec = self._append_placeholder_clone(placeholder)
        self._slide._presentation._queue_placeholder_shape_add(
            self._slide._index,
            len(self._shapes) - 1,
            spec["placeholder_type"],
            spec["placeholder_orient"],
            spec["placeholder_size"],
            spec["placeholder_idx"],
        )

    def _append_placeholder_clone(
        self,
        placeholder: Any,
    ) -> dict[str, str | bool | None]:
        return self._append_placeholder_clone_payload(
            {
                "placeholder_type": _placeholder_type_xml(placeholder),
                "placeholder_orient": _placeholder_raw_value(
                    placeholder,
                    "placeholder_orient",
                ),
                "placeholder_size": _placeholder_raw_value(
                    placeholder,
                    "placeholder_size",
                ),
                "placeholder_idx": _placeholder_raw_value(
                    placeholder,
                    "placeholder_idx",
                ),
            }
        )

    def _append_placeholder_clone_payload(
        self,
        placeholder_payload: dict[str, Any],
    ) -> dict[str, str | bool | None]:
        placeholder_type = _payload_string(placeholder_payload, "placeholder_type")
        placeholder_orient = _payload_string(placeholder_payload, "placeholder_orient")
        placeholder_size = _payload_string(placeholder_payload, "placeholder_size")
        placeholder_idx = _payload_string(placeholder_payload, "placeholder_idx")
        shape_id = _next_shape_id(self._shapes)
        name = _next_placeholder_name(
            self._shapes,
            shape_id,
            placeholder_type,
            placeholder_orient,
        )
        shape_index = len(self._shapes)
        payload = {
            "id": str(shape_id),
            "name": name,
            "kind": "shape",
            "text": "",
            "paragraphs": [""],
            "paragraph_runs": [[]],
            "is_placeholder": True,
            "placeholder_type": placeholder_type,
            "placeholder_idx": placeholder_idx,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
        }
        shape = Shape(self._slide, shape_index, payload)
        self._shapes.append(shape)
        placeholders = getattr(self._slide, "_placeholders", None)
        if placeholders is None:
            placeholders = PlaceholderCollection(self._slide, self._shapes[:-1])
            self._slide._placeholders = placeholders
        placeholders._placeholders.append(shape)
        return {
            "id": str(shape_id),
            "name": name,
            "placeholder_type": placeholder_type,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
            "placeholder_idx": placeholder_idx,
            "has_text_body": True,
        }

    def add_picture(
        self,
        image_file: Any,
        left: int,
        top: int,
        width: int | None = None,
        height: int | None = None,
    ) -> "Shape":
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        image_source = _image_source_for_queue(image_file)
        cx_emu, cy_emu = _picture_dimensions(image_source, width, height)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_picture_add(
            self._slide._index,
            image_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Picture {shape_id - 1}",
                "kind": "picture",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "has_picture": True,
                "_image_file": image_source,
            },
        )
        self._shapes.append(shape)
        return shape

    def add_movie(
        self,
        movie_file: Any,
        left: int,
        top: int,
        width: int,
        height: int,
        poster_frame_image: Any = None,
        mime_type: str = "video/unknown",
    ) -> "Shape":
        mime_type_value = str(mime_type)
        movie_source = _movie_source_for_queue(movie_file, mime_type_value)
        poster_source = (
            None
            if poster_frame_image is None
            else _image_source_for_queue(poster_frame_image)
        )
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_movie_add(
            self._slide._index,
            movie_source,
            poster_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type_value,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": _source_display_filename(movie_source),
                "kind": "movie",
                "text": "",
                "paragraphs": [],
                "_poster_frame_file": poster_source,
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_ole_object(
        self,
        object_file: Any,
        prog_id: Any,
        left: int,
        top: int,
        width: int | None = None,
        height: int | None = None,
        icon_file: Any = None,
        icon_width: int | None = None,
        icon_height: int | None = None,
    ) -> "Shape":
        object_source = _binary_source_for_queue(object_file, "object.bin")
        icon_source = None if icon_file is None else _image_source_for_queue(icon_file)
        prog_id_value = str(getattr(prog_id, "progId", prog_id))
        default_width = int(getattr(prog_id, "width", 965200))
        default_height = int(getattr(prog_id, "height", 609600))
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = default_width if width is None else _coerce_emu(width, "width")
        cy_emu = default_height if height is None else _coerce_emu(height, "height")
        icon_cx_emu = 965200 if icon_width is None else _coerce_emu(icon_width, "icon_width")
        icon_cy_emu = (
            609600 if icon_height is None else _coerce_emu(icon_height, "icon_height")
        )
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_ole_object_add(
            self._slide._index,
            object_source,
            prog_id_value,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_source,
            icon_cx_emu,
            icon_cy_emu,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Object {len(self._shapes) + 1}",
                "kind": "ole_object",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_table(
        self,
        rows: int,
        cols: int,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> "Shape":
        row_count = _coerce_positive_int(rows, "rows")
        col_count = _coerce_positive_int(cols, "cols")
        table_index = _shape_collection_table_count(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_table_add(
            self._slide._index,
            table_index,
            row_count,
            col_count,
            _coerce_emu(left, "left"),
            _coerce_emu(top, "top"),
            _coerce_emu(width, "width"),
            _coerce_emu(height, "height"),
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "graphic_frame",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": _coerce_emu(left, "left"),
                    "y": _coerce_emu(top, "top"),
                    "cx": _coerce_emu(width, "width"),
                    "cy": _coerce_emu(height, "height"),
                },
                "tables": [
                    {
                        "rows": [["" for _ in range(col_count)] for _ in range(row_count)],
                        "row_count": row_count,
                        "col_count": col_count,
                    }
                ],
            },
            table_index,
        )
        self._shapes.append(shape)
        return shape

    def add_chart(
        self,
        chart_type: Any,
        x: int,
        y: int,
        cx: int,
        cy: int,
        chart_data: Any,
    ) -> "Shape":
        x_emu = _coerce_emu(x, "x")
        y_emu = _coerce_emu(y, "y")
        cx_emu = _coerce_emu(cx, "cx")
        cy_emu = _coerce_emu(cy, "cy")
        normalized = _normalize_chart_add_data(chart_data)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_chart_add(
            self._slide._index,
            chart_type,
            normalized,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        chart_payload = {
            "chart_type": _chart_type_payload_from_value(chart_type),
            "series": [
                {
                    "name": series["name"],
                    "categories": list(series["categories"]),
                    "x_values": list(series.get("x_values") or []),
                    "bubble_sizes": list(series.get("bubble_sizes") or []),
                    "values": list(series["values"]),
                }
                for series in normalized["series"]
            ],
            "part": "",
            "has_title": False,
            "title_text": "",
            "has_legend": False,
            "legend_position": "r",
            "legend_include_in_layout": True,
            "axes": {},
        }
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Chart {len(self._shapes) + 1}",
                "kind": "graphic_frame",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "has_chart": True,
                "_chart_payload": chart_payload,
            },
        )
        self._shapes.append(shape)
        return shape

    def add_textbox(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> "Shape":
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_text_box_add(
            self._slide._index,
            len(self._shapes),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "shape",
                "is_text_box": True,
                "text": "",
                "paragraphs": [""],
                "paragraph_runs": [[]],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_group_shape(self, shapes: Sequence["Shape"] = ()) -> "Shape":
        grouped_shapes = tuple(shapes)
        if not grouped_shapes:
            shape_id = _next_shape_id(self._shapes)
            self._slide._presentation._queue_group_shape_add(self._slide._index)
            shape = Shape(
                self._slide,
                len(self._shapes),
                {
                    **_pending_shape_identity(shape_id),
                    "name": f"Group {len(self._shapes) + 1}",
                    "kind": "group",
                    "text": "",
                    "paragraphs": [],
                    "paragraph_runs": [],
                    "transform": {
                        "x": 0,
                        "y": 0,
                        "cx": 0,
                        "cy": 0,
                    },
                    "children": [],
                    "has_group": True,
                },
            )
            self._shapes.append(shape)
            return shape

        shape_indices = self._grouped_shape_indices(grouped_shapes)
        shape_id = _next_shape_id(self._shapes)
        left, top, width, height = self._grouped_shape_bounds(grouped_shapes)
        self._slide._presentation._queue_existing_shape_group_add(
            self._slide._index,
            shape_indices,
        )
        shape = Shape(
            self._slide,
            len(self._shapes) - len(shape_indices),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Group {shape_id - 1}",
                "kind": "group",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "transform": {
                    "x": left,
                    "y": top,
                    "cx": width,
                    "cy": height,
                },
                "children": [deepcopy(child._payload) for child in grouped_shapes],
                "has_group": True,
            },
        )
        selected = set(shape_indices)
        remaining = [
            candidate
            for index, candidate in enumerate(self._shapes)
            if index not in selected
        ]
        self._shapes = [*remaining, shape]
        for index, candidate in enumerate(self._shapes):
            candidate._index = index
        return shape

    def _grouped_shape_indices(self, shapes: tuple["Shape", ...]) -> tuple[int, ...]:
        indices: list[int] = []
        for shape in shapes:
            if shape not in self._shapes:
                raise ValueError("shape is not in this shape collection")
            indices.append(self._shapes.index(shape))
        if len(set(indices)) != len(indices):
            raise ValueError("cannot group the same shape more than once")
        return tuple(indices)

    def _grouped_shape_bounds(
        self,
        shapes: tuple["Shape", ...],
    ) -> tuple[int, int, int, int]:
        boxes = [
            (
                _shape_transform_value(shape, "x"),
                _shape_transform_value(shape, "y"),
                _shape_transform_value(shape, "cx"),
                _shape_transform_value(shape, "cy"),
            )
            for shape in shapes
        ]
        left = min(x for x, _y, _cx, _cy in boxes)
        top = min(y for _x, y, _cx, _cy in boxes)
        right = max(x + cx for x, _y, cx, _cy in boxes)
        bottom = max(y + cy for _x, y, _cx, cy in boxes)
        return left, top, right - left, bottom - top

    def build_freeform(
        self,
        start_x: float = 0,
        start_y: float = 0,
        scale: tuple[float, float] | float = 1.0,
    ) -> FreeformBuilder:
        x_scale, y_scale = scale if isinstance(scale, tuple) else (scale, scale)
        return FreeformBuilder(self, Shape, start_x, start_y, x_scale, y_scale)

    def add_shape(
        self,
        auto_shape_type: Any,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> "Shape":
        preset_geometry = _auto_shape_preset_geometry(auto_shape_type)
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_index = len(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_auto_shape_add(
            self._slide._index,
            shape_index,
            shape_id,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        shape = Shape(
            self._slide,
            shape_index,
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "shape",
                "text": "",
                "paragraphs": [""],
                "paragraph_runs": [[]],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "preset_geometry": preset_geometry,
            },
        )
        self._shapes.append(shape)
        return shape

    def add_connector(
        self,
        connector_type: Any,
        begin_x: int,
        begin_y: int,
        end_x: int,
        end_y: int,
    ) -> "Shape":
        preset_geometry = _connector_preset_geometry(connector_type)
        begin_x_emu = _coerce_emu(begin_x, "begin_x")
        begin_y_emu = _coerce_emu(begin_y, "begin_y")
        end_x_emu = _coerce_emu(end_x, "end_x")
        end_y_emu = _coerce_emu(end_y, "end_y")
        x_emu = min(begin_x_emu, end_x_emu)
        y_emu = min(begin_y_emu, end_y_emu)
        cx_emu = abs(end_x_emu - begin_x_emu)
        cy_emu = abs(end_y_emu - begin_y_emu)
        shape_index = len(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_connector_add(
            self._slide._index,
            shape_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        shape = Shape(
            self._slide,
            shape_index,
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "connector",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "begin_x": begin_x_emu,
                "begin_y": begin_y_emu,
                "end_x": end_x_emu,
                "end_y": end_y_emu,
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "preset_geometry": preset_geometry,
            },
        )
        self._shapes.append(shape)
        return shape
