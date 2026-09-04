"""Chart drop-in benchmark metadata readers."""
# ruff: noqa: F401

from __future__ import annotations

from typing import Any

from .benchmark_dropin_chart_shape_lookup import (
    CHART_EDIT_FIXTURES,
    _first_chart_shape,
    _first_shell_chart_shape,
    _slide_may_have_chart,
)
from .presentation import Presentation as WolfPresentation


def _read_python_pptx_chart_metadata(fixture_id: str, prs: Any) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart read benchmark does not support fixture {fixture_id}"
        )
    shape = _first_chart_shape(prs)
    chart = shape.chart
    legend = chart.legend
    has_title = bool(chart.has_title)
    chart_title = chart.chart_title
    chart_title_has_text_frame = chart_title.has_text_frame
    metadata = {
        "has_chart": bool(shape.has_chart),
        "has_title": has_title,
        "title_text": str(chart_title.text_frame.text),
        "has_legend": bool(chart.has_legend),
        "legend_position": str(legend.position) if legend is not None else None,
        "legend_include_in_layout": legend.include_in_layout if legend is not None else None,
        **_legend_font_metadata(legend),
        "category_axis_has_title": bool(chart.category_axis.has_title),
        "category_axis_title_text": str(
            chart.category_axis.axis_title.text_frame.text
        ),
        **_axis_title_format_metadata(chart.category_axis, "category"),
        "value_axis_has_title": bool(chart.value_axis.has_title),
        "value_axis_title_text": str(chart.value_axis.axis_title.text_frame.text),
        **_axis_title_format_metadata(chart.value_axis, "value"),
        "chart_type": str(chart.chart_type),
        "chart_style": chart.chart_style,
        "chart_element_tag": chart.element.tag,
        "chart_part": _part_metadata(shape.chart_part),
        "plot_count": len(chart.plots),
        "categories": [str(category) for category in chart.plots[0].categories],
        "series": [
            {
                "name": series.name,
                "values": [float(value) for value in series.values],
            }
            for series in chart.series
        ],
        "chart_title_has_text_frame": chart_title_has_text_frame,
        "chart_title_element_tag": chart_title.element.tag,
    }
    metadata.update(_read_chart_proxy_metadata(chart))
    return metadata


def _read_wolfppt_chart_metadata(fixture_id: str, prs: WolfPresentation) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart read benchmark does not support fixture {fixture_id}"
        )
    shape = _first_chart_shape(prs)
    chart = shape.chart
    legend = chart.legend
    has_title = bool(chart.has_title)
    chart_title = chart.chart_title
    chart_title_has_text_frame = chart_title.has_text_frame
    metadata = {
        "has_chart": bool(shape.has_chart),
        "has_title": has_title,
        "title_text": chart_title.text_frame.text,
        "has_legend": bool(chart.has_legend),
        "legend_position": str(legend.position) if legend is not None else None,
        "legend_include_in_layout": legend.include_in_layout if legend is not None else None,
        **_legend_font_metadata(legend),
        "category_axis_has_title": bool(chart.category_axis.has_title),
        "category_axis_title_text": chart.category_axis.axis_title.text_frame.text,
        **_axis_title_format_metadata(chart.category_axis, "category"),
        "value_axis_has_title": bool(chart.value_axis.has_title),
        "value_axis_title_text": chart.value_axis.axis_title.text_frame.text,
        **_axis_title_format_metadata(chart.value_axis, "value"),
        "chart_type": str(chart.chart_type),
        "chart_style": chart.chart_style,
        "chart_element_tag": chart.element.tag,
        "chart_part": _part_metadata(shape.chart_part),
        "plot_count": len(chart.plots),
        "categories": chart.plots[0].categories,
        "series": [
            {
                "name": series.name,
                "values": series.values,
            }
            for series in chart.series
        ],
        "chart_title_has_text_frame": chart_title_has_text_frame,
        "chart_title_element_tag": chart_title.element.tag,
    }
    metadata.update(_read_chart_proxy_metadata(chart))
    return metadata


