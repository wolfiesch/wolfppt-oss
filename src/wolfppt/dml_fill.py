"""DrawingML fill XML helpers for presentation facade edits."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from copy import deepcopy
from enum import StrEnum
from typing import Any
from xml.etree import ElementTree as ET

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class GradientFillRefusal(ValueError):
    """An unsupported gradient edit was refused before replacing its fill."""


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
    """Read a ``a:gradFill`` into the editable payload `set_shape_gradient_fill` writes.

    Besides angle and stops, the payload carries the path shade (``circle``,
    ``rect`` or ``shape``; ``None`` for linear), its focus rectangle, the tile
    rectangle, the flip mode and the rotate-with-shape and scaled flags, so a
    payload read here and written back keeps a radial, rectangular or shape
    path gradient instead of flattening it to a linear one.
    """
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
                "position": _color_percentage(stop.attrib.get("pos", "0")),
                "color": gradient_stop_color_element(stop),
            }
        )
    fill_to_rect = None
    if path is not None:
        focus = path.find(f"{{{A_NS}}}fillToRect")
        fill_to_rect = None if focus is None else _relative_rect_from_xml(focus)
    tile = gradient.find(f"{{{A_NS}}}tileRect")
    return {
        "angle": angle,
        "path": path.attrib.get("path") if path is not None else None,
        "stops": stops,
        "fill_to_rect": fill_to_rect,
        "tile_rect": None if tile is None else _relative_rect_from_xml(tile),
        "flip": _stored_mirror_mode(gradient.attrib.get("flip")),
        "rot_with_shape": gradient.attrib.get("rotWithShape", "1") in {"1", "true"},
        "scaled": lin is not None and lin.attrib.get("scaled") in {"1", "true"},
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
    """Replace the fill of ``shape_properties`` with the gradient ``gradient``.

    ``gradient`` keys: ``stops`` (``position`` 0..1 and a colour element or
    `color_element` spec), ``angle`` (linear, degrees counter-clockwise),
    ``path`` (``None`` for linear, else ``circle`` = radial, ``rect`` =
    rectangular, ``shape`` = shape path), ``direction`` (a
    `GRADIENT_DIRECTIONS` preset, path gradients only), ``fill_to_rect`` (the
    focus rectangle) and ``tile_rect`` as ``(left, top, right, bottom)`` inset
    fractions or a mapping with those keys, ``flip`` (a `TileMirrorMode` or its
    token ``none``, ``x``, ``y``, ``xy``), ``rot_with_shape`` (default ``True``)
    and ``scaled``.

    Invalid payloads raise `GradientFillRefusal` before the original fill changes;
    an unknown mirror mode raises one that is also a `TileMirrorModeRefusal`.
    """
    gradient_fill = ET.Element(f"{{{A_NS}}}gradFill")
    _write_gradient_fill(gradient_fill, gradient)
    fill = replace_fill_element(shape_properties, "gradFill")
    fill.attrib.update(gradient_fill.attrib)
    fill.extend(gradient_fill)


def _write_gradient_fill(gradient_fill: ET.Element, gradient: dict[str, Any]) -> None:
    if not isinstance(gradient, dict):
        raise GradientFillRefusal("gradient payload must be a mapping")
    try:
        _populate_gradient_fill(gradient_fill, gradient)
    except GradientFillRefusal:
        raise
    except (ValueError, TypeError, OverflowError) as error:
        raise GradientFillRefusal(str(error)) from error


def _populate_gradient_fill(gradient_fill: ET.Element, gradient: dict[str, Any]) -> None:
    path = gradient.get("path")
    if path not in (None, "linear", *GRADIENT_PATH_SHADES):
        raise ValueError(
            f"gradient path must be one of {', '.join(GRADIENT_PATH_SHADES)} "
            f"or None for linear, got {path!r}"
        )
    if path == "linear":
        path = None
    direction = gradient.get("direction")
    fill_to_rect = gradient.get("fill_to_rect")
    tile_rect = gradient.get("tile_rect")
    if direction is not None:
        if fill_to_rect is not None or tile_rect is not None:
            raise ValueError("give either a gradient direction preset or fill_to_rect/tile_rect")
        if direction not in GRADIENT_DIRECTIONS:
            raise ValueError(
                "gradient direction must be one of "
                f"{', '.join(GRADIENT_DIRECTIONS)}, got {direction!r}"
            )
        fill_to_rect, tile_rect = GRADIENT_DIRECTIONS[direction]
    if path is None and fill_to_rect is not None:
        raise ValueError(
            "a gradient direction or focus rectangle needs a circle, rect or shape path"
        )
    if path is not None and gradient.get("angle") is not None:
        raise ValueError("a path gradient has no linear angle")
    focus = None if fill_to_rect is None else _relative_rect(fill_to_rect, "fill_to_rect")
    tile = None if tile_rect is None else _relative_rect(tile_rect, "tile_rect")
    flip = gradient.get("flip")
    if flip is not None:
        try:
            mode = tile_mirror_mode(flip, "gradient flip")
        except TileMirrorModeRefusal as error:
            raise _GradientTileMirrorModeRefusal(str(error)) from None
        gradient_fill.set("flip", mode.value)
    rot_with_shape = gradient.get("rot_with_shape", True)
    gradient_fill.set("rotWithShape", "1" if rot_with_shape else "0")
    stops = gradient.get("stops") or default_gradient_payload()["stops"]
    stop_list = ET.SubElement(gradient_fill, f"{{{A_NS}}}gsLst")
    for stop in stops:
        stop_list.append(gradient_stop_element(stop))
    if path is None:
        linear = ET.SubElement(gradient_fill, f"{{{A_NS}}}lin")
        linear.set("scaled", "1" if gradient.get("scaled") else "0")
        angle = gradient.get("angle")
        if angle is not None:
            linear.set("ang", str(gradient_openxml_angle(float(angle))))
    else:
        shade = ET.SubElement(gradient_fill, f"{{{A_NS}}}path")
        shade.set("path", path)
        if focus is not None:
            _set_relative_rect(ET.SubElement(shade, f"{{{A_NS}}}fillToRect"), focus)
    if tile is not None:
        _set_relative_rect(ET.SubElement(gradient_fill, f"{{{A_NS}}}tileRect"), tile)


def gradient_direction(parent: ET.Element) -> str | None:
    """Return the `GRADIENT_DIRECTIONS` preset of the path gradient in ``parent``."""
    payload = gradient_payload_from_fill_parent(parent)
    if payload is None or payload["path"] is None:
        return None
    rects = (payload["fill_to_rect"] or _ZERO_RECT, payload["tile_rect"] or _ZERO_RECT)
    for name, preset in GRADIENT_DIRECTIONS.items():
        if rects == preset:
            return name
    return None


def _relative_rect(value: Any, name: str) -> tuple[float, float, float, float]:
    if isinstance(value, dict):
        unknown = set(value) - {"left", "top", "right", "bottom"}
        if unknown:
            raise ValueError(f"{name} has unknown keys: {', '.join(sorted(unknown))}")
        value = tuple(value.get(key, 0.0) for key in ("left", "top", "right", "bottom"))
    if not isinstance(value, Sequence) or isinstance(value, str) or len(value) != 4:
        raise ValueError(f"{name} must be (left, top, right, bottom) fractions")
    insets = []
    for inset in value:
        if isinstance(inset, bool) or not isinstance(inset, (int, float)):
            raise ValueError(f"{name} insets must be numbers, got {inset!r}")
        if not math.isfinite(inset) or not -21474.0 < inset < 21474.0:
            raise ValueError(f"{name} inset {inset!r} is out of range")
        insets.append(float(inset))
    return (insets[0], insets[1], insets[2], insets[3])


def _set_relative_rect(element: ET.Element, rect: tuple[float, float, float, float]) -> None:
    for key, inset in zip(("l", "t", "r", "b"), rect, strict=True):
        if inset != 0.0:
            element.set(key, str(round(inset * 100000)))


def _relative_rect_from_xml(element: ET.Element) -> tuple[float, float, float, float]:
    left, top, right, bottom = (
        _color_percentage(element.get(key, "0")) for key in ("l", "t", "r", "b")
    )
    return (left, top, right, bottom)


def gradient_stop_element(stop: dict[str, Any]) -> ET.Element:
    if not isinstance(stop, dict):
        raise GradientFillRefusal("gradient stop must be a mapping")
    try:
        position = float(stop.get("position", 0.0))
    except (ValueError, TypeError, OverflowError) as error:
        raise GradientFillRefusal("gradient stop position must be a finite fraction") from error
    if not 0.0 <= position <= 1.0:
        raise GradientFillRefusal(
            f"gradient stop position must be between 0.0 and 1.0, got {position!r}"
        )
    element = ET.Element(f"{{{A_NS}}}gs")
    element.set("pos", str(round(position * 100000)))
    color = stop.get("color")
    if isinstance(color, ET.Element):
        element.append(deepcopy(color))
    elif isinstance(color, dict):
        element.append(color_element(color))
    elif color is None:
        element.append(scheme_color_element("accent1"))
    else:
        raise GradientFillRefusal(f"unsupported gradient stop color: {color!r}")
    return element


def gradient_openxml_angle(angle: float) -> int:
    """Quantize a finite angle to the DrawingML range, including the wrap boundary."""
    if not math.isfinite(angle):
        raise GradientFillRefusal("gradient angle must be finite")
    clockwise_angle = (360.0 - angle) % 360.0
    return round(clockwise_angle * 60000) % 21600000


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
    """Replace a run fill with a validated gradient, ``gradient`` as for shapes.

    Invalid payloads raise `GradientFillRefusal` without replacing the run's fill.
    """
    gradient_fill = ET.Element(f"{{{A_NS}}}gradFill")
    _write_gradient_fill(gradient_fill, gradient)
    fill = run_gradient_fill_element(run_properties)
    fill.attrib.update(gradient_fill.attrib)
    fill.extend(gradient_fill)


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
    """Fill ``fill`` with an RGB hex string or a `color_element` spec."""
    if isinstance(color, str):
        set_solid_fill_rgb(fill, color)
        return
    element = color_element(color)
    fill.clear()
    fill.append(element)


def color_element(spec: dict[str, Any]) -> ET.Element:
    """Build an editable DrawingML colour element from ``spec``.

    ``type`` selects the colour: ``rgb`` (``value`` ``RRGGBB``), ``scheme``
    (``value`` a theme slot such as ``accent1``), ``preset`` (``value`` a preset
    colour name) or ``system`` (``value`` a system colour such as ``windowText``
    plus ``last_color``, the ``RRGGBB`` the colour last resolved to, which is what
    a reader without that machine palette shows). ``brightness`` (-1..1, rgb and
    scheme) writes PowerPoint's luminance pair; ``transforms`` is the colour's
    ordered transform list as accepted by `set_color_transforms`.
    """
    if not isinstance(spec, dict):
        raise ValueError(f"unsupported color payload: {spec!r}")
    kind = spec.get("type")
    value = spec.get("value")
    if kind == "xml":
        if set(spec) != {"type", "value"} or not isinstance(value, str):
            raise ValueError("XML color payload requires a serialized color only")
        try:
            element = ET.fromstring(value)
        except ET.ParseError as error:
            raise ValueError("invalid XML color payload") from error
        validate_text_color_element(element)
        return element
    if kind == "rgb":
        _validate_color_hex(str(value))
        element = ET.Element(f"{{{A_NS}}}srgbClr", {"val": str(value)})
    elif kind == "scheme":
        element = scheme_color_element(str(value))
    elif kind == "preset":
        if value not in _PRESET_COLOR_NAMES:
            raise ValueError(f"invalid preset color: {value!r}")
        element = ET.Element(f"{{{A_NS}}}prstClr", {"val": value})
    elif kind == "system":
        element = system_color_element(str(value), spec.get("last_color"))
    else:
        raise ValueError(f"unsupported color payload: {spec!r}")
    brightness = float(spec.get("brightness", 0.0))
    if brightness != 0.0:
        if kind not in {"rgb", "scheme"}:
            raise ValueError("brightness applies to rgb and scheme colors")
        set_color_brightness(element, brightness)
    transforms = spec.get("transforms")
    if transforms:
        set_color_transforms(element, [*color_transforms(element), *transforms])
    validate_text_color_element(element)
    return element


def color_payload_from_element(color: ET.Element) -> dict[str, Any]:
    """Preserve a supported color's base and ordered transforms in an edit payload."""
    validate_text_color_element(color)
    kinds = {"srgbClr": "rgb", "schemeClr": "scheme", "prstClr": "preset", "sysClr": "system"}
    kind = kinds.get(_xml_local_name(color.tag))
    if kind is None:
        return {"type": "xml", "value": ET.tostring(color, encoding="unicode")}
    payload: dict[str, Any] = {
        "type": kind,
        "value": color.get("val"),
        "transforms": color_transforms(color),
    }
    if kind == "system" and color.get("lastClr") is not None:
        payload["last_color"] = color.get("lastClr")
    return payload


