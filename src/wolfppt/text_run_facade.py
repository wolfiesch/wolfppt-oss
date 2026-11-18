"""Text run facade helpers."""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, overload
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .shape_core_facade import Shape

from .dml.color import ColorTextAndTransforms, color_alpha
from .dml_fill import (
    A_NS,
)
from .dml_fill import (
    brightness_from_color_element as _brightness_from_color_element,
)
from .dml_fill import default_gradient_payload as _default_gradient_payload
from .dml_fill import (
    set_color_brightness as _set_color_brightness,
)
from .dml_fill import (
    validate_text_color_element as _validate_text_color_element,
)
from .enum.dml import MSO_COLOR_TYPE
from .enum.text import MSO_UNDERLINE
from .facade_values import (
    LANGUAGE_ID_NONE as _LANGUAGE_ID_NONE,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    language_id_value as _language_id_value,
)
from .facade_values import (
    normalize_language_id as _normalize_language_id,
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
from .package_parts import PackagePart
from .shape_3d_format import (
    ThreeDFormatRefusal,
    _coordinate,
    _rotation_attributes,
    _scaled,
    _token,
)
from .shape_format_facade import GradientStops as _GradientStops
from .shape_payloads import (
    _shape_paragraph_run_bold,
    _shape_paragraph_run_font_brightness,
    _shape_paragraph_run_font_color_kind,
    _shape_paragraph_run_font_fill_type,
    _shape_paragraph_run_font_language,
    _shape_paragraph_run_font_name,
    _shape_paragraph_run_font_rgb,
    _shape_paragraph_run_font_size,
    _shape_paragraph_run_font_theme_color,
    _shape_paragraph_run_hyperlink_address,
    _shape_paragraph_run_italic,
    _shape_paragraph_run_property_matrix,
    _shape_paragraph_run_strike,
    _shape_paragraph_run_underline,
    _shape_paragraph_runs,
    _sync_shape_text_from_paragraph_runs,
)
from .shape_xml import (
    HyperlinkColorSourceRefusal,
    _part_text_run_xml_element,
    _shape_xml_element,
    hyperlink_color_source_member,
    hyperlink_color_source_xml,
    queued_hyperlink_address,
    saved_hyperlink_color_source,
)
from .text_facade_inspection import (
    _shape_text_run_fill_type,
    _shape_text_run_gradient_payload,
    _shape_text_run_hyperlink_address,
    _shape_text_run_language_id,
    _shape_text_run_pattern,
    _shape_text_run_pattern_rgb,
)
from .text_facade_queue import (
    _group_child_key,
    _group_child_shape_index,
    _is_appended_run,
    _is_group_child_text_shape,
    _is_part_scoped_text_shape,
    _queue_run_bold_state,
    _queue_run_font_color_state,
    _queue_run_font_fill_type_state,
    _queue_run_font_language_state,
    _queue_run_font_name_state,
    _queue_run_font_size_state,
    _queue_run_italic_state,
    _queue_run_state,
    _queue_run_strike_state,
    _queue_run_underline_state,
)
from .text_facade_xml_inspection import (
    _shape_text_part_root,
    _shape_text_run_color,
    _shape_text_run_properties,
)
from .text_text import Font, _Run
from .text_xml import _UNDERLINE_TOKENS, _read_portion_field, _set_portion_format
from .xml_helpers import find_ooxml

#: a:rPr/@sz is ST_TextFontSize (hundredths of a point, 100..400000); Font.size is in EMU and the
#: writer stores ``size // 127``.
_MIN_FONT_SIZE_EMU = 100 * 127
_MAX_FONT_SIZE_EMU = 400000 * 127


def _normalize_underline(value: Any) -> str | None:
    """Map a public underline value to its ``u`` attribute token.

    Accepts ``None`` (inherit), booleans, ``MSO_UNDERLINE`` members, and raw
    ``ST_TextUnderlineType`` tokens such as ``"dbl"``. Other values keep the
    historical truthiness coercion.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "sng" if value else "none"
    token = getattr(value, "xml_value", value)
    if isinstance(token, str):
        if token not in _UNDERLINE_TOKENS:
            raise ValueError(f"unsupported underline value: {value!r}")
        return token
    return "sng" if value else "none"


def _underline_value(token: str | None) -> Any:
    """Public underline value for a ``u`` token, matching python-pptx."""
    if token is None:
        return None
    if token == "sng":
        return True
    if token == "none":
        return False
    for member in MSO_UNDERLINE:
        if member.xml_value == token:
            return member
    return token


def _underline_queue_value(token: str | None) -> bool | str | None:
    """Writer value for a ``u`` token: ``sng``/``none`` keep their boolean
    form; every other style token is written verbatim."""
    if token is None or token not in {"sng", "none"}:
        return token
    return token == "sng"


_COLOR_TYPE_MEMBERS = {
    "srgbClr": "RGB",
    "schemeClr": "SCHEME",
    "hslClr": "HSL",
    "prstClr": "PRESET",
    "scrgbClr": "SCRGB",
    "sysClr": "SYSTEM",
}


def _text_color_type(color: ET.Element | None) -> Any:
    """``MSO_COLOR_TYPE`` member for a DrawingML color choice, or None."""
    if color is None:
        return None
    member = _COLOR_TYPE_MEMBERS.get(color.tag.rpartition("}")[2])
    if member is None:
        return None
    return getattr(MSO_COLOR_TYPE, member)


@dataclass(frozen=True)
class TextShadow:
    """An outer text shadow, as PowerPoint's Format Text Effects > Shadow.

    ``color`` is a six-digit RGB hex string or a theme colour name
    (``"accent1"``, ``"tx1"``, ...); ``transparency`` runs from 0 (opaque) to 1;
    ``blur_radius`` and ``distance`` are EMU; ``direction`` is the clockwise
    angle in degrees from the positive x axis (45 casts down and right).
    """

    color: str = "000000"
    transparency: float = 0.6
    blur_radius: int = 38100
    distance: int = 38100
    direction: float = 45.0


@dataclass(frozen=True)
class TextGlow:
    """A text glow, as PowerPoint's Format Text Effects > Glow.

    ``color`` is a six-digit RGB hex string or a theme colour name, ``radius``
    is the glow size in EMU, and ``transparency`` runs from 0 to 1.
    """

    color: str = "FFC000"
    radius: int = 63500
    transparency: float = 0.6


@dataclass(frozen=True)
class Text3D:
    """A 3-D text format, as PowerPoint's Format Text Effects > 3-D Format.

    ``bevel`` is an ``ST_BevelPresetType`` name for the top bevel (or ``None``);
    lengths are EMU; ``extrusion_color`` is six-digit RGB or ``None``;
    ``material``, ``camera`` and ``lighting`` are the DrawingML preset names.
    Light direction is one of t/tr/r/br/b/bl/l/tl; rotations are (latitude,
    longitude, revolution) degrees modulo 360. Camera field of view is
    optional, in degrees from 0 to 180; bottom bevel defaults to absent.
    """

    bevel: str | None = "circle"
    bevel_width: int = 76200
    bevel_height: int = 76200
    extrusion_height: int = 0
    extrusion_color: str | None = None
    material: str = "warmMatte"
    camera: str = "orthographicFront"
    lighting: str = "threePt"
    lighting_direction: str = "t"
    lighting_rotation: tuple[float, float, float] | None = None
    camera_rotation: tuple[float, float, float] | None = None
    camera_field_of_view: float | None = None
    bottom_bevel: str | None = None
    bottom_bevel_width: int = 76200
    bottom_bevel_height: int = 76200


@dataclass(frozen=True)
class TextLine:
    """A text outline or underline line (``a:ln`` / ``a:uLn``).

    ``width`` is EMU (``None`` inherits); ``color`` is six-digit RGB hex for a
    solid line (``None`` inherits the line fill).
    """

    width: int | None = None
    color: str | None = None


#: Public ``strikethrough_type`` names and their ``ST_TextStrikeType`` tokens.
_STRIKETHROUGH_TOKENS = {
    "none": "noStrike",
    "single": "sngStrike",
    "double": "dblStrike",
}
_STRIKETHROUGH_NAMES = {token: name for name, token in _STRIKETHROUGH_TOKENS.items()}


def _text_line_value(value: Any) -> TextLine | None:
    if value is None:
        return None
    return TextLine(width=value["width"], color=value["color"])


def _text_line_payload(value: TextLine | None, name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, TextLine):
        raise TypeError(f"{name} must be a TextLine or None")
    return {
        "width": value.width,
        "color": None if value.color is None else _normalize_rgb(value.color),
    }


_THEME_COLOR_NAMES = frozenset(
    {
        "bg1",
        "tx1",
        "bg2",
        "tx2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "hlink",
        "folHlink",
        "dk1",
        "lt1",
        "dk2",
        "lt2",
    }
)
#: ST_PositiveCoordinate upper bound (ECMA-376 Part 1, 20.1.10.42).
_MAX_COORDINATE = 27273042316900


def _effect_color_value(value: Any) -> str:
    if isinstance(value, str) and value in _THEME_COLOR_NAMES:
        return value
    return _normalize_rgb(value)


def _alpha(transparency: Any) -> int:
    value = float(transparency)
    if not 0.0 <= value <= 1.0 or math.isnan(value):
        raise ValueError("transparency must be between 0 and 1")
    return round((1.0 - value) * 100000)


def _transparency(alpha: int) -> float:
    return round(1.0 - alpha / 100000.0, 5)


def _effect_length(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int length in EMU")
    if not 0 <= value <= _MAX_COORDINATE:
        raise ValueError(f"{name} must be a non-negative EMU length")
    return int(value)


def _effect_direction(value: Any) -> int:
    degrees = float(value)
    if math.isnan(degrees) or math.isinf(degrees):
        raise ValueError("direction must be a finite angle in degrees")
    return round(degrees * 60000) % 21600000


def _normalize_text_3d(value: Text3D) -> dict[str, Any]:
    def rotation(raw: Any) -> tuple[float, ...] | None:
        attributes = _rotation_attributes(raw)
        return None if attributes is None else tuple(int(v) / 60000 for v in attributes.values())

    try:
        extrusion_color = (
            None if value.extrusion_color is None else _normalize_rgb(value.extrusion_color)
        )
    except ValueError as exc:
        raise ThreeDFormatRefusal(str(exc)) from exc
    fov = _scaled("camera_field_of_view", 60000, 180)(value.camera_field_of_view)
    return {
        "bevel": _token("BEVEL_PRESETS", "bevel", optional=True)(value.bevel),
        "bevel_width": int(_coordinate("bevel_width")(value.bevel_width)),
        "bevel_height": int(_coordinate("bevel_height")(value.bevel_height)),
        "extrusion_height": int(_coordinate("extrusion_height")(value.extrusion_height)),
        "extrusion_color": extrusion_color,
        "material": _token("MATERIAL_PRESETS", "material")(value.material),
        "camera": _token("CAMERA_PRESETS", "camera")(value.camera),
        "lighting": _token("LIGHT_RIG_PRESETS", "lighting")(value.lighting),
        "lighting_direction": _token("LIGHT_RIG_DIRECTIONS", "light rig direction")(
            value.lighting_direction
        ),
        "lighting_rotation": rotation(value.lighting_rotation),
        "camera_rotation": rotation(value.camera_rotation),
        "camera_field_of_view": None if fov is None else int(fov) / 60000,
        "bottom_bevel": _token("BEVEL_PRESETS", "bottom bevel", optional=True)(value.bottom_bevel),
        "bottom_bevel_width": int(_coordinate("bottom_bevel_width")(value.bottom_bevel_width)),
        "bottom_bevel_height": int(_coordinate("bottom_bevel_height")(value.bottom_bevel_height)),
    }


def _source_effect_color(effect: ET.Element) -> tuple[str | None, int]:
    color = next(iter(effect), None)
    if color is None:
        return None, 100000
    name = color.tag.rpartition("}")[2]
    rgb = {
        "srgbClr": color.get("val"),
        "schemeClr": color.get("val"),
        "sysClr": color.get("lastClr"),
    }.get(name)
    alpha = color.find(f"{{{A_NS}}}alpha")
    return rgb, 100000 if alpha is None else int(alpha.get("val", "100000"))


def _source_text_effect(properties: ET.Element, attr: str) -> Any:
    """Read one run text effect from stored ``a:rPr`` in its queue form."""
    if attr == "text_fill_alpha":
        alpha = properties.find(f"{{{A_NS}}}solidFill/*/{{{A_NS}}}alpha")
        return None if alpha is None else int(alpha.get("val", "100000"))
    tag = "glow" if attr == "text_glow" else "outerShdw"
    effect = properties.find(f"{{{A_NS}}}effectLst/{{{A_NS}}}{tag}")
    if effect is None:
        return None
    color, alpha = _source_effect_color(effect)
    if tag == "glow":
        return {"color": color, "alpha": alpha, "radius": int(effect.get("rad", "0"))}
    return {
        "color": color,
        "alpha": alpha,
        "blur_radius": int(effect.get("blurRad", "0")),
        "distance": int(effect.get("dist", "0")),
        "direction": int(effect.get("dir", "0")),
    }


def _source_text_3d(shape: Shape) -> dict[str, Any] | None:
    """Read the stored 3-D text format of a shape's ``a:bodyPr``."""
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        body = find_ooxml(_shape_xml_element(root, shape._payload), f".//{{{A_NS}}}bodyPr")
    except (AttributeError, KeyError, FileNotFoundError):
        return None
    if body is None:
        return None
    scene = find_ooxml(body, f"{{{A_NS}}}scene3d")
    shape_3d = find_ooxml(body, f"{{{A_NS}}}sp3d")
    if scene is None and shape_3d is None:
        return None
    camera = None if scene is None else find_ooxml(scene, f"{{{A_NS}}}camera")
    light = None if scene is None else find_ooxml(scene, f"{{{A_NS}}}lightRig")
    bevel = None if shape_3d is None else find_ooxml(shape_3d, f"{{{A_NS}}}bevelT")
    bottom = None if shape_3d is None else find_ooxml(shape_3d, f"{{{A_NS}}}bevelB")

    def rotation(node: ET.Element | None) -> tuple[float, ...] | None:
        rot = None if node is None else find_ooxml(node, f"{{{A_NS}}}rot")
        return (
            None
            if rot is None
            else tuple(int(rot.get(name, "0")) / 60000 for name in ("lat", "lon", "rev"))
        )

    extrusion = (
        None
        if shape_3d is None
        else find_ooxml(shape_3d, f"{{{A_NS}}}extrusionClr/{{{A_NS}}}srgbClr")
    )
    return {
        "bevel": None if bevel is None else bevel.get("prst", "circle"),
        "bevel_width": 76200 if bevel is None else int(bevel.get("w", "76200")),
        "bevel_height": 76200 if bevel is None else int(bevel.get("h", "76200")),
        "extrusion_height": 0 if shape_3d is None else int(shape_3d.get("extrusionH", "0")),
        "extrusion_color": None if extrusion is None else extrusion.get("val"),
        "material": "warmMatte" if shape_3d is None else shape_3d.get("prstMaterial", "warmMatte"),
        "camera": "orthographicFront"
        if camera is None
        else camera.get("prst", "orthographicFront"),
        "lighting": "threePt" if light is None else light.get("rig", "threePt"),
        "lighting_direction": "t" if light is None else light.get("dir", "t"),
        "lighting_rotation": rotation(light),
        "camera_rotation": rotation(camera),
        "camera_field_of_view": None
        if camera is None or camera.get("fov") is None
        else int(camera.attrib["fov"]) / 60000,
        "bottom_bevel": None if bottom is None else bottom.get("prst", "circle"),
        "bottom_bevel_width": 76200 if bottom is None else int(bottom.get("w", "76200")),
        "bottom_bevel_height": 76200 if bottom is None else int(bottom.get("h", "76200")),
    }


class TextRunCollection(Sequence["TextRun"]):
    def __init__(self, shape: Shape, paragraph_index: int) -> None:
        self._shape = shape
        self._paragraph_index = paragraph_index

    @overload
    def __getitem__(self, index: int) -> TextRun: ...

    @overload
    def __getitem__(self, index: slice) -> list[TextRun]: ...

    def __getitem__(self, index: int | slice) -> TextRun | list[TextRun]:
        runs = _shape_paragraph_runs(self._shape)[self._paragraph_index]
        if isinstance(index, slice):
            return [
                TextRun(self._shape, self._paragraph_index, run_index)
                for run_index in range(*index.indices(len(runs)))
            ]
        if index < 0:
            index += len(runs)
        if index < 0 or index >= len(runs):
            raise IndexError("run index out of range")
        return TextRun(self._shape, self._paragraph_index, index)

    def __iter__(self) -> Iterator[TextRun]:
        for index in range(len(self)):
            yield TextRun(self._shape, self._paragraph_index, index)

    def __len__(self) -> int:
        return len(_shape_paragraph_runs(self._shape)[self._paragraph_index])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [run.text for run in self] == other
        return super().__eq__(other)


class TextRun(_Run):
    def __init__(self, shape: Shape, paragraph_index: int, index: int) -> None:
        self._shape = shape
        self._paragraph_index = paragraph_index
        self._index = index

    def get_effective(self) -> Any:
        """Return this run's effective character formatting and its sources
        (commercial edition; see
        :func:`wolfppt.effective_format_readback.run_effective`)."""
        from .editions import commercial_module

        readback = commercial_module("effective_format_readback", "Reading effective formatting")
        return readback.run_effective(self)

    @property
    def text(self) -> str:
        return _shape_paragraph_runs(self._shape)[self._paragraph_index][self._index]

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        from .shape_locks import check_text_edit_lock

        check_text_edit_lock(self._shape)
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._paragraph_index][self._index] = text
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_run_state(self._shape, self._paragraph_index, self._index)

    @property
    def font(self) -> TextRunFont:
        return TextRunFont(self)

    @property
    def hyperlink(self) -> TextRunHyperlink:
        return TextRunHyperlink(self)


