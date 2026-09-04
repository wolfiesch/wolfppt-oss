"""Chart data drop-in benchmark edit actions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .benchmark_cases import (
    CHART_BUBBLE_DATA_EDIT_CASES,
    CHART_DATA_EDIT_CASES,
    CHART_EMPTY_BUBBLE_DATA_EDIT_CASES,
    CHART_EMPTY_CATEGORY_DATA_EDIT_CASES,
    CHART_EMPTY_XY_DATA_EDIT_CASES,
    CHART_HIERARCHICAL_CATEGORY_DATA_EDIT_CASES,
    CHART_SPARSE_CATEGORY_DATA_EDIT_CASES,
    CHART_XY_DATA_EDIT_CASES,
)
from .benchmark_dropin_chart_readers import _first_chart_shape
from .presentation import Presentation as WolfPresentation


def _apply_python_pptx_dropin_chart_data_edit(fixture_id: str, prs: Any) -> None:
    chart_data = _chart_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_data_edit(fixture_id: str, prs: WolfPresentation) -> None:
    chart_data = _chart_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_sparse_category_data_edit(
    fixture_id: str,
    prs: Any,
) -> None:
    chart_data = _chart_sparse_category_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_sparse_category_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_sparse_category_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_hierarchical_category_data_edit(
    fixture_id: str,
    prs: Any,
) -> None:
    chart_data = _chart_hierarchical_category_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_hierarchical_category_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_hierarchical_category_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_empty_category_data_edit(
    fixture_id: str,
    prs: Any,
) -> None:
    chart_data = _chart_empty_category_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_empty_category_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_empty_category_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_xy_data_edit(fixture_id: str, prs: Any) -> None:
    chart_data = _chart_xy_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_xy_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_xy_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_empty_xy_data_edit(
    fixture_id: str,
    prs: Any,
) -> None:
    chart_data = _chart_empty_xy_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_empty_xy_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_empty_xy_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_bubble_data_edit(
    fixture_id: str,
    prs: Any,
) -> None:
    chart_data = _chart_bubble_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_bubble_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_bubble_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_python_pptx_dropin_chart_empty_bubble_data_edit(
    fixture_id: str,
    prs: Any,
) -> None:
    chart_data = _chart_empty_bubble_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _apply_wolfppt_dropin_chart_empty_bubble_data_edit(
    fixture_id: str,
    prs: WolfPresentation,
) -> None:
    chart_data = _chart_empty_bubble_data_edit_payload(fixture_id)
    _first_chart_shape(prs).chart.replace_data(chart_data)


def _chart_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import CategoryChartData

    case = _chart_data_edit_case(fixture_id)
    chart_data = CategoryChartData()
    chart_data.categories = case.get("category_values", case["categories"])
    for series in case["series"]:
        chart_data.add_series(series["name"], tuple(series["values"]))
    return chart_data


def _chart_sparse_category_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import CategoryChartData

    case = _chart_sparse_category_data_edit_case(fixture_id)
    chart_data = CategoryChartData()
    chart_data.categories = case["categories"]
    for series in case["series"]:
        chart_data.add_series(series["name"], tuple(series["values"]))
    return chart_data


def _chart_hierarchical_category_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import CategoryChartData

    case = _chart_hierarchical_category_data_edit_case(fixture_id)
    chart_data = CategoryChartData()
    for parent in case["hierarchy"]:
        category = chart_data.categories.add_category(parent["label"])
        _add_hierarchical_category_children(category, parent["children"])
    for series in case["series"]:
        chart_data.add_series(series["name"], tuple(series["values"]))
    return chart_data


def _add_hierarchical_category_children(category: Any, children: list[Any]) -> None:
    for child in children:
        if isinstance(child, Mapping):
            sub_category = category.add_sub_category(child["label"])
            _add_hierarchical_category_children(
                sub_category,
                child.get("children", []),
            )
            continue
        category.add_sub_category(child)


def _chart_empty_category_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import CategoryChartData

    case = _chart_empty_category_data_edit_case(fixture_id)
    chart_data = CategoryChartData()
    chart_data.categories = case["categories"]
    for series in case["series"]:
        chart_data.add_series(series["name"], tuple(series["values"]))
    return chart_data


def _chart_xy_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import XyChartData

    case = _chart_xy_data_edit_case(fixture_id)
    chart_data = XyChartData()
    for series in case["series"]:
        xy_series = chart_data.add_series(series["name"])
        for x_value, y_value in zip(
            series["x_values"],
            series["values"],
            strict=True,
        ):
            xy_series.add_data_point(x_value, y_value)
    return chart_data


def _chart_empty_xy_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import XyChartData

    case = _chart_empty_xy_data_edit_case(fixture_id)
    chart_data = XyChartData()
    for series in case["series"]:
        chart_data.add_series(series["name"])
    return chart_data


def _chart_bubble_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import BubbleChartData

    case = _chart_bubble_data_edit_case(fixture_id)
    chart_data = BubbleChartData()
    for series in case["series"]:
        bubble_series = chart_data.add_series(series["name"])
        for x_value, y_value, bubble_size in zip(
            series["x_values"],
            series["values"],
            series["bubble_sizes"],
            strict=True,
        ):
            bubble_series.add_data_point(x_value, y_value, bubble_size)
    return chart_data


def _chart_empty_bubble_data_edit_payload(fixture_id: str) -> Any:
    from pptx.chart.data import BubbleChartData

    case = _chart_empty_bubble_data_edit_case(fixture_id)
    chart_data = BubbleChartData()
    for series in case["series"]:
        chart_data.add_series(series["name"])
    return chart_data


def _chart_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            f"drop-in chart data benchmark does not support fixture {fixture_id}"
        ) from exc


def _chart_sparse_category_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_SPARSE_CATEGORY_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            "drop-in sparse category chart data benchmark does not support "
            f"fixture {fixture_id}"
        ) from exc


def _chart_hierarchical_category_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_HIERARCHICAL_CATEGORY_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            "drop-in hierarchical category chart data benchmark does not support "
            f"fixture {fixture_id}"
        ) from exc


def _chart_empty_category_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_EMPTY_CATEGORY_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            "drop-in empty category chart data benchmark does not support "
            f"fixture {fixture_id}"
        ) from exc


def _chart_xy_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_XY_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            f"drop-in XY chart data benchmark does not support fixture {fixture_id}"
        ) from exc


def _chart_empty_xy_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_EMPTY_XY_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            f"drop-in empty XY chart data benchmark does not support fixture {fixture_id}"
        ) from exc


def _chart_bubble_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_BUBBLE_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            f"drop-in bubble chart data benchmark does not support fixture {fixture_id}"
        ) from exc


def _chart_empty_bubble_data_edit_case(fixture_id: str) -> dict[str, Any]:
    try:
        return CHART_EMPTY_BUBBLE_DATA_EDIT_CASES[fixture_id]
    except KeyError as exc:
        raise RuntimeError(
            "drop-in empty bubble chart data benchmark does not support "
            f"fixture {fixture_id}"
        ) from exc


def _read_wolfppt_chart_xy_data_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    _chart_xy_data_edit_case(fixture_id)
    chart = _first_chart_shape(prs).chart
    return {
        "chart_type": str(chart.chart_type),
        "categories": list(chart.categories),
        "series": [
            {
                "name": series.name,
                "x_values": series.x_values,
                "values": series.values,
            }
            for series in chart.series
        ],
    }


def _read_wolfppt_chart_bubble_data_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    _chart_bubble_data_edit_case(fixture_id)
    chart = _first_chart_shape(prs).chart
    return {
        "chart_type": str(chart.chart_type),
        "categories": list(chart.categories),
        "series": [
            {
                "name": series.name,
                "x_values": series.x_values,
                "values": series.values,
                "bubble_sizes": series.bubble_sizes,
            }
            for series in chart.series
        ],
    }