def system_color_element(
    name: str,
    last_color: str | None = None,
    transforms: Sequence[Any] = (),
) -> ET.Element:
    """Build ``a:sysClr`` for system colour ``name`` with its stored last colour."""
    if name not in _SYSTEM_COLOR_NAMES:
        raise ValueError(f"invalid system color: {name!r}")
    element = ET.Element(f"{{{A_NS}}}sysClr", {"val": name})
    if last_color is not None:
        _validate_color_hex(str(last_color))
        element.set("lastClr", str(last_color).upper())
    set_color_transforms(element, transforms)
    return element


def system_color_last_color(color: ET.Element) -> str | None:
    """Return the ``RRGGBB`` a system colour last resolved to, if stored."""
    if color.tag != f"{{{A_NS}}}sysClr":
        raise ValueError("not a system color (a:sysClr)")
    value = color.get("lastClr")
    return None if value is None else value.upper()


def set_system_color_last_color(color: ET.Element, last_color: str | None) -> None:
    """Set or clear the stored last colour of a system colour."""
    if color.tag != f"{{{A_NS}}}sysClr":
        raise ValueError("not a system color (a:sysClr)")
    if last_color is None:
        color.attrib.pop("lastClr", None)
        return
    _validate_color_hex(str(last_color))
    color.set("lastClr", str(last_color).upper())


