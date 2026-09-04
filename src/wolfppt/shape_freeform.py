"""Freeform shape builder facade."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from .facade_values import coerce_emu as _coerce_emu
from .shape_inspection import _next_shape_id


class FreeformBuilder(Sequence[dict[str, Any]]):
    def __init__(
        self,
        shapes: Any,
        shape_factory: Any,
        start_x: float = 0,
        start_y: float = 0,
        x_scale: float = 1.0,
        y_scale: float = 1.0,
    ) -> None:
        self._shapes = shapes
        self._shape_factory = shape_factory
        self._start_x = int(round(start_x))
        self._start_y = int(round(start_y))
        self._x_scale = float(x_scale)
        self._y_scale = float(y_scale)
        self._operations: list[dict[str, int | str]] = []

    def __getitem__(self, index: int | slice) -> Any:
        return self._operations[index]

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._operations)

    def __len__(self) -> int:
        return len(self._operations)

    def add_line_segments(
        self,
        vertices: Sequence[tuple[float, float]],
        close: bool = True,
    ) -> "FreeformBuilder":
        for x, y in vertices:
            self._operations.append(
                {"type": "line_to", "x": int(round(x)), "y": int(round(y))}
            )
        if close:
            self._operations.append({"type": "close"})
        return self

    def move_to(self, x: float, y: float) -> "FreeformBuilder":
        self._operations.append(
            {"type": "move_to", "x": int(round(x)), "y": int(round(y))}
        )
        return self

    @property
    def shape_offset_x(self) -> int:
        return min(x for x, _ in self._points)

    @property
    def shape_offset_y(self) -> int:
        return min(y for _, y in self._points)

    def convert_to_shape(self, origin_x: int = 0, origin_y: int = 0) -> Any:
        offset_x = self.shape_offset_x
        offset_y = self.shape_offset_y
        path_w = max(x for x, _ in self._points) - offset_x
        path_h = max(y for _, y in self._points) - offset_y
        x_emu = _coerce_emu(origin_x, "origin_x") + int(round(offset_x * self._x_scale))
        y_emu = _coerce_emu(origin_y, "origin_y") + int(round(offset_y * self._y_scale))
        cx_emu = int(round(path_w * self._x_scale))
        cy_emu = int(round(path_h * self._y_scale))
        path_operations = self._path_operations(offset_x, offset_y)
        shape_index = len(self._shapes._shapes)
        is_group_child = hasattr(self._shapes, "_group_shape")
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if is_group_child:
            slide = self._shapes._group_shape._slide
            group_index = self._shapes._group_ordinal()
            if self._shapes._is_deeper_nested_group_target():
                group_index = int(self._shapes._group_shape._payload["_group_index"])
                nested_group_child_index = int(
                    self._shapes._group_shape._payload["_nested_group_child_index"]
                )
                deeper_group_child_index = int(
                    self._shapes._group_shape._payload["_group_child_index"]
                )
                slide._presentation._queue_deeper_nested_group_freeform_shape_add(
                    slide._index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    path_operations,
                )
            elif self._shapes._is_nested_group_target():
                group_index = int(self._shapes._group_shape._payload["_group_index"])
                nested_group_child_index = int(
                    self._shapes._group_shape._payload["_group_child_index"]
                )
                slide._presentation._queue_nested_group_freeform_shape_add(
                    slide._index,
                    group_index,
                    nested_group_child_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    path_operations,
                )
            else:
                slide._presentation._queue_group_freeform_shape_add(
                    slide._index,
                    group_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    path_operations,
                )
        else:
            slide = self._shapes._slide
            shape_id = _next_shape_id(self._shapes._shapes)
            slide._presentation._queue_freeform_shape_add(
                slide._index,
                shape_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                path_operations,
            )
            group_index = None
        if is_group_child:
            shape_id = self._shapes._next_pending_shape_id()
            identity_payload = {"id": str(shape_id), "_pending_shape": True}
        else:
            identity_payload = {"id": str(shape_id), "_pending_shape": True}
        shape = self._shape_factory(
            slide,
            shape_index,
            {
                **identity_payload,
                "name": f"Freeform {shape_index + 1}",
                "kind": "freeform",
                "text": "",
                "paragraphs": [""],
                "paragraph_runs": [[]],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                **(
                    {
                        "_group_child": True,
                        "_pending_group_child": True,
                        "_pending_group_child_kind": "freeform",
                        "_group_shape_index": self._shapes._group_shape._index,
                        "_group_index": group_index,
                        "_group_child_index": shape_index,
                        **(
                            {
                                "_nested_group_child": True,
                                "_nested_group_child_index": nested_group_child_index,
                            }
                            if nested_group_child_index is not None
                            else {}
                        ),
                        **(
                            {
                                "_deep_nested_group_child": True,
                                "_deeper_group_child_index": deeper_group_child_index,
                            }
                            if deeper_group_child_index is not None
                            else {}
                        ),
                    }
                    if is_group_child
                    else {}
                ),
            },
        )
        self._shapes._shapes.append(shape)
        return shape

    @property
    def _points(self) -> list[tuple[int, int]]:
        points = [(self._start_x, self._start_y)]
        for operation in self._operations:
            if operation["type"] == "close":
                continue
            points.append((int(operation["x"]), int(operation["y"])))
        return points

    def _path_operations(
        self,
        offset_x: int,
        offset_y: int,
    ) -> list[dict[str, int | str]]:
        operations: list[dict[str, int | str]] = [
            {
                "type": "move_to",
                "x": self._start_x - offset_x,
                "y": self._start_y - offset_y,
            }
        ]
        for operation in self._operations:
            if operation["type"] == "close":
                operations.append({"type": "close"})
                continue
            operations.append(
                {
                    "type": operation["type"],
                    "x": int(operation["x"]) - offset_x,
                    "y": int(operation["y"]) - offset_y,
                }
            )
        return operations
