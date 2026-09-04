"""Queued shape-format operations for the presentation facade."""

from __future__ import annotations

from typing import Any

from .shape_edit_refs import ShapeEditRef

ShapeStyleRef = ShapeEditRef


class PresentationShapeQueueMixin:
    def _queue_shape_delete(self, slide_index: int, shape_index: int) -> None:
        self._shape_deletes.add((slide_index, shape_index))

    def _queue_group_shape_child_delete(
        self, slide_index: int, group_shape_id: int, child_shape_id: int
    ) -> None:
        self._group_child_shape_deletes.add(
            (slide_index, group_shape_id, child_shape_id)
        )

    def _queue_shape_geometry(
        self,
        slide_index: int,
        shape_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_geometry_edits[(slide_index, shape_index)] = (
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )

    def _queue_group_child_geometry(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._group_child_geometry_edits[(slide_index, group_index, child_index)] = (
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )

    def _queue_nested_group_child_geometry(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._nested_group_child_geometry_edits[
            (slide_index, group_index, nested_group_child_index, child_index)
        ] = (x_emu, y_emu, cx_emu, cy_emu)

    def _queue_deeper_group_child_geometry(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._deeper_group_child_geometry_edits[
            (
                slide_index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
            )
        ] = (x_emu, y_emu, cx_emu, cy_emu)

    def _queue_shape_fill_color(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        color: str | dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_solid_edits.discard(key)
        self._shape_fill_background_edits.discard(key)
        self._shape_fill_pattern_edits.pop(key, None)
        self._shape_fill_pattern_fore_color_edits.pop(key, None)
        self._shape_fill_pattern_back_color_edits.pop(key, None)
        self._shape_fill_gradient_edits.pop(key, None)
        self._shape_fill_color_edits[key] = color

    def _queue_shape_fill_solid(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_color_edits.pop(key, None)
        self._shape_fill_background_edits.discard(key)
        self._shape_fill_pattern_edits.pop(key, None)
        self._shape_fill_pattern_fore_color_edits.pop(key, None)
        self._shape_fill_pattern_back_color_edits.pop(key, None)
        self._shape_fill_gradient_edits.pop(key, None)
        self._shape_fill_solid_edits.add(key)

    def _queue_shape_fill_background(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_color_edits.pop(key, None)
        self._shape_fill_solid_edits.discard(key)
        self._shape_fill_pattern_edits.pop(key, None)
        self._shape_fill_pattern_fore_color_edits.pop(key, None)
        self._shape_fill_pattern_back_color_edits.pop(key, None)
        self._shape_fill_gradient_edits.pop(key, None)
        self._shape_fill_background_edits.add(key)

    def _queue_shape_fill_patterned(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        pattern: str | None,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_color_edits.pop(key, None)
        self._shape_fill_solid_edits.discard(key)
        self._shape_fill_background_edits.discard(key)
        self._shape_fill_gradient_edits.pop(key, None)
        self._shape_fill_pattern_edits[key] = pattern

    def _queue_shape_fill_pattern_fore_color(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        rgb: str,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_color_edits.pop(key, None)
        self._shape_fill_solid_edits.discard(key)
        self._shape_fill_background_edits.discard(key)
        self._shape_fill_gradient_edits.pop(key, None)
        self._shape_fill_pattern_fore_color_edits[key] = rgb

    def _queue_shape_fill_pattern_back_color(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        rgb: str,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_color_edits.pop(key, None)
        self._shape_fill_solid_edits.discard(key)
        self._shape_fill_background_edits.discard(key)
        self._shape_fill_gradient_edits.pop(key, None)
        self._shape_fill_pattern_back_color_edits[key] = rgb

    def _queue_shape_fill_gradient(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        gradient: dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_fill_color_edits.pop(key, None)
        self._shape_fill_solid_edits.discard(key)
        self._shape_fill_background_edits.discard(key)
        self._shape_fill_pattern_edits.pop(key, None)
        self._shape_fill_pattern_fore_color_edits.pop(key, None)
        self._shape_fill_pattern_back_color_edits.pop(key, None)
        self._shape_fill_gradient_edits[key] = gradient

    def _queue_shape_line_color(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        color: str | dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_line_solid_edits.discard(key)
        self._shape_line_background_edits.discard(key)
        self._shape_line_pattern_edits.pop(key, None)
        self._shape_line_pattern_fore_color_edits.pop(key, None)
        self._shape_line_pattern_back_color_edits.pop(key, None)
        self._shape_line_color_edits[key] = color

    def _queue_shape_line_solid(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_line_color_edits.pop(key, None)
        self._shape_line_background_edits.discard(key)
        self._shape_line_pattern_edits.pop(key, None)
        self._shape_line_pattern_fore_color_edits.pop(key, None)
        self._shape_line_pattern_back_color_edits.pop(key, None)
        self._shape_line_solid_edits.add(key)

    def _queue_shape_line_background(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_line_color_edits.pop(key, None)
        self._shape_line_solid_edits.discard(key)
        self._shape_line_pattern_edits.pop(key, None)
        self._shape_line_pattern_fore_color_edits.pop(key, None)
        self._shape_line_pattern_back_color_edits.pop(key, None)
        self._shape_line_background_edits.add(key)

    def _queue_shape_line_patterned(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        pattern: str | None,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_line_color_edits.pop(key, None)
        self._shape_line_solid_edits.discard(key)
        self._shape_line_background_edits.discard(key)
        self._shape_line_pattern_edits[key] = pattern

    def _queue_shape_line_pattern_fore_color(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        rgb: str,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_line_color_edits.pop(key, None)
        self._shape_line_solid_edits.discard(key)
        self._shape_line_background_edits.discard(key)
        self._shape_line_pattern_fore_color_edits[key] = rgb

    def _queue_shape_line_pattern_back_color(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        rgb: str,
    ) -> None:
        key = (slide_index, shape_index)
        self._shape_line_color_edits.pop(key, None)
        self._shape_line_solid_edits.discard(key)
        self._shape_line_background_edits.discard(key)
        self._shape_line_pattern_back_color_edits[key] = rgb

    def _queue_shape_line_width(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        width: int,
    ) -> None:
        self._shape_line_width_edits[(slide_index, shape_index)] = width

    def _queue_shape_line_dash(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        dash_style: str | None,
    ) -> None:
        self._shape_line_dash_edits[(slide_index, shape_index)] = dash_style

    def _queue_connector_connection(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        endpoint: str,
        connection: dict[str, Any],
        begin_x_emu: int,
        begin_y_emu: int,
        end_x_emu: int,
        end_y_emu: int,
        transform: dict[str, int],
        flip_h: bool,
        flip_v: bool,
    ) -> None:
        if self._queue_pending_connector_connection(
            slide_index,
            shape_index,
            endpoint,
            connection,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ):
            return
        key = (slide_index, shape_index)
        edits = self._connector_connection_edits.setdefault(key, {})
        edits[endpoint] = dict(connection)
        edits["transform"] = dict(transform)
        edits["flip_h"] = bool(flip_h)
        edits["flip_v"] = bool(flip_v)

    def _queue_shape_shadow_inherit(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        inherit: bool,
    ) -> None:
        self._shape_shadow_inherit_edits[(slide_index, shape_index)] = inherit

    def _queue_shape_hyperlink(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        address: str | None,
    ) -> None:
        self._shape_target_slide_edits.pop((slide_index, shape_index), None)
        self._shape_hyperlink_edits[(slide_index, shape_index)] = address

    def _queue_part_shape_hyperlink(
        self,
        partname: str,
        shape_index: int,
        address: str | None,
    ) -> None:
        self._part_shape_hyperlink_edits[(str(partname), shape_index)] = address

    def _queue_shape_target_slide(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        target_slide_index: int | None,
    ) -> None:
        self._shape_hyperlink_edits.pop((slide_index, shape_index), None)
        self._shape_target_slide_edits[(slide_index, shape_index)] = target_slide_index

    def _queue_text_run_hyperlink(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        address: str | None,
    ) -> None:
        self._text_run_hyperlink_edits[
            (slide_index, shape_index, paragraph_index, run_index)
        ] = address

    def _queue_shape_rotation(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        rotation: float,
    ) -> None:
        self._shape_rotation_edits[(slide_index, shape_index)] = rotation

    def _queue_shape_name(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        name: str,
    ) -> None:
        self._shape_name_edits[(slide_index, shape_index)] = name

    def _queue_shape_adjustments(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        guides: list[tuple[str, int]],
    ) -> None:
        self._shape_adjustment_edits[(slide_index, shape_index)] = list(guides)

    def _queue_shape_line_element(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
    ) -> None:
        self._shape_line_element_edits.add((slide_index, shape_index))

    def _queue_picture_crop(
        self,
        slide_index: int,
        shape_index: ShapeStyleRef,
        crop: dict[str, float],
    ) -> None:
        self._picture_crop_edits[(slide_index, shape_index)] = dict(crop)