def color_transforms(color: ET.Element) -> list[tuple[str, float | None]]:
    """Return the ordered transform list of a colour element.

    Each item is ``(name, value)`` with ``name`` the DrawingML transform
    (``tint``, ``shade``, ``comp``, ``inv``, ``gray``, ``alpha``, ``alphaOff``,
    ``alphaMod``, ``hue``, ``hueOff``, ``hueMod``, ``sat``, ``satOff``,
    ``satMod``, ``lum``, ``lumOff``, ``lumMod``, ``red``/``green``/``blue`` and
    their ``Off``/``Mod`` forms, ``gamma``, ``invGamma``). Percentages are
    fractions (``0.25`` is 25 %), hue values are degrees, and the valueless
    transforms (``comp``, ``inv``, ``gray``, ``gamma``, ``invGamma``) carry
    ``None``.
    """
    transforms: list[tuple[str, float | None]] = []
    for child in color:
        name = _xml_local_name(child.tag)
        kind = COLOR_TRANSFORMS.get(name)
        if kind is None or child.tag != f"{{{A_NS}}}{name}":
            continue
        if kind == "flag":
            transforms.append((name, None))
        elif kind in {"angle", "positive_angle"}:
            transforms.append((name, int(child.get("val", "0")) / 60000.0))
        else:
            transforms.append((name, _color_percentage(child.get("val"))))
    return transforms


def set_color_transforms(color: ET.Element, transforms: Sequence[Any]) -> None:
    """Replace the transform list of ``color`` with ``transforms``, in order.

    Items are ``(name, value)`` pairs, ``{"name": ..., "value": ...}`` mappings,
    or bare names for the valueless transforms. Names are DrawingML transform
    names or the readable aliases in `COLOR_TRANSFORM_ALIASES` (``complement``,
    ``inverse``, ``luminance_modulation`` ...). Units are those
    `color_transforms` reports. The list is validated before ``color`` changes.
    """
    if not isinstance(transforms, Sequence) or isinstance(transforms, (str, bytes)):
        raise ValueError("color transforms must be an ordered sequence")
    elements = [_color_transform_element(item) for item in transforms]
    for child in list(color):
        if child.tag == f"{{{A_NS}}}{_xml_local_name(child.tag)}" and (
            _xml_local_name(child.tag) in COLOR_TRANSFORMS
        ):
            color.remove(child)
    for element in elements:
        color.append(element)