def _read_chart_proxy_metadata(chart: Any) -> dict[str, Any]:
    category_axis = chart.category_axis
    value_axis = chart.value_axis
    return {
        "chart_font_bold": chart.font.bold,
        "chart_font_italic": chart.font.italic,
        "chart_font_underline": chart.font.underline,
        "chart_font_name": chart.font.name,
        "chart_font_size": None if chart.font.size is None else int(chart.font.size),
        "chart_font_rgb": _font_rgb(chart.font),
        "chart_font_language_id": _font_language(chart.font),
        "chart_title_format_element_tag": chart.chart_title.format.element.tag,
        **_chart_title_format_metadata(chart),
        "category_axis_category_type": str(category_axis.category_type),
        "category_axis_format_element_tag": category_axis.format.element.tag,
        "category_major_gridlines_element_tag": category_axis.major_gridlines.element.tag,
        "category_major_gridlines_format_element_tag": (
            category_axis.major_gridlines.format.element.tag
        ),
        "category_tick_labels_number_format": category_axis.tick_labels.number_format,
        "category_tick_labels_number_format_is_linked": (
            category_axis.tick_labels.number_format_is_linked
        ),
        "category_tick_labels_offset": category_axis.tick_labels.offset,
        "category_tick_labels_font_size": (
            None
            if category_axis.tick_labels.font.size is None
            else int(category_axis.tick_labels.font.size)
        ),
        "category_tick_labels_font_language_id": _font_language(
            category_axis.tick_labels.font
        ),
        "value_axis_format_element_tag": value_axis.format.element.tag,
        "value_major_gridlines_element_tag": value_axis.major_gridlines.element.tag,
        "value_major_gridlines_format_element_tag": (
            value_axis.major_gridlines.format.element.tag
        ),
        "value_tick_labels_number_format": value_axis.tick_labels.number_format,
        "value_tick_labels_number_format_is_linked": (
            value_axis.tick_labels.number_format_is_linked
        ),
        "value_tick_labels_has_offset": hasattr(value_axis.tick_labels, "offset"),
        "value_tick_labels_font_size": (
            None
            if value_axis.tick_labels.font.size is None
            else int(value_axis.tick_labels.font.size)
        ),
        "value_tick_labels_font_language_id": _font_language(
            value_axis.tick_labels.font
        ),
    }


def _chart_title_format_metadata(chart: Any) -> dict[str, Any]:
    if not chart.has_title:
        return {
            "chart_title_fill_type": None,
            "chart_title_fill_rgb": None,
            "chart_title_line_fill_type": None,
            "chart_title_line_rgb": None,
            "chart_title_line_pattern": None,
            "chart_title_line_pattern_back_rgb": None,
            "chart_title_line_width": None,
            "chart_title_line_dash_style": None,
        }
    title_format = chart.chart_title.format
    fill_type = title_format.fill.type
    line_fill_type = title_format.line.fill.type
    line_dash = title_format.line.dash_style
    return {
        "chart_title_fill_type": _enum_name(fill_type),
        "chart_title_fill_rgb": (
            None if fill_type is None else _color_rgb(title_format.fill.fore_color)
        ),
        "chart_title_line_fill_type": _enum_name(line_fill_type),
        "chart_title_line_rgb": (
            None if line_fill_type is None else _color_rgb(title_format.line.color)
        ),
        "chart_title_line_pattern": _fill_pattern(title_format.line.fill),
        "chart_title_line_pattern_back_rgb": _fill_back_rgb(title_format.line.fill),
        "chart_title_line_width": (
            None
            if line_fill_type is None or title_format.line.width is None
            else int(title_format.line.width)
        ),
        "chart_title_line_dash_style": getattr(line_dash, "xml_value", line_dash),
    }


def _axis_title_format_metadata(axis: Any, prefix: str) -> dict[str, Any]:
    keys = {
        "fill_type": f"{prefix}_axis_title_fill_type",
        "fill_rgb": f"{prefix}_axis_title_fill_rgb",
        "line_fill_type": f"{prefix}_axis_title_line_fill_type",
        "line_rgb": f"{prefix}_axis_title_line_rgb",
        "line_width": f"{prefix}_axis_title_line_width",
        "line_dash_style": f"{prefix}_axis_title_line_dash_style",
    }
    if not axis.has_title:
        return {value: None for value in keys.values()}
    axis_format = axis.axis_title.format
    fill_type = axis_format.fill.type
    line_fill_type = axis_format.line.fill.type
    line_dash = axis_format.line.dash_style
    return {
        keys["fill_type"]: _enum_name(fill_type),
        keys["fill_rgb"]: (
            None if fill_type is None else _color_rgb(axis_format.fill.fore_color)
        ),
        keys["line_fill_type"]: _enum_name(line_fill_type),
        keys["line_rgb"]: (
            None if line_fill_type is None else _color_rgb(axis_format.line.color)
        ),
        keys["line_width"]: (
            None
            if line_fill_type is None or axis_format.line.width is None
            else int(axis_format.line.width)
        ),
        keys["line_dash_style"]: getattr(line_dash, "xml_value", line_dash),
    }


