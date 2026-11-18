"""Chart element fill and line formatting XML helpers.

Every chart owner of a ``c:spPr`` (series, data points, markers, titles, legends,
axes, gridlines, ...) is written through this module so fill and outline edits keep
DrawingML schema order inside ``c:spPr`` and ``a:ln`` and accept the same color
payloads: an ``RRGGBB`` string or a `dml_fill.color_element` spec, which
`chart_color_payload` produces losslessly from any supported color element.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_xml_utils import A_NS, C_NS
from .chart_xml_utils import xml_local_name as _xml_local_name
from .dml_fill import (
    color_element as _color_element,
)
from .dml_fill import (
    pattern_color_element as _pattern_color_element,
)
from .dml_fill import (
    replace_fill_element as _replace_fill_element,
)
from .dml_fill import (
    set_shape_gradient_fill as _set_shape_gradient_fill,
)

#: Format properties in the order `set_chart_element_format_properties` applies them.
CHART_FORMAT_PROPERTY_ORDER = (
    "fill_type",
    "fill_rgb",
    "fill_gradient",
    "fill_pattern",
    "fill_pattern_fore_rgb",
    "fill_pattern_back_rgb",
    "line_fill_type",
    "line_pattern",
    "line_pattern_fore_rgb",
    "line_pattern_back_rgb",
    "line_rgb",
    "line_width",
    "line_dash",
    "line_compound",
    "line_head_end",
    "line_tail_end",
)
CHART_FORMAT_PROPERTIES = frozenset(CHART_FORMAT_PROPERTY_ORDER)
#: DrawingML ``ST_CompoundLine`` tokens accepted as ``a:ln@cmpd``.
CHART_LINE_COMPOUNDS = frozenset({"sng", "dbl", "thickThin", "thinThick", "tri"})
#: Line-end spec keys and the ``a:headEnd``/``a:tailEnd`` attributes they write.
_LINE_END_ATTRIBUTES = (("type", "type"), ("width", "w"), ("length", "len"))

_FILL_TAGS = frozenset(
    f"{{{A_NS}}}{name}"
    for name in ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")
)
_LINE_FILL_TAGS = frozenset(
    f"{{{A_NS}}}{name}" for name in ("noFill", "solidFill", "gradFill", "pattFill")
)
#: ``c:spPr`` children that follow the fill choice, in schema order.
_SHAPE_PROPERTIES_AFTER_FILL = ("ln", "effectLst", "effectDag", "scene3d", "sp3d", "extLst")
#: ``a:ln`` children that follow the dash choice, in schema order.
_LINE_AFTER_DASH = ("round", "bevel", "miter", "headEnd", "tailEnd", "extLst")
#: ``a:ln`` children that follow the line fill choice, in schema order.
_LINE_AFTER_FILL = ("prstDash", "custDash", *_LINE_AFTER_DASH)

_AXIS_BEFORE_SHAPE_PROPERTIES = frozenset(
    {
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
    }
)
#: Children that precede ``c:spPr`` in each chart owner type (ECMA-376 Part 1 §21.2.2).
_BEFORE_SHAPE_PROPERTIES: dict[str, frozenset[str]] = {
    "ser": frozenset({"idx", "order", "tx"}),
    "dPt": frozenset({"idx", "invertIfNegative", "marker", "bubble3D", "explosion"}),
    "marker": frozenset({"symbol", "size"}),
    "title": frozenset({"tx", "layout", "overlay"}),
    "legend": frozenset({"legendPos", "legendEntry", "layout", "overlay"}),
    "dispUnitsLbl": frozenset({"layout", "tx"}),
    "dLbl": frozenset({"idx", "delete", "layout", "tx", "numFmt"}),
    "dLbls": frozenset({"dLbl", "delete", "numFmt"}),
    "trendline": frozenset({"name"}),
    "errBars": frozenset(
        {"errDir", "errBarType", "errValType", "noEndCap", "plus", "minus", "val"}
    ),
    "majorGridlines": frozenset(),
    "minorGridlines": frozenset(),
    "catAx": _AXIS_BEFORE_SHAPE_PROPERTIES,
    "valAx": _AXIS_BEFORE_SHAPE_PROPERTIES,
    "dateAx": _AXIS_BEFORE_SHAPE_PROPERTIES,
    "serAx": _AXIS_BEFORE_SHAPE_PROPERTIES,
}
_GENERIC_CHILD_ORDER = {
    "idx": 0,
    "order": 1,
    "tx": 2,
    "layout": 3,
    "overlay": 4,
    "spPr": 5,
    "txPr": 6,
    "extLst": 7,
}


def chart_color_payload(color: ET.Element) -> dict[str, str]:
    """Queue a validated detached color losslessly as a serialized color spec."""
    return {"type": "xml", "value": ET.tostring(color, encoding="unicode")}


def chart_color_element(value: Any) -> ET.Element:
    """Build the DrawingML color of a queued chart color payload."""
    if isinstance(value, dict):
        return _color_element(value)
    return ET.Element(f"{{{A_NS}}}srgbClr", {"val": str(value)})


def replace_chart_color_choice(holder: ET.Element, value: Any) -> None:
    """Replace the color inside ``a:solidFill``, ``a:fgClr`` or ``a:bgClr``."""
    color = chart_color_element(value)
    for child in list(holder):
        holder.remove(child)
    holder.append(color)


def set_chart_element_format_properties(
    element: ET.Element,
    properties: dict[str, Any],
) -> None:
    """Apply recognised format properties in `CHART_FORMAT_PROPERTY_ORDER`."""
    for attr in CHART_FORMAT_PROPERTY_ORDER:
        if attr in properties:
            set_chart_element_format_property(element, attr, properties[attr], properties)


def set_chart_element_format_properties_in_order(
    element: ET.Element,
    properties: dict[str, Any],
    owner: str,
) -> None:
    """Apply format properties in edit order; any other property is refused."""
    for attr, value in properties.items():
        if attr not in CHART_FORMAT_PROPERTIES:
            raise ValueError(f"unsupported chart {owner} format property: {attr!r}")
        set_chart_element_format_property(element, attr, value, properties)


def set_chart_element_format_property(
    element: ET.Element,
    attr: str,
    value: Any,
    properties: dict[str, Any] | None = None,
) -> None:
    """Apply one `CHART_FORMAT_PROPERTIES` member to ``element``'s ``c:spPr``.

    ``properties`` is the edit carrying ``attr``; a gradient fill type takes its
    stops from that edit's ``fill_gradient``.
    """
    if attr == "fill_type":
        if value == "solid":
            set_chart_element_solid_fill(element)
        elif value == "background":
            set_chart_element_background_fill(element)
        elif value == "patterned":
            set_chart_element_pattern_fill(element, None)
        elif value == "gradient":
            set_chart_element_gradient_fill(element, (properties or {}).get("fill_gradient"))
        else:
            raise ValueError(f"unsupported chart fill type: {value!r}")
    elif attr == "fill_rgb":
        set_chart_element_fill_rgb(element, value)
    elif attr == "fill_gradient":
        set_chart_element_gradient_fill(element, value)
    elif attr == "fill_pattern":
        set_chart_element_pattern_fill(element, value)
    elif attr == "fill_pattern_fore_rgb":
        set_chart_element_pattern_rgb(element, "fgClr", value)
    elif attr == "fill_pattern_back_rgb":
        set_chart_element_pattern_rgb(element, "bgClr", value)
    elif attr == "line_fill_type":
        set_chart_element_line_fill_type(element, str(value))
    elif attr == "line_pattern":
        set_chart_element_line_pattern_fill(element, value)
    elif attr == "line_pattern_fore_rgb":
        set_chart_element_line_pattern_rgb(element, "fgClr", value)
    elif attr == "line_pattern_back_rgb":
        set_chart_element_line_pattern_rgb(element, "bgClr", value)
    elif attr == "line_rgb":
        set_chart_element_line_rgb(element, value)
    elif attr == "line_width":
        set_chart_element_line_width(element, int(value))
    elif attr == "line_dash":
        set_chart_element_line_dash(element, value)
    elif attr == "line_compound":
        set_chart_element_line_compound(element, value)
    elif attr == "line_head_end":
        set_chart_element_line_end(element, "headEnd", value)
    elif attr == "line_tail_end":
        set_chart_element_line_end(element, "tailEnd", value)
    else:
        raise ValueError(f"unsupported chart format property: {attr!r}")


def chart_element_shape_properties(element: ET.Element) -> ET.Element:
    shape_properties = element.find(f"{{{C_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{C_NS}}}spPr")
    element.insert(chart_element_sppr_insert_index(element), shape_properties)
    return shape_properties


def chart_element_sppr_insert_index(element: ET.Element) -> int:
    before = _BEFORE_SHAPE_PROPERTIES.get(_xml_local_name(element.tag))
    if before is not None:
        for index, child in enumerate(list(element)):
            if _xml_local_name(child.tag) not in before:
                return index
        return len(element)
    target_order = _GENERIC_CHILD_ORDER["spPr"]
    for index, child in enumerate(list(element)):
        child_order = _GENERIC_CHILD_ORDER.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(element)


def _place(parent: ET.Element, child: ET.Element, successors: tuple[str, ...]) -> None:
    """Move ``child`` before the first of its DrawingML schema ``successors``."""
    parent.remove(child)
    tags = {f"{{{A_NS}}}{name}" for name in successors}
    for index, existing in enumerate(list(parent)):
        if existing.tag in tags:
            parent.insert(index, child)
            return
    parent.append(child)


def _replace_fill(parent: ET.Element, tag_name: str, fill_tags: frozenset[str]) -> ET.Element:
    for child in list(parent):
        if child.tag in fill_tags:
            parent.remove(child)
    fill = ET.Element(f"{{{A_NS}}}{tag_name}")
    parent.append(fill)
    successors = _LINE_AFTER_FILL if parent.tag == f"{{{A_NS}}}ln" else _SHAPE_PROPERTIES_AFTER_FILL
    _place(parent, fill, successors)
    return fill


def _pattern_fill(parent: ET.Element, pattern: Any) -> None:
    fill = _replace_fill_element(parent, "pattFill")
    successors = _LINE_AFTER_FILL if parent.tag == f"{{{A_NS}}}ln" else _SHAPE_PROPERTIES_AFTER_FILL
    _place(parent, fill, successors)
    if pattern is None:
        fill.attrib.pop("prst", None)
    else:
        fill.set("prst", str(pattern))


def _pattern_color(parent: ET.Element, color_tag: str, value: Any) -> None:
    color = chart_color_element(value)
    fill = parent.find(f"{{{A_NS}}}pattFill")
    if fill is None:
        _pattern_fill(parent, None)
        fill = parent.find(f"{{{A_NS}}}pattFill")
    assert fill is not None
    holder = _pattern_color_element(fill, color_tag)
    for child in list(holder):
        holder.remove(child)
    holder.append(color)


def _solid_color(parent: ET.Element, fill_tags: frozenset[str], value: Any) -> None:
    color = chart_color_element(value)
    solid_fill = parent.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        solid_fill = _replace_fill(parent, "solidFill", fill_tags)
    for child in list(solid_fill):
        solid_fill.remove(child)
    solid_fill.append(color)


def set_chart_element_solid_fill(element: ET.Element) -> None:
    _replace_fill(chart_element_shape_properties(element), "solidFill", _FILL_TAGS)


def set_chart_element_fill_rgb(element: ET.Element, rgb: Any) -> None:
    _solid_color(chart_element_shape_properties(element), _FILL_TAGS, rgb)


def set_chart_element_pattern_fill(element: ET.Element, pattern: Any) -> None:
    _pattern_fill(chart_element_shape_properties(element), pattern)


def set_chart_element_pattern_rgb(
    element: ET.Element,
    color_tag: str,
    rgb: Any,
) -> None:
    _pattern_color(chart_element_shape_properties(element), color_tag, rgb)


def set_chart_element_background_fill(element: ET.Element) -> None:
    _replace_fill(chart_element_shape_properties(element), "noFill", _FILL_TAGS)


def set_chart_element_gradient_fill(element: ET.Element, gradient: Any) -> None:
    shape_properties = chart_element_shape_properties(element)
    _set_shape_gradient_fill(shape_properties, gradient if isinstance(gradient, dict) else {})
    fill = shape_properties.find(f"{{{A_NS}}}gradFill")
    assert fill is not None
    _place(shape_properties, fill, _SHAPE_PROPERTIES_AFTER_FILL)


def chart_element_line(element: ET.Element) -> ET.Element:
    shape_properties = chart_element_shape_properties(element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.SubElement(shape_properties, f"{{{A_NS}}}ln")
        _place(shape_properties, line, _SHAPE_PROPERTIES_AFTER_FILL[1:])
    return line


def set_chart_element_line_fill_type(element: ET.Element, fill_type: str) -> None:
    line = chart_element_line(element)
    if fill_type == "solid":
        _replace_fill(line, "solidFill", _LINE_FILL_TAGS)
    elif fill_type == "background":
        _replace_fill(line, "noFill", _LINE_FILL_TAGS)
    elif fill_type == "patterned":
        _pattern_fill(line, None)
    else:
        raise ValueError(f"unsupported chart line fill type: {fill_type!r}")


def set_chart_element_line_pattern_fill(element: ET.Element, pattern: Any) -> None:
    _pattern_fill(chart_element_line(element), pattern)


def set_chart_element_line_pattern_rgb(
    element: ET.Element,
    color_tag: str,
    rgb: Any,
) -> None:
    _pattern_color(chart_element_line(element), color_tag, rgb)


def set_chart_element_line_rgb(element: ET.Element, rgb: Any) -> None:
    _solid_color(chart_element_line(element), _LINE_FILL_TAGS, rgb)


def set_chart_element_line_width(element: ET.Element, width: int) -> None:
    chart_element_line(element).set("w", str(width))


def set_chart_element_line_dash(element: ET.Element, dash_style: Any) -> None:
    line = chart_element_line(element)
    custom_dash = line.find(f"{{{A_NS}}}custDash")
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    if dash_style is None:
        if preset_dash is not None:
            line.remove(preset_dash)
        return
    if custom_dash is not None:
        line.remove(custom_dash)
    if preset_dash is None:
        preset_dash = ET.SubElement(line, f"{{{A_NS}}}prstDash")
        _place(line, preset_dash, _LINE_AFTER_DASH)
    preset_dash.set("val", str(dash_style))


def _existing_chart_element_line(element: ET.Element) -> ET.Element | None:
    shape_properties = element.find(f"{{{C_NS}}}spPr")
    return None if shape_properties is None else shape_properties.find(f"{{{A_NS}}}ln")


def set_chart_element_line_compound(element: ET.Element, compound: Any) -> None:
    """Set ``a:ln@cmpd`` to an ``ST_CompoundLine`` token; ``None`` removes it."""
    if compound is None:
        line = _existing_chart_element_line(element)
        if line is not None:
            line.attrib.pop("cmpd", None)
        return
    if compound not in CHART_LINE_COMPOUNDS:
        raise ValueError(f"unsupported chart line compound style: {compound!r}")
    chart_element_line(element).set("cmpd", str(compound))


def set_chart_element_line_end(element: ET.Element, end_name: str, spec: Any) -> None:
    """Replace ``a:headEnd`` or ``a:tailEnd`` from a ``type``/``width``/``length`` spec.

    ``None`` (or a spec without values) removes the end. The new end keeps schema
    order: after the dash and join choices, ``a:headEnd`` before ``a:tailEnd``.
    """
    if end_name not in {"headEnd", "tailEnd"}:
        raise ValueError(f"unsupported chart line end: {end_name!r}")
    attributes = (
        {}
        if spec is None
        else {xml: str(spec[key]) for key, xml in _LINE_END_ATTRIBUTES if spec.get(key) is not None}
    )
    line = chart_element_line(element) if attributes else _existing_chart_element_line(element)
    if line is None:
        return
    for existing in line.findall(f"{{{A_NS}}}{end_name}"):
        line.remove(existing)
    if not attributes:
        return
    end = ET.SubElement(line, f"{{{A_NS}}}{end_name}", attributes)
    _place(line, end, ("tailEnd", "extLst") if end_name == "headEnd" else ("extLst",))