def add_color_transform(color: ET.Element, name: str, value: float | None = None) -> None:
    """Append one transform to the end of the transform list of ``color``."""
    color.append(_color_transform_element((name, value)))


def remove_color_transforms(color: ET.Element, name: str | None = None) -> int:
    """Remove every transform named ``name`` (all transforms when ``None``)."""
    tag = None if name is None else _color_transform_name(name)
    removed = 0
    for child in list(color):
        local = _xml_local_name(child.tag)
        if local in COLOR_TRANSFORMS and (tag is None or local == tag):
            color.remove(child)
            removed += 1
    return removed


def _color_transform_name(name: Any) -> str:
    if not isinstance(name, str):
        raise ValueError(f"color transform name must be a string, got {name!r}")
    tag = COLOR_TRANSFORM_ALIASES.get(name, name)
    if tag not in COLOR_TRANSFORMS:
        raise ValueError(f"unsupported color transform: {name!r}")
    return tag


def _color_transform_element(item: Any) -> ET.Element:
    if isinstance(item, str):
        name, value = item, None
    elif isinstance(item, dict):
        unknown = set(item) - {"name", "value"}
        if unknown:
            raise ValueError(f"color transform has unknown keys: {sorted(unknown)}")
        name, value = item.get("name"), item.get("value")
    elif isinstance(item, Sequence) and len(item) == 2:
        name, value = item
    else:
        raise ValueError(f"color transform must be (name, value): {item!r}")
    tag = _color_transform_name(name)
    kind = COLOR_TRANSFORMS[tag]
    element = ET.Element(f"{{{A_NS}}}{tag}")
    if kind == "flag":
        if value is not None:
            raise ValueError(f"color transform {tag!r} takes no value")
        return element
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"color transform {tag!r} needs a number, got {value!r}")
    try:
        finite = math.isfinite(value)
    except OverflowError as error:
        raise ValueError(f"color transform {tag!r} value is out of range") from error
    if not finite:
        raise ValueError(f"color transform {tag!r} value must be finite")
    if kind == "positive_angle" and not 0 <= value < 360:
        raise ValueError(f"color transform {tag!r} must lie in 0..360 degrees")
    if kind == "unit" and not 0 <= value <= 1:
        raise ValueError(f"color transform {tag!r} must lie in 0..1")
    if kind == "signed_unit" and not -1 <= value <= 1:
        raise ValueError(f"color transform {tag!r} must lie in -1..1")
    if kind == "positive" and value < 0:
        raise ValueError(f"color transform {tag!r} must be non-negative")
    scaled = value * (60000 if kind in {"angle", "positive_angle"} else 100000)
    if not math.isfinite(scaled) or not -(2**31) <= scaled < 2**31:
        raise ValueError(f"color transform {tag!r} value is out of range")
    raw = round(scaled)
    if not -(2**31) <= raw < 2**31:
        raise ValueError(f"color transform {tag!r} value is out of range")
    element.set("val", str(raw))
    return element


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


def brightness_from_color_element(color: ET.Element) -> float:
    lum_off = color.find(f"{{{A_NS}}}lumOff")
    if lum_off is not None:
        value = lum_off.attrib.get("val")
        return 0.0 if value is None else _color_percentage(value)
    lum_mod = color.find(f"{{{A_NS}}}lumMod")
    if lum_mod is not None:
        value = lum_mod.attrib.get("val")
        return 0.0 if value is None else _color_percentage(value) - 1.0
    return 0.0


def has_brightness_modifiers(color: ET.Element) -> bool:
    luminance_tags = {f"{{{A_NS}}}lumMod", f"{{{A_NS}}}lumOff"}
    return any(child.tag in luminance_tags for child in color)


def set_color_brightness(color: ET.Element, brightness: float) -> None:
    modifiers = brightness_modifiers(brightness)
    luminance_tags = {f"{{{A_NS}}}lumMod", f"{{{A_NS}}}lumOff"}
    children = list(color)
    insert_at = next(
        (index for index, child in enumerate(children) if child.tag in luminance_tags),
        len(children),
    )
    for child in children:
        if child.tag in luminance_tags:
            color.remove(child)
    for tag, value in modifiers:
        color.insert(insert_at, ET.Element(f"{{{A_NS}}}{tag}", {"val": value}))
        insert_at += 1


