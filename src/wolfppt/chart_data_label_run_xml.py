"""Chart point data-label run XML helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_point_data_label_xml import (
    point_data_label_run_element as _point_data_label_run_element,
    set_run_properties_font as _set_run_properties_font,
)
from .chart_point_facade_xml import _chart_point_data_label_element
from .dml_fill import (
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def data_label_run_properties(
    label: Any,
    paragraph_index: int,
    run_index: int,
) -> dict[str, str]:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    return {} if run_properties is None else dict(run_properties.attrib)


def data_label_run_rgb(
    label: Any,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    return None if color is None else color.attrib.get("val")


def data_label_run_fill_type(
    label: Any,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    return None if run_properties is None else _fill_type_from_xml_children(
        run_properties
    )


def data_label_run_pattern(
    label: Any,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    if run_properties is None:
        return None
    pattern_fill = run_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def data_label_run_pattern_rgb(
    label: Any,
    paragraph_index: int,
    run_index: int,
    color_tag: str,
) -> str | None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    if run_properties is None:
        return None
    return _fill_rgb_from_xml_children(run_properties, color_tag)


def data_label_run_gradient_payload(
    label: Any,
    paragraph_index: int,
    run_index: int,
) -> dict[str, Any] | None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    if run_properties is None:
        return None
    return _gradient_payload_from_fill_parent(run_properties)


def data_label_run_font_name(
    label: Any,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=False,
    )
    if run_properties is None:
        return None
    latin = run_properties.find(f"{{{A_NS}}}latin")
    return None if latin is None else latin.attrib.get("typeface")


def set_data_label_run_font(
    label: Any,
    paragraph_index: int,
    run_index: int,
    properties: dict[str, Any],
) -> None:
    run_properties = data_label_run_properties_element(
        label,
        paragraph_index,
        run_index,
        create=True,
    )
    assert run_properties is not None
    _set_run_properties_font(run_properties, properties)


def data_label_run_properties_element(
    label: Any,
    paragraph_index: int,
    run_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    label_element = _chart_point_data_label_element(
        label._point._series._chart._shape,
        label._point._series.index,
        label._point._index,
        create=create,
    )
    run_element = _point_data_label_run_element(
        label_element,
        paragraph_index,
        run_index,
        create=create,
    )
    if run_element is None:
        return None
    run_properties = run_element.find(f"{{{A_NS}}}rPr")
    if run_properties is None and create:
        run_properties = ET.Element(f"{{{A_NS}}}rPr")
        run_element.insert(0, run_properties)
    return run_properties
