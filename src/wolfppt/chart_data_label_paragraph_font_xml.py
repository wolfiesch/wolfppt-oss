"""Chart point data-label paragraph font XML helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_data_label_text_xml import (
    chart_data_label_paragraph_default_run_properties as _point_data_label_paragraph_default_run_properties,
)
from .chart_point_facade_xml import _chart_point_data_label_element
from .chart_point_data_label_xml import (
    set_run_properties_font as _set_run_properties_font,
)
from .dml_fill import (
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def data_label_paragraph_font_properties(paragraph: Any) -> dict[str, str]:
    run_properties = data_label_paragraph_font_element(paragraph, create=False)
    return {} if run_properties is None else dict(run_properties.attrib)


def data_label_paragraph_rgb(paragraph: Any) -> str | None:
    run_properties = data_label_paragraph_font_element(paragraph, create=False)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    return None if color is None else color.attrib.get("val")


def data_label_paragraph_fill_type(paragraph: Any) -> str | None:
    run_properties = data_label_paragraph_font_element(paragraph, create=False)
    return None if run_properties is None else _fill_type_from_xml_children(
        run_properties
    )


def data_label_paragraph_pattern(paragraph: Any) -> str | None:
    run_properties = data_label_paragraph_font_element(paragraph, create=False)
    if run_properties is None:
        return None
    pattern_fill = run_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def data_label_paragraph_pattern_rgb(
    paragraph: Any,
    color_tag: str,
) -> str | None:
    run_properties = data_label_paragraph_font_element(paragraph, create=False)
    if run_properties is None:
        return None
    return _fill_rgb_from_xml_children(run_properties, color_tag)


def data_label_paragraph_gradient_payload(paragraph: Any) -> dict[str, Any] | None:
    run_properties = data_label_paragraph_font_element(paragraph, create=False)
    if run_properties is None:
        return None
    return _gradient_payload_from_fill_parent(run_properties)


def set_data_label_paragraph_font(
    paragraph: Any,
    properties: dict[str, Any],
) -> None:
    run_properties = data_label_paragraph_font_element(paragraph, create=True)
    assert run_properties is not None
    _set_run_properties_font(run_properties, properties)


def data_label_paragraph_font_element(
    paragraph: Any,
    *,
    create: bool,
) -> ET.Element | None:
    label_element = _chart_point_data_label_element(
        paragraph._label._point._series._chart._shape,
        paragraph._label._point._series.index,
        paragraph._label._point._index,
        create=create,
    )
    return _point_data_label_paragraph_default_run_properties(
        label_element,
        paragraph._index,
        create=create,
    )