def validate_text_color_element(color: ET.Element) -> None:
    """Validate an editable color without resolving a theme or system palette."""
    tag = _xml_local_name(color.tag)
    if color.tag != f"{{{A_NS}}}{tag}":
        raise ValueError("unsupported text color namespace")
    value = color.get("val", "")
    if tag == "srgbClr":
        _validate_color_hex(value)
    elif tag == "schemeClr":
        if value not in {
            "bg1",
            "tx1",
            "bg2",
            "tx2",
            "dk1",
            "lt1",
            "dk2",
            "lt2",
            "accent1",
            "accent2",
            "accent3",
            "accent4",
            "accent5",
            "accent6",
            "hlink",
            "folHlink",
            "phClr",
        }:
            raise ValueError(f"invalid scheme text color: {value!r}")
    elif tag == "sysClr":
        if value not in _SYSTEM_COLOR_NAMES:
            raise ValueError(f"invalid system text color: {value!r}")
        if "lastClr" in color.attrib:
            _validate_color_hex(color.attrib["lastClr"])
    elif tag == "prstClr":
        if value not in _PRESET_COLOR_NAMES:
            raise ValueError(f"invalid preset text color: {value!r}")
    elif tag == "scrgbClr":
        for channel in ("r", "g", "b"):
            _color_percentage(color.get(channel))
    elif tag == "hslClr":
        hue = color.get("hue", "")
        if re.fullmatch(r"[0-9]+", hue) is None or not 0 <= int(hue) < 21600000:
            raise ValueError(f"invalid HSL hue: {hue!r}")
        for channel in ("sat", "lum"):
            if not 0 <= _color_percentage(color.get(channel)) <= 1:
                raise ValueError(f"invalid HSL {channel}")
    else:
        raise ValueError(f"unsupported text color: {tag!r}")
    allowed_attributes = (
        {"hue", "sat", "lum"}
        if tag == "hslClr"
        else {"r", "g", "b"}
        if tag == "scrgbClr"
        else {"val", "lastClr"}
        if tag == "sysClr"
        else {"val"}
    )
    if set(color.attrib) - allowed_attributes or (color.text or "").strip():
        raise ValueError("malformed text color content")
    for transform in color:
        name = _xml_local_name(transform.tag)
        if (
            transform.tag != f"{{{A_NS}}}{name}"
            or len(transform)
            or (transform.text or "").strip()
            or (transform.tail or "").strip()
        ):
            raise ValueError(f"malformed text color transform: {name!r}")
        if name in {"comp", "inv", "gray", "gamma", "invGamma"}:
            if transform.attrib:
                raise ValueError(f"malformed text color transform: {name!r}")
            continue
        if set(transform.attrib) != {"val"}:
            raise ValueError(f"malformed text color transform: {name!r}")
        raw = transform.get("val")
        if name in {"hue", "hueOff"}:
            if raw is None or re.fullmatch(r"[+-]?[0-9]+", raw.strip()) is None:
                raise ValueError(f"invalid text color angle: {raw!r}")
            angle = int(raw)
            if not -(2**31) <= angle < 2**31 or (name == "hue" and not 0 <= angle < 21600000):
                raise ValueError(f"text color angle out of range: {raw!r}")
            continue
        if name not in _PERCENTAGE_COLOR_TRANSFORMS:
            raise ValueError(f"unsupported text color transform: {name!r}")
        number = _color_percentage(raw)
        if name in {"alpha", "tint", "shade"} and not 0 <= number <= 1:
            raise ValueError(f"text color transform {name!r} out of range")
        if name == "alphaOff" and not -1 <= number <= 1:
            raise ValueError("text color transform 'alphaOff' out of range")
        if name in {"alphaMod", "hueMod"} and number < 0:
            raise ValueError(f"text color transform {name!r} must be non-negative")


def _validate_color_hex(value: str) -> None:
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value) is None:
        raise ValueError(f"invalid text color RGB: {value!r}")


def _color_percentage(raw: str | None) -> float:
    if raw is None:
        raise ValueError("text color percentage has no value")
    value = raw.strip()
    if value.endswith("%"):
        if re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?%", value) is None:
            raise ValueError(f"invalid text color percentage: {raw!r}")
        number = float(value[:-1]) / 100
        if not math.isfinite(number):
            raise ValueError(f"non-finite text color percentage: {raw!r}")
        return number
    if re.fullmatch(r"[+-]?[0-9]+", value) is None:
        raise ValueError(f"invalid text color percentage: {raw!r}")
    integer = int(value)
    if not -(2**31) <= integer < 2**31:
        raise ValueError(f"text color percentage out of range: {raw!r}")
    return integer / 100000


_PERCENTAGE_COLOR_TRANSFORMS = frozenset(
    [
        "alpha",
        "alphaMod",
        "alphaOff",
        "hueMod",
        "sat",
        "satMod",
        "satOff",
        "lum",
        "lumMod",
        "lumOff",
        "red",
        "redMod",
        "redOff",
        "green",
        "greenMod",
        "greenOff",
        "blue",
        "blueMod",
        "blueOff",
        "tint",
        "shade",
    ]
)
_SYSTEM_COLOR_NAMES = frozenset(
    [
        "scrollBar",
        "background",
        "activeCaption",
        "inactiveCaption",
        "menu",
        "window",
        "windowFrame",
        "menuText",
        "windowText",
        "captionText",
        "activeBorder",
        "inactiveBorder",
        "appWorkspace",
        "highlight",
        "highlightText",
        "btnFace",
        "btnShadow",
        "grayText",
        "btnText",
        "inactiveCaptionText",
        "btnHighlight",
        "3dDkShadow",
        "3dLight",
        "infoText",
        "infoBk",
        "hotLight",
        "gradientActiveCaption",
        "gradientInactiveCaption",
        "menuHighlight",
        "menuBar",
    ]
)
_PRESET_COLOR_NAMES = frozenset(
    [
        "aliceBlue",
        "antiqueWhite",
        "aqua",
        "aquamarine",
        "azure",
        "beige",
        "bisque",
        "black",
        "blanchedAlmond",
        "blue",
        "blueViolet",
        "brown",
        "burlyWood",
        "cadetBlue",
        "chartreuse",
        "chocolate",
        "coral",
        "cornflowerBlue",
        "cornsilk",
        "crimson",
        "cyan",
        "dkBlue",
        "dkCyan",
        "dkGoldenrod",
        "dkGray",
        "dkGreen",
        "dkKhaki",
        "dkMagenta",
        "dkOliveGreen",
        "dkOrange",
        "dkOrchid",
        "dkRed",
        "dkSalmon",
        "dkSeaGreen",
        "dkSlateBlue",
        "dkSlateGray",
        "dkTurquoise",
        "dkViolet",
        "deepPink",
        "deepSkyBlue",
        "dimGray",
        "dodgerBlue",
        "firebrick",
        "floralWhite",
        "forestGreen",
        "fuchsia",
        "gainsboro",
        "ghostWhite",
        "gold",
        "goldenrod",
        "gray",
        "green",
        "greenYellow",
        "honeydew",
        "hotPink",
        "indianRed",
        "indigo",
        "ivory",
        "khaki",
        "lavender",
        "lavenderBlush",
        "lawnGreen",
        "lemonChiffon",
        "ltBlue",
        "ltCoral",
        "ltCyan",
        "ltGoldenrodYellow",
        "ltGray",
        "ltGreen",
        "ltPink",
        "ltSalmon",
        "ltSeaGreen",
        "ltSkyBlue",
        "ltSlateGray",
        "ltSteelBlue",
        "ltYellow",
        "lime",
        "limeGreen",
        "linen",
        "magenta",
        "maroon",
        "medAquamarine",
        "medBlue",
        "medOrchid",
        "medPurple",
        "medSeaGreen",
        "medSlateBlue",
        "medSpringGreen",
        "medTurquoise",
        "medVioletRed",
        "midnightBlue",
        "mintCream",
        "mistyRose",
        "moccasin",
        "navajoWhite",
        "navy",
        "oldLace",
        "olive",
        "oliveDrab",
        "orange",
        "orangeRed",
        "orchid",
        "paleGoldenrod",
        "paleGreen",
        "paleTurquoise",
        "paleVioletRed",
        "papayaWhip",
        "peachPuff",
        "peru",
        "pink",
        "plum",
        "powderBlue",
        "purple",
        "red",
        "rosyBrown",
        "royalBlue",
        "saddleBrown",
        "salmon",
        "sandyBrown",
        "seaGreen",
        "seaShell",
        "sienna",
        "silver",
        "skyBlue",
        "slateBlue",
        "slateGray",
        "snow",
        "springGreen",
        "steelBlue",
        "tan",
        "teal",
        "thistle",
        "tomato",
        "turquoise",
        "violet",
        "wheat",
        "white",
        "whiteSmoke",
        "yellow",
        "yellowGreen",
    ]
)


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
    pattern = parent.find(f"{{{A_NS}}}pattFill/{{{A_NS}}}{pattern_role}/{{{A_NS}}}srgbClr")
    if pattern is None:
        return None
    value = pattern.attrib.get("val")
    return value.upper() if value else None