def _major_gridlines_format_metadata(axis: Any, prefix: str) -> dict[str, Any]:
    gridline_format = axis.major_gridlines.format
    line_fill_type = gridline_format.line.fill.type
    line_dash = gridline_format.line.dash_style
    return {
        f"{prefix}_major_gridlines_line_fill_type": _enum_name(line_fill_type),
        f"{prefix}_major_gridlines_line_rgb": (
            None if line_fill_type is None else _color_rgb(gridline_format.line.color)
        ),
        f"{prefix}_major_gridlines_line_width": (
            None
            if line_fill_type is None or gridline_format.line.width is None
            else int(gridline_format.line.width)
        ),
        f"{prefix}_major_gridlines_line_dash_style": getattr(
            line_dash,
            "xml_value",
            line_dash,
        ),
    }


def _axis_format_metadata(axis: Any, prefix: str) -> dict[str, Any]:
    axis_format = axis.format
    fill_type = axis_format.fill.type
    line_fill_type = axis_format.line.fill.type
    line_dash = axis_format.line.dash_style
    return {
        f"{prefix}_axis_fill_type": _enum_name(fill_type),
        f"{prefix}_axis_fill_rgb": (
            None if fill_type is None else _color_rgb(axis_format.fill.fore_color)
        ),
        f"{prefix}_axis_line_fill_type": _enum_name(line_fill_type),
        f"{prefix}_axis_line_rgb": (
            None if line_fill_type is None else _color_rgb(axis_format.line.color)
        ),
        f"{prefix}_axis_line_width": (
            None
            if line_fill_type is None or axis_format.line.width is None
            else int(axis_format.line.width)
        ),
        f"{prefix}_axis_line_dash_style": getattr(line_dash, "xml_value", line_dash),
    }


def _enum_name(value: Any) -> Any:
    return None if value is None else getattr(value, "name", str(value))


def _color_rgb(color: Any) -> str | None:
    try:
        rgb = color.rgb
    except (AttributeError, TypeError):
        return None
    return None if rgb is None else str(rgb)


def _fill_pattern(fill: Any) -> Any:
    try:
        return _enum_name(fill.pattern)
    except (AttributeError, TypeError):
        return None


def _fill_back_rgb(fill: Any) -> str | None:
    try:
        rgb = fill.back_color.rgb
    except (AttributeError, TypeError):
        return None
    return None if rgb is None else str(rgb)


def _legend_font_metadata(legend: Any | None) -> dict[str, Any]:
    if legend is None:
        return {
            "legend_font_bold": None,
            "legend_font_italic": None,
            "legend_font_underline": None,
            "legend_font_size": None,
            "legend_font_fill_type": None,
            "legend_font_rgb": None,
            "legend_font_gradient_angle": None,
            "legend_font_gradient_stop_count": None,
            "legend_font_gradient_first_stop_position": None,
            "legend_font_gradient_first_stop_rgb": None,
            "legend_font_name": None,
        }
    return {
        "legend_font_bold": legend.font.bold,
        "legend_font_italic": legend.font.italic,
        "legend_font_underline": legend.font.underline,
        "legend_font_size": None if legend.font.size is None else int(legend.font.size),
        "legend_font_fill_type": _font_fill_type(legend.font),
        "legend_font_rgb": _font_rgb(legend.font),
        "legend_font_gradient_angle": _font_gradient_angle(legend.font),
        "legend_font_gradient_stop_count": _font_gradient_stop_count(legend.font),
        "legend_font_gradient_first_stop_position": _font_gradient_stop_position(
            legend.font,
            0,
        ),
        "legend_font_gradient_first_stop_rgb": _font_gradient_stop_rgb(legend.font, 0),
        "legend_font_name": legend.font.name,
    }


def _font_rgb(font: Any) -> str | None:
    try:
        rgb = font.color.rgb
    except AttributeError:
        return None
    return None if rgb is None else str(rgb)


def _font_fill_type(font: Any) -> Any:
    try:
        return _enum_name(font.fill.type)
    except AttributeError:
        return None


