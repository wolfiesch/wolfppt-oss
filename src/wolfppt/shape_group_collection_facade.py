"""Group-shape child collection facade."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from copy import deepcopy
from typing import Any

from .chart_adds import _normalize_chart_add_data
from .chart_xml import chart_type_payload_from_value as _chart_type_payload_from_value
from .facade_values import coerce_emu as _coerce_emu
from .package_parts import PackagePart, XmlElementProxy
from .shape_core_facade import Shape
from .shape_edit_refs import queued_shape_add_weight as _queued_shape_add_weight
from .shape_group_media_adds import (
    add_group_ole_object as _add_group_ole_object,
    add_group_picture as _add_group_picture,
)
from .shape_group_payloads import (
    _group_child_payload,
    _pending_group_child_payload,
)
from .shape_inspection import _connector_preset_geometry
from .shape_payloads import _shape_transform_value


class GroupShapeCollection(Sequence["Shape"]):
    def __init__(self, group_shape: Shape) -> None:
        self._group_shape = group_shape
        self._turbo_add_enabled = False
        group_index = self._group_payload_ordinal()
        nested_group_child_index = self._nested_group_child_index_for_children()
        deeper_group_child_index = self._deeper_group_child_index_for_children()
        group_shape_id = getattr(group_shape, "shape_id", None)
        self._shapes = [
            Shape(
                group_shape._slide,
                index,
                _group_child_payload(
                    child,
                    group_shape._index,
                    group_index,
                    index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    group_shape_id=group_shape_id,
                ),
            )
            for index, child in enumerate(group_shape._payload.get("children") or [])
            if isinstance(child, dict)
        ]

    def __getitem__(self, index: int | slice) -> "Shape | list[Shape]":
        return self._shapes[index]

    def __iter__(self) -> Iterator["Shape"]:
        return iter(self._shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    def index(self, shape: Shape) -> int:
        for index, candidate in enumerate(self._shapes):
            if candidate is shape:
                return index
        shape_id = getattr(shape, "shape_id", None)
        for index, candidate in enumerate(self._shapes):
            if candidate.shape_id == shape_id:
                return index
        raise ValueError(f"{shape.element!r} is not in list")

    def remove(self, shape: Shape) -> None:
        if getattr(shape, "_slide", None) is not self._group_shape._slide:
            raise ValueError(f"{shape!r} is not in this group shape collection")
        if shape._payload.get("_deleted"):
            raise ValueError(f"{shape!r} is not in this group shape collection")
        if self._group_shape._payload.get("_deleted"):
            raise ValueError(f"cannot remove shape from deleted group")
        if not self._group_shape._slide.partname or shape._payload.get("_pending_shape"):
            raise NotImplementedError("deleting an unsaved shape is not supported yet")
        position = next(
            (index for index, candidate in enumerate(self._shapes) if candidate is shape),
            None,
        )
        if position is None:
            target_id = getattr(shape, "shape_id", None)
            if target_id is not None:
                position = next(
                    (
                        index
                        for index, candidate in enumerate(self._shapes)
                        if getattr(candidate, "shape_id", None) == target_id
                    ),
                    None,
                )
        if position is None:
            raise ValueError(f"{shape!r} is not in this group shape collection")

        target_shape = self._shapes[position]
        slide_index = self._group_shape._slide._index
        group_shape_id = self._group_shape.shape_id
        child_shape_id = target_shape.shape_id

        self._group_shape._slide._presentation._queue_group_shape_child_delete(
            slide_index,
            group_shape_id,
            child_shape_id,
        )
        self._shapes.pop(position)
        children = self._group_shape._payload.get("children")
        if isinstance(children, list) and position < len(children):
            children.pop(position)
        def _mark_deleted_recursive(s: Any) -> None:
            if hasattr(s, "_payload") and isinstance(s._payload, dict):
                s._payload["_deleted"] = True
            shapes_col = getattr(s, "shapes", None)
            if shapes_col is not None:
                for ch in getattr(shapes_col, "_shapes", []):
                    _mark_deleted_recursive(ch)

        _mark_deleted_recursive(target_shape)
        _mark_deleted_recursive(shape)

        for idx, s in enumerate(self._shapes):
            s._index = idx
            s._payload["_group_child_index"] = idx

    @property
    def element(self) -> XmlElementProxy:
        return self._group_shape.element

    @property
    def parent(self) -> Shape:
        return self._group_shape

    @property
    def part(self) -> PackagePart:
        return self._group_shape.part

    @property
    def turbo_add_enabled(self) -> bool:
        return self._turbo_add_enabled

    @turbo_add_enabled.setter
    def turbo_add_enabled(self, value: Any) -> None:
        self._turbo_add_enabled = bool(value)

    def ph_basename(self, ph_type: Any) -> str:
        from .shape_inspection import _placeholder_basename

        return _placeholder_basename(ph_type)

    def _is_nested_group_target(self) -> bool:
        if (
            self._group_shape._payload.get("_group_child")
            and self._group_shape._payload.get("kind") == "group"
        ):
            return True
        return False

    def _is_deeper_nested_group_target(self) -> bool:
        return bool(self._group_shape._payload.get("_deep_nested_group_target"))

    def _next_group_name(self) -> str:
        return self._next_pending_shape_name("Group")

    def _next_pending_shape_id(self) -> int:
        max_shape_id = self._group_shape._payload.get("_max_shape_id")
        if max_shape_id is not None and "shapes" not in self._group_shape._slide._payload:
            try:
                shape_ids = [int(max_shape_id)]
            except (TypeError, ValueError):
                shape_ids = [1]
        else:
            shape_ids = [1]

            def visit_payload(payload: dict[str, Any]) -> None:
                if payload.get("_pending_shape") or payload.get("_pending_group_child"):
                    return
                shape_id = payload.get("id")
                try:
                    shape_ids.append(int(shape_id))
                except (TypeError, ValueError):
                    pass
                for child in payload.get("children") or ():
                    if isinstance(child, dict):
                        visit_payload(child)

            for shape in self._group_shape._slide.shapes:
                visit_payload(shape._payload)
        queued_shape_adds = sum(
            _queued_shape_add_weight(add_kind)
            for add_kind, args in self._group_shape._slide._presentation._shape_adds
            if args and args[0] == self._group_shape._slide._index
        )
        return max(shape_ids) + queued_shape_adds

    def _pending_group_child_identity(self) -> dict[str, Any]:
        return {"id": str(self._next_pending_shape_id()), "_pending_shape": True}

    def _append_pending_shape(self, shape: "Shape") -> None:
        self._shapes.append(shape)
        children = self._group_shape._payload.setdefault("children", [])
        if isinstance(children, list):
            children.append(shape._payload)

    def _next_pending_shape_name(self, prefix: str) -> str:
        return f"{prefix} {self._next_pending_shape_id() - 1}"

    def add_chart(
        self,
        chart_type: Any,
        x: int,
        y: int,
        cx: int,
        cy: int,
        chart_data: Any,
    ) -> Shape:
        x_emu = _coerce_emu(x, "x")
        y_emu = _coerce_emu(y, "y")
        cx_emu = _coerce_emu(cx, "cx")
        cy_emu = _coerce_emu(cy, "cy")
        normalized = _normalize_chart_add_data(chart_data)
        child_index = len(self._shapes)
        group_index = self._group_ordinal()
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if self._is_deeper_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_nested_group_child_index"]
            )
            deeper_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_deeper_nested_group_chart_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
                chart_type,
                normalized,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        elif self._is_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_nested_group_chart_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                child_index,
                chart_type,
                normalized,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        else:
            self._group_shape._slide._presentation._queue_group_chart_add(
                self._group_shape._slide._index,
                group_index,
                child_index,
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
        group_payload = _pending_group_child_payload(
            "chart",
            self._group_shape._index,
            group_index,
            child_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
        shape = Shape(
            self._group_shape._slide,
            child_index,
            {
                **self._pending_group_child_identity(),
                "name": self._next_pending_shape_name("Chart"),
                "kind": "graphic_frame",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "has_chart": True,
                "_chart_payload": chart_payload,
                **group_payload,
            },
        )
        self._append_pending_shape(shape)
        return shape

    def add_connector(
        self,
        connector_type: Any,
        begin_x: int,
        begin_y: int,
        end_x: int,
        end_y: int,
    ) -> Shape:
        preset_geometry = _connector_preset_geometry(connector_type)
        begin_x_emu = _coerce_emu(begin_x, "begin_x")
        begin_y_emu = _coerce_emu(begin_y, "begin_y")
        end_x_emu = _coerce_emu(end_x, "end_x")
        end_y_emu = _coerce_emu(end_y, "end_y")
        x_emu = min(begin_x_emu, end_x_emu)
        y_emu = min(begin_y_emu, end_y_emu)
        cx_emu = abs(end_x_emu - begin_x_emu)
        cy_emu = abs(end_y_emu - begin_y_emu)
        child_index = len(self._shapes)
        group_index = self._group_ordinal()
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if self._is_deeper_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_nested_group_child_index"]
            )
            deeper_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_deeper_nested_group_connector_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
                preset_geometry,
                begin_x_emu,
                begin_y_emu,
                end_x_emu,
                end_y_emu,
            )
        elif self._is_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_nested_group_connector_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                child_index,
                preset_geometry,
                begin_x_emu,
                begin_y_emu,
                end_x_emu,
                end_y_emu,
            )
        else:
            self._group_shape._slide._presentation._queue_group_connector_add(
                self._group_shape._slide._index,
                group_index,
                int(self._group_shape._index),
                child_index,
                preset_geometry,
                begin_x_emu,
                begin_y_emu,
                end_x_emu,
                end_y_emu,
            )
        group_payload = _pending_group_child_payload(
            "connector",
            self._group_shape._index,
            group_index,
            child_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
        shape = Shape(
            self._group_shape._slide,
            child_index,
            {
                **self._pending_group_child_identity(),
                "name": "",
                "kind": "connector",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "begin_x": begin_x_emu,
                "begin_y": begin_y_emu,
                "end_x": end_x_emu,
                "end_y": end_y_emu,
                "flip_h": begin_x_emu > end_x_emu,
                "flip_v": begin_y_emu > end_y_emu,
                "preset_geometry": preset_geometry,
                **group_payload,
            },
        )
        self._append_pending_shape(shape)
        return shape

    def add_group_shape(self, shapes: Sequence[Shape] = ()) -> Shape:
        grouped_shapes = tuple(shapes)
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if self._is_deeper_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_nested_group_child_index"]
            )
            deeper_group_child_index = int(
                self._group_shape._payload.get(
                    "_deeper_group_child_index",
                    self._group_shape._payload["_group_child_index"],
                )
            )
        elif self._is_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
        else:
            group_index = self._group_ordinal()
        if not grouped_shapes:
            child_index = len(self._shapes)
            if deeper_group_child_index is not None:
                self._group_shape._slide._presentation._queue_group_shape_to_deeper_nested_group_add(
                    self._group_shape._slide._index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                )
            elif nested_group_child_index is not None:
                self._group_shape._slide._presentation._queue_group_shape_to_nested_group_add(
                    self._group_shape._slide._index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                )
            else:
                self._group_shape._slide._presentation._queue_nested_group_shape_add(
                    self._group_shape._slide._index,
                    group_index,
                    child_index,
                )
            group_payload = _pending_group_child_payload(
                "group",
                self._group_shape._index,
                group_index,
                child_index,
                nested_group_child_index,
                deeper_group_child_index,
                mark_deep_nested_target=True,
            )
            shape = Shape(
                self._group_shape._slide,
                child_index,
                {
                    **self._pending_group_child_identity(),
                    "name": self._next_group_name(),
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
                    "_max_shape_id": self._group_shape._payload.get("_max_shape_id"),
                    "children": [],
                    **group_payload,
                },
            )
            self._append_pending_shape(shape)
            return shape

        child_indices = self._grouped_child_indices(grouped_shapes)
        left, top, width, height = self._grouped_child_bounds(grouped_shapes)
        if deeper_group_child_index is not None:
            self._group_shape._slide._presentation._queue_existing_deeper_nested_group_child_group_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_indices,
            )
        elif nested_group_child_index is not None:
            self._group_shape._slide._presentation._queue_existing_nested_group_child_group_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                child_indices,
            )
        else:
            self._group_shape._slide._presentation._queue_existing_group_child_group_add(
                self._group_shape._slide._index,
                group_index,
                child_indices,
            )
        shape_id = self._next_pending_shape_id()
        new_child_index = len(self._shapes) - len(child_indices)
        group_payload = _pending_group_child_payload(
            "group",
            self._group_shape._index,
            group_index,
            new_child_index,
            nested_group_child_index,
            deeper_group_child_index,
            mark_deep_nested_target=True,
        )
        shape = Shape(
            self._group_shape._slide,
            new_child_index,
            {
                "id": str(shape_id),
                "_pending_shape": True,
                "kind": "group",
                "name": f"Group {shape_id - 1}",
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
                **group_payload,
            },
        )
        selected = set(child_indices)
        remaining = [
            candidate
            for index, candidate in enumerate(self._shapes)
            if index not in selected
        ]
        self._shapes = [*remaining, shape]
        for index, candidate in enumerate(self._shapes):
            candidate._index = index
            candidate._payload["_group_child_index"] = index
        self._group_shape._payload["children"] = [
            deepcopy(candidate._payload) for candidate in self._shapes
        ]
        return shape

    def _grouped_child_indices(self, shapes: tuple[Shape, ...]) -> tuple[int, ...]:
        indices: list[int] = []
        for shape in shapes:
            indices.append(self.index(shape))
        if len(set(indices)) != len(indices):
            raise ValueError("cannot group the same shape more than once")
        return tuple(indices)

    def _grouped_child_bounds(
        self,
        shapes: tuple[Shape, ...],
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
    ) -> Shape:
        return _add_group_ole_object(
            self,
            object_file,
            prog_id,
            left,
            top,
            width,
            height,
            icon_file,
            icon_width,
            icon_height,
        )

    def add_picture(
        self,
        image_file: Any,
        left: int,
        top: int,
        width: int | None = None,
        height: int | None = None,
    ) -> Shape:
        return _add_group_picture(self, image_file, left, top, width, height)

    def add_shape(
        self,
        auto_shape_type: Any,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Shape:
        from .facade_values import coerce_emu
        from .shape_inspection import _auto_shape_preset_geometry

        preset_geometry = _auto_shape_preset_geometry(auto_shape_type)
        x_emu = coerce_emu(left, "left")
        y_emu = coerce_emu(top, "top")
        cx_emu = coerce_emu(width, "width")
        cy_emu = coerce_emu(height, "height")
        child_index = len(self._shapes)
        group_index = self._group_ordinal()
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if self._is_deeper_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_nested_group_child_index"]
            )
            deeper_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_deeper_nested_group_auto_shape_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
            identity = self._pending_group_child_identity()
        elif self._is_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_nested_group_auto_shape_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                child_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
            identity = self._pending_group_child_identity()
        else:
            shape_id = self._next_pending_shape_id() + 1
            self._group_shape._slide._presentation._queue_group_auto_shape_add(
                self._group_shape._slide._index,
                group_index,
                child_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                shape_id,
            )
            identity = {"id": str(shape_id), "_pending_shape": True}
        group_payload = _pending_group_child_payload(
            "auto_shape",
            self._group_shape._index,
            group_index,
            child_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
        shape = Shape(
            self._group_shape._slide,
            child_index,
            {
                **identity,
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
                **group_payload,
            },
        )
        self._append_pending_shape(shape)
        return shape

    def add_textbox(self, left: int, top: int, width: int, height: int) -> Shape:
        from .facade_values import coerce_emu

        x_emu = coerce_emu(left, "left")
        y_emu = coerce_emu(top, "top")
        cx_emu = coerce_emu(width, "width")
        cy_emu = coerce_emu(height, "height")
        child_index = len(self._shapes)
        group_index = self._group_ordinal()
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if self._is_deeper_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_nested_group_child_index"]
            )
            deeper_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_deeper_nested_group_text_box_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        elif self._is_nested_group_target():
            group_index = int(self._group_shape._payload["_group_index"])
            nested_group_child_index = int(
                self._group_shape._payload["_group_child_index"]
            )
            self._group_shape._slide._presentation._queue_nested_group_text_box_add(
                self._group_shape._slide._index,
                group_index,
                nested_group_child_index,
                child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        else:
            self._group_shape._slide._presentation._queue_group_text_box_add(
                self._group_shape._slide._index,
                group_index,
                child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        group_payload = _pending_group_child_payload(
            "text_box",
            self._group_shape._index,
            group_index,
            child_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
        shape = Shape(
            self._group_shape._slide,
            child_index,
            {
                **self._pending_group_child_identity(),
                "name": f"TextBox {child_index + 1}",
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
                **group_payload,
            },
        )
        self._append_pending_shape(shape)
        return shape

    def _group_ordinal(self) -> int:
        group_index = self._group_shape._payload.get("_group_index")
        if group_index is not None and "shapes" not in self._group_shape._slide._payload:
            try:
                return int(group_index)
            except (TypeError, ValueError):
                pass
        ordinal = 0
        for shape in self._group_shape._slide.shapes:
            if shape is self._group_shape:
                return ordinal
            if shape._payload.get("kind") == "group":
                ordinal += 1
        return ordinal

    def _group_payload_ordinal(self) -> int:
        if self._group_shape._payload.get("_group_child"):
            return int(self._group_shape._payload["_group_index"])
        return self._group_ordinal()

    def _nested_group_child_index_for_children(self) -> int | None:
        if self._group_shape._payload.get("_deep_nested_group_target"):
            return int(self._group_shape._payload["_nested_group_child_index"])
        if (
            self._group_shape._payload.get("_group_child")
            and self._group_shape._payload.get("kind") == "group"
        ):
            return int(self._group_shape._payload["_group_child_index"])
        return None

    def _deeper_group_child_index_for_children(self) -> int | None:
        if not self._group_shape._payload.get("_deep_nested_group_target"):
            return None
        return int(
            self._group_shape._payload.get(
                "_deeper_group_child_index",
                self._group_shape._payload["_group_child_index"],
            )
        )

    def build_freeform(
        self,
        start_x: float = 0,
        start_y: float = 0,
        scale: tuple[float, float] | float = 1.0,
    ) -> Any:
        from .shape_freeform import FreeformBuilder

        x_scale, y_scale = scale if isinstance(scale, tuple) else (scale, scale)
        return FreeformBuilder(self, Shape, start_x, start_y, x_scale, y_scale)

    def clone_placeholder(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("adding shapes inside a group is not supported yet")