COLOR_TRANSFORMS: dict[str, str] = {
    "tint": "unit",
    "shade": "unit",
    "comp": "flag",
    "inv": "flag",
    "gray": "flag",
    "alpha": "unit",
    "alphaOff": "signed_unit",
    "alphaMod": "positive",
    "hue": "positive_angle",
    "hueOff": "angle",
    "hueMod": "positive",
    "sat": "percentage",
    "satOff": "percentage",
    "satMod": "percentage",
    "lum": "percentage",
    "lumOff": "percentage",
    "lumMod": "percentage",
    "red": "percentage",
    "redOff": "percentage",
    "redMod": "percentage",
    "green": "percentage",
    "greenOff": "percentage",
    "greenMod": "percentage",
    "blue": "percentage",
    "blueOff": "percentage",
    "blueMod": "percentage",
    "gamma": "flag",
    "invGamma": "flag",
}
"""DrawingML colour transforms (EG_ColorTransform) and the value kind each takes."""

COLOR_TRANSFORM_ALIASES: dict[str, str] = {
    "complement": "comp",
    "inverse": "inv",
    "grayscale": "gray",
    "inverse_gamma": "invGamma",
    "alpha_offset": "alphaOff",
    "alpha_modulation": "alphaMod",
    "hue_offset": "hueOff",
    "hue_modulation": "hueMod",
    "saturation": "sat",
    "saturation_offset": "satOff",
    "saturation_modulation": "satMod",
    "luminance": "lum",
    "luminance_offset": "lumOff",
    "luminance_modulation": "lumMod",
    "red_offset": "redOff",
    "red_modulation": "redMod",
    "green_offset": "greenOff",
    "green_modulation": "greenMod",
    "blue_offset": "blueOff",
    "blue_modulation": "blueMod",
}

GRADIENT_PATH_SHADES = ("circle", "rect", "shape")
"""``a:path`` shades: radial, rectangular and shape-outline path gradients."""

_ZERO_RECT = (0.0, 0.0, 0.0, 0.0)

GRADIENT_DIRECTIONS: dict[
    str, tuple[tuple[float, float, float, float], tuple[float, float, float, float]]
] = {
    "from_center": ((0.5, 0.5, 0.5, 0.5), _ZERO_RECT),
    "from_top_left": ((0.0, 0.0, 1.0, 1.0), (-1.0, -1.0, 0.0, 0.0)),
    "from_top_right": ((1.0, 0.0, 0.0, 1.0), (0.0, -1.0, -1.0, 0.0)),
    "from_bottom_left": ((0.0, 1.0, 1.0, 0.0), (-1.0, 0.0, 0.0, -1.0)),
    "from_bottom_right": ((1.0, 1.0, 0.0, 0.0), (0.0, 0.0, -1.0, -1.0)),
}
"""Path gradient direction presets as ``(fill_to_rect, tile_rect)`` inset fractions.

The focus rectangle collapses to the centre or to a corner; for a corner the
tile rectangle grows away from that corner so the shading is centred on it and
reaches the opposite corner, the markup PowerPoint writes for its "From
Center" and "From ... Corner" gradient directions.
"""


class TileMirrorMode(StrEnum):
    """How the repeated tiles of a picture or gradient fill mirror (``flip``).

    Each value is the DrawingML token, so a mode equals its raw string
    (``TileMirrorMode.HORIZONTAL == "x"``) and serializes as it. ``HORIZONTAL``
    mirrors every other tile column, ``VERTICAL`` every other row, ``BOTH`` both.
    """

    NONE = "none"
    HORIZONTAL = "x"
    VERTICAL = "y"
    BOTH = "xy"