def _font_pattern(font: Any) -> Any:
    try:
        return _enum_name(font.fill.pattern)
    except (AttributeError, TypeError):
        return None


def _font_pattern_rgb(font: Any, color_attr: str) -> str | None:
    try:
        rgb = getattr(font.fill, color_attr).rgb
    except (AttributeError, TypeError):
        return None
    return None if rgb is None else str(rgb)


def _font_gradient_angle(font: Any) -> float | None:
    try:
        return font.fill.gradient_angle
    except (AttributeError, TypeError):
        return None


def _font_gradient_stop_count(font: Any) -> int | None:
    try:
        return len(font.fill.gradient_stops)
    except (AttributeError, TypeError):
        return None


def _font_gradient_stop_position(font: Any, index: int) -> float | None:
    try:
        return font.fill.gradient_stops[index].position
    except (AttributeError, IndexError, TypeError):
        return None


def _font_gradient_stop_rgb(font: Any, index: int) -> str | None:
    try:
        rgb = font.fill.gradient_stops[index].color.rgb
    except (AttributeError, IndexError, TypeError):
        return None
    return None if rgb is None else str(rgb)


def _fill_rgb(fill: Any) -> str | None:
    try:
        rgb = fill.fore_color.rgb
    except (AttributeError, TypeError):
        return None
    return None if rgb is None else str(rgb)


def _fill_gradient_angle(fill: Any) -> float | None:
    try:
        return fill.gradient_angle
    except (AttributeError, TypeError):
        return None


def _fill_gradient_stop_count(fill: Any) -> int | None:
    try:
        return len(fill.gradient_stops)
    except (AttributeError, TypeError):
        return None


def _fill_gradient_stop_position(fill: Any, index: int) -> float | None:
    try:
        return fill.gradient_stops[index].position
    except (AttributeError, IndexError, TypeError):
        return None


def _fill_gradient_stop_rgb(fill: Any, index: int) -> str | None:
    try:
        rgb = fill.gradient_stops[index].color.rgb
    except (AttributeError, IndexError, TypeError):
        return None
    return None if rgb is None else str(rgb)


def _font_language(font: Any) -> str:
    return str(font.language_id)


def _part_metadata(part_owner: Any) -> dict[str, Any]:
    part = part_owner.part
    try:
        name = part.name
    except AttributeError:
        name = None
    return {
        "partname": str(part.partname),
        "content_type": part.content_type,
        "has_blob": len(part.blob) > 0,
        "part_is_self": part.part is part,
        "name": name,
    }


