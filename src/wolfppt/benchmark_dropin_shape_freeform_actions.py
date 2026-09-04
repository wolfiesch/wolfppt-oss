"""Freeform shape drop-in benchmark edit actions."""

from __future__ import annotations

from typing import Any

from .benchmark_cases import (
    ADD_FREEFORM_EXPECTED_TEXT,
    ADD_FREEFORM_EXPECTED_TRANSFORM,
)
from .benchmark_dropin_common_actions import _shape_at, _shape_collection_at
from .presentation import Presentation as WolfPresentation

TOP_LEVEL_CREATION_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
GROUP_FREEFORM_TARGETS = {
    "shapes/grouped_shapes": (0, 0),
    "workloads/management_reporting_deck": (2, 1),
    "workloads/customer_success_review_pack": (4, 1),
}


def _dropin_group_shape(fixture_id: str, prs: Any, operation: str) -> Any:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            f"drop-in {operation} benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_FREEFORM_TARGETS[fixture_id]
    if isinstance(prs, WolfPresentation):
        return _shape_at(prs, slide_index, group_index)
    return prs.slides[slide_index].shapes[group_index]


def _apply_python_pptx_dropin_build_freeform(fixture_id: str, prs: Any) -> None:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in build-freeform benchmark does not support fixture {fixture_id}"
        )
    shape = (
        prs.slides[0]
        .shapes.build_freeform(0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100)
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_wolfppt_dropin_build_freeform(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in build-freeform benchmark does not support fixture {fixture_id}"
        )
    shape = (
        _shape_collection_at(prs, 0)
        .build_freeform(0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100)
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_python_pptx_dropin_build_group_freeform(fixture_id: str, prs: Any) -> None:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            f"drop-in build-group-freeform benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_FREEFORM_TARGETS[fixture_id]
    shape = (
        prs.slides[slide_index]
        .shapes[group_index]
        .shapes.build_freeform(0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100)
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_wolfppt_dropin_build_group_freeform(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    shape = (
        _dropin_group_shape(fixture_id, prs, "build-group-freeform")
        .shapes.build_freeform(0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100)
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_python_pptx_dropin_build_nested_group_freeform(
    fixture_id: str,
    prs: Any,
) -> None:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            f"drop-in build-nested-group-freeform benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_FREEFORM_TARGETS[fixture_id]
    nested_group = prs.slides[slide_index].shapes[group_index].shapes.add_group_shape()
    shape = (
        nested_group.shapes.build_freeform(
            0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100
        )
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_python_pptx_dropin_build_deeper_nested_group_freeform(
    fixture_id: str,
    prs: Any,
) -> None:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            "drop-in build-deeper-nested-group-freeform benchmark does not "
            f"support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_FREEFORM_TARGETS[fixture_id]
    deeper_group = (
        prs.slides[slide_index]
        .shapes[group_index]
        .shapes.add_group_shape()
        .shapes.add_group_shape()
    )
    shape = (
        deeper_group.shapes.build_freeform(
            0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100
        )
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_wolfppt_dropin_build_nested_group_freeform(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    nested_group = _dropin_group_shape(
        fixture_id, prs, "build-nested-group-freeform"
    ).shapes.add_group_shape()
    shape = (
        nested_group.shapes.build_freeform(
            0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100
        )
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT


def _apply_wolfppt_dropin_build_deeper_nested_group_freeform(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    deeper_group = (
        _dropin_group_shape(fixture_id, prs, "build-deeper-nested-group-freeform")
        .shapes.add_group_shape()
        .shapes.add_group_shape()
    )
    shape = (
        deeper_group.shapes.build_freeform(
            0, 0, scale=ADD_FREEFORM_EXPECTED_TRANSFORM["cx"] / 100
        )
        .add_line_segments([(100, 0), (100, 100), (0, 100)], close=True)
        .convert_to_shape(
            ADD_FREEFORM_EXPECTED_TRANSFORM["x"],
            ADD_FREEFORM_EXPECTED_TRANSFORM["y"],
        )
    )
    shape.text = ADD_FREEFORM_EXPECTED_TEXT
