"""Shape fill, line, shadow, and color formatting facade."""

from __future__ import annotations

import math
import zipfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .dml.color import (
    MSO_COLOR_TYPE,
    ColorFormatRefusal,
    ColorTextAndTransforms,
)
from .dml.color import (
    ColorResolutionRefusal as ColorResolutionRefusal,
)
from .dml.color import (
    format_color_string as format_color_string,
)
from .dml.color import (
    parse_color_string as parse_color_string,
)
from .dml_fill import (
    TileMirrorMode as TileMirrorMode,
)
from .dml_fill import (
    TileMirrorModeRefusal as TileMirrorModeRefusal,
)
from .dml_fill import (
    brightness_from_color_element as _brightness_from_color_element,
)
from .dml_fill import (
    color_element,
    color_payload_from_element,
    gradient_payload_from_fill_parent,
    picture_fill_element,
    picture_fill_payload,
    replace_fill_element,
    validate_text_color_element,
)
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
)
from .dml_fill import (
    gradient_stop_element as _gradient_stop_element,
)
from .dml_fill import (
    has_brightness_modifiers as _has_brightness_modifiers,
)
from .dml_fill import (
    set_color_brightness as _set_color_brightness,
)
from .dml_fill import (
    set_shape_gradient_fill as _set_shape_gradient_fill,
)
from .dml_fill import (
    set_shape_no_fill as _set_shape_no_fill,
)
from .dml_fill import (
    set_shape_pattern_fill as _set_shape_pattern_fill,
)
from .dml_fill import (
    set_shape_solid_fill as _set_shape_solid_fill,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
)
from .facade_values import (
    emu_value as _emu_value,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    line_dash_style_value as _line_dash_style_value,
)
from .facade_values import (
    normalize_line_dash_style as _normalize_line_dash_style,
)
from .facade_values import (
    normalize_pattern_type as _normalize_pattern_type,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    pattern_type_value as _pattern_type_value,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .shape_edit_refs import (
    ShapeEditRef,
)
from .shape_edit_refs import (
    shape_edit_ref as _shape_edit_ref,
)
from .shape_format_inspection import (
    _detached_fill_parent,
    _is_pending_shape,
    _shape_fill_pattern,
    _shape_fill_type,
    _shape_gradient_fill_payload,
    _shape_line_dash_style,
    _shape_line_fill_pattern,
    _shape_line_fill_type,
    _shape_line_width,
    _shape_shadow_inherit,
)
from .shape_format_inspection import (
    _shape_pattern_rgb as _shape_pattern_rgb,
)
from .shape_format_inspection import (
    _shape_style_rgb as _shape_style_rgb,
)
from .shape_xml import _shape_xml_element
from .xml_helpers import find_ooxml
from .xml_helpers import xml_local_name as _xml_local_name

if TYPE_CHECKING:
    from .shape_core_facade import Shape
    from .shape_shadow_edits import OuterShadowSpec
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _shape_style_ref(shape: Any) -> ShapeEditRef:
    return _shape_edit_ref(shape)


def _is_group_shape(shape: Any) -> bool:
    return getattr(shape, "_payload", {}).get("kind") == "group"


def _group_shadow_inherit(shape: Shape) -> bool:
    """Report whether a group inherits effects, reading its ``p:grpSpPr``."""
    if _is_pending_shape(shape):
        return True
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    group_element = _shape_xml_element(root, shape._payload)
    group_properties = find_ooxml(group_element, f"{{{P_NS}}}grpSpPr")
    if group_properties is None:
        return True
    return not any(
        _xml_local_name(child.tag) in {"effectLst", "effectDag"} for child in group_properties
    )


class FillFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @classmethod
    def from_fill_parent(cls, eg_fillProperties_parent: Any) -> FillFormat:
        return cls(_DetachedFillShape(eg_fillProperties_parent))

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        self._shape._payload["fill_type"] = "solid"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload.pop("fill_gradient", None)
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_solid_fill(detached_parent)
            return
        self._shape._slide._presentation._queue_shape_fill_solid(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def background(self) -> None:
        if self._fill_type() == "background":
            return
        self._shape._payload["fill_type"] = "background"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload.pop("fill_gradient", None)
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_no_fill(detached_parent)
            return
        self._shape._slide._presentation._queue_shape_fill_background(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        pattern = None
        self._shape._payload["fill_type"] = "patterned"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload["fill_pattern"] = pattern
        self._shape._payload.pop("fill_gradient", None)
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_pattern_fill(detached_parent, pattern)
            return
        self._shape._slide._presentation._queue_shape_fill_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        gradient = _default_gradient_payload()
        self._shape._payload["fill_type"] = "gradient"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload["fill_gradient"] = gradient
        self._queue_gradient(gradient)

    def group(self) -> None:
        """Inherit the enclosing group's fill (``a:grpFill``).

        Package-backed edits require a saved presentation, as for blend mode.
        """
        _edit_shape_properties(
            self._shape,
            "setting group fill",
            lambda properties: replace_fill_element(properties, "grpFill"),
        )
        self._set_rewritten_fill_type("group")

    def picture(
        self,
        image_file: Any,
        *,
        crop: Any = (0.0, 0.0, 0.0, 0.0),
        tile: dict[str, Any] | None = None,
        stretch: Any = (0.0, 0.0, 0.0, 0.0),
        dpi: int = 0,
        cstate: str | None = None,
        rot_with_shape: bool = True,
    ) -> None:
        """Embed an image as a shape fill, replacing the previous fill atomically.

        ``image_file`` accepts the same paths, bytes and streams as pictures.
        Crop/stretch are left/top/right/bottom inset fractions. Tile settings
        use EMU offsets, fractional scales, a DrawingML alignment and a
        `TileMirrorMode` (or its raw token) as ``flip``; an unknown mirror
        mode raises `TileMirrorModeRefusal` before the package changes.
        Save pending presentation edits first. Detached XML cannot own media.
        """
        from .background_edits import _add_image_relationship, _ensure_content_type
        from .image_dimensions import image_native_size_emu
        from .image_inputs import InMemoryImage, image_extension_from_blob, image_input_bytes
        from .package_parts import rels_part_for_package_part

        fill = picture_fill_element(
            "",
            crop=crop,
            tile=tile,
            stretch=stretch,
            dpi=dpi,
            cstate=cstate,
            rot_with_shape=rot_with_shape,
        )
        if _detached_fill_parent(self._shape) is not None:
            raise ValueError("picture fill embedding requires a presentation package")
        blob = (
            bytes(image_file)
            if isinstance(image_file, (bytes, bytearray))
            else image_input_bytes(image_file)
        )
        image_native_size_emu(InMemoryImage(blob))
        extension = image_extension_from_blob(blob)
        presentation = self._shape._slide._presentation
        partname = self._shape._slide.partname

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            root = ET.fromstring(package.read(partname))
            properties = _shape_properties_of(
                _shape_xml_element(root, self._shape._payload),
                create=True,
            )
            names = set(package.namelist())
            number = 1
            while f"ppt/media/image{number}.{extension}" in names:
                number += 1
            media_part = f"ppt/media/image{number}.{extension}"
            replacements = {media_part: blob}
            _ensure_content_type(package, replacements, extension)
            relationship_id = _add_image_relationship(
                package,
                replacements,
                rels_part_for_package_part(partname).lstrip("/"),
                media_part,
                partname,
            )
            fill.find(f"{{{A_NS}}}blip").set(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed",
                relationship_id,
            )
            replaced = replace_fill_element(properties, "blipFill")
            replaced.attrib.update(fill.attrib)
            replaced.extend(fill)
            replacements[partname] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            return replacements, set(), None

        presentation._rewrite_package("setting picture fill", plan)
        self._set_rewritten_fill_type("picture")

    @property
    def picture_fill(self) -> dict[str, Any] | None:
        """Image references, crop, tile/stretch, dpi, compression and copied effects.

        ``None`` means no picture fill. Effect XML returned here is detached;
        changing it never edits the source presentation.
        """
        if self._fill_type() != "picture":
            return None
        properties = _read_shape_properties(self._shape)
        return None if properties is None else picture_fill_payload(properties)

    def _set_rewritten_fill_type(self, kind: str) -> None:
        for name in (
            "fill_rgb",
            "fill_pattern",
            "fill_pattern_fore_rgb",
            "fill_pattern_back_rgb",
            "fill_gradient",
        ):
            self._shape._payload.pop(name, None)
        self._shape._payload["fill_type"] = kind

    @property
    def gradient_path(self) -> str | None:
        """Path shade: circle, rect, shape, or None for linear shading."""
        return self._gradient_setting("path")

    @gradient_path.setter
    def gradient_path(self, value: str | None) -> None:
        if value not in (None, "circle", "rect", "shape"):
            raise ValueError("gradient path must be circle, rect, shape or None")
        if self.gradient_path == value:
            return
        changes = {"path": value, "angle": None}
        if value is None:
            changes["fill_to_rect"] = None
        self._set_gradient_settings(**changes)

    @property
    def gradient_focus(self) -> tuple[float, float, float, float] | None:
        """Path focus rectangle in left/top/right/bottom inset fractions."""
        return self._gradient_setting("fill_to_rect")

    @gradient_focus.setter
    def gradient_focus(self, value: Any) -> None:
        self._set_gradient_settings(fill_to_rect=value)

    @property
    def gradient_tile_rect(self) -> tuple[float, float, float, float] | None:
        """Tile rectangle in left/top/right/bottom inset fractions."""
        return self._gradient_setting("tile_rect")

    @gradient_tile_rect.setter
    def gradient_tile_rect(self, value: Any) -> None:
        self._set_gradient_settings(tile_rect=value)

    @property
    def gradient_flip(self) -> TileMirrorMode | str | None:
        """Tile mirror mode as a `TileMirrorMode`; None omits the attribute."""
        return self._gradient_setting("flip")

    @gradient_flip.setter
    def gradient_flip(self, value: TileMirrorMode | str | None) -> None:
        """Accept a `TileMirrorMode` or its token; refuse unknown modes before writing."""
        self._set_gradient_settings(flip=value)

    @property
    def gradient_rot_with_shape(self) -> bool:
        return self._gradient_setting("rot_with_shape", True)

    @gradient_rot_with_shape.setter
    def gradient_rot_with_shape(self, value: bool) -> None:
        self._set_gradient_settings(rot_with_shape=value)

    @property
    def gradient_scaled(self) -> bool:
        return self._gradient_setting("scaled", False)

    @gradient_scaled.setter
    def gradient_scaled(self, value: bool) -> None:
        if self.gradient_path is not None:
            raise ValueError("a path gradient has no linear scaled flag")
        self._set_gradient_settings(scaled=value)

    def _gradient_setting(self, name: str, default: Any = None) -> Any:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return self._gradient_payload().get(name, default)

    def _set_gradient_settings(self, **changes: Any) -> None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        for name in ("rot_with_shape", "scaled"):
            if name in changes and not isinstance(changes[name], bool):
                raise ValueError(f"gradient {name} must be a bool")
        gradient = {**self._gradient_payload(), **changes}
        validation = ET.Element("validation")
        _set_shape_gradient_fill(validation, gradient)
        normalized = gradient_payload_from_fill_parent(validation)
        self._queue_gradient(normalized)
        self._shape._payload["fill_gradient"] = normalized

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> ColorFormat:
        return ColorFormat(self._shape, "fill_fore")

    @property
    def back_color(self) -> ColorFormat:
        return ColorFormat(self._shape, "fill_back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._pattern_raw())

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern == self._pattern_raw():
            return
        self._shape._payload["fill_pattern"] = pattern
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_pattern_fill(detached_parent, pattern)
            return
        self._shape._slide._presentation._queue_shape_fill_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    @property
    def gradient_angle(self) -> float | None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return self._gradient_payload().get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        angle = float(value)
        if gradient.get("angle") == angle:
            return
        gradient["angle"] = angle
        self._queue_gradient(gradient)

    @property
    def gradient_stops(self) -> GradientStops:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return GradientStops(self)

    @property
    def blend_mode(self) -> str | None:
        """How the fill blends with what lies beneath (``a:fillOverlay``).

        One of overlay, multiply, screen, darken or lighten; None is normal.
        Setting a mode overlays a copy of the shape's explicit fill.
        """
        return _fill_blend_mode(_read_shape_properties(self._shape))

    @blend_mode.setter
    def blend_mode(self, value: Any) -> None:
        blend = _choice(value, FILL_BLEND_MODES, "fill blend mode")
        # Setting a mode always re-copies the current fill into the overlay.
        if blend is None and self.blend_mode is None:
            return
        _edit_shape_properties(
            self._shape,
            "setting the fill blend mode",
            lambda properties: _set_fill_blend_mode(properties, blend),
        )

    def _fill_type(self) -> str | None:
        if "fill_type" not in self._shape._payload:
            self._shape._payload["fill_type"] = _shape_fill_type(self._shape)
        return self._shape._payload["fill_type"]

    def _pattern_raw(self) -> str | None:
        if "fill_pattern" not in self._shape._payload:
            self._shape._payload["fill_pattern"] = _shape_fill_pattern(self._shape)
        return self._shape._payload["fill_pattern"]

    def _gradient_payload(self) -> dict[str, Any]:
        if "fill_gradient" not in self._shape._payload:
            payload = _shape_gradient_fill_payload(self._shape)
            if payload is None:
                payload = _default_gradient_payload()
            self._shape._payload["fill_gradient"] = payload
        return self._shape._payload["fill_gradient"]

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_gradient_fill(detached_parent, gradient)
            return
        self._shape._slide._presentation._queue_shape_fill_gradient(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            gradient,
        )


class GradientStops(Sequence):
    def __init__(self, fill: FillFormat) -> None:
        self._fill = fill

    def __getitem__(self, index: int) -> GradientStop:
        stops = self._stops()
        if index < 0:
            index += len(stops)
        if index < 0 or index >= len(stops):
            raise IndexError("gradient stop index out of range")
        return GradientStop(self._fill, index)

    def __len__(self) -> int:
        return len(self._stops())

    def append(self, position: Any) -> GradientStop:
        """Add a stop after the last stop; see `insert`."""
        return self.insert(len(self._stops()), position)

    def insert(self, index: int, position: Any) -> GradientStop:
        """Insert a stop at `index` and return it.

        `position` must lie in 0.0..1.0 and between the positions of the stops
        it lands between, so authored stops stay ordered by `pos`. The new stop
        copies the color of the stop it follows (or precedes, when inserted
        first), leaving the rendered gradient unchanged until its color is set.
        """
        stops = self._stops()
        count = len(stops)
        if index < 0:
            index = max(count + index, 0)
        index = min(index, count)
        position = float(position)
        if not 0.0 <= position <= 1.0:
            raise ValueError(f"gradient stop position must be between 0.0 and 1.0, got {position}")
        lower = _stop_position(stops[index - 1]) if index > 0 else 0.0
        upper = _stop_position(stops[index]) if index < count else 1.0
        if not lower <= position <= upper:
            raise ValueError(
                f"gradient stop position {position} at index {index} must lie "
                f"between neighboring stop positions {lower} and {upper}"
            )
        neighbor = stops[index - 1] if index > 0 else (stops[0] if stops else {})
        color = neighbor.get("color")
        stops.insert(
            index,
            {
                "position": position,
                "color": deepcopy(color) if isinstance(color, ET.Element) else None,
            },
        )
        self._fill._queue_gradient(self._fill._gradient_payload())
        return GradientStop(self._fill, index)

    def _stops(self) -> list[dict[str, Any]]:
        return self._fill._gradient_payload().setdefault("stops", [])


def _stop_position(stop: dict[str, Any]) -> float:
    return float(stop.get("position", 0.0))


class GradientStop:
    def __init__(self, fill: FillFormat, index: int) -> None:
        self._fill = fill
        self._index = index

    @property
    def color(self) -> GradientStopColorFormat:
        return GradientStopColorFormat(self)

    @property
    def element(self) -> ET.Element:
        return _gradient_stop_element(self._stop())

    @property
    def position(self) -> float:
        return float(self._stop().get("position", 0.0))

    @position.setter
    def position(self, value: Any) -> None:
        position = float(value)
        if self.position == position:
            return
        self._stop()["position"] = position
        self._fill._queue_gradient(self._fill._gradient_payload())

    def _stop(self) -> dict[str, Any]:
        return self._fill._gradient_payload()["stops"][self._index]


class GradientStopColorFormat(ColorTextAndTransforms):
    def __init__(self, stop: GradientStop) -> None:
        self._stop = stop

    def _theme_part_owner(self) -> Any:
        return getattr(self._stop._fill._shape, "_slide", None)

    @property
    def brightness(self) -> float:
        return _brightness_from_color_element(self._color_element())

    @brightness.setter
    def brightness(self, value: Any) -> None:
        try:
            brightness = float(value)
            if isinstance(value, bool) or not -1.0 <= brightness <= 1.0:
                raise ValueError("brightness must be between -1.0 and 1.0")
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        color = deepcopy(self._color_element())
        if _brightness_from_color_element(color) == brightness and (
            brightness != 0.0 or not _has_brightness_modifiers(color)
        ):
            return
        _set_color_brightness(color, brightness)
        self._set_color_element(color)

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color.tag != f"{{{A_NS}}}srgbClr":
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        value = color.attrib.get("val")
        return None if value is None else _rgb_value(value.upper())

    @rgb.setter
    def rgb(self, value: Any) -> None:
        try:
            rgb = _normalize_rgb(value)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}srgbClr" and color.attrib.get("val") == rgb:
            return
        color = ET.Element(f"{{{A_NS}}}srgbClr")
        color.set("val", rgb)
        self._set_color_element(color)

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.attrib.get("val", ""))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        try:
            xml_value = _normalize_theme_color(value)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}schemeClr" and color.attrib.get("val") == xml_value:
            return
        color = ET.Element(f"{{{A_NS}}}schemeClr")
        color.set("val", xml_value)
        self._set_color_element(color)

    @property
    def type(self) -> Any:
        color = self._color_element()
        return {
            "srgbClr": MSO_COLOR_TYPE.RGB,
            "schemeClr": MSO_COLOR_TYPE.SCHEME,
            "sysClr": MSO_COLOR_TYPE.SYSTEM,
            "prstClr": MSO_COLOR_TYPE.PRESET,
            "scrgbClr": MSO_COLOR_TYPE.SCRGB,
            "hslClr": MSO_COLOR_TYPE.HSL,
        }.get(_xml_local_name(color.tag))

    def _color_element(self) -> ET.Element:
        color = self._stop._stop().get("color")
        if isinstance(color, ET.Element):
            return color
        if isinstance(color, dict):
            return color_element(color)
        return ET.Element(f"{{{A_NS}}}schemeClr", {"val": "accent1"})

    def _set_color_element(self, color: ET.Element) -> None:
        current = self._stop._fill._gradient_payload()
        gradient = deepcopy(current)
        gradient["stops"][self._stop._index]["color"] = deepcopy(color)
        # Validate the complete replacement before changing a cached stop or queue.
        properties = ET.Element(f"{{{P_NS}}}spPr")
        _set_shape_gradient_fill(properties, gradient)
        self._stop._fill._queue_gradient(gradient)
        current.clear()
        current.update(gradient)


class _DetachedFillShape:
    def __init__(self, fill_parent: Any) -> None:
        element = getattr(fill_parent, "_element", fill_parent)
        if not hasattr(element, "find") or not hasattr(element, "insert"):
            raise TypeError("fill parent must be an XML element")
        self._payload = {"kind": "shape", "fill_parent": element}


class LineDashRefusal(ValueError):
    """A custom line dash edit was refused before changing the package."""


def _check_arrowhead_locks(shape: Shape) -> None:
    from .shape_locks import check_shape_locks

    check_shape_locks(shape, "arrowhead edit", "no_change_arrowheads")


class LineFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @property
    def color(self) -> ColorFormat:
        return ColorFormat(self._shape, "line")

    @property
    def fill(self) -> LineFillFormat:
        return LineFillFormat(self._shape)

    @property
    def width(self) -> Any:
        raw = self._shape._payload.get("line_width")
        if not isinstance(raw, int):
            raw = _shape_line_width(self._shape)
            self._shape._payload["line_width"] = raw
        return _emu_value(raw)

    @width.setter
    def width(self, value: Any) -> None:
        width = _coerce_emu(value, "line width")
        if width == int(self.width):
            return
        self._shape._payload["line_width"] = width
        self._shape._slide._presentation._queue_shape_line_width(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            width,
        )

    @property
    def dash_style(self) -> Any:
        if "line_dash_style" not in self._shape._payload:
            self._shape._payload["line_dash_style"] = _shape_line_dash_style(self._shape)
        return _line_dash_style_value(self._shape._payload["line_dash_style"])

    @dash_style.setter
    def dash_style(self, value: Any) -> None:
        dash_style = _normalize_line_dash_style(value)
        if self.custom_dash is not None:
            # The queued preset writer cannot remove a:custDash; cleanly cut over.
            def mutate(properties: ET.Element) -> None:
                line = _ensure_line(properties)
                _remove_children(line, "custDash")
                _remove_children(line, "prstDash")
                if dash_style is not None:
                    _insert_ordered(
                        line, ET.Element(_a("prstDash"), {"val": dash_style}), _LINE_ORDER
                    )

            _edit_shape_properties(self._shape, "setting a preset line dash", mutate)
            self._shape._payload["line_dash_style"] = dash_style
            return
        if "line_dash_style" not in self._shape._payload:
            self._shape._payload["line_dash_style"] = _shape_line_dash_style(self._shape)
        if dash_style == self._shape._payload["line_dash_style"]:
            return
        self._shape._payload["line_dash_style"] = dash_style
        self._shape._slide._presentation._queue_shape_line_dash(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            dash_style,
        )

    @property
    def custom_dash(self) -> tuple[tuple[float, float], ...] | None:
        """Ordered ``(dash, gap)`` pairs, measured in multiples of line width."""
        line = _line_of(_read_shape_properties(self._shape))
        custom = None if line is None else line.find(_a("custDash"))
        if custom is None:
            return None
        try:
            pairs = tuple(
                (float(stop.attrib["d"]) / 100000, float(stop.attrib["sp"]) / 100000)
                for stop in custom.findall(_a("ds"))
            )
            if not pairs or any(
                not math.isfinite(length) or length <= 0 for pair in pairs for length in pair
            ):
                raise ValueError("custom dash must contain positive dash/gap pairs")
        except (ValueError, KeyError, OverflowError) as error:
            raise LineDashRefusal(str(error)) from error
        return pairs

    @custom_dash.setter
    def custom_dash(self, value: Any) -> None:
        custom = None
        if value is not None:
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
                raise LineDashRefusal("custom dash must be a nonempty ordered sequence or None")
            custom = ET.Element(_a("custDash"))
            for pair in value:
                if (
                    not isinstance(pair, Sequence)
                    or isinstance(pair, (str, bytes))
                    or len(pair) != 2
                ):
                    raise LineDashRefusal("custom dash items must be (dash, gap) pairs")
                attributes = {}
                for name, length in zip(("d", "sp"), pair, strict=True):
                    if isinstance(length, bool) or not isinstance(length, (int, float)):
                        raise LineDashRefusal("custom dash lengths must be finite positive numbers")
                    if not 0 < length <= (2**31 - 1) / 100000:
                        raise LineDashRefusal(
                            "custom dash lengths are outside the positive XML range"
                        )
                    raw = round(length * 100000)
                    if raw <= 0:
                        raise LineDashRefusal("custom dash length is below DrawingML precision")
                    attributes[name] = str(raw)
                ET.SubElement(custom, _a("ds"), attributes)
        normalized = (
            None
            if custom is None
            else tuple(
                (int(stop.attrib["d"]) / 100000, int(stop.attrib["sp"]) / 100000) for stop in custom
            )
        )
        if normalized == self.custom_dash:
            return

        def mutate(properties: ET.Element) -> None:
            line = _ensure_line(properties)
            _remove_children(line, "custDash")
            if custom is not None:
                _remove_children(line, "prstDash")
                _insert_ordered(line, deepcopy(custom), _LINE_ORDER)

        try:
            _edit_shape_properties(self._shape, "setting a custom line dash", mutate)
        except ValueError as error:
            raise LineDashRefusal(str(error)) from error
        self._shape._payload.pop("line_dash_style", None)

    @property
    def cap(self) -> str | None:
        if "line_cap" in self._shape._payload:
            return self._shape._payload["line_cap"]
        from .shape_line_end_edits import get_shape_line_cap

        return get_shape_line_cap(self._shape)

    @cap.setter
    def cap(self, value: Any) -> None:
        from .shape_line_end_edits import validate_line_cap

        val = validate_line_cap(value)
        self._shape._payload["line_cap"] = val
        self._shape._slide._presentation._queue_shape_line_end_property(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            "cap",
            val,
        )

    @property
    def join(self) -> str | None:
        if "line_join" in self._shape._payload:
            return self._shape._payload["line_join"]
        from .shape_line_end_edits import get_shape_line_join

        return get_shape_line_join(self._shape)

    @join.setter
    def join(self, value: Any) -> None:
        from .shape_line_end_edits import validate_line_join

        val = validate_line_join(value)
        self._shape._payload["line_join"] = val
        self._shape._slide._presentation._queue_shape_line_end_property(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            "join",
            val,
        )

    @property
    def miter_limit(self) -> int | None:
        if "line_miter_limit" in self._shape._payload:
            return self._shape._payload["line_miter_limit"]
        from .shape_line_end_edits import get_shape_line_miter_limit

        return get_shape_line_miter_limit(self._shape)

    @miter_limit.setter
    def miter_limit(self, value: Any) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("miter_limit must be an int or None")
            if value < 0:
                raise ValueError(f"miter limit must be non-negative, got {value}")
        self._shape._payload["line_miter_limit"] = value
        self._shape._slide._presentation._queue_shape_line_end_property(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            "miter_limit",
            value,
        )

    @property
    def head_end(self) -> dict[str, str | None] | None:
        if "line_head_end" in self._shape._payload:
            return self._shape._payload["line_head_end"]
        from .shape_line_end_edits import get_shape_line_head_end

        return get_shape_line_head_end(self._shape)

    @head_end.setter
    def head_end(self, value: Any) -> None:
        from .shape_line_end_edits import validate_line_end_spec

        spec = validate_line_end_spec(value)
        _check_arrowhead_locks(self._shape)
        self._shape._payload["line_head_end"] = spec
        self._shape._slide._presentation._queue_shape_line_end_property(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            "head_end",
            spec,
        )

    @property
    def tail_end(self) -> dict[str, str | None] | None:
        if "line_tail_end" in self._shape._payload:
            return self._shape._payload["line_tail_end"]
        from .shape_line_end_edits import get_shape_line_tail_end

        return get_shape_line_tail_end(self._shape)

    @tail_end.setter
    def tail_end(self, value: Any) -> None:
        from .shape_line_end_edits import validate_line_end_spec

        spec = validate_line_end_spec(value)
        _check_arrowhead_locks(self._shape)
        self._shape._payload["line_tail_end"] = spec
        self._shape._slide._presentation._queue_shape_line_end_property(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            "tail_end",
            spec,
        )

    @property
    def compound_style(self) -> str | None:
        """single, double, thick_thin, thin_thick or triple; None when unset."""
        raw = _line_attribute(self._shape, "cmpd")
        return None if raw is None else _FRIENDLY_COMPOUND.get(raw, raw)

    @compound_style.setter
    def compound_style(self, value: Any) -> None:
        compound = _choice(value, LINE_COMPOUND_STYLES, "line compound style")
        _set_line_attribute(self._shape, "cmpd", compound, "compound style")

    @property
    def alignment(self) -> str | None:
        """Pen alignment: ``center`` or ``inset``; None when unset (centre)."""
        raw = _line_attribute(self._shape, "algn")
        return None if raw is None else _FRIENDLY_ALIGNMENT.get(raw, raw)

    @alignment.setter
    def alignment(self, value: Any) -> None:
        alignment = _choice(value, LINE_ALIGNMENTS, "line alignment")
        _set_line_attribute(self._shape, "algn", alignment, "alignment")

    @property
    def sketch_style(self) -> str | None:
        """Hand-drawn style (``ask:lineSketchStyleProps``): curved, freehand,
        scribble, or None for a straight line."""
        return _line_sketch_style(_read_shape_properties(self._shape))

    @sketch_style.setter
    def sketch_style(self, value: Any) -> None:
        if isinstance(value, str) and value.strip().lower() == "none":
            value = None
        xml_value = _choice(value, LINE_SKETCH_STYLES, "line sketch style")
        sketch = None if xml_value is None else _FRIENDLY_SKETCH[xml_value]
        if sketch == self.sketch_style:
            return
        seed = _sketch_seed(self._shape)
        _edit_shape_properties(
            self._shape,
            "setting the line sketch style",
            lambda properties: _set_line_sketch_style(properties, sketch, seed),
        )


class ShadowFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @property
    def inherit(self) -> bool:
        prs = getattr(getattr(self._shape, "_slide", None), "_presentation", None)
        if prs is not None:
            queue = getattr(prs, "_shape_effect_edits", None)
            if isinstance(queue, dict):
                key = (self._shape._slide._index, _shape_style_ref(self._shape))
                pending = queue.get(key)
                if isinstance(pending, dict) and pending.get("outer_shadow") is not None:
                    return False
            inherit_queue = getattr(prs, "_shape_shadow_inherit_edits", None)
            if isinstance(inherit_queue, dict):
                key = (self._shape._slide._index, _shape_style_ref(self._shape))
                if key in inherit_queue:
                    return bool(inherit_queue[key])
        raw = self._shape._payload.get("shadow_inherit")
        if not isinstance(raw, bool):
            raw = (
                _group_shadow_inherit(self._shape)
                if _is_group_shape(self._shape)
                else _shape_shadow_inherit(self._shape)
            )
            self._shape._payload["shadow_inherit"] = raw
        return raw

    @inherit.setter
    def inherit(self, value: Any) -> None:
        inherit = bool(value)
        if inherit == self.inherit:
            return
        prs = self._shape._slide._presentation
        if inherit:
            _ = self.outer_shadow
            self._shape._payload["outer_shadow"] = "__cleared__"
            if prs is not None:
                queue = getattr(prs, "_shape_effect_edits", None)
                if isinstance(queue, dict):
                    key = (self._shape._slide._index, _shape_style_ref(self._shape))
                    pending = queue.get(key)
                    if isinstance(pending, dict):
                        pending.pop("outer_shadow", None)
                        if not pending:
                            queue.pop(key, None)
        self._shape._payload["shadow_inherit"] = inherit
        self._shape._slide._presentation._queue_shape_shadow_inherit(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            inherit,
        )

    @property
    def outer_shadow(self) -> OuterShadowSpec | None:
        from .shape_shadow_edits import get_shape_outer_shadow

        return get_shape_outer_shadow(self._shape)

    @outer_shadow.setter
    def outer_shadow(self, value: Any) -> None:
        if value is None:
            self.clear_outer_shadow()
        else:
            self.set_outer_shadow(value)

    def set_outer_shadow(
        self,
        spec: OuterShadowSpec | Mapping[str, Any],
    ) -> None:
        from .shape_shadow_edits import (
            _assert_shape_editable,
            validate_outer_shadow_spec,
        )

        _assert_shape_editable(self._shape)
        validated = validate_outer_shadow_spec(spec)
        if validated is None:
            self.clear_outer_shadow()
            return

        current = self.outer_shadow
        if current == validated and not self.inherit:
            return

        self._shape._payload["outer_shadow"] = validated
        self._shape._payload["shadow_inherit"] = False
        prs = self._shape._slide._presentation
        ref = _shape_style_ref(self._shape)
        slide_idx = self._shape._slide._index
        prs._queue_shape_effect(slide_idx, ref, "outer_shadow", validated.to_dict())

    def clear_outer_shadow(self) -> None:
        from .shape_shadow_edits import _assert_shape_editable

        _assert_shape_editable(self._shape)
        current = self.outer_shadow
        if current is None:
            return

        self._shape._payload["outer_shadow"] = "__cleared__"
        prs = self._shape._slide._presentation
        ref = _shape_style_ref(self._shape)
        slide_idx = self._shape._slide._index
        prs._queue_shape_effect(slide_idx, ref, "outer_shadow", None)

    def _set_advanced_effect(self, effect: str, value: Any) -> None:
        from .shape_shadow_edits import (
            _assert_shape_editable,
            _validate_advanced_effect,
        )

        _assert_shape_editable(self._shape)
        presentation = self._shape._slide._presentation
        queue = getattr(presentation, "_queue_shape_effect", None)
        if not callable(queue):
            raise TypeError("presentation does not provide the shape-effect save queue")
        validated = _validate_advanced_effect(effect, value)
        spec = None if validated is None else validated.to_dict()
        queue(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            effect,
            spec,
        )

    @property
    def inner_shadow(self) -> Any:
        from .shape_shadow_edits import _get_shape_advanced_effect

        return _get_shape_advanced_effect(self._shape, "inner_shadow")

    @inner_shadow.setter
    def inner_shadow(self, value: Any) -> None:
        self._set_advanced_effect("inner_shadow", value)

    @property
    def soft_edge(self) -> Any:
        from .shape_shadow_edits import _get_shape_advanced_effect

        return _get_shape_advanced_effect(self._shape, "soft_edge")

    @soft_edge.setter
    def soft_edge(self, value: Any) -> None:
        self._set_advanced_effect("soft_edge", value)

    @property
    def reflection(self) -> Any:
        from .shape_shadow_edits import _get_shape_advanced_effect

        return _get_shape_advanced_effect(self._shape, "reflection")

    @reflection.setter
    def reflection(self, value: Any) -> None:
        self._set_advanced_effect("reflection", value)

    @property
    def blur(self) -> Any:
        """The shape's ``a:blur`` as a ``BlurEffect``, or ``None``; assign ``None`` to delete."""
        from .shape_shadow_edits import _get_shape_advanced_effect

        return _get_shape_advanced_effect(self._shape, "blur")

    @blur.setter
    def blur(self, value: Any) -> None:
        self._set_advanced_effect("blur", value)

    @property
    def fill_overlay(self) -> Any:
        """The shape's ``a:fillOverlay`` as a ``FillOverlayEffect``, or ``None``."""
        from .shape_shadow_edits import _get_shape_advanced_effect

        return _get_shape_advanced_effect(self._shape, "fill_overlay")

    @fill_overlay.setter
    def fill_overlay(self, value: Any) -> None:
        self._set_advanced_effect("fill_overlay", value)

    @property
    def preset_shadow(self) -> Any:
        """The shape's ``a:prstShdw`` as a ``PresetShadowEffect``, or ``None``."""
        from .shape_shadow_edits import _get_shape_advanced_effect

        return _get_shape_advanced_effect(self._shape, "preset_shadow")

    @preset_shadow.setter
    def preset_shadow(self, value: Any) -> None:
        self._set_advanced_effect("preset_shadow", value)


class LineFillFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        self._shape._payload["line_fill_type"] = "solid"
        self._shape._payload.pop("line_rgb", None)
        self._shape._payload.pop("line_pattern", None)
        self._shape._payload.pop("line_pattern_fore_rgb", None)
        self._shape._payload.pop("line_pattern_back_rgb", None)
        self._shape._slide._presentation._queue_shape_line_solid(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def background(self) -> None:
        if self._fill_type() == "background":
            return
        self._shape._payload["line_fill_type"] = "background"
        self._shape._payload.pop("line_rgb", None)
        self._shape._payload.pop("line_pattern", None)
        self._shape._payload.pop("line_pattern_fore_rgb", None)
        self._shape._payload.pop("line_pattern_back_rgb", None)
        self._shape._slide._presentation._queue_shape_line_background(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        pattern = None
        self._shape._payload["line_fill_type"] = "patterned"
        self._shape._payload.pop("line_rgb", None)
        self._shape._payload["line_pattern"] = pattern
        self._shape._slide._presentation._queue_shape_line_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> ColorFormat:
        return ColorFormat(self._shape, "line_fill_fore")

    @property
    def back_color(self) -> ColorFormat:
        return ColorFormat(self._shape, "line_fill_back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._pattern_raw())

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern == self._pattern_raw():
            return
        self._shape._payload["line_pattern"] = pattern
        self._shape._slide._presentation._queue_shape_line_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    def _fill_type(self) -> str | None:
        if "line_fill_type" not in self._shape._payload:
            self._shape._payload["line_fill_type"] = _shape_line_fill_type(self._shape)
        return self._shape._payload["line_fill_type"]

    def _pattern_raw(self) -> str | None:
        if "line_pattern" not in self._shape._payload:
            self._shape._payload["line_pattern"] = _shape_line_fill_pattern(self._shape)
        return self._shape._payload["line_pattern"]


class ColorFormat(ColorTextAndTransforms):
    """Package-preserving solid and pattern color formatting."""

    def __init__(self, shape: Shape, target: str) -> None:
        self._shape = shape
        self._target = target

    @property
    def rgb(self) -> Any:
        try:
            color = self._color_element()
        except ColorFormatRefusal as error:
            raise TypeError(str(error)) from error
        if color is None:
            return None
        if color.tag != _a("srgbClr"):
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        return _rgb_value(color.get("val", "").upper())

    @rgb.setter
    def rgb(self, value: Any) -> None:
        try:
            rgb = _normalize_rgb(value)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        try:
            color = self._color_element()
        except ColorFormatRefusal as error:
            raise TypeError(str(error)) from error
        if color is not None and color.tag == _a("srgbClr") and color.get("val") == rgb:
            return
        self._set_color_element(ET.Element(_a("srgbClr"), {"val": rgb}))

    @property
    def brightness(self) -> float:
        color = self._color_element()
        return 0.0 if color is None else _brightness_from_color_element(color)

    @brightness.setter
    def brightness(self, value: Any) -> None:
        try:
            brightness = float(value)
            if isinstance(value, bool) or not -1.0 <= brightness <= 1.0:
                raise ValueError("brightness must be between -1.0 and 1.0")
            color = deepcopy(self._color_element())
            if color is None:
                return
            if _brightness_from_color_element(color) == brightness and (
                brightness != 0.0 or not _has_brightness_modifiers(color)
            ):
                return
            _set_color_brightness(color, brightness)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        self._set_color_element(color)

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        return _theme_color_value(
            color.get("val", "") if color is not None and color.tag == _a("schemeClr") else ""
        )

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        try:
            xml_value = _normalize_theme_color(value)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        existing = self._color_element()
        if (
            existing is not None
            and existing.tag == _a("schemeClr")
            and (existing.get("val") == xml_value)
        ):
            return
        color = ET.Element(_a("schemeClr"), {"val": xml_value})
        if existing is not None:
            color.extend(deepcopy(list(existing)))
        self._set_color_element(color)

    @property
    def type(self) -> Any:
        color = self._color_element()
        return (
            None
            if color is None
            else {
                "srgbClr": MSO_COLOR_TYPE.RGB,
                "schemeClr": MSO_COLOR_TYPE.SCHEME,
                "sysClr": MSO_COLOR_TYPE.SYSTEM,
                "prstClr": MSO_COLOR_TYPE.PRESET,
                "scrgbClr": MSO_COLOR_TYPE.SCRGB,
                "hslClr": MSO_COLOR_TYPE.HSL,
            }.get(_xml_local_name(color.tag))
        )

    def _location(self) -> tuple[str, str | None]:
        target = "line" if self._target.startswith("line") else "fill"
        key = "line_fill_type" if target == "line" else "fill_type"
        fill_type = self._shape._payload.get(key)
        if fill_type is None:
            fill_type = (
                _shape_line_fill_type(self._shape)
                if target == "line"
                else _shape_fill_type(self._shape)
            )
        is_back = self._target.endswith("back")
        if is_back and fill_type != "patterned":
            raise ColorFormatRefusal("fill is not patterned, call .patterned() first")
        role = ("back" if is_back else "fore") if fill_type == "patterned" else None
        return target, role

    def _theme_part_owner(self) -> Any:
        return getattr(self._shape, "_slide", None)

    def _color_element(self) -> ET.Element | None:
        target, role = self._location()
        slide = getattr(self._shape, "_slide", None)
        if slide is not None:
            key = (slide._index, _shape_style_ref(self._shape))
            suffix = "color" if role is None else f"pattern_{role}_color"
            edits = getattr(slide._presentation, f"_shape_{target}_{suffix}_edits", {})
            if key in edits:
                value = edits[key]
                return color_element(
                    {"type": "rgb", "value": value} if isinstance(value, str) else value
                )
            if role is None and key in getattr(
                slide._presentation, f"_shape_{target}_background_edits", ()
            ):
                return None
        properties = _read_shape_properties(self._shape)
        parent = _line_of(properties) if target == "line" else properties
        if parent is not None:
            path = (
                "solidFill"
                if role is None
                else ("pattFill/" + ("bgClr" if role == "back" else "fgClr"))
            )
            container = parent.find("/".join(_a(name) for name in path.split("/")))
            if container is not None:
                for child in container:
                    if _xml_local_name(child.tag).endswith("Clr"):
                        return deepcopy(child)
        if role is not None:
            return ET.Element(_a("srgbClr"), {"val": "FFFFFF" if role == "back" else "000000"})
        return None

    def _set_color_element(self, color: ET.Element) -> None:
        try:
            validate_text_color_element(color)
            target, role = self._location()
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        detached = _detached_fill_parent(self._shape)
        element_backed = color.tag in {_a("scrgbClr"), _a("hslClr")}
        if detached is None and (
            element_backed
            or (role is not None and len(color))
            or (role is not None and color.tag != _a("srgbClr"))
        ):

            def mutate(properties: ET.Element) -> None:
                parent = _ensure_line(properties) if target == "line" else properties
                if role is None:
                    container = replace_fill_element(parent, "solidFill")
                else:
                    pattern = parent.find(_a("pattFill"))
                    if pattern is None:
                        raise ColorFormatRefusal(
                            "pattern fill is missing; save pending edits first"
                        )
                    container = _ensure_child(
                        pattern,
                        "bgClr" if role == "back" else "fgClr",
                        {
                            "fgClr": 0,
                            "bgClr": 1,
                        },
                    )
                for child in list(container):
                    container.remove(child)
                container.append(deepcopy(color))

            try:
                _edit_shape_properties(self._shape, "editing a color", mutate)
            except ValueError as error:
                raise ColorFormatRefusal(str(error)) from error
            self._shape._payload.pop(f"{target}_pattern_{role}_rgb", None)
            self._shape._payload.pop(f"{target}_color_payload", None)
            self._shape._payload.pop(f"{target}_rgb", None)
            return
        if detached is not None:
            parent = _ensure_line(detached) if target == "line" else detached
            if role is None:
                container = replace_fill_element(parent, "solidFill")
            else:
                pattern = parent.find(_a("pattFill"))
                container = _ensure_child(
                    pattern,
                    "bgClr" if role == "back" else "fgClr",
                    {
                        "fgClr": 0,
                        "bgClr": 1,
                    },
                )
            for child in list(container):
                container.remove(child)
            container.append(deepcopy(color))
        else:
            slide = self._shape._slide
            suffix = "color" if role is None else f"pattern_{role}_color"
            payload = color_payload_from_element(color) if role is None else color.get("val")
            queue = getattr(slide._presentation, f"_queue_shape_{target}_{suffix}")
            queue(slide._index, _shape_style_ref(self._shape), payload)
        key = "line_fill_type" if target == "line" else "fill_type"
        if role is None:
            self._shape._payload[key] = "solid"
            for suffix in (
                "rgb",
                "color_payload",
                "pattern",
                "pattern_fore_rgb",
                "pattern_back_rgb",
            ):
                self._shape._payload.pop(f"{target}_{suffix}", None)
            if target == "fill":
                self._shape._payload.pop("fill_gradient", None)
        else:
            self._shape._payload.pop(f"{target}_pattern_{role}_rgb", None)


# --------------------------------------------------------------------------- #
# Package-backed shape-property edits                                         #
# --------------------------------------------------------------------------- #
#
# The settings below have no save-queue channel; each edit rewrites the saved
# slide part through ``Presentation._rewrite_package`` and rebases the
# presentation on it, exactly like the slide utilities. Queued facade edits
# must therefore be saved before one of these setters runs.

ASK_NS = "http://schemas.microsoft.com/office/drawing/2018/sketchyshapes"
LINE_SKETCH_EXT_URI = "{C807C97D-BFC1-408E-A445-0C87EB9F89A2}"
ET.register_namespace("ask", ASK_NS)

_FILL_NAMES = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")
_SHAPE_PROPERTIES_ORDER = {
    "xfrm": 0,
    "custGeom": 1,
    "prstGeom": 1,
    **dict.fromkeys(_FILL_NAMES, 2),
    "ln": 3,
    "effectLst": 4,
    "effectDag": 4,
    "scene3d": 5,
    "sp3d": 6,
    "extLst": 7,
}
_LINE_ORDER = {
    **dict.fromkeys(("noFill", "solidFill", "gradFill", "pattFill"), 0),
    "prstDash": 1,
    "custDash": 1,
    "round": 2,
    "bevel": 2,
    "miter": 2,
    "headEnd": 3,
    "tailEnd": 4,
    "extLst": 5,
}


def _a(name: str) -> str:
    return f"{{{A_NS}}}{name}"


def _insert_ordered(parent: ET.Element, child: ET.Element, order: dict[str, int]) -> None:
    """Insert ``child`` before the first sibling that the schema orders later."""
    rank = order[_xml_local_name(child.tag)]
    for index, existing in enumerate(parent):
        if order.get(_xml_local_name(existing.tag), -1) > rank:
            parent.insert(index, child)
            return
    parent.append(child)


def _ensure_child(
    parent: ET.Element,
    name: str,
    order: dict[str, int],
    attrib: dict[str, str] | None = None,
) -> ET.Element:
    child = parent.find(_a(name))
    if child is None:
        child = ET.Element(_a(name), attrib or {})
        _insert_ordered(parent, child, order)
    return child


def _remove_children(parent: ET.Element, name: str) -> None:
    for child in parent.findall(_a(name)):
        parent.remove(child)


def _choice(value: Any, choices: dict[str, str], label: str) -> str | None:
    """Resolve a friendly name or XML token; ``None`` clears the setting."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a str or None")
    key = value.strip()
    if key in choices.values():
        return key
    xml_value = choices.get(key.lower().replace("-", "_").replace(" ", "_"))
    if xml_value is None:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"unsupported {label} {value!r}; expected one of {allowed}")
    return xml_value


def _shape_properties_of(element: ET.Element, *, create: bool) -> ET.Element | None:
    tag = _xml_local_name(element.tag)
    if tag not in {"sp", "cxnSp", "pic"}:
        raise TypeError("this format is only available on shapes, connectors and pictures")
    properties = element.find(f"{{{P_NS}}}spPr")
    if properties is None and create:
        properties = ET.SubElement(element, f"{{{P_NS}}}spPr")
    return properties


def _read_shape_properties(shape: Any) -> ET.Element | None:
    """Return the shape's saved ``p:spPr`` (or detached fill parent), or None."""
    detached = _detached_fill_parent(shape)
    if detached is not None:
        return detached
    if _is_pending_shape(shape):
        return None
    from .package_parts import open_package_source

    with open_package_source(shape._slide._presentation._source_path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    return _shape_properties_of(_shape_xml_element(root, shape._payload), create=False)


def _edit_shape_properties(shape: Any, operation: str, mutate: Any) -> None:
    """Apply ``mutate(spPr)`` to the shape's saved XML and rebase on the result."""
    detached = _detached_fill_parent(shape)
    if detached is not None:
        mutate(detached)
        return
    presentation = shape._slide._presentation
    partname = shape._slide.partname
    payload = shape._payload

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        root = ET.fromstring(package.read(partname))
        properties = _shape_properties_of(_shape_xml_element(root, payload), create=True)
        mutate(properties)
        return (
            {partname: ET.tostring(root, encoding="utf-8", xml_declaration=True)},
            set(),
            None,
        )

    presentation._rewrite_package(operation, plan)


# --------------------------------------------------------------------------- #
# Line compound style, alignment and sketch style                             #
# --------------------------------------------------------------------------- #

LINE_COMPOUND_STYLES = {
    "single": "sng",
    "double": "dbl",
    "thick_thin": "thickThin",
    "thin_thick": "thinThick",
    "triple": "tri",
}
LINE_ALIGNMENTS = {"center": "ctr", "centre": "ctr", "inset": "in"}
LINE_SKETCH_STYLES = {
    "curved": "lineSketchCurved",
    "freehand": "lineSketchFreehand",
    "scribble": "lineSketchScribble",
}
_FRIENDLY_COMPOUND = {xml: name for name, xml in LINE_COMPOUND_STYLES.items()}
_FRIENDLY_ALIGNMENT = {"ctr": "center", "in": "inset"}
_FRIENDLY_SKETCH = {xml: name for name, xml in LINE_SKETCH_STYLES.items()}


def _line_of(properties: ET.Element | None) -> ET.Element | None:
    return None if properties is None else properties.find(_a("ln"))


def _ensure_line(properties: ET.Element) -> ET.Element:
    return _ensure_child(properties, "ln", _SHAPE_PROPERTIES_ORDER)


def _line_sketch_ext(line: ET.Element | None) -> ET.Element | None:
    extensions = None if line is None else line.find(_a("extLst"))
    if extensions is None:
        return None
    for extension in extensions.findall(_a("ext")):
        if extension.get("uri") == LINE_SKETCH_EXT_URI:
            return extension
    return None


def _line_sketch_style(properties: ET.Element | None) -> str | None:
    extension = _line_sketch_ext(_line_of(properties))
    if extension is None:
        return None
    props = extension.find(f"{{{ASK_NS}}}lineSketchStyleProps")
    kind = None if props is None else props.find(f"{{{ASK_NS}}}type")
    if kind is None or not len(kind):
        return None
    name = _xml_local_name(kind[0].tag)
    if name == "lineSketchNone":
        return None
    if name not in _FRIENDLY_SKETCH:
        raise ValueError(f"unsupported line sketch type {name!r}")
    return _FRIENDLY_SKETCH[name]


def _set_line_sketch_style(properties: ET.Element, sketch: str | None, seed: int) -> None:
    """Apply ``sketch`` the way PowerPoint stores a Sketchy Shape.

    PowerPoint keeps the shape's original geometry inside
    ``ask:lineSketchStyleProps`` and regenerates the hand-drawn outline from it
    and the seed; the shape's own geometry must then be an ``a:custGeom`` (a
    preset geometry next to the extension makes PowerPoint drop the sketch).
    That custGeom carries the unsketched outline so consumers without sketch
    support still draw the shape.  Clearing restores the original geometry.
    """
    line = _line_of(properties)
    existing = _line_sketch_ext(line)
    old_props = None if existing is None else existing.find(f"{{{ASK_NS}}}lineSketchStyleProps")
    original = None if old_props is None else _geometry_of(old_props)
    if sketch is None:
        if existing is None:
            return
        extensions = line.find(_a("extLst"))
        extensions.remove(existing)
        if not len(extensions):
            line.remove(extensions)
        if original is not None:
            _replace_geometry(properties, deepcopy(original))
        return
    if original is None:
        original = _geometry_of(properties)
        if original is None:
            raise ValueError("a line sketch style needs an explicit shape geometry")
        outline = (
            deepcopy(original)
            if _xml_local_name(original.tag) == "custGeom"
            else _preset_outline_geometry(properties, original)
        )
        _replace_geometry(properties, outline)
    line = _ensure_line(properties)
    sketch_seed = seed if old_props is None else int(old_props.get("sd", str(seed)))
    props = ET.Element(f"{{{ASK_NS}}}lineSketchStyleProps", {"sd": str(sketch_seed)})
    props.append(deepcopy(original))
    kind = ET.SubElement(props, f"{{{ASK_NS}}}type")
    ET.SubElement(kind, f"{{{ASK_NS}}}{LINE_SKETCH_STYLES[sketch]}")
    if existing is None:
        extensions = _ensure_child(line, "extLst", _LINE_ORDER)
        existing = ET.SubElement(extensions, _a("ext"), {"uri": LINE_SKETCH_EXT_URI})
    for child in list(existing):
        existing.remove(child)
    existing.append(props)


def _geometry_of(parent: ET.Element) -> ET.Element | None:
    geometry = parent.find(_a("custGeom"))
    return parent.find(_a("prstGeom")) if geometry is None else geometry


def _replace_geometry(properties: ET.Element, geometry: ET.Element) -> None:
    _remove_children(properties, "custGeom")
    _remove_children(properties, "prstGeom")
    _insert_ordered(properties, geometry, _SHAPE_PROPERTIES_ORDER)


def _preset_outline_geometry(properties: ET.Element, preset_geometry: ET.Element) -> ET.Element:
    """The ``a:custGeom`` tracing ``preset_geometry`` at the shape's size."""
    from .preset_outline_geometry import resolve_preset
    from .render_refusals import RenderRefusal

    adjustments: list[float] = []
    for guide in preset_geometry.findall(f"{_a('avLst')}/{_a('gd')}"):
        formula = guide.get("fmla", "")
        try:
            if not formula.startswith("val "):
                raise ValueError
            adjustments.append(float(formula[4:]))
        except ValueError:
            raise ValueError(
                f"cannot trace preset adjustment {formula!r} for a line sketch style"
            ) from None

    preset = preset_geometry.get("prst", "")
    extent = properties.find(f"{_a('xfrm')}/{_a('ext')}")
    if extent is None:
        raise ValueError(
            "a line sketch style on a preset shape needs the shape's own size (a:xfrm)"
        )
    width, height = int(extent.get("cx", "0")), int(extent.get("cy", "0"))
    try:
        resolved = resolve_preset(preset, float(width), float(height), tuple(adjustments))
    except RenderRefusal as exc:
        raise ValueError(
            f"cannot trace preset geometry {preset!r} for a line sketch style: {exc}"
        ) from exc

    def point(parent: ET.Element, xy: tuple[float, float]) -> None:
        ET.SubElement(parent, _a("pt"), {"x": str(round(xy[0])), "y": str(round(xy[1]))})

    custom = ET.Element(_a("custGeom"))
    for name in ("avLst", "gdLst", "ahLst", "cxnLst"):
        ET.SubElement(custom, _a(name))
    ET.SubElement(custom, _a("rect"), {"l": "l", "t": "t", "r": "r", "b": "b"})
    paths = ET.SubElement(custom, _a("pathLst"))
    commands = {"line": "lnTo", "quad": "quadBezTo", "cubic": "cubicBezTo"}
    for preset_path in resolved.paths:
        attributes = {"w": str(width), "h": str(height)}
        if not preset_path.filled:
            attributes["fill"] = "none"
        if not preset_path.stroked:
            attributes["stroke"] = "0"
        path = ET.SubElement(paths, _a("path"), attributes)
        point(ET.SubElement(path, _a("moveTo")), preset_path.start)
        for segment in preset_path.segments:
            command = ET.SubElement(path, _a(commands[segment.kind]))
            targets = segment.points[-1:] if segment.kind == "line" else segment.points
            for xy in targets:
                point(command, xy)
        if preset_path.closed:
            ET.SubElement(path, _a("close"))
    return custom


def _line_attribute(shape: Any, name: str) -> str | None:
    line = _line_of(_read_shape_properties(shape))
    return None if line is None else line.get(name)


def _set_line_attribute(shape: Any, name: str, value: str | None, label: str) -> None:
    if _line_attribute(shape, name) == value:
        return

    def mutate(properties: ET.Element) -> None:
        if value is None:
            line = _line_of(properties)
            if line is not None:
                line.attrib.pop(name, None)
            return
        _ensure_line(properties).set(name, value)

    _edit_shape_properties(shape, f"setting line {label}", mutate)


def _sketch_seed(shape: Any) -> int:
    """Deterministic ``sd`` for a new sketch: PowerPoint seeds randomly."""
    import zlib

    return zlib.crc32(f"wolfppt-line-sketch:{shape._payload.get('id')}".encode())


# --------------------------------------------------------------------------- #
# Fill blend mode                                                             #
# --------------------------------------------------------------------------- #

FILL_BLEND_MODES = {
    "overlay": "over",
    "multiply": "mult",
    "screen": "screen",
    "darken": "darken",
    "lighten": "lighten",
}
_FRIENDLY_BLEND = {xml: name for name, xml in FILL_BLEND_MODES.items()}


def _fill_overlay(properties: ET.Element | None) -> ET.Element | None:
    effects = None if properties is None else properties.find(_a("effectLst"))
    return None if effects is None else effects.find(_a("fillOverlay"))


def _fill_blend_mode(properties: ET.Element | None) -> str | None:
    overlay = _fill_overlay(properties)
    if overlay is None:
        return None
    blend = overlay.get("blend")
    if blend not in _FRIENDLY_BLEND:
        raise ValueError(f"fill overlay declares unsupported blend {blend!r}")
    return _FRIENDLY_BLEND[blend]


def _set_fill_blend_mode(properties: ET.Element, blend: str | None) -> None:
    """Blend the shape's own fill over what lies beneath (``a:fillOverlay``)."""
    if properties.find(_a("effectDag")) is not None:
        raise ValueError("shape declares an effectDag; cannot set a fill blend mode")
    effects = properties.find(_a("effectLst"))
    if blend is None:
        if effects is None:
            return
        _remove_children(effects, "fillOverlay")
        if not len(effects):
            properties.remove(effects)
        return
    fill = next(
        (child for child in properties if _xml_local_name(child.tag) in _FILL_NAMES),
        None,
    )
    if fill is None:
        raise ValueError("set an explicit shape fill before choosing a blend mode")
    from .shape_shadow_edits import _insert_effect_list_child

    effects = _ensure_child(properties, "effectLst", _SHAPE_PROPERTIES_ORDER)
    _remove_children(effects, "fillOverlay")
    overlay = ET.Element(_a("fillOverlay"), {"blend": blend})
    overlay.append(deepcopy(fill))
    _insert_effect_list_child(effects, overlay)