def _read_wolfppt_chart_axis_property_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart axis property benchmark does not support fixture {fixture_id}"
        )
    chart = _first_chart_shape(prs).chart
    category_axis = chart.category_axis
    value_axis = chart.value_axis
    return {
        "category_visible": category_axis.visible,
        **_axis_format_metadata(category_axis, "category"),
        "category_has_major_gridlines": category_axis.has_major_gridlines,
        **_major_gridlines_format_metadata(category_axis, "category"),
        "category_has_minor_gridlines": category_axis.has_minor_gridlines,
        "category_major_tick_mark": str(category_axis.major_tick_mark),
        "category_minor_tick_mark": str(category_axis.minor_tick_mark),
        "category_tick_label_position": str(category_axis.tick_label_position),
        "category_tick_label_number_format": category_axis.tick_labels.number_format,
        "category_tick_label_number_format_is_linked": (
            category_axis.tick_labels.number_format_is_linked
        ),
        "category_tick_label_offset": category_axis.tick_labels.offset,
        "category_tick_label_font_bold": category_axis.tick_labels.font.bold,
        "category_tick_label_font_italic": category_axis.tick_labels.font.italic,
        "category_tick_label_font_underline": category_axis.tick_labels.font.underline,
        "category_tick_label_font_size": (
            None
            if category_axis.tick_labels.font.size is None
            else int(category_axis.tick_labels.font.size)
        ),
        "category_tick_label_font_fill_type": _font_fill_type(
            category_axis.tick_labels.font
        ),
        "category_tick_label_font_rgb": _font_rgb(category_axis.tick_labels.font),
        "category_tick_label_font_gradient_angle": _font_gradient_angle(
            category_axis.tick_labels.font
        ),
        "category_tick_label_font_gradient_stop_count": _font_gradient_stop_count(
            category_axis.tick_labels.font
        ),
        "category_tick_label_font_gradient_first_stop_position": (
            _font_gradient_stop_position(category_axis.tick_labels.font, 0)
        ),
        "category_tick_label_font_gradient_first_stop_rgb": _font_gradient_stop_rgb(
            category_axis.tick_labels.font,
            0,
        ),
        "category_tick_label_font_name": category_axis.tick_labels.font.name,
        "category_tick_label_font_language_id": _font_language(
            category_axis.tick_labels.font
        ),
        "category_reverse_order": category_axis.reverse_order,
        "category_minimum_scale": category_axis.minimum_scale,
        "category_maximum_scale": category_axis.maximum_scale,
        "value_visible": value_axis.visible,
        **_axis_format_metadata(value_axis, "value"),
        "value_has_major_gridlines": value_axis.has_major_gridlines,
        **_major_gridlines_format_metadata(value_axis, "value"),
        "value_has_minor_gridlines": value_axis.has_minor_gridlines,
        "value_major_tick_mark": str(value_axis.major_tick_mark),
        "value_minor_tick_mark": str(value_axis.minor_tick_mark),
        "value_tick_label_position": str(value_axis.tick_label_position),
        "value_tick_label_number_format": value_axis.tick_labels.number_format,
        "value_tick_label_number_format_is_linked": (
            value_axis.tick_labels.number_format_is_linked
        ),
        "value_tick_label_font_bold": value_axis.tick_labels.font.bold,
        "value_tick_label_font_italic": value_axis.tick_labels.font.italic,
        "value_tick_label_font_underline": value_axis.tick_labels.font.underline,
        "value_tick_label_font_size": (
            None
            if value_axis.tick_labels.font.size is None
            else int(value_axis.tick_labels.font.size)
        ),
        "value_tick_label_font_fill_type": _font_fill_type(
            value_axis.tick_labels.font
        ),
        "value_tick_label_font_rgb": _font_rgb(value_axis.tick_labels.font),
        "value_tick_label_font_pattern": _font_pattern(value_axis.tick_labels.font),
        "value_tick_label_font_pattern_fore_rgb": _font_pattern_rgb(
            value_axis.tick_labels.font,
            "fore_color",
        ),
        "value_tick_label_font_pattern_back_rgb": _font_pattern_rgb(
            value_axis.tick_labels.font,
            "back_color",
        ),
        "value_tick_label_font_name": value_axis.tick_labels.font.name,
        "value_tick_label_font_language_id": _font_language(value_axis.tick_labels.font),
        "value_reverse_order": value_axis.reverse_order,
        "value_minimum_scale": value_axis.minimum_scale,
        "value_maximum_scale": value_axis.maximum_scale,
        "value_major_unit": value_axis.major_unit,
        "value_minor_unit": value_axis.minor_unit,
        "value_crosses": str(value_axis.crosses),
        "value_crosses_at": value_axis.crosses_at,
    }


def _read_wolfppt_chart_plot_property_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart plot property benchmark does not support fixture {fixture_id}"
        )
    plot = _first_chart_shape(prs).chart.plots[0]
    return {
        "vary_by_categories": plot.vary_by_categories,
        "gap_width": plot.gap_width,
        "overlap": plot.overlap,
    }


