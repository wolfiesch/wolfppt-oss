"""Group-shape drop-in benchmark operation implementations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from .benchmark_dropin_actions import (
    _apply_python_pptx_dropin_add_deeper_nested_group_auto_shape,
    _apply_python_pptx_dropin_add_deeper_nested_group_chart,
    _apply_python_pptx_dropin_add_deeper_nested_group_shape,
    _apply_python_pptx_dropin_add_deeper_nested_group_textbox,
    _apply_python_pptx_dropin_add_group_auto_shape,
    _apply_python_pptx_dropin_add_group_chart,
    _apply_python_pptx_dropin_add_group_shape,
    _apply_python_pptx_dropin_add_group_textbox,
    _apply_python_pptx_dropin_add_nested_group_auto_shape,
    _apply_python_pptx_dropin_add_nested_group_chart,
    _apply_python_pptx_dropin_add_nested_group_shape,
    _apply_python_pptx_dropin_add_nested_group_textbox,
    _apply_python_pptx_dropin_group_existing_children,
    _apply_python_pptx_dropin_group_existing_shapes,
    _apply_wolfppt_dropin_add_deeper_nested_group_auto_shape,
    _apply_wolfppt_dropin_add_deeper_nested_group_chart,
    _apply_wolfppt_dropin_add_deeper_nested_group_shape,
    _apply_wolfppt_dropin_add_deeper_nested_group_textbox,
    _apply_wolfppt_dropin_add_group_auto_shape,
    _apply_wolfppt_dropin_add_group_chart,
    _apply_wolfppt_dropin_add_group_shape,
    _apply_wolfppt_dropin_add_group_textbox,
    _apply_wolfppt_dropin_add_nested_group_auto_shape,
    _apply_wolfppt_dropin_add_nested_group_chart,
    _apply_wolfppt_dropin_add_nested_group_shape,
    _apply_wolfppt_dropin_add_nested_group_textbox,
    _apply_wolfppt_dropin_group_existing_children,
    _apply_wolfppt_dropin_group_existing_shapes,
)
from .benchmark_dropin_shape_details import (
    _dropin_add_deeper_nested_group_auto_shape_details,
    _dropin_add_deeper_nested_group_chart_details,
    _dropin_add_deeper_nested_group_shape_details,
    _dropin_add_deeper_nested_group_textbox_details,
    _dropin_add_group_auto_shape_details,
    _dropin_add_group_chart_details,
    _dropin_add_group_shape_details,
    _dropin_add_group_textbox_details,
    _dropin_add_nested_group_auto_shape_details,
    _dropin_add_nested_group_chart_details,
    _dropin_add_nested_group_shape_details,
    _dropin_add_nested_group_textbox_details,
    _dropin_group_existing_children_details,
    _dropin_group_existing_shapes_details,
)
from .benchmark_runtime import elapsed_ms as _elapsed_ms, stamp as _stamp
from .chart_axis_ids import (
    normalize_chart_axis_ids_in_package as _normalize_chart_axis_ids,
)
from .presentation import Presentation as WolfPresentation

_PresentationAction = Callable[[str, Any], None]
_DetailsBuilder = Callable[[str, Path, Path, bool], dict[str, Any]]


def _bench_python_pptx_group_shape_operation(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
    *,
    operation_slug: str,
    action: _PresentationAction,
    details: _DetailsBuilder,
    normalize_chart_axes: bool = False,
) -> tuple[float, dict[str, Any]]:
    from pptx import Presentation as PythonPptxPresentation

    out = tmp_path / (
        f"python-pptx-dropin-{operation_slug}-{fixture_path.stem}-{_stamp()}{fixture_path.suffix}"
    )
    start = perf_counter()
    prs = PythonPptxPresentation(str(fixture_path))
    action(fixture_id, prs)
    prs.save(str(out))
    elapsed_ms = _elapsed_ms(start)
    if normalize_chart_axes:
        _normalize_chart_axis_ids(out)
    return elapsed_ms, details(fixture_id, fixture_path, out, validate_openxml)


def _bench_wolfppt_group_shape_operation(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
    *,
    operation_slug: str,
    action: _PresentationAction,
    details: _DetailsBuilder,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / (
        f"wolfppt-dropin-{operation_slug}-{fixture_path.stem}-{_stamp()}{fixture_path.suffix}"
    )
    start = perf_counter()
    prs = WolfPresentation(fixture_path)
    action(fixture_id, prs)
    prs.save(out)
    elapsed_ms = _elapsed_ms(start)
    return elapsed_ms, details(fixture_id, fixture_path, out, validate_openxml)


def _bench_python_pptx_dropin_add_group_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-shape",
        action=_apply_python_pptx_dropin_add_group_shape,
        details=_dropin_add_group_shape_details,
    )


def _bench_wolfppt_facade_dropin_add_group_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-shape",
        action=_apply_wolfppt_dropin_add_group_shape,
        details=_dropin_add_group_shape_details,
    )


def _bench_python_pptx_dropin_group_existing_shapes(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="group-existing-shapes",
        action=_apply_python_pptx_dropin_group_existing_shapes,
        details=_dropin_group_existing_shapes_details,
    )


def _bench_wolfppt_facade_dropin_group_existing_shapes(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="group-existing-shapes",
        action=_apply_wolfppt_dropin_group_existing_shapes,
        details=_dropin_group_existing_shapes_details,
    )


def _bench_python_pptx_dropin_add_nested_group_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-shape",
        action=_apply_python_pptx_dropin_add_nested_group_shape,
        details=_dropin_add_nested_group_shape_details,
    )


def _bench_wolfppt_facade_dropin_add_nested_group_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-shape",
        action=_apply_wolfppt_dropin_add_nested_group_shape,
        details=_dropin_add_nested_group_shape_details,
    )


def _bench_python_pptx_dropin_add_deeper_nested_group_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-shape",
        action=_apply_python_pptx_dropin_add_deeper_nested_group_shape,
        details=_dropin_add_deeper_nested_group_shape_details,
    )


def _bench_wolfppt_facade_dropin_add_deeper_nested_group_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-shape",
        action=_apply_wolfppt_dropin_add_deeper_nested_group_shape,
        details=_dropin_add_deeper_nested_group_shape_details,
    )


def _bench_python_pptx_dropin_add_deeper_nested_group_textbox(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-textbox",
        action=_apply_python_pptx_dropin_add_deeper_nested_group_textbox,
        details=_dropin_add_deeper_nested_group_textbox_details,
    )


def _bench_wolfppt_facade_dropin_add_deeper_nested_group_textbox(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-textbox",
        action=_apply_wolfppt_dropin_add_deeper_nested_group_textbox,
        details=_dropin_add_deeper_nested_group_textbox_details,
    )


def _bench_python_pptx_dropin_add_deeper_nested_group_auto_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-auto-shape",
        action=_apply_python_pptx_dropin_add_deeper_nested_group_auto_shape,
        details=_dropin_add_deeper_nested_group_auto_shape_details,
    )


def _bench_wolfppt_facade_dropin_add_deeper_nested_group_auto_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-auto-shape",
        action=_apply_wolfppt_dropin_add_deeper_nested_group_auto_shape,
        details=_dropin_add_deeper_nested_group_auto_shape_details,
    )


def _bench_python_pptx_dropin_group_existing_children(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="group-existing-children",
        action=_apply_python_pptx_dropin_group_existing_children,
        details=_dropin_group_existing_children_details,
    )


def _bench_wolfppt_facade_dropin_group_existing_children(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="group-existing-children",
        action=_apply_wolfppt_dropin_group_existing_children,
        details=_dropin_group_existing_children_details,
    )


def _bench_python_pptx_dropin_add_nested_group_auto_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-auto-shape",
        action=_apply_python_pptx_dropin_add_nested_group_auto_shape,
        details=_dropin_add_nested_group_auto_shape_details,
    )


def _bench_wolfppt_facade_dropin_add_nested_group_auto_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-auto-shape",
        action=_apply_wolfppt_dropin_add_nested_group_auto_shape,
        details=_dropin_add_nested_group_auto_shape_details,
    )


def _bench_python_pptx_dropin_add_nested_group_textbox(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-textbox",
        action=_apply_python_pptx_dropin_add_nested_group_textbox,
        details=_dropin_add_nested_group_textbox_details,
    )


def _bench_wolfppt_facade_dropin_add_nested_group_textbox(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-textbox",
        action=_apply_wolfppt_dropin_add_nested_group_textbox,
        details=_dropin_add_nested_group_textbox_details,
    )


def _bench_python_pptx_dropin_add_group_textbox(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-textbox",
        action=_apply_python_pptx_dropin_add_group_textbox,
        details=_dropin_add_group_textbox_details,
    )


def _bench_wolfppt_facade_dropin_add_group_textbox(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-textbox",
        action=_apply_wolfppt_dropin_add_group_textbox,
        details=_dropin_add_group_textbox_details,
    )


def _bench_python_pptx_dropin_add_group_auto_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-auto-shape",
        action=_apply_python_pptx_dropin_add_group_auto_shape,
        details=_dropin_add_group_auto_shape_details,
    )


def _bench_wolfppt_facade_dropin_add_group_auto_shape(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-auto-shape",
        action=_apply_wolfppt_dropin_add_group_auto_shape,
        details=_dropin_add_group_auto_shape_details,
    )


def _bench_python_pptx_dropin_add_group_chart(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-chart",
        action=_apply_python_pptx_dropin_add_group_chart,
        details=_dropin_add_group_chart_details,
        normalize_chart_axes=True,
    )


def _bench_wolfppt_facade_dropin_add_group_chart(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-group-chart",
        action=_apply_wolfppt_dropin_add_group_chart,
        details=_dropin_add_group_chart_details,
    )


def _bench_python_pptx_dropin_add_nested_group_chart(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-chart",
        action=_apply_python_pptx_dropin_add_nested_group_chart,
        details=_dropin_add_nested_group_chart_details,
        normalize_chart_axes=True,
    )


def _bench_wolfppt_facade_dropin_add_nested_group_chart(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-nested-group-chart",
        action=_apply_wolfppt_dropin_add_nested_group_chart,
        details=_dropin_add_nested_group_chart_details,
    )


def _bench_python_pptx_dropin_add_deeper_nested_group_chart(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_python_pptx_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-chart",
        action=_apply_python_pptx_dropin_add_deeper_nested_group_chart,
        details=_dropin_add_deeper_nested_group_chart_details,
        normalize_chart_axes=True,
    )


def _bench_wolfppt_facade_dropin_add_deeper_nested_group_chart(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    return _bench_wolfppt_group_shape_operation(
        fixture_id,
        fixture_path,
        expected_path,
        tmp_path,
        validate_openxml,
        operation_slug="add-deeper-nested-group-chart",
        action=_apply_wolfppt_dropin_add_deeper_nested_group_chart,
        details=_dropin_add_deeper_nested_group_chart_details,
    )
