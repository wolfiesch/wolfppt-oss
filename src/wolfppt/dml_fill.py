"""DrawingML fill XML helpers for presentation facade edits."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

_FILL_PROPERTY_TAGS = {
    f"{{{A_NS}}}noFill",
    f"{{{A_NS}}}solidFill",
    f"{{{A_NS}}}gradFill",
    f"{{{A_NS}}}blipFill",
    f"{{{A_NS}}}pattFill",
    f"{{{A_NS}}}grpFill",
}
_FONT_CHILD_TAGS = {
    f"{{{A_NS}}}latin",
    f"{{{A_NS}}}ea",
    f"{{{A_NS}}}cs",
    f"{{{A_NS}}}sym",
}
_DEFAULT_GRADIENT_STOPS = (
    (
        0.0,
        "accent1",
        (
            ("tint", "100000"),
            ("shade", "100000"),
            ("satMod", "130000"),
        ),
    ),
    (
        1.0,
        "accent1",
        (
            ("tint", "50000"),
            ("shade", "100000"),
            ("satMod", "350000"),
        ),
    ),
)


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def replace_fill_element(parent: ET.Element, tag_name: str) -> ET.Element:
    first_fill_index: int | None = None
    for index, child in enumerate(list(parent)):
        if child.tag not in _FILL_PROPERTY_TAGS:
            continue
        if first_fill_index is None:
            first_fill_index = index
        parent.remove(child)
    fill = ET.Element(f"{{{A_NS}}}{tag_name}")
    parent.insert(first_fill_index if first_fill_index is not None else len(parent), fill)
    return fill


def solid_fill_element(parent: ET.Element) -> ET.Element:
    solid_fill = replace_fill_element(parent, "solidFill")
    return solid_fill


def no_fill_element(parent: ET.Element) -> ET.Element:
    no_fill = replace_fill_element(parent, "noFill")
    return no_fill


def pattern_fill_element(parent: ET.Element) -> ET.Element:
    pattern_fill = replace_fill_element(parent, "pattFill")
    return pattern_fill


def existing_pattern_fill_element(parent: ET.Element) -> ET.Element:
    pattern_fill = parent.find(f"{{{A_NS}}}pattFill")
    if pattern_fill is not None:
        return pattern_fill
    return pattern_fill_element(parent)


def default_gradient_payload() -> dict[str, Any]:
    return {
        "angle": None,
        "stops": [
            {
                "position": position,
                "color": scheme_color_element(theme_color, modifiers),
            }
            for position, theme_color, modifiers in _DEFAULT_GRADIENT_STOPS
        ],
    }


def scheme_color_element(
    theme_color: str,
    modifiers: Sequence[tuple[str, str]] = (),
) -> ET.Element:
    color = ET.Element(f"{{{A_NS}}}schemeClr")
    color.set("val", theme_color)
    for tag, value in modifiers:
        ET.SubElement(color, f"{{{A_NS}}}{tag}").set("val", value)
    return color


def gradient_payload_from_fill_parent(parent: ET.Element) -> dict[str, Any] | None:
    gradient = parent.find(f"{{{A_NS}}}gradFill")
    if gradient is None:
        return None
    lin = gradient.find(f"{{{A_NS}}}lin")
    path = gradient.find(f"{{{A_NS}}}path")
    angle = None
    if lin is not None and lin.attrib.get("ang") is not None:
        clockwise_angle = int(lin.attrib["ang"]) / 60000.0
        angle = 0.0 if clockwise_angle == 0.0 else 360.0 - clockwise_angle
    stops = []
    for stop in gradient.findall(f"{{{A_NS}}}gsLst/{{{A_NS}}}gs"):
        stops.append(
            {
                "position": int(stop.attrib.get("pos", "0")) / 100000.0,
                "color": gradient_stop_color_element(stop),
            }
        )
    return {
        "angle": angle,
        "path": path.attrib.get("path") if path is not None else None,
        "stops": stops,
    }


def gradient_stop_color_element(stop: ET.Element) -> ET.Element:
    for child in stop:
        if _xml_local_name(child.tag).endswith("Clr"):
            return deepcopy(child)
    return scheme_color_element("accent1")


def set_shape_gradient_fill(
    shape_properties: ET.Element,
    gradient: dict[str, Any],
) -> None:
    gradient_fill = replace_fill_element(shape_properties, "gradFill")
    gradient_fill.set("rotWithShape", "1")
    stops = gradient.get("stops") or default_gradient_payload()["stops"]
    stop_list = ET.SubElement(gradient_fill, f"{{{A_NS}}}gsLst")
    for stop in stops:
        stop_list.append(gradient_stop_element(stop))
    linear = ET.SubElement(gradient_fill, f"{{{A_NS}}}lin")
    linear.set("scaled", "0")
    angle = gradient.get("angle")
    if angle is not None:
        linear.set("ang", str(gradient_openxml_angle(float(angle))))


def gradient_stop_element(stop: dict[str, Any]) -> ET.Element:
    position = float(stop.get("position", 0.0))
    element = ET.Element(f"{{{A_NS}}}gs")
    element.set("pos", str(int(round(position * 100000))))
    color = stop.get("color")
    if isinstance(color, ET.Element):
        element.append(deepcopy(color))
    else:
        element.append(scheme_color_element("accent1"))
    return element


def gradient_openxml_angle(angle: float) -> int:
    clockwise_angle = (360.0 - angle) % 360.0
    return int(round(clockwise_angle * 60000))


def pattern_color_element(pattern_fill: ET.Element, color_tag: str) -> ET.Element:
    color = pattern_fill.find(f"{{{A_NS}}}{color_tag}")
    if color is not None:
        return color
    color = ET.Element(f"{{{A_NS}}}{color_tag}")
    if color_tag == "fgClr":
        bg_color = pattern_fill.find(f"{{{A_NS}}}bgClr")
        if bg_color is not None:
            pattern_fill.insert(list(pattern_fill).index(bg_color), color)
            return color
    pattern_fill.append(color)
    return color


def set_color_choice_rgb(color_parent: ET.Element, rgb: str) -> None:
    color_parent.clear()
    color = ET.SubElement(color_parent, f"{{{A_NS}}}srgbClr")
    color.set("val", rgb)


def set_shape_solid_fill(
    shape_properties: ET.Element,
    color: str | dict[str, Any] | None = None,
) -> None:
    fill = solid_fill_element(shape_properties)
    if color is not None:
        set_solid_fill_color(fill, color)


def set_shape_no_fill(shape_properties: ET.Element) -> None:
    fill = no_fill_element(shape_properties)
    fill.clear()


def set_shape_pattern_fill(
    shape_properties: ET.Element,
    pattern: str | None,
) -> None:
    fill = pattern_fill_element(shape_properties)
    if pattern is None:
        fill.attrib.pop("prst", None)
        return
    fill.set("prst", pattern)


def set_shape_pattern_fill_color(
    shape_properties: ET.Element,
    color_tag: str,
    color_value: str | dict[str, Any],
) -> None:
    fill = existing_pattern_fill_element(shape_properties)
    color = pattern_color_element(fill, color_tag)
    set_solid_fill_color(color, color_value)


def run_solid_fill_element(run_properties: ET.Element) -> ET.Element:
    return _replace_run_fill_element(run_properties, "solidFill")


def run_no_fill_element(run_properties: ET.Element) -> ET.Element:
    return _replace_run_fill_element(run_properties, "noFill")


def run_pattern_fill_element(run_properties: ET.Element) -> ET.Element:
    return _replace_run_fill_element(run_properties, "pattFill")


def run_gradient_fill_element(run_properties: ET.Element) -> ET.Element:
    return _replace_run_fill_element(run_properties, "gradFill")


def existing_run_pattern_fill_element(run_properties: ET.Element) -> ET.Element:
    pattern_fill = run_properties.find(f"{{{A_NS}}}pattFill")
    if pattern_fill is not None:
        return pattern_fill
    return run_pattern_fill_element(run_properties)


def _replace_run_fill_element(
    run_properties: ET.Element,
    tag_name: str,
) -> ET.Element:
    first_fill_index: int | None = None
    first_font_index: int | None = None
    for index, child in enumerate(list(run_properties)):
        if child.tag in _FILL_PROPERTY_TAGS:
            if first_fill_index is None:
                first_fill_index = index
            run_properties.remove(child)
        elif child.tag in _FONT_CHILD_TAGS and first_font_index is None:
            first_font_index = index
    if first_fill_index is not None:
        insert_at = first_fill_index
    elif first_font_index is not None:
        insert_at = first_font_index
    else:
        insert_at = len(run_properties)
    fill = ET.Element(f"{{{A_NS}}}{tag_name}")
    run_properties.insert(insert_at, fill)
    return fill


def set_solid_fill_rgb(fill: ET.Element, rgb: str) -> None:
    fill.clear()
    color = ET.SubElement(fill, f"{{{A_NS}}}srgbClr")
    color.set("val", rgb)


def set_run_pattern_fill(run_properties: ET.Element, pattern: str | None) -> None:
    fill = run_pattern_fill_element(run_properties)
    if pattern is None:
        fill.attrib.pop("prst", None)
        return
    fill.set("prst", pattern)


def set_run_pattern_fill_color(
    run_properties: ET.Element,
    color_tag: str,
    color_value: str | dict[str, Any],
) -> None:
    fill = existing_run_pattern_fill_element(run_properties)
    color = pattern_color_element(fill, color_tag)
    set_solid_fill_color(color, color_value)


def set_run_gradient_fill(
    run_properties: ET.Element,
    gradient: dict[str, Any],
) -> None:
    gradient_fill = run_gradient_fill_element(run_properties)
    gradient_fill.set("rotWithShape", "1")
    stops = gradient.get("stops") or default_gradient_payload()["stops"]
    stop_list = ET.SubElement(gradient_fill, f"{{{A_NS}}}gsLst")
    for stop in stops:
        stop_list.append(gradient_stop_element(stop))
    linear = ET.SubElement(gradient_fill, f"{{{A_NS}}}lin")
    linear.set("scaled", "0")
    angle = gradient.get("angle")
    if angle is not None:
        linear.set("ang", str(gradient_openxml_angle(float(angle))))


def set_solid_fill_rgb_with_brightness(
    fill: ET.Element,
    rgb: str,
    brightness: float = 0.0,
) -> None:
    fill.clear()
    color = ET.SubElement(fill, f"{{{A_NS}}}srgbClr")
    color.set("val", rgb)
    for tag, value in brightness_modifiers(brightness):
        ET.SubElement(color, f"{{{A_NS}}}{tag}").set("val", value)


def set_solid_fill_scheme(
    fill: ET.Element,
    theme_color: str,
    brightness: float = 0.0,
) -> None:
    fill.clear()
    color = scheme_color_element(theme_color, brightness_modifiers(brightness))
    fill.append(color)


def set_solid_fill_color(fill: ET.Element, color: str | dict[str, Any]) -> None:
    if isinstance(color, str):
        set_solid_fill_rgb(fill, color)
        return
    if color.get("type") == "rgb":
        set_solid_fill_rgb_with_brightness(
            fill,
            str(color["value"]),
            float(color.get("brightness", 0.0)),
        )
        return
    if color.get("type") != "scheme":
        raise ValueError(f"unsupported color payload: {color!r}")
    set_solid_fill_scheme(
        fill,
        str(color["value"]),
        float(color.get("brightness", 0.0)),
    )


def brightness_modifiers(brightness: float) -> tuple[tuple[str, str], ...]:
    if not -1.0 <= brightness <= 1.0:
        raise ValueError("brightness must be between -1.0 and 1.0")
    if brightness == 0:
        return ()
    if brightness > 0:
        return (
            ("lumMod", str(round((1.0 - brightness) * 100000))),
            ("lumOff", str(round(brightness * 100000))),
        )
    return (("lumMod", str(round((1.0 + brightness) * 100000))),)


def fill_type_from_xml_children(parent: ET.Element) -> str | None:
    for child in parent:
        if child.tag == f"{{{A_NS}}}solidFill":
            return "solid"
        if child.tag == f"{{{A_NS}}}noFill":
            return "background"
        if child.tag == f"{{{A_NS}}}pattFill":
            return "patterned"
        if child.tag == f"{{{A_NS}}}gradFill":
            return "gradient"
        if child.tag == f"{{{A_NS}}}blipFill":
            return "picture"
        if child.tag == f"{{{A_NS}}}grpFill":
            return "group"
    return None


def fill_rgb_from_xml_children(parent: ET.Element, pattern_role: str) -> str | None:
    solid = parent.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if solid is not None:
        value = solid.attrib.get("val")
        return value.upper() if value else None
    pattern = parent.find(
        f"{{{A_NS}}}pattFill/{{{A_NS}}}{pattern_role}/{{{A_NS}}}srgbClr"
    )
    if pattern is None:
        return None
    value = pattern.attrib.get("val")
    return value.upper() if value else None