class TileMirrorModeRefusal(ValueError):
    """An unknown tile mirror mode was refused before any fill changed."""


class _GradientTileMirrorModeRefusal(TileMirrorModeRefusal, GradientFillRefusal):
    """A gradient payload named an unknown tile mirror mode."""


TILE_FLIP_MODES = tuple(mode.value for mode in TileMirrorMode)


def tile_mirror_mode(value: TileMirrorMode | str, context: str = "tile flip") -> TileMirrorMode:
    """Return the `TileMirrorMode` named by a member or its token (``none``, ``x``, ``y``, ``xy``).

    Anything else raises `TileMirrorModeRefusal`, naming ``context``.
    """
    if isinstance(value, str):
        try:
            return TileMirrorMode(value)
        except ValueError:
            pass
    raise TileMirrorModeRefusal(
        f"{context} must be one of {', '.join(TILE_FLIP_MODES)} or a TileMirrorMode, got {value!r}"
    )


def _stored_mirror_mode(raw: str | None) -> TileMirrorMode | str | None:
    """Type a stored ``flip`` token; a token outside the schema is returned verbatim."""
    if raw is None:
        return None
    try:
        return TileMirrorMode(raw)
    except ValueError:
        return raw


TILE_ALIGNMENTS = ("tl", "t", "tr", "l", "ctr", "r", "bl", "b", "br")

PATH_FILL_MODES: dict[str, str] = {
    "none": "none",
    "normal": "norm",
    "lighten": "lighten",
    "lighten_less": "lightenLess",
    "darken": "darken",
    "darken_less": "darkenLess",
}
"""Freeform path fill modes (``a:path/@fill``) by readable name."""


def set_freeform_path_fill_mode(
    geometry_parent: ET.Element, mode: str, path_index: int | None = None
) -> None:
    """Set the fill mode of the custom-geometry paths of a freeform shape.

    ``geometry_parent`` is the shape's ``spPr`` or its ``a:custGeom``; ``mode``
    is a `PATH_FILL_MODES` name. ``path_index`` selects one path of
    ``a:pathLst``; ``None`` sets every path. ``normal`` is the schema default
    and is written by removing the attribute.
    """
    if mode not in PATH_FILL_MODES:
        raise ValueError(
            f"path fill mode must be one of {', '.join(PATH_FILL_MODES)}, got {mode!r}"
        )
    paths = _freeform_paths(geometry_parent)
    if path_index is not None:
        if isinstance(path_index, bool) or not isinstance(path_index, int):
            raise ValueError("path_index must be an integer")
        if not -len(paths) <= path_index < len(paths):
            raise IndexError(f"freeform has {len(paths)} paths, no index {path_index}")
        paths = [paths[path_index]]
    for path in paths:
        if mode == "normal":
            path.attrib.pop("fill", None)
        else:
            path.set("fill", PATH_FILL_MODES[mode])


def freeform_path_fill_modes(geometry_parent: ET.Element) -> list[str]:
    """Return the `PATH_FILL_MODES` name of each custom-geometry path, in order."""
    names = {value: name for name, value in PATH_FILL_MODES.items()}
    modes = []
    for path in _freeform_paths(geometry_parent):
        raw = path.get("fill", "norm")
        if raw not in names:
            raise ValueError(f"invalid path fill mode: {raw!r}")
        modes.append(names[raw])
    return modes


def _freeform_paths(geometry_parent: ET.Element) -> list[ET.Element]:
    custom = (
        geometry_parent
        if geometry_parent.tag == f"{{{A_NS}}}custGeom"
        else geometry_parent.find(f"{{{A_NS}}}custGeom")
    )
    if custom is None:
        raise ValueError("path fill modes apply to freeform (a:custGeom) shapes only")
    paths = custom.findall(f"{{{A_NS}}}pathLst/{{{A_NS}}}path")
    if not paths:
        raise ValueError("freeform geometry has no paths")
    return paths


def set_blip_fill_tile(
    blip_fill: ET.Element,
    offset_x: int = 0,
    offset_y: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    alignment: str = "tl",
    flip: TileMirrorMode | str = TileMirrorMode.NONE,
) -> None:
    """Tile a picture fill instead of stretching it.

    ``blip_fill`` is an ``a:blipFill`` or an element holding one (``spPr``,
    ``bgPr``). Offsets are EMU from the aligned tile origin, scales are
    fractions of the image's natural size (``1.0`` = 100 %), ``alignment`` is
    a `TILE_ALIGNMENTS` anchor and ``flip`` a `TileMirrorMode` or its raw token.
    An unknown mirror mode raises `TileMirrorModeRefusal` before the fill changes.
    """
    fill = _blip_fill(blip_fill)
    attributes = {}
    for name, value in (("tx", offset_x), ("ty", offset_y)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"tile offset must be integer EMU, got {value!r}")
        if not -27273042329600 <= value <= 27273042316900:
            raise ValueError(f"tile offset {value} is out of range")
        attributes[name] = str(value)
    for name, value in (("sx", scale_x), ("sy", scale_y)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"tile scale must be a number, got {value!r}")
        raw = round(value * 100000) if math.isfinite(value) else 0
        if not 0 < raw < 2**31:
            raise ValueError(f"tile scale must be a positive finite fraction, got {value!r}")
        attributes[name] = str(raw)
    if alignment not in TILE_ALIGNMENTS:
        raise ValueError(
            f"tile alignment must be one of {', '.join(TILE_ALIGNMENTS)}, got {alignment!r}"
        )
    attributes["flip"] = tile_mirror_mode(flip).value
    attributes["algn"] = alignment
    _replace_blip_fill_mode(fill, ET.Element(f"{{{A_NS}}}tile", attributes))