def _read_wolfppt_chart_data_label_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart data-label benchmark does not support fixture {fixture_id}"
        )
    chart = _first_chart_shape(prs).chart
    plot = chart.plots[0]
    metadata: dict[str, Any] = {
        "has_data_labels": plot.has_data_labels,
    }
    if not plot.has_data_labels:
        return metadata
    labels = plot.data_labels
    metadata.update(
        {
            "show_value": labels.show_value,
            "show_category_name": labels.show_category_name,
            "show_series_name": labels.show_series_name,
            "show_percentage": labels.show_percentage,
            "show_legend_key": labels.show_legend_key,
            "position": str(labels.position),
            "number_format": labels.number_format,
            "number_format_is_linked": labels.number_format_is_linked,
            "font_bold": labels.font.bold,
            "font_italic": labels.font.italic,
            "font_underline": labels.font.underline,
            "font_size": None if labels.font.size is None else int(labels.font.size),
            "font_fill_type": _font_fill_type(labels.font),
            "font_rgb": _font_rgb(labels.font),
            "font_gradient_angle": _font_gradient_angle(labels.font),
            "font_gradient_stop_count": _font_gradient_stop_count(labels.font),
            "font_gradient_first_stop_position": _font_gradient_stop_position(
                labels.font,
                0,
            ),
            "font_gradient_first_stop_rgb": _font_gradient_stop_rgb(labels.font, 0),
            "font_name": labels.font.name,
            "font_language_id": _font_language(labels.font),
        }
    )
    series_labels = chart.series[0].data_labels
    metadata["series_data_labels"] = {
        "show_value": series_labels.show_value,
        "show_category_name": series_labels.show_category_name,
        "show_series_name": series_labels.show_series_name,
        "show_percentage": series_labels.show_percentage,
        "show_legend_key": series_labels.show_legend_key,
        "position": str(series_labels.position),
        "number_format": series_labels.number_format,
        "number_format_is_linked": series_labels.number_format_is_linked,
        "font_bold": series_labels.font.bold,
        "font_italic": series_labels.font.italic,
        "font_underline": series_labels.font.underline,
        "font_size": None
        if series_labels.font.size is None
        else int(series_labels.font.size),
        "font_fill_type": _font_fill_type(series_labels.font),
        "font_rgb": _font_rgb(series_labels.font),
        "font_pattern": _font_pattern(series_labels.font),
        "font_pattern_fore_rgb": _font_pattern_rgb(series_labels.font, "fore_color"),
        "font_pattern_back_rgb": _font_pattern_rgb(series_labels.font, "back_color"),
        "font_name": series_labels.font.name,
        "font_language_id": _font_language(series_labels.font),
    }
    return metadata


def _read_wolfppt_chart_point_data_label_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart point data-label benchmark does not support fixture {fixture_id}"
        )
    label = _first_chart_shape(prs).chart.series[0].points[0].data_label
    text_frame = label.text_frame
    paragraph = text_frame.paragraphs[0]
    run = label.text_frame.paragraphs[0].runs[0]
    vertical_anchor = text_frame.vertical_anchor
    auto_size = text_frame.auto_size
    return {
        "point_data_label_has_text_frame": label.has_text_frame,
        "point_data_label_position": str(label.position),
        "point_data_label_font_bold": label.font.bold,
        "point_data_label_font_italic": label.font.italic,
        "point_data_label_font_underline": label.font.underline,
        "point_data_label_font_size": (
            None if label.font.size is None else int(label.font.size)
        ),
        "point_data_label_font_fill_type": _font_fill_type(label.font),
        "point_data_label_font_rgb": _font_rgb(label.font),
        "point_data_label_font_pattern": _font_pattern(label.font),
        "point_data_label_font_pattern_fore_rgb": _font_pattern_rgb(
            label.font,
            "fore_color",
        ),
        "point_data_label_font_pattern_back_rgb": _font_pattern_rgb(
            label.font,
            "back_color",
        ),
        "point_data_label_font_name": label.font.name,
        "point_data_label_font_language_id": _font_language(label.font),
        "point_data_label_text": text_frame.text,
        "point_data_label_margin_left": int(text_frame.margin_left),
        "point_data_label_margin_right": int(text_frame.margin_right),
        "point_data_label_margin_top": int(text_frame.margin_top),
        "point_data_label_margin_bottom": int(text_frame.margin_bottom),
        "point_data_label_word_wrap": text_frame.word_wrap,
        "point_data_label_vertical_anchor": (
            None
            if vertical_anchor is None
            else getattr(vertical_anchor, "name", str(vertical_anchor))
        ),
        "point_data_label_auto_size": (
            None if auto_size is None else getattr(auto_size, "name", str(auto_size))
        ),
        "point_data_label_first_paragraph_alignment": str(paragraph.alignment),
        "point_data_label_first_paragraph_level": paragraph.level,
        "point_data_label_first_paragraph_space_before": (
            None if paragraph.space_before is None else int(paragraph.space_before)
        ),
        "point_data_label_first_paragraph_space_after": (
            None if paragraph.space_after is None else int(paragraph.space_after)
        ),
        "point_data_label_first_paragraph_line_spacing": paragraph.line_spacing,
        "point_data_label_first_paragraph_font_bold": paragraph.font.bold,
        "point_data_label_first_paragraph_font_italic": paragraph.font.italic,
        "point_data_label_first_paragraph_font_underline": paragraph.font.underline,
        "point_data_label_first_paragraph_font_size": (
            None if paragraph.font.size is None else int(paragraph.font.size)
        ),
        "point_data_label_first_paragraph_font_rgb": _font_rgb(paragraph.font),
        "point_data_label_first_paragraph_font_fill_type": _enum_name(
            paragraph.font.fill.type
        ),
        "point_data_label_first_paragraph_font_gradient_angle": (
            _font_gradient_angle(paragraph.font)
        ),
        "point_data_label_first_paragraph_font_gradient_stop_count": (
            _font_gradient_stop_count(paragraph.font)
        ),
        "point_data_label_first_paragraph_font_gradient_first_stop_position": (
            _font_gradient_stop_position(paragraph.font, 0)
        ),
        "point_data_label_first_paragraph_font_gradient_first_stop_rgb": (
            _font_gradient_stop_rgb(paragraph.font, 0)
        ),
        "point_data_label_first_paragraph_font_name": paragraph.font.name,
        "point_data_label_first_paragraph_font_language_id": _font_language(
            paragraph.font
        ),
        "point_data_label_first_run_bold": run.font.bold,
        "point_data_label_first_run_italic": run.font.italic,
        "point_data_label_first_run_underline": run.font.underline,
        "point_data_label_first_run_size": (
            None if run.font.size is None else int(run.font.size)
        ),
        "point_data_label_first_run_rgb": _font_rgb(run.font),
        "point_data_label_first_run_fill_type": _enum_name(run.font.fill.type),
        "point_data_label_first_run_gradient_angle": _font_gradient_angle(run.font),
        "point_data_label_first_run_gradient_stop_count": (
            _font_gradient_stop_count(run.font)
        ),
        "point_data_label_first_run_gradient_first_stop_position": (
            _font_gradient_stop_position(run.font, 0)
        ),
        "point_data_label_first_run_gradient_first_stop_rgb": (
            _font_gradient_stop_rgb(run.font, 0)
        ),
        "point_data_label_first_run_name": run.font.name,
        "point_data_label_first_run_language_id": _font_language(run.font),
    }


