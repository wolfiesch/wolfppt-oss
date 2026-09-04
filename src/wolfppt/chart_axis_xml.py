"""Chart axis XML mutation helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_xml_utils import A_NS, C_NS, xml_local_name as _xml_local_name
from .dml_fill import (
    no_fill_element as _no_fill_element,
    run_gradient_fill_element as _run_gradient_fill_element,
    run_no_fill_element as _run_no_fill_element,
    run_pattern_fill_element as _run_pattern_fill_element,
    run_solid_fill_element as _run_solid_fill_element,
    set_run_gradient_fill as _set_run_gradient_fill,
    set_run_pattern_fill as _set_run_pattern_fill,
    set_run_pattern_fill_color as _set_run_pattern_fill_color,
    set_solid_fill_rgb as _set_solid_fill_rgb,
    solid_fill_element as _solid_fill_element,
)

_CHART_AXIS_CHILD_ORDER = [
    "axId",
    "scaling",
    "delete",
    "axPos",
    "majorGridlines",
    "minorGridlines",
    "title",
    "numFmt",
    "majorTickMark",
    "minorTickMark",
    "tickLblPos",
    "spPr",
    "txPr",
    "crossAx",
    "crosses",
    "crossesAt",
    "crossBetween",
    "auto",
    "lblAlgn",
    "lblOffset",
    "tickLblSkip",
    "tickMarkSkip",
    "noMultiLvlLbl",
    "majorUnit",
    "minorUnit",
    "dispUnits",
    "extLst",
]
_CHART_AXIS_CHILD_INDEX = {
    local_name: index for index, local_name in enumerate(_CHART_AXIS_CHILD_ORDER)
}
_CHART_AXIS_SCALING_CHILD_ORDER = ["logBase", "orientation", "max", "min"]
_CHART_AXIS_SCALING_CHILD_INDEX = {
    local_name: index
    for index, local_name in enumerate(_CHART_AXIS_SCALING_CHILD_ORDER)
}


def set_chart_axis_property(axis_element: ET.Element, attr: str, value: Any) -> None:
    if attr == "visible":
        _set_chart_axis_delete(axis_element, not bool(value))
        return
    if attr == "has_major_gridlines":
        _set_chart_axis_empty_child(axis_element, "majorGridlines", bool(value))
        return
    if attr == "has_minor_gridlines":
        _set_chart_axis_empty_child(axis_element, "minorGridlines", bool(value))
        return
    if attr == "axis_fill_type":
        set_chart_axis_fill_type(axis_element, str(value))
        return
    if attr == "axis_fill_rgb":
        set_chart_axis_fill_rgb(axis_element, str(value))
        return
    if attr == "axis_line_fill_type":
        set_chart_axis_line_fill_type(axis_element, str(value))
        return
    if attr == "axis_line_rgb":
        set_chart_axis_line_rgb(axis_element, str(value))
        return
    if attr == "axis_line_width":
        set_chart_axis_line_width(axis_element, int(value))
        return
    if attr == "axis_line_dash":
        set_chart_axis_line_dash(axis_element, value)
        return
    if attr == "major_gridlines_line_fill_type":
        _set_chart_axis_major_gridlines_line_fill_type(axis_element, str(value))
        return
    if attr == "major_gridlines_line_rgb":
        _set_chart_axis_major_gridlines_line_rgb(axis_element, str(value))
        return
    if attr == "major_gridlines_line_width":
        _set_chart_axis_major_gridlines_line_width(axis_element, int(value))
        return
    if attr == "major_gridlines_line_dash":
        _set_chart_axis_major_gridlines_line_dash(axis_element, value)
        return
    if attr == "major_tick_mark":
        _set_chart_axis_val_child(axis_element, "majorTickMark", str(value))
        return
    if attr == "minor_tick_mark":
        _set_chart_axis_val_child(axis_element, "minorTickMark", str(value))
        return
    if attr == "tick_label_position":
        _set_chart_axis_val_child(axis_element, "tickLblPos", str(value))
        return
    if attr == "reverse_order":
        _set_chart_axis_orientation(axis_element, bool(value))
        return
    if attr == "minimum_scale":
        _set_chart_axis_scaling_bound(axis_element, "min", value)
        return
    if attr == "maximum_scale":
        _set_chart_axis_scaling_bound(axis_element, "max", value)
        return
    if attr == "number_format":
        _set_chart_axis_number_format(axis_element, str(value))
        return
    if attr == "number_format_is_linked":
        _set_chart_axis_number_format_source_linked(axis_element, bool(value))
        return
    if attr == "tick_label_offset":
        _set_chart_axis_int_child(axis_element, "lblOffset", value)
        return
    if attr == "tick_label_font_size":
        _set_chart_axis_tick_label_font_size(axis_element, value)
        return
    if attr == "tick_label_font_bold":
        _set_chart_axis_tick_label_font_bool(axis_element, "b", value)
        return
    if attr == "tick_label_font_italic":
        _set_chart_axis_tick_label_font_bool(axis_element, "i", value)
        return
    if attr == "tick_label_font_underline":
        _set_chart_axis_tick_label_font_underline(axis_element, value)
        return
    if attr == "tick_label_font_fill_type":
        _set_chart_axis_tick_label_font_fill_type(axis_element, str(value))
        return
    if attr == "tick_label_font_pattern":
        _set_chart_axis_tick_label_font_pattern(axis_element, value)
        return
    if attr == "tick_label_font_pattern_fore_rgb":
        _set_chart_axis_tick_label_font_pattern_rgb(axis_element, "fgClr", value)
        return
    if attr == "tick_label_font_pattern_back_rgb":
        _set_chart_axis_tick_label_font_pattern_rgb(axis_element, "bgClr", value)
        return
    if attr == "tick_label_font_gradient":
        _set_chart_axis_tick_label_font_gradient(axis_element, value)
        return
    if attr == "tick_label_font_rgb":
        _set_chart_axis_tick_label_font_rgb(
            axis_element,
            None if value is None else str(value),
        )
        return
    if attr == "tick_label_font_name":
        _set_chart_axis_tick_label_font_name(
            axis_element,
            None if value is None else str(value),
        )
        return
    if attr == "tick_label_font_language_id":
        _set_chart_axis_tick_label_font_language_id(
            axis_element,
            None if value is None else str(value),
        )
        return
    if attr == "major_unit":
        _set_chart_axis_optional_float_child(axis_element, "majorUnit", value)
        return
    if attr == "minor_unit":
        _set_chart_axis_optional_float_child(axis_element, "minorUnit", value)
        return
    if attr == "crosses":
        _set_chart_axis_crosses(axis_element, value)
        return
    if attr == "crosses_at":
        _set_chart_axis_crosses_at(axis_element, value)
        return
    raise ValueError(f"unsupported chart axis property: {attr!r}")


def axis_title_element(axis_element: ET.Element) -> ET.Element:
    title = axis_element.find(f"{{{C_NS}}}title")
    if title is not None:
        return title
    title = ET.Element(f"{{{C_NS}}}title")
    insert_at = len(axis_element)
    for index, child in enumerate(list(axis_element)):
        if child.tag in {
            f"{{{C_NS}}}majorTickMark",
            f"{{{C_NS}}}minorTickMark",
            f"{{{C_NS}}}tickLblPos",
            f"{{{C_NS}}}spPr",
            f"{{{C_NS}}}txPr",
            f"{{{C_NS}}}crossAx",
            f"{{{C_NS}}}crosses",
            f"{{{C_NS}}}crossBetween",
            f"{{{C_NS}}}auto",
            f"{{{C_NS}}}lblAlgn",
            f"{{{C_NS}}}lblOffset",
            f"{{{C_NS}}}noMultiLvlLbl",
            f"{{{C_NS}}}majorUnit",
            f"{{{C_NS}}}minorUnit",
            f"{{{C_NS}}}dispUnits",
            f"{{{C_NS}}}extLst",
        }:
            insert_at = index
            break
    axis_element.insert(insert_at, title)
    return title


def axis_shape_properties(axis_element: ET.Element) -> ET.Element:
    shape_properties = axis_element.find(f"{{{C_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{C_NS}}}spPr")
    axis_element.insert(
        _chart_axis_insert_index(axis_element, "spPr"),
        shape_properties,
    )
    return shape_properties


def set_chart_axis_fill_type(axis_element: ET.Element, fill_type: str) -> None:
    shape_properties = axis_shape_properties(axis_element)
    if fill_type == "solid":
        _solid_fill_element(shape_properties)
        return
    raise ValueError(f"unsupported chart fill type: {fill_type!r}")


def set_chart_axis_fill_rgb(axis_element: ET.Element, rgb: str) -> None:
    shape_properties = axis_shape_properties(axis_element)
    solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        _solid_fill_element(shape_properties)
        solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def chart_axis_line(axis_element: ET.Element) -> ET.Element:
    shape_properties = axis_shape_properties(axis_element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is not None:
        return line
    line = ET.Element(f"{{{A_NS}}}ln")
    shape_properties.append(line)
    return line


def set_chart_axis_line_fill_type(axis_element: ET.Element, fill_type: str) -> None:
    line = chart_axis_line(axis_element)
    if fill_type == "solid":
        _solid_fill_element(line)
        return
    if fill_type == "background":
        _no_fill_element(line)
        return
    raise ValueError(f"unsupported chart line fill type: {fill_type!r}")


def set_chart_axis_line_rgb(axis_element: ET.Element, rgb: str) -> None:
    line = chart_axis_line(axis_element)
    solid_fill = line.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        _solid_fill_element(line)
        solid_fill = line.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def set_chart_axis_line_width(axis_element: ET.Element, width: int) -> None:
    chart_axis_line(axis_element).set("w", str(width))


def set_chart_axis_line_dash(axis_element: ET.Element, dash_style: Any) -> None:
    line = chart_axis_line(axis_element)
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    if dash_style is None:
        if preset_dash is not None:
            line.remove(preset_dash)
        return
    if preset_dash is None:
        preset_dash = ET.Element(f"{{{A_NS}}}prstDash")
        line.append(preset_dash)
    preset_dash.set("val", str(dash_style))


def _chart_axis_major_gridlines_element(axis_element: ET.Element) -> ET.Element:
    gridlines = axis_element.find(f"{{{C_NS}}}majorGridlines")
    if gridlines is not None:
        return gridlines
    gridlines = ET.Element(f"{{{C_NS}}}majorGridlines")
    axis_element.insert(
        _chart_axis_insert_index(axis_element, "majorGridlines"),
        gridlines,
    )
    return gridlines


def _chart_axis_major_gridlines_shape_properties(
    axis_element: ET.Element,
) -> ET.Element:
    gridlines = _chart_axis_major_gridlines_element(axis_element)
    shape_properties = gridlines.find(f"{{{C_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{C_NS}}}spPr")
    for index, child in enumerate(list(gridlines)):
        if child.tag == f"{{{C_NS}}}extLst":
            gridlines.insert(index, shape_properties)
            return shape_properties
    gridlines.append(shape_properties)
    return shape_properties


def _chart_axis_major_gridlines_line(
    axis_element: ET.Element,
) -> ET.Element:
    shape_properties = _chart_axis_major_gridlines_shape_properties(axis_element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is not None:
        return line
    line = ET.Element(f"{{{A_NS}}}ln")
    shape_properties.append(line)
    return line


def _set_chart_axis_major_gridlines_line_fill_type(
    axis_element: ET.Element,
    fill_type: str,
) -> None:
    line = _chart_axis_major_gridlines_line(axis_element)
    if fill_type == "solid":
        _solid_fill_element(line)
        return
    if fill_type == "background":
        _no_fill_element(line)
        return
    raise ValueError(f"unsupported chart line fill type: {fill_type!r}")


def _set_chart_axis_major_gridlines_line_rgb(
    axis_element: ET.Element,
    rgb: str,
) -> None:
    line = _chart_axis_major_gridlines_line(axis_element)
    solid_fill = line.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        _solid_fill_element(line)
        solid_fill = line.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def _set_chart_axis_major_gridlines_line_width(
    axis_element: ET.Element,
    width: int,
) -> None:
    _chart_axis_major_gridlines_line(axis_element).set("w", str(width))


def _set_chart_axis_major_gridlines_line_dash(
    axis_element: ET.Element,
    dash_style: Any,
) -> None:
    line = _chart_axis_major_gridlines_line(axis_element)
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    if dash_style is None:
        if preset_dash is not None:
            line.remove(preset_dash)
        return
    if preset_dash is None:
        preset_dash = ET.Element(f"{{{A_NS}}}prstDash")
        line.append(preset_dash)
    preset_dash.set("val", str(dash_style))


def _set_chart_axis_delete(axis_element: ET.Element, deleted: bool) -> None:
    delete = axis_element.find(f"{{{C_NS}}}delete")
    if not deleted:
        if delete is not None:
            axis_element.remove(delete)
        return
    if delete is None:
        delete = ET.Element(f"{{{C_NS}}}delete")
        axis_element.insert(_chart_axis_insert_index(axis_element, "delete"), delete)
    delete.attrib.pop("val", None)


def _set_chart_axis_empty_child(
    axis_element: ET.Element,
    local_name: str,
    enabled: bool,
) -> None:
    child = axis_element.find(f"{{{C_NS}}}{local_name}")
    if not enabled:
        if child is not None:
            axis_element.remove(child)
        return
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        axis_element.insert(_chart_axis_insert_index(axis_element, local_name), child)


def _set_chart_axis_val_child(
    axis_element: ET.Element,
    local_name: str,
    value: str,
) -> None:
    child = axis_element.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        axis_element.insert(_chart_axis_insert_index(axis_element, local_name), child)
    child.set("val", value)


def _set_chart_axis_orientation(axis_element: ET.Element, reverse_order: bool) -> None:
    scaling = axis_element.find(f"{{{C_NS}}}scaling")
    if not reverse_order:
        if scaling is not None:
            orientation = scaling.find(f"{{{C_NS}}}orientation")
            if orientation is not None:
                scaling.remove(orientation)
        return
    scaling = _chart_axis_scaling_element(axis_element)
    orientation = scaling.find(f"{{{C_NS}}}orientation")
    if orientation is None:
        orientation = ET.Element(f"{{{C_NS}}}orientation")
        scaling.insert(
            _chart_axis_scaling_insert_index(scaling, "orientation"),
            orientation,
        )
    orientation.set("val", "maxMin")


def _set_chart_axis_scaling_bound(
    axis_element: ET.Element,
    local_name: str,
    value: Any,
) -> None:
    scaling = axis_element.find(f"{{{C_NS}}}scaling")
    if value is None:
        if scaling is not None:
            child = scaling.find(f"{{{C_NS}}}{local_name}")
            if child is not None:
                scaling.remove(child)
        return
    scaling = _chart_axis_scaling_element(axis_element)
    _set_chart_axis_scaling_val_child(scaling, local_name, str(float(value)))


def _set_chart_axis_optional_float_child(
    axis_element: ET.Element,
    local_name: str,
    value: Any,
) -> None:
    child = axis_element.find(f"{{{C_NS}}}{local_name}")
    if value is None:
        if child is not None:
            axis_element.remove(child)
        return
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        axis_element.insert(_chart_axis_insert_index(axis_element, local_name), child)
    child.set("val", str(float(value)))


def _set_chart_axis_int_child(
    axis_element: ET.Element,
    local_name: str,
    value: Any,
) -> None:
    child = axis_element.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        axis_element.insert(_chart_axis_insert_index(axis_element, local_name), child)
    child.set("val", str(int(value)))


def _chart_axis_num_fmt_element(axis_element: ET.Element) -> ET.Element:
    num_fmt = axis_element.find(f"{{{C_NS}}}numFmt")
    if num_fmt is not None:
        return num_fmt
    num_fmt = ET.Element(f"{{{C_NS}}}numFmt")
    axis_element.insert(_chart_axis_insert_index(axis_element, "numFmt"), num_fmt)
    return num_fmt


def _set_chart_axis_number_format(axis_element: ET.Element, format_code: str) -> None:
    num_fmt = _chart_axis_num_fmt_element(axis_element)
    num_fmt.set("formatCode", format_code)
    num_fmt.set("sourceLinked", "0")


def _set_chart_axis_number_format_source_linked(
    axis_element: ET.Element,
    source_linked: bool,
) -> None:
    num_fmt = _chart_axis_num_fmt_element(axis_element)
    if num_fmt.get("formatCode") is None:
        num_fmt.set("formatCode", "General")
    num_fmt.set("sourceLinked", "1" if source_linked else "0")


def _set_chart_axis_crosses(axis_element: ET.Element, value: str) -> None:
    crosses_at = axis_element.find(f"{{{C_NS}}}crossesAt")
    if crosses_at is not None:
        axis_element.remove(crosses_at)
    crosses = axis_element.find(f"{{{C_NS}}}crosses")
    if crosses is None:
        crosses = ET.Element(f"{{{C_NS}}}crosses")
        axis_element.insert(_chart_axis_insert_index(axis_element, "crosses"), crosses)
    crosses.set("val", value)


def _set_chart_axis_crosses_at(axis_element: ET.Element, value: Any) -> None:
    crosses = axis_element.find(f"{{{C_NS}}}crosses")
    if crosses is not None:
        axis_element.remove(crosses)
    crosses_at = axis_element.find(f"{{{C_NS}}}crossesAt")
    if value is None:
        if crosses_at is not None:
            axis_element.remove(crosses_at)
        return
    if crosses_at is None:
        crosses_at = ET.Element(f"{{{C_NS}}}crossesAt")
        axis_element.insert(
            _chart_axis_insert_index(axis_element, "crossesAt"),
            crosses_at,
        )
    crosses_at.set("val", str(float(value)))


def _chart_axis_text_default_run_properties(axis_element: ET.Element) -> ET.Element:
    text_properties = axis_element.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        axis_element.insert(_chart_axis_insert_index(axis_element, "txPr"), text_properties)
    run_properties = text_properties.find(
        f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )
    if run_properties is None:
        paragraph = text_properties.find(f"{{{A_NS}}}p")
        if paragraph is None:
            paragraph = ET.Element(f"{{{A_NS}}}p")
            text_properties.append(paragraph)
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        if paragraph_properties is None:
            paragraph_properties = ET.Element(f"{{{A_NS}}}pPr")
            paragraph.insert(0, paragraph_properties)
        run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
        if run_properties is None:
            run_properties = ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    return run_properties


def _set_chart_axis_tick_label_font_size(axis_element: ET.Element, value: Any) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    from .facade_values import emu_to_centipoints as _emu_to_centipoints

    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def _set_chart_axis_tick_label_font_bool(
    axis_element: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if bool(value) else "0")


def _set_chart_axis_tick_label_font_underline(
    axis_element: ET.Element,
    value: bool | None,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if bool(value) else "none")


def _set_chart_axis_tick_label_font_rgb(
    axis_element: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    if value is None:
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            run_properties.remove(solid_fill)
        return
    solid_fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_rgb(solid_fill, value)


def _set_chart_axis_tick_label_font_fill_type(
    axis_element: ET.Element,
    value: str,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    if value == "solid":
        if run_properties.find(f"{{{A_NS}}}solidFill") is None:
            _run_solid_fill_element(run_properties)
        no_fill = run_properties.find(f"{{{A_NS}}}noFill")
        if no_fill is not None:
            run_properties.remove(no_fill)
        return
    if value == "background":
        _run_no_fill_element(run_properties)
        return
    if value == "patterned":
        if run_properties.find(f"{{{A_NS}}}pattFill") is None:
            _run_pattern_fill_element(run_properties)
        return
    if value == "gradient":
        if run_properties.find(f"{{{A_NS}}}gradFill") is None:
            _run_gradient_fill_element(run_properties)
        return
    raise ValueError(f"unsupported chart tick-label font fill type: {value!r}")


def _set_chart_axis_tick_label_font_pattern(
    axis_element: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    _set_run_pattern_fill(run_properties, value)


def _set_chart_axis_tick_label_font_pattern_rgb(
    axis_element: ET.Element,
    color_tag: str,
    value: str | None,
) -> None:
    if value is None:
        return
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    _set_run_pattern_fill_color(run_properties, color_tag, value)


def _set_chart_axis_tick_label_font_gradient(
    axis_element: ET.Element,
    value: dict[str, Any],
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    _set_run_gradient_fill(run_properties, value)


def _set_chart_axis_tick_label_font_name(
    axis_element: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        run_properties.append(latin)
    latin.set("typeface", value)


def _set_chart_axis_tick_label_font_language_id(
    axis_element: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_axis_text_default_run_properties(axis_element)
    if value is None:
        run_properties.attrib.pop("lang", None)
        return
    run_properties.set("lang", value)


def _chart_axis_scaling_element(axis_element: ET.Element) -> ET.Element:
    scaling = axis_element.find(f"{{{C_NS}}}scaling")
    if scaling is not None:
        return scaling
    scaling = ET.Element(f"{{{C_NS}}}scaling")
    axis_element.insert(_chart_axis_insert_index(axis_element, "scaling"), scaling)
    return scaling


def _set_chart_axis_scaling_val_child(
    scaling: ET.Element,
    local_name: str,
    value: str,
) -> None:
    child = scaling.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        scaling.insert(_chart_axis_scaling_insert_index(scaling, local_name), child)
    child.set("val", value)


def _chart_axis_insert_index(axis_element: ET.Element, local_name: str) -> int:
    target_order = _CHART_AXIS_CHILD_INDEX.get(local_name)
    if target_order is None:
        return len(axis_element)
    for index, child in enumerate(list(axis_element)):
        child_order = _CHART_AXIS_CHILD_INDEX.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(axis_element)


def _chart_axis_scaling_insert_index(scaling: ET.Element, local_name: str) -> int:
    target_order = _CHART_AXIS_SCALING_CHILD_INDEX.get(local_name)
    if target_order is None:
        return len(scaling)
    for index, child in enumerate(list(scaling)):
        child_order = _CHART_AXIS_SCALING_CHILD_INDEX.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(scaling)