class TextRunHyperlink:
    def __init__(self, run: TextRun) -> None:
        self._run = run

    @property
    def address(self) -> str | None:
        queued, key = self._pending_edits()
        if key in queued:
            value = queued[key]
            return None if value is None else str(value)
        hyperlinks = _shape_paragraph_run_hyperlink_address(self._run._shape)
        address = hyperlinks[self._run._paragraph_index][self._run._index]
        if address is None:
            address = _shape_text_run_hyperlink_address(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            hyperlinks[self._run._paragraph_index][self._run._index] = address
        return str(address) if address else None

    @property
    def part(self) -> PackagePart:
        return self._run.part

    @address.setter
    def address(self, value: str | None) -> None:
        address = str(value) if value else None
        if address == self.address:
            return
        shape = self._run._shape
        paragraph_index = self._run._paragraph_index
        run_index = self._run._index
        top_level = not _is_part_scoped_text_shape(shape) and not _is_group_child_text_shape(shape)
        # Retargeting a link keeps its tooltip and color source; removing it drops them.
        screen_tip = self.screen_tip if top_level and address is not None else None
        color_edit = self._pending_color_edit() if address is not None else None
        hyperlinks = _shape_paragraph_run_hyperlink_address(shape)
        hyperlinks[paragraph_index][run_index] = address
        if address is None and (
            _shape_text_run_hyperlink_address(shape, paragraph_index, run_index) is None
        ):
            # No saved link to remove: clearing only cancels the pending link.
            # A queued removal would target a run the writer may never emit.
            queued, key = self._pending_edits()
            queued.pop(key, None)
            return
        self._queue(address, screen_tip, color_edit)

    @property
    def screen_tip(self) -> str | None:
        """Tooltip text stored in the ``tooltip`` attribute of ``a:hlinkClick``."""
        if self.address is None:
            return None
        queued, key = self._pending_edits()
        if key in queued:
            return getattr(queued[key], "screen_tip", None)
        hyperlink = self._saved_click()
        return None if hyperlink is None else hyperlink.get("tooltip")

    @screen_tip.setter
    def screen_tip(self, value: str | None) -> None:
        screen_tip = None if value is None else str(value)
        if screen_tip == self.screen_tip:
            return
        address = self.address
        if address is None:
            raise ValueError("screen_tip requires a hyperlink address on the run")
        shape = self._run._shape
        if _is_part_scoped_text_shape(shape) or _is_group_child_text_shape(shape):
            raise NotImplementedError(
                "run hyperlink screen_tip editing is only supported for top-level slide shapes"
            )
        self._queue(address, screen_tip, self._pending_color_edit())

    @property
    def color_source(self) -> Any:
        """Where the link text takes its color, stored as ``hlinkClr/@val``.

        A ``PP_HYPERLINK_COLOR_SOURCE`` member, or ``None`` when the hyperlink
        carries no color source. A malformed saved value raises
        ``HyperlinkColorSourceRefusal``.
        """
        return hyperlink_color_source_member(self._color_source_xml())

    @color_source.setter
    def color_source(self, value: Any) -> None:
        requested = hyperlink_color_source_xml(value)
        address = self.address
        if address is None:
            raise HyperlinkColorSourceRefusal(
                "color_source requires a hyperlink address on the run"
            )
        try:
            unchanged = requested == self._color_source_xml()
        except HyperlinkColorSourceRefusal:
            unchanged = False  # an explicit edit replaces a malformed saved value
        if not unchanged:
            self._queue(address, self.screen_tip, (requested,))

    def _color_source_xml(self) -> str | None:
        if self.address is None:
            return None
        edit = self._pending_color_edit()
        if edit is not None:
            return edit[0]
        return saved_hyperlink_color_source(self._saved_click())

    def _pending_color_edit(self) -> tuple[str | None] | None:
        queued, key = self._pending_edits()
        return getattr(queued.get(key), "color_source_edit", None)

    def _saved_click(self) -> Any:
        """The saved ``a:hlinkClick`` of this run, if any."""
        run_properties = _shape_text_run_properties(
            self._run._shape, self._run._paragraph_index, self._run._index
        )
        if run_properties is None:
            return None
        return next(
            (
                child
                for child in run_properties
                if isinstance(child.tag, str) and child.tag.endswith("}hlinkClick")
            ),
            None,
        )

    def _pending_edits(self) -> tuple[dict[Any, Any], tuple[Any, ...]]:
        """The pending hyperlink queue for this run's scope and its key."""
        shape = self._run._shape
        presentation = shape._slide._presentation
        paragraph_index = self._run._paragraph_index
        run_index = self._run._index
        if _is_part_scoped_text_shape(shape):
            return presentation._part_run_hyperlink_edits, (
                shape._slide.partname,
                shape._index,
                paragraph_index,
                run_index,
            )
        if _is_group_child_text_shape(shape):
            return presentation._group_child_run_hyperlink_edits, (
                *_group_child_key(shape),
                paragraph_index,
                run_index,
            )
        return presentation._text_run_hyperlink_edits, self._top_level_key()

    def _top_level_key(self) -> tuple[int, int, int, int]:
        return (
            self._run._shape._slide._index,
            self._run._shape._index,
            self._run._paragraph_index,
            self._run._index,
        )

    def _queue(
        self,
        address: str | None,
        screen_tip: str | None,
        color_edit: tuple[str | None] | None = None,
    ) -> None:
        queued = queued_hyperlink_address(address, screen_tip, color_edit)
        shape = self._run._shape
        presentation = shape._slide._presentation
        paragraph_index = self._run._paragraph_index
        run_index = self._run._index
        if _is_part_scoped_text_shape(shape):
            presentation._queue_part_run_hyperlink(
                shape._slide.partname, shape._index, paragraph_index, run_index, queued
            )
        elif _is_group_child_text_shape(shape):
            presentation._queue_group_child_run_hyperlink(
                *_group_child_key(shape), paragraph_index, run_index, queued
            )
        else:
            presentation._queue_text_run_hyperlink(*self._top_level_key(), queued)


class TextRunFont(Font):
    def __init__(self, run: TextRun) -> None:
        self._run = run

    @property
    def panose(self) -> str | None:
        """Latin font PANOSE classification: 20 hexadecimal digits; None inherits."""
        return self._portion_value("latin.panose")

    @panose.setter
    def panose(self, value: str | None) -> None:
        self._set_portion_value("latin.panose", value)

    @property
    def pitch_family(self) -> int | None:
        """Latin font ST_PitchFamily integer; None removes only this metadata."""
        return self._portion_value("latin.pitchFamily")

    @pitch_family.setter
    def pitch_family(self, value: int | None) -> None:
        self._set_portion_value("latin.pitchFamily", value)

    @property
    def charset(self) -> int | None:
        """Latin font character set as a signed byte (-128 to 127)."""
        return self._portion_value("latin.charset")

    @charset.setter
    def charset(self, value: int | None) -> None:
        self._set_portion_value("latin.charset", value)

    @property
    def east_asian_panose(self) -> str | None:
        """East Asian font PANOSE classification (a:ea@panose)."""
        return self._portion_value("ea.panose")

    @east_asian_panose.setter
    def east_asian_panose(self, value: str | None) -> None:
        self._set_portion_value("ea.panose", value)

    @property
    def east_asian_pitch_family(self) -> int | None:
        """East Asian font ST_PitchFamily integer (a:ea@pitchFamily)."""
        return self._portion_value("ea.pitchFamily")

    @east_asian_pitch_family.setter
    def east_asian_pitch_family(self, value: int | None) -> None:
        self._set_portion_value("ea.pitchFamily", value)

    @property
    def east_asian_charset(self) -> int | None:
        """East Asian font character set as a signed byte (a:ea@charset)."""
        return self._portion_value("ea.charset")

    @east_asian_charset.setter
    def east_asian_charset(self, value: int | None) -> None:
        self._set_portion_value("ea.charset", value)

    @property
    def complex_script_panose(self) -> str | None:
        """Complex-script font PANOSE classification (a:cs@panose)."""
        return self._portion_value("cs.panose")

    @complex_script_panose.setter
    def complex_script_panose(self, value: str | None) -> None:
        self._set_portion_value("cs.panose", value)

    @property
    def complex_script_pitch_family(self) -> int | None:
        """Complex-script font ST_PitchFamily integer (a:cs@pitchFamily)."""
        return self._portion_value("cs.pitchFamily")

    @complex_script_pitch_family.setter
    def complex_script_pitch_family(self, value: int | None) -> None:
        self._set_portion_value("cs.pitchFamily", value)

    @property
    def complex_script_charset(self) -> int | None:
        """Complex-script font character set as a signed byte (a:cs@charset)."""
        return self._portion_value("cs.charset")

    @complex_script_charset.setter
    def complex_script_charset(self, value: int | None) -> None:
        self._set_portion_value("cs.charset", value)

    @property
    def symbol_panose(self) -> str | None:
        """Symbol font PANOSE classification (a:sym@panose)."""
        return self._portion_value("sym.panose")

    @symbol_panose.setter
    def symbol_panose(self, value: str | None) -> None:
        self._set_portion_value("sym.panose", value)

    @property
    def symbol_pitch_family(self) -> int | None:
        """Symbol font ST_PitchFamily integer (a:sym@pitchFamily)."""
        return self._portion_value("sym.pitchFamily")

    @symbol_pitch_family.setter
    def symbol_pitch_family(self, value: int | None) -> None:
        self._set_portion_value("sym.pitchFamily", value)

    @property
    def symbol_charset(self) -> int | None:
        """Symbol font character set as a signed byte (a:sym@charset)."""
        return self._portion_value("sym.charset")

    @symbol_charset.setter
    def symbol_charset(self, value: int | None) -> None:
        self._set_portion_value("sym.charset", value)

    @property
    def rtl(self) -> bool | None:
        """Run-level a:rtl, independent of paragraph direction; None removes it."""
        return self._portion_value("rtl")

    @rtl.setter
    def rtl(self, value: bool | None) -> None:
        self._set_portion_value("rtl", value)

    @property
    def bold(self) -> bool | None:
        run_bold = _shape_paragraph_run_bold(self._run._shape)
        return run_bold[self._run._paragraph_index][self._run._index]

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        run_bold = _shape_paragraph_run_bold(self._run._shape)
        if bold == run_bold[self._run._paragraph_index][self._run._index]:
            return
        run_bold[self._run._paragraph_index][self._run._index] = bold
        _queue_run_bold_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            bold,
        )

    @property
    def italic(self) -> bool | None:
        run_italic = _shape_paragraph_run_italic(self._run._shape)
        return run_italic[self._run._paragraph_index][self._run._index]

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        run_italic = _shape_paragraph_run_italic(self._run._shape)
        if italic == run_italic[self._run._paragraph_index][self._run._index]:
            return
        run_italic[self._run._paragraph_index][self._run._index] = italic
        _queue_run_italic_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            italic,
        )

    @property
    def underline(self) -> Any:
        return _underline_value(self._underline_token())

    @underline.setter
    def underline(self, value: Any) -> None:
        underline = _normalize_underline(value)
        if underline is not None and underline == self._underline_token():
            return
        run_underline = _shape_paragraph_run_underline(self._run._shape)
        run_underline[self._run._paragraph_index][self._run._index] = underline
        _queue_run_underline_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            _underline_queue_value(underline),
        )

    def _underline_token(self) -> str | None:
        shape = self._run._shape
        paragraph_index, run_index = self._run._paragraph_index, self._run._index
        run_underline = _shape_paragraph_run_underline(shape)
        value = run_underline[paragraph_index][run_index]
        if value is True and not _is_appended_run(shape, paragraph_index, run_index):
            # Native summaries report every non-"none" style as True; the run
            # XML carries the exact style.
            run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
            token = None if run_properties is None else run_properties.get("u")
            value = token if token in _UNDERLINE_TOKENS and token != "none" else "sng"
            run_underline[paragraph_index][run_index] = value
        if value is None or isinstance(value, str):
            return value
        return "sng" if value else "none"

    @property
    def strike(self) -> bool | None:
        run_strike = _shape_paragraph_run_strike(self._run._shape)
        return run_strike[self._run._paragraph_index][self._run._index]

    @strike.setter
    def strike(self, value: bool | None) -> None:
        strike = None if value is None else bool(value)
        run_strike = _shape_paragraph_run_strike(self._run._shape)
        # A pending ``strikethrough_type`` would be written after this edit;
        # setting ``strike`` replaces it, as the latest call wins.
        overrides = self._portion_overrides()
        if "strike" in overrides:
            del overrides["strike"]
            self._queue_portion()
        elif (
            strike is not None
            and strike == run_strike[self._run._paragraph_index][self._run._index]
        ):
            return
        run_strike[self._run._paragraph_index][self._run._index] = strike
        self._portion_cache()["native_strike"] = True
        _queue_run_strike_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            strike,
        )

    @property
    def size(self) -> int | None:
        run_size = _shape_paragraph_run_font_size(self._run._shape)
        return run_size[self._run._paragraph_index][self._run._index]

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        if size is not None and not _MIN_FONT_SIZE_EMU <= size <= _MAX_FONT_SIZE_EMU:
            raise ValueError(
                f"font size must be between {_MIN_FONT_SIZE_EMU} and {_MAX_FONT_SIZE_EMU} EMU"
                f" (1 to 4000 points), got {size}"
            )
        run_size = _shape_paragraph_run_font_size(self._run._shape)
        if size is not None and size == run_size[self._run._paragraph_index][self._run._index]:
            return
        run_size[self._run._paragraph_index][self._run._index] = size
        _queue_run_font_size_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            size,
        )

    @property
    def name(self) -> str | None:
        run_name = _shape_paragraph_run_font_name(self._run._shape)
        return run_name[self._run._paragraph_index][self._run._index]

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        run_name = _shape_paragraph_run_font_name(self._run._shape)
        if name is not None and name == run_name[self._run._paragraph_index][self._run._index]:
            return
        run_name[self._run._paragraph_index][self._run._index] = name
        _queue_run_font_name_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            name,
        )

    @property
    def color(self) -> TextRunColorFormat:
        return TextRunColorFormat(self._run)

    @property
    def fill(self) -> TextRunFillFormat:
        return TextRunFillFormat(self._run)

    @property
    def language_id(self) -> Any:
        run_language = _shape_paragraph_run_font_language(self._run._shape)
        value = run_language[self._run._paragraph_index][self._run._index]
        if value is None:
            value = _shape_text_run_language_id(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_language[self._run._paragraph_index][self._run._index] = value
        return _language_id_value(value)

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        run_language = _shape_paragraph_run_font_language(self._run._shape)
        current = run_language[self._run._paragraph_index][self._run._index]
        if current is None:
            current = _shape_text_run_language_id(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_language[self._run._paragraph_index][self._run._index] = current
        if language_id is None and current in (None, _LANGUAGE_ID_NONE):
            return
        if language_id == current:
            return
        run_language[self._run._paragraph_index][self._run._index] = (
            _LANGUAGE_ID_NONE if language_id is None else language_id
        )
        _queue_run_font_language_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            language_id,
        )

    @property
    def shadow(self) -> TextShadow | None:
        """The run's outer text shadow (``a:effectLst/a:outerShdw``)."""
        value = self._effect_state("text_outer_shadow")
        if value is None:
            return None
        return TextShadow(
            color=value["color"],
            transparency=_transparency(value["alpha"]),
            blur_radius=value["blur_radius"],
            distance=value["distance"],
            direction=value["direction"] / 60000.0,
        )

    @shadow.setter
    def shadow(self, value: TextShadow | None) -> None:
        if value is not None and not isinstance(value, TextShadow):
            raise TypeError("shadow must be a TextShadow or None")
        normalized = None
        if value is not None:
            normalized = {
                "color": _effect_color_value(value.color),
                "alpha": _alpha(value.transparency),
                "blur_radius": _effect_length(value.blur_radius, "blur_radius"),
                "distance": _effect_length(value.distance, "distance"),
                "direction": _effect_direction(value.direction),
            }
        self._set_effect_state("text_outer_shadow", normalized)

    @property
    def glow(self) -> TextGlow | None:
        """The run's text glow (``a:effectLst/a:glow``)."""
        value = self._effect_state("text_glow")
        if value is None:
            return None
        return TextGlow(
            color=value["color"],
            radius=value["radius"],
            transparency=_transparency(value["alpha"]),
        )

    @glow.setter
    def glow(self, value: TextGlow | None) -> None:
        if value is not None and not isinstance(value, TextGlow):
            raise TypeError("glow must be a TextGlow or None")
        normalized = None
        if value is not None:
            normalized = {
                "color": _effect_color_value(value.color),
                "alpha": _alpha(value.transparency),
                "radius": _effect_length(value.radius, "radius"),
            }
        self._set_effect_state("text_glow", normalized)

    @property
    def transparency(self) -> float | None:
        """Transparency (0-1) of the run's solid text colour; ``None`` if opaque."""
        value = self._effect_state("text_fill_alpha")
        return None if value is None else _transparency(value)

    @transparency.setter
    def transparency(self, value: float | None) -> None:
        alpha = None if value is None else _alpha(value)
        if alpha == 100000:
            alpha = None
        if alpha is not None and not self._has_solid_color():
            raise ValueError(
                "text transparency needs a solid text colour on the run; set font.color first"
            )
        self._set_effect_state("text_fill_alpha", alpha)

    @property
    def text_3d(self) -> Text3D | None:
        """The 3-D text format of the run's text body.

        DrawingML stores 3-D text on ``a:bodyPr`` (``a:scene3d`` and
        ``a:sp3d``), never on a run, so it applies to every run of the body,
        as PowerPoint's Format Text Effects > 3-D Format does.
        """
        shape = self._run._shape
        if "text_frame_text_3d" not in shape._payload:
            shape._payload["text_frame_text_3d"] = _source_text_3d(shape)
        value = shape._payload["text_frame_text_3d"]
        return None if value is None else Text3D(**value)

    @text_3d.setter
    def text_3d(self, value: Text3D | None) -> None:
        if value is not None and not isinstance(value, Text3D):
            raise TypeError("text_3d must be a Text3D or None")
        normalized = None if value is None else _normalize_text_3d(value)
        current = self.text_3d
        if normalized == (None if current is None else _normalize_text_3d(current)):
            return
        shape = self._run._shape
        shape._payload["text_frame_text_3d"] = normalized
        presentation = shape._slide._presentation
        if _is_part_scoped_text_shape(shape):
            presentation._queue_part_text_frame_advanced(
                shape._slide.partname, shape._index, "text_3d", normalized
            )
        elif _is_group_child_text_shape(shape):
            presentation._queue_group_child_text_frame_advanced(
                shape._slide._index,
                _group_child_shape_index(shape),
                int(shape._payload["_group_child_index"]),
                "text_3d",
                normalized,
            )
        else:
            presentation._queue_text_frame_advanced(
                shape._slide._index, shape._index, "text_3d", normalized
            )

    def _effect_state(self, attr: str) -> Any:
        shape = self._run._shape
        key = (self._run._paragraph_index, self._run._index)
        cached = shape._payload.setdefault("_advanced_run_font", {}).setdefault(key, {})
        if attr not in cached:
            properties = _shape_text_run_properties(shape, *key)
            cached[attr] = None if properties is None else _source_text_effect(properties, attr)
        return cached[attr]

    def _set_effect_state(self, attr: str, value: Any) -> None:
        shape = self._run._shape
        if _is_part_scoped_text_shape(shape) or _is_group_child_text_shape(shape):
            raise ValueError("run text effects are editable on top-level slide shapes only")
        if value == self._effect_state(attr):
            return
        key = (self._run._paragraph_index, self._run._index)
        shape._payload["_advanced_run_font"][key][attr] = value
        shape._slide._presentation._queue_text_run_advanced(
            shape._slide._index, shape._index, *key, attr, value
        )

    def _has_solid_color(self) -> bool:
        shape = self._run._shape
        key = (self._run._paragraph_index, self._run._index)
        queued = shape._slide._presentation._text_run_font_color_edits
        if (shape._slide._index, shape._index, *key) in queued:
            return True
        properties = _shape_text_run_properties(shape, *key)
        fill = None if properties is None else properties.find(f"{{{A_NS}}}solidFill")
        return fill is not None and len(fill) > 0

    # -- portion format fields (a:rPr) ---------------------------------------
    #
    # Every field below is queued as one ``portion`` edit per run holding the
    # session's overrides, written by ``text_xml._set_portion_format``.

    @property
    def strikethrough_type(self) -> str | None:
        """``"none"``, ``"single"`` or ``"double"`` strikethrough; None inherits."""
        overrides = self._portion_overrides()
        if "strike" in overrides:
            token = overrides["strike"]
            return None if token is None else _STRIKETHROUGH_NAMES[token]
        strike = self.strike
        if strike is None:
            return None
        if not strike:
            return "none"
        if self._portion_cache().get("native_strike"):
            return "single"
        source = self._source_portion_value("strike")
        return "double" if source == "dblStrike" else "single"

    @strikethrough_type.setter
    def strikethrough_type(self, value: str | None) -> None:
        if value is not None and value not in _STRIKETHROUGH_TOKENS:
            raise ValueError("strikethrough_type must be 'none', 'single', 'double' or None")
        if value == self.strikethrough_type:
            return
        token = None if value is None else _STRIKETHROUGH_TOKENS[value]
        self._portion_overrides()["strike"] = token
        run_strike = _shape_paragraph_run_strike(self._run._shape)
        run_strike[self._run._paragraph_index][self._run._index] = (
            None if token is None else token != "noStrike"
        )
        self._queue_portion()

    @property
    def double_strike(self) -> bool:
        """True when the run draws a double strikethrough (``dblStrike``)."""
        return self.strikethrough_type == "double"

    @double_strike.setter
    def double_strike(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("double_strike must be bool")
        if value:
            self.strikethrough_type = "double"
        elif self.double_strike:
            self.strikethrough_type = "none"

    @property
    def kerning(self) -> int | None:
        """Smallest font size, in hundredths of a point, kerned (``kern``)."""
        return self._portion_value("kern")

    @kerning.setter
    def kerning(self, value: int | None) -> None:
        self._set_portion_value("kern", value)

    @property
    def caps(self) -> str | None:
        """Capitalisation ``"none"``, ``"small"`` or ``"all"`` (``cap``)."""
        return self._portion_value("cap")

    @caps.setter
    def caps(self, value: str | None) -> None:
        self._set_portion_value("cap", value)
        self._portion_cache()["small_caps"] = None if value is None else value == "small"

    @property
    def east_asian_font(self) -> str | None:
        """East Asian typeface (``a:ea``)."""
        return self._portion_value("ea")

    @east_asian_font.setter
    def east_asian_font(self, value: str | None) -> None:
        self._set_portion_value("ea", value)

    @property
    def complex_script_font(self) -> str | None:
        """Complex-script typeface (``a:cs``)."""
        return self._portion_value("cs")

    @complex_script_font.setter
    def complex_script_font(self, value: str | None) -> None:
        self._set_portion_value("cs", value)

    @property
    def symbol_font(self) -> str | None:
        """Symbol typeface (``a:sym``)."""
        return self._portion_value("sym")

    @symbol_font.setter
    def symbol_font(self, value: str | None) -> None:
        self._set_portion_value("sym", value)

    @property
    def alternative_language_id(self) -> str | None:
        """Alternative language tag such as ``"ja-JP"`` (``altLang``)."""
        return self._portion_value("altLang")

    @alternative_language_id.setter
    def alternative_language_id(self, value: str | None) -> None:
        self._set_portion_value("altLang", value)

    @property
    def bookmark_id(self) -> str | None:
        """Bookmark link target of the run (``bmk``)."""
        return self._portion_value("bmk")

    @bookmark_id.setter
    def bookmark_id(self, value: str | None) -> None:
        self._set_portion_value("bmk", value)

    @property
    def kumimoji(self) -> bool | None:
        """Vertical East Asian text set horizontally (``kumimoji``)."""
        return self._portion_value("kumimoji")

    @kumimoji.setter
    def kumimoji(self, value: bool | None) -> None:
        self._set_portion_value("kumimoji", value)

    @property
    def normalize_height(self) -> bool | None:
        """Normalise character heights to the line (``normalizeH``)."""
        return self._portion_value("normalizeH")

    @normalize_height.setter
    def normalize_height(self, value: bool | None) -> None:
        self._set_portion_value("normalizeH", value)

    @property
    def proofing_disabled(self) -> bool | None:
        """Exclude the run from spelling and grammar checks (``noProof``)."""
        return self._portion_value("noProof")

    @proofing_disabled.setter
    def proofing_disabled(self, value: bool | None) -> None:
        self._set_portion_value("noProof", value)

    @property
    def dirty(self) -> bool | None:
        """Run text changed since the last proofing pass (``dirty``)."""
        return self._portion_value("dirty")

    @dirty.setter
    def dirty(self, value: bool | None) -> None:
        self._set_portion_value("dirty", value)

    @property
    def spelling_error(self) -> bool | None:
        """Run marked as a spelling error (``err``)."""
        return self._portion_value("err")

    @spelling_error.setter
    def spelling_error(self, value: bool | None) -> None:
        self._set_portion_value("err", value)

    @property
    def smart_tag_clean(self) -> bool | None:
        """Smart tags of the run are up to date (``smtClean``)."""
        return self._portion_value("smtClean")

    @smart_tag_clean.setter
    def smart_tag_clean(self, value: bool | None) -> None:
        self._set_portion_value("smtClean", value)

    @property
    def smart_tag_id(self) -> int | None:
        """Smart tag identifier of the run (``smtId``)."""
        return self._portion_value("smtId")

    @smart_tag_id.setter
    def smart_tag_id(self, value: int | None) -> None:
        self._set_portion_value("smtId", value)

    @property
    def outline(self) -> TextLine | None:
        """Text outline (``a:ln``) as a :class:`TextLine`."""
        return _text_line_value(self._portion_value("ln"))

    @outline.setter
    def outline(self, value: TextLine | None) -> None:
        self._set_portion_value("ln", _text_line_payload(value, "outline"))

    @property
    def underline_line(self) -> TextLine | str | None:
        """Underline stroke: a :class:`TextLine` (``a:uLn``) or ``"text"`` to
        follow the text outline (``a:uLnTx``)."""
        value = self._portion_value("uLn")
        return value if value is None or value == "text" else _text_line_value(value)

    @underline_line.setter
    def underline_line(self, value: TextLine | str | None) -> None:
        payload = value if value == "text" else _text_line_payload(value, "underline_line")
        self._set_portion_value("uLn", payload)

    @property
    def underline_fill(self) -> str | None:
        """Underline colour as RGB hex (``a:uFill``) or ``"text"`` to follow the
        text fill (``a:uFillTx``)."""
        return self._portion_value("uFill")

    @underline_fill.setter
    def underline_fill(self, value: Any) -> None:
        payload = value if value is None or value == "text" else _normalize_rgb(value)
        self._set_portion_value("uFill", payload)

    def _portion_cache(self) -> dict[str, Any]:
        shape = self._run._shape
        key = (self._run._paragraph_index, self._run._index)
        return shape._payload.setdefault("_advanced_run_font", {}).setdefault(key, {})

    def _portion_overrides(self) -> dict[str, Any]:
        return self._portion_cache().setdefault("portion", {})

    def _source_portion_value(self, name: str) -> Any:
        shape = self._run._shape
        paragraph_index, run_index = self._run._paragraph_index, self._run._index
        if _is_appended_run(shape, paragraph_index, run_index):
            return None
        try:
            if "." in name or name == "rtl":
                root = _shape_text_part_root(shape)
                element = _shape_xml_element(root, shape._payload)
                run = _part_text_run_xml_element(element, paragraph_index, run_index)
                properties = find_ooxml(run, f"{{{A_NS}}}rPr")
            else:
                properties = _shape_text_run_properties(shape, paragraph_index, run_index)
        except (AttributeError, IndexError, KeyError, FileNotFoundError):
            return None
        return _read_portion_field(properties, name)

    def _portion_value(self, name: str) -> Any:
        overrides = self._portion_overrides()
        if name in overrides:
            return overrides[name]
        return self._source_portion_value(name)

    def _set_portion_value(self, name: str, value: Any) -> None:
        _set_portion_format(ET.Element(f"{{{A_NS}}}rPr"), {name: value})
        if value == self._portion_value(name):
            return
        self._portion_overrides()[name] = value
        self._queue_portion()

    def _queue_portion(self) -> None:
        shape = self._run._shape
        presentation = shape._slide._presentation
        paragraph_index, run_index = self._run._paragraph_index, self._run._index
        value = dict(self._portion_overrides())
        if _is_part_scoped_text_shape(shape):
            presentation._queue_part_run_font(
                shape._slide.partname,
                shape._index,
                paragraph_index,
                run_index,
                "portion",
                value,
            )
        elif _is_group_child_text_shape(shape):
            presentation._queue_group_child_run_font(
                shape._slide._index,
                _group_child_shape_index(shape),
                int(shape._payload["_group_child_index"]),
                paragraph_index,
                run_index,
                "portion",
                value,
            )
        else:
            presentation._queue_text_run_advanced(
                shape._slide._index,
                shape._index,
                paragraph_index,
                run_index,
                "portion",
                value,
            )


def _shape_paragraph_run_font_fill_payload(
    shape: Shape,
) -> list[list[dict[str, Any] | None]]:
    return _shape_paragraph_run_property_matrix(
        shape,
        "paragraph_run_font_fill_payload",
        filter_fn=lambda val: val if isinstance(val, dict) else None,
    )


class TextRunFillFormat:
    def __init__(self, run: TextRun) -> None:
        self._run = run

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        run_fill_types[self._run._paragraph_index][self._run._index] = "solid"
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        color_kind = _shape_paragraph_run_font_color_kind(self._run._shape)
        color_kind[self._run._paragraph_index][self._run._index] = None
        self._set_payload({"type": "solid", "color": None})
        _queue_run_font_fill_type_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            "solid",
        )

    def background(self) -> None:
        if self._fill_type() == "background":
            return
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        run_fill_types[self._run._paragraph_index][self._run._index] = "background"
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        color_kind = _shape_paragraph_run_font_color_kind(self._run._shape)
        color_kind[self._run._paragraph_index][self._run._index] = None
        self._set_payload({"type": "background"})
        _queue_run_font_fill_type_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            "background",
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        payload = {"type": "patterned", "pattern": None}
        self._queue_payload(payload)

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        payload = {"type": "gradient", "gradient": _default_gradient_payload()}
        self._queue_payload(payload)

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> TextRunFillColorFormat:
        return TextRunFillColorFormat(self._run, "fore")

    @property
    def back_color(self) -> TextRunFillColorFormat:
        return TextRunFillColorFormat(self._run, "back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._payload().get("pattern"))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        payload = self._payload()
        if payload.get("pattern") == pattern:
            return
        payload["pattern"] = pattern
        self._queue_payload(payload)

    @property
    def gradient_angle(self) -> float | None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

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
    def gradient_stops(self) -> _GradientStops:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _fill_type(self) -> str | None:
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        value = run_fill_types[self._run._paragraph_index][self._run._index]
        if value is None:
            value = _shape_text_run_fill_type(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_fill_types[self._run._paragraph_index][self._run._index] = value
        return value

    def _payload(self) -> dict[str, Any]:
        payloads = _shape_paragraph_run_font_fill_payload(self._run._shape)
        payload = payloads[self._run._paragraph_index][self._run._index]
        if isinstance(payload, dict):
            return payload
        fill_type = self._fill_type()
        payload = {"type": fill_type}
        if fill_type == "patterned":
            payload["pattern"] = _shape_text_run_pattern(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            payload["pattern_fore_rgb"] = _shape_text_run_pattern_rgb(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
                "fgClr",
            )
            payload["pattern_back_rgb"] = _shape_text_run_pattern_rgb(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
                "bgClr",
            )
        elif fill_type == "gradient":
            payload["gradient"] = (
                _shape_text_run_gradient_payload(
                    self._run._shape,
                    self._run._paragraph_index,
                    self._run._index,
                )
                or _default_gradient_payload()
            )
        payloads[self._run._paragraph_index][self._run._index] = payload
        return payload

    def _set_payload(self, payload: dict[str, Any]) -> None:
        payloads = _shape_paragraph_run_font_fill_payload(self._run._shape)
        payloads[self._run._paragraph_index][self._run._index] = payload

    def _queue_payload(self, payload: dict[str, Any]) -> None:
        payload = deepcopy(payload)
        self._set_payload(payload)
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        run_fill_types[self._run._paragraph_index][self._run._index] = payload.get("type")
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        color_kind = _shape_paragraph_run_font_color_kind(self._run._shape)
        color_kind[self._run._paragraph_index][self._run._index] = None
        _queue_run_font_fill_type_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            payload,
        )

    def _gradient_payload(self) -> dict[str, Any]:
        payload = self._payload()
        gradient = payload.get("gradient")
        if not isinstance(gradient, dict):
            gradient = _default_gradient_payload()
            payload["gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        payload = self._payload()
        payload["type"] = "gradient"
        payload["gradient"] = gradient
        self._queue_payload(payload)


class TextRunFillColorFormat(ColorTextAndTransforms):
    def __init__(self, run: TextRun, target: str) -> None:
        self._run = run
        self._target = target

    def _theme_part_owner(self) -> Any:
        return getattr(self._run._shape, "_slide", None)

    def _color_element(self) -> ET.Element | None:
        fill = TextRunFillFormat(self._run)
        if fill._fill_type() != "patterned":
            if self._target == "back":
                raise TypeError("fill is not patterned, call .patterned() first")
            return TextRunColorFormat(self._run)._color_element()
        payload = fill._payload()
        color_key = f"pattern_{self._target}_color"
        if isinstance(payload.get(color_key), ET.Element):
            return deepcopy(payload[color_key])
        properties = _shape_text_run_properties(
            self._run._shape, self._run._paragraph_index, self._run._index
        )
        holder = "bgClr" if self._target == "back" else "fgClr"
        source = (
            None
            if properties is None
            else find_ooxml(properties, f"{{{A_NS}}}pattFill/{{{A_NS}}}{holder}")
        )
        color = None if source is None or not len(source) else deepcopy(source[0])
        key = "pattern_back_rgb" if self._target == "back" else "pattern_fore_rgb"
        rgb = fill._payload().get(key)
        if rgb is not None:
            if color is None:
                color = ET.Element(f"{{{A_NS}}}srgbClr", {"val": rgb})
            else:
                color.tag = f"{{{A_NS}}}srgbClr"
                color.attrib.clear()
                color.set("val", rgb)
        return color

    def _set_color_element(self, color: ET.Element) -> None:
        fill = TextRunFillFormat(self._run)
        if fill._fill_type() == "patterned":
            payload = fill._payload()
            payload[f"pattern_{self._target}_color"] = deepcopy(color)
            payload.pop(f"pattern_{self._target}_rgb", None)
            fill._queue_payload(payload)
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        TextRunColorFormat(self._run)._queue_color(color)

    @property
    def rgb(self) -> Any:
        fill = TextRunFillFormat(self._run)
        if fill._fill_type() == "patterned":
            color = self._color_element()
            return (
                _rgb_value(color.get("val"))
                if color is not None and color.tag == f"{{{A_NS}}}srgbClr"
                else None
            )
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        return TextRunColorFormat(self._run).rgb

    @rgb.setter
    def rgb(self, value: Any) -> None:
        fill = TextRunFillFormat(self._run)
        rgb = _normalize_rgb(value)
        if fill._fill_type() == "patterned":
            color = self._color_element()
            if color is None:
                color = ET.Element(f"{{{A_NS}}}srgbClr", {"val": rgb})
            else:
                color.tag = f"{{{A_NS}}}srgbClr"
                color.attrib.clear()
                color.set("val", rgb)
            self._set_color_element(color)
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        TextRunColorFormat(self._run).rgb = rgb


class TextRunColorFormat(ColorTextAndTransforms):
    def __init__(self, run: TextRun) -> None:
        self._run = run

    def _theme_part_owner(self) -> Any:
        return getattr(self._run._shape, "_slide", None)

    def _set_color_element(self, color: ET.Element) -> None:
        self._queue_color(color)

    def _color_element(self) -> ET.Element | None:
        color = self._stored_color_element()
        shape = self._run._shape
        if _is_part_scoped_text_shape(shape) or _is_group_child_text_shape(shape):
            return color
        key = (shape._slide._index, shape._index, self._run._paragraph_index, self._run._index)
        edits = shape._slide._presentation._text_run_advanced_edits.get(key, {})
        if color is None or "text_fill_alpha" not in edits:
            return color
        color = deepcopy(color)
        for alpha in color.findall(f"{{{A_NS}}}alpha"):
            color.remove(alpha)
        if edits["text_fill_alpha"] is not None:
            ET.SubElement(color, f"{{{A_NS}}}alpha", {"val": str(edits["text_fill_alpha"])})
        return color

    def _stored_color_element(self) -> ET.Element | None:
        payloads = _shape_paragraph_run_font_fill_payload(self._run._shape)
        payload = payloads[self._run._paragraph_index][self._run._index]
        if payload is not None:
            if payload.get("type") != "solid":
                return None
            if "color" in payload:
                return payload["color"]
        if _is_appended_run(self._run._shape, self._run._paragraph_index, self._run._index):
            return None
        return _shape_text_run_color(self._run._shape, self._run._paragraph_index, self._run._index)

    def _queue_color(self, color: ET.Element) -> None:
        _validate_text_color_element(color)
        alpha = round(color_alpha(color) * 100000)
        xml = ET.tostring(color, encoding="unicode")
        _queue_run_font_color_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            {"type": "xml", "value": xml},
        )
        TextRunFillFormat(self._run)._set_payload({"type": "solid", "color": color})
        shape = self._run._shape
        paragraph, run = self._run._paragraph_index, self._run._index
        shape._payload.setdefault("_advanced_run_font", {}).setdefault((paragraph, run), {})[
            "text_fill_alpha"
        ] = None if alpha == 100000 else alpha
        if not (_is_part_scoped_text_shape(shape) or _is_group_child_text_shape(shape)):
            key = (shape._slide._index, shape._index, paragraph, run)
            advanced = shape._slide._presentation._text_run_advanced_edits
            if key in advanced:
                advanced[key].pop("text_fill_alpha", None)
                if not advanced[key]:
                    del advanced[key]
        is_rgb = color.tag == f"{{{A_NS}}}srgbClr"
        is_scheme = color.tag == f"{{{A_NS}}}schemeClr"
        _shape_paragraph_run_font_rgb(shape)[paragraph][run] = color.get("val") if is_rgb else None
        _shape_paragraph_run_font_theme_color(shape)[paragraph][run] = (
            color.get("val") if is_scheme else None
        )
        _shape_paragraph_run_font_color_kind(shape)[paragraph][run] = (
            "rgb" if is_rgb else "scheme" if is_scheme else None
        )
        _shape_paragraph_run_font_fill_type(shape)[paragraph][run] = "solid"
        _shape_paragraph_run_font_brightness(shape)[paragraph][run] = (
            _brightness_from_color_element(color)
        )

    def _set_base_color(self, tag: str, value: str) -> None:
        color = self._color_element()
        if color is None:
            color = ET.Element(f"{{{A_NS}}}{tag}", {"val": value})
        else:
            if color.tag == f"{{{A_NS}}}{tag}" and color.get("val") == value:
                return
            color = deepcopy(color)
            # Keep the full ordered transform sequence, including noncanonical
            # luminance pairs that cannot be represented by scalar brightness.
            color.tag = f"{{{A_NS}}}{tag}"
            color.attrib.clear()
            color.set("val", value)
        self._queue_color(color)

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}srgbClr":
            return None
        return _rgb_value(color.attrib["val"].upper())

    @rgb.setter
    def rgb(self, value: Any) -> None:
        self._set_base_color("srgbClr", _normalize_rgb(value))

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.attrib["val"])

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        self._set_base_color("schemeClr", _normalize_theme_color(value))

    @property
    def type(self) -> Any:
        return _text_color_type(self._color_element())

    @property
    def brightness(self) -> float:
        color = self._color_element()
        return 0.0 if color is None else _brightness_from_color_element(color)

    @brightness.setter
    def brightness(self, value: Any) -> None:
        brightness = float(value)
        if not math.isfinite(brightness) or not -1.0 <= brightness <= 1.0:
            raise ValueError("brightness must be a finite number between -1.0 and 1.0")
        color = self._color_element()
        if color is None:
            raise ValueError("brightness requires an explicit solid text color")
        color = deepcopy(color)
        _set_color_brightness(color, brightness)
        self._queue_color(color)