def _read_wolfppt_chart_style_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart style benchmark does not support fixture {fixture_id}"
        )
    return {"chart_style": _first_chart_shape(prs).chart.chart_style}


def _read_wolfppt_chart_format_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart format benchmark does not support fixture {fixture_id}"
        )
    chart = _first_chart_shape(prs).chart
    series = chart.series[0]
    point = series.points[0]
    background_point = series.points[1]
    marker = point.marker
    background_marker = background_point.marker
    series_line_dash = series.format.line.dash_style
    point_line_dash = point.format.line.dash_style
    marker_line_dash = marker.format.line.dash_style
    marker_style = marker.style
    series_fill_type = series.format.fill.type
    point_fill_type = point.format.fill.type
    background_point_fill_type = background_point.format.fill.type
    series_line_fill_type = series.format.line.fill.type
    point_line_fill_type = point.format.line.fill.type
    background_point_line_fill_type = background_point.format.line.fill.type
    marker_fill_type = marker.format.fill.type
    background_marker_fill_type = background_marker.format.fill.type
    marker_line_fill_type = marker.format.line.fill.type
    return {
        "chart_font_bold": chart.font.bold,
        "chart_font_italic": chart.font.italic,
        "chart_font_underline": chart.font.underline,
        "chart_font_size": None if chart.font.size is None else int(chart.font.size),
        "chart_font_fill_type": _font_fill_type(chart.font),
        "chart_font_pattern": _font_pattern(chart.font),
        "chart_font_pattern_fore_rgb": _font_pattern_rgb(chart.font, "fore_color"),
        "chart_font_pattern_back_rgb": _font_pattern_rgb(chart.font, "back_color"),
        "chart_font_gradient_angle": _font_gradient_angle(chart.font),
        "chart_font_gradient_stop_count": _font_gradient_stop_count(chart.font),
        "chart_font_gradient_first_stop_position": _font_gradient_stop_position(
            chart.font,
            0,
        ),
        "chart_font_gradient_first_stop_rgb": _font_gradient_stop_rgb(chart.font, 0),
        "chart_font_rgb": _font_rgb(chart.font),
        "chart_font_name": chart.font.name,
        "chart_font_language_id": _font_language(chart.font),
        "series_fill_type": getattr(series_fill_type, "name", str(series_fill_type)),
        "series_fill_rgb": str(series.format.fill.fore_color.rgb),
        "series_fill_pattern": getattr(
            series.format.fill.pattern,
            "name",
            str(series.format.fill.pattern),
        ),
        "series_fill_pattern_back_rgb": str(series.format.fill.back_color.rgb),
        "series_line_fill_type": getattr(
            series_line_fill_type,
            "name",
            str(series_line_fill_type),
        ),
        "series_line_fill_rgb": str(series.format.line.fill.fore_color.rgb),
        "series_line_fill_pattern": getattr(
            series.format.line.fill.pattern,
            "name",
            str(series.format.line.fill.pattern),
        ),
        "series_line_fill_pattern_back_rgb": str(
            series.format.line.fill.back_color.rgb
        ),
        "series_line_rgb": str(series.format.line.color.rgb),
        "series_line_width": int(series.format.line.width),
        "series_line_dash_style": getattr(
            series_line_dash,
            "xml_value",
            series_line_dash,
        ),
        "point_fill_type": getattr(point_fill_type, "name", str(point_fill_type)),
        "point_fill_rgb": _fill_rgb(point.format.fill),
        "point_fill_gradient_angle": _fill_gradient_angle(point.format.fill),
        "point_fill_gradient_stop_count": _fill_gradient_stop_count(point.format.fill),
        "point_fill_gradient_first_stop_position": _fill_gradient_stop_position(
            point.format.fill,
            0,
        ),
        "point_fill_gradient_first_stop_rgb": _fill_gradient_stop_rgb(
            point.format.fill,
            0,
        ),
        "background_point_fill_type": getattr(
            background_point_fill_type,
            "name",
            str(background_point_fill_type),
        ),
        "background_point_fill_rgb": _fill_rgb(background_point.format.fill),
        "point_line_fill_type": getattr(
            point_line_fill_type,
            "name",
            str(point_line_fill_type),
        ),
        "point_line_fill_rgb": None
        if point.format.line.fill.fore_color.rgb is None
        else str(point.format.line.fill.fore_color.rgb),
        "point_line_rgb": None
        if point.format.line.color.rgb is None
        else str(point.format.line.color.rgb),
        "point_line_width": int(point.format.line.width),
        "point_line_dash_style": getattr(
            point_line_dash,
            "xml_value",
            point_line_dash,
        ),
        "background_point_line_fill_type": getattr(
            background_point_line_fill_type,
            "name",
            str(background_point_line_fill_type),
        ),
        "background_point_line_fill_rgb": str(
            background_point.format.line.fill.fore_color.rgb
        ),
        "background_point_line_fill_pattern": getattr(
            background_point.format.line.fill.pattern,
            "name",
            str(background_point.format.line.fill.pattern),
        ),
        "background_point_line_fill_pattern_back_rgb": str(
            background_point.format.line.fill.back_color.rgb
        ),
        "marker_fill_type": getattr(marker_fill_type, "name", str(marker_fill_type)),
        "marker_fill_rgb": str(marker.format.fill.fore_color.rgb),
        "marker_fill_pattern": getattr(
            marker.format.fill.pattern,
            "name",
            str(marker.format.fill.pattern),
        ),
        "marker_fill_pattern_back_rgb": str(marker.format.fill.back_color.rgb),
        "background_marker_fill_type": getattr(
            background_marker_fill_type,
            "name",
            str(background_marker_fill_type),
        ),
        "background_marker_fill_rgb": _fill_rgb(background_marker.format.fill),
        "marker_line_fill_type": getattr(
            marker_line_fill_type,
            "name",
            str(marker_line_fill_type),
        ),
        "marker_line_fill_rgb": None
        if marker.format.line.fill.fore_color.rgb is None
        else str(marker.format.line.fill.fore_color.rgb),
        "marker_line_fill_pattern": getattr(
            marker.format.line.fill.pattern,
            "name",
            str(marker.format.line.fill.pattern),
        ),
        "marker_line_fill_pattern_back_rgb": str(
            marker.format.line.fill.back_color.rgb
        ),
        "marker_line_rgb": None
        if marker.format.line.color.rgb is None
        else str(marker.format.line.color.rgb),
        "marker_line_width": int(marker.format.line.width),
        "marker_line_dash_style": getattr(
            marker_line_dash,
            "xml_value",
            marker_line_dash,
        ),
        "marker_style": getattr(marker_style, "xml_value", marker_style),
        "marker_size": marker.size,
    }