def set_blip_fill_stretch(blip_fill: ET.Element) -> None:
    """Stretch a picture fill over the whole box (``a:stretch/a:fillRect``)."""
    stretch = ET.Element(f"{{{A_NS}}}stretch")
    ET.SubElement(stretch, f"{{{A_NS}}}fillRect")
    _replace_blip_fill_mode(_blip_fill(blip_fill), stretch)


def blip_fill_tile(blip_fill: ET.Element) -> dict[str, Any] | None:
    """Return the tile settings of a picture fill, or ``None`` when it does not tile.

    ``flip`` is a `TileMirrorMode`; a stored token outside the schema is returned verbatim.
    """
    tile = _blip_fill(blip_fill).find(f"{{{A_NS}}}tile")
    if tile is None:
        return None
    return {
        "offset_x": int(tile.get("tx", "0")),
        "offset_y": int(tile.get("ty", "0")),
        "scale_x": _color_percentage(tile.get("sx", "100000")),
        "scale_y": _color_percentage(tile.get("sy", "100000")),
        "alignment": tile.get("algn", "tl"),
        "flip": _stored_mirror_mode(tile.get("flip", "none")),
    }


def _blip_fill(element: ET.Element) -> ET.Element:
    if element.tag == f"{{{A_NS}}}blipFill":
        return element
    fill = element.find(f"{{{A_NS}}}blipFill")
    if fill is None:
        raise ValueError("element holds no picture fill (a:blipFill)")
    return fill


def _replace_blip_fill_mode(fill: ET.Element, mode: ET.Element) -> None:
    for child in list(fill):
        if _xml_local_name(child.tag) in {"tile", "stretch"}:
            fill.remove(child)
    insert_at = 0
    for index, child in enumerate(fill):
        if _xml_local_name(child.tag) in {"blip", "srcRect"}:
            insert_at = index + 1
    fill.insert(insert_at, mode)


def picture_fill_payload(parent: ET.Element) -> dict[str, Any] | None:
    """Read image references, crop, mode and blip effects without flattening them."""
    fill = parent.find(f"{{{A_NS}}}blipFill")
    if fill is None:
        return None
    blip = fill.find(f"{{{A_NS}}}blip")
    crop = fill.find(f"{{{A_NS}}}srcRect")
    stretch = fill.find(f"{{{A_NS}}}stretch")
    fill_rect = None if stretch is None else stretch.find(f"{{{A_NS}}}fillRect")
    relationship_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    return {
        "embed": None if blip is None else blip.get(f"{{{relationship_ns}}}embed"),
        "link": None if blip is None else blip.get(f"{{{relationship_ns}}}link"),
        "crop": _ZERO_RECT if crop is None else _relative_rect_from_xml(crop),
        "tile": blip_fill_tile(fill),
        "stretch": (
            None
            if stretch is None
            else _ZERO_RECT
            if fill_rect is None
            else _relative_rect_from_xml(fill_rect)
        ),
        "dpi": int(fill.get("dpi", "0")),
        "cstate": None if blip is None else blip.get("cstate"),
        "rot_with_shape": fill.get("rotWithShape", "1") in {"1", "true"},
        "effects": [] if blip is None else [deepcopy(child) for child in blip],
    }


def picture_fill_element(
    relationship_id: str,
    *,
    crop: Any = _ZERO_RECT,
    tile: dict[str, Any] | None = None,
    stretch: Any = _ZERO_RECT,
    dpi: int = 0,
    cstate: str | None = None,
    rot_with_shape: bool = True,
) -> ET.Element:
    """Build a validated embedded picture fill before mutating a package.

    Crop and stretch rectangles use left/top/right/bottom inset fractions.
    Tile keys and units follow ``set_blip_fill_tile``. Tile and stretch are
    exclusive; when tile is given, leave stretch at its zero-rectangle default.
    """
    crop_rect = _relative_rect(crop, "picture crop")
    stretch_rect = _relative_rect(stretch, "picture stretch")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 0 <= dpi < 2**32:
        raise ValueError("picture dpi must be an unsigned 32-bit integer")
    if cstate not in {None, "email", "hqprint", "none", "print", "screen"}:
        raise ValueError("picture cstate must be email, hqprint, none, print or screen")
    if not isinstance(rot_with_shape, bool):
        raise ValueError("picture rot_with_shape must be a bool")
    if tile is not None and stretch_rect != _ZERO_RECT:
        raise ValueError("picture tile and stretch rectangles are mutually exclusive")
    fill = ET.Element(
        f"{{{A_NS}}}blipFill",
        {
            "dpi": str(dpi),
            "rotWithShape": "1" if rot_with_shape else "0",
        },
    )
    blip = ET.SubElement(fill, f"{{{A_NS}}}blip")
    blip.set(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed",
        relationship_id,
    )
    if cstate is not None:
        blip.set("cstate", cstate)
    if crop_rect != _ZERO_RECT:
        _set_relative_rect(ET.SubElement(fill, f"{{{A_NS}}}srcRect"), crop_rect)
    if tile is None:
        mode = ET.SubElement(fill, f"{{{A_NS}}}stretch")
        _set_relative_rect(ET.SubElement(mode, f"{{{A_NS}}}fillRect"), stretch_rect)
    else:
        if not isinstance(tile, dict):
            raise ValueError("picture tile must be a mapping of tile settings")
        set_blip_fill_tile(fill, **tile)
    return fill
