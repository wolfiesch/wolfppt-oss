"""Typed DrawingML effect containers: effect lists, effect graphs and their codec."""

from __future__ import annotations

import copy
import math
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .shape_edit_refs import shape_edit_ref
from .shape_glow_edits import (
    GlowSpec,
    glow_element,
    inspect_glow_element,
    validate_glow_spec,
)
from .shape_shadow_edits import (
    _SUPPORTED_COLOR_TAGS,
    A_NS,
    P_NS,
    VALID_SHADOW_COLOR_TYPES,
    InnerShadowSpec,
    OuterShadowSpec,
    ReflectionSpec,
    SoftEdgeSpec,
    _advanced_effect_element,
    _assert_shape_editable,
    _canonical_source_path,
    _inspect_advanced_element,
    _inspect_outer_shadow_element,
    _outer_shadow_element,
    _shape_properties_element_from_shape,
    _supports_shape_shadow,
    _walk_effect_dag,
    validate_blur_radius,
    validate_direction,
    validate_distance,
    validate_outer_shadow_spec,
    validate_transparency,
)
from .shape_xml import _shape_xml_element
from .xml_helpers import xml_local_name as _xml_local_name

# --------------------------------------------------------------------------- #
# Effect containers: typed effect lists and effect graphs                     #
# --------------------------------------------------------------------------- #

VALID_BLEND_MODES: frozenset[str] = frozenset({"over", "mult", "screen", "darken", "lighten"})
# ST_PresetShadowVal: the twenty preset shadows of the shadow gallery.
VALID_PRESET_SHADOWS: frozenset[str] = frozenset(f"shdw{n}" for n in range(1, 21))
VALID_CONTAINER_TYPES: frozenset[str] = frozenset({"sib", "tree"})
_ANGLE_UNITS = 21600000


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite, got {number}")
    return number


def _fraction(value: Any, label: str, *, low: float = 0.0, high: float | None = 1.0) -> float:
    """A DrawingML percentage as a fraction, at its 1/1000 % resolution."""
    number = _number(value, label)
    if number < low or (high is not None and number > high):
        bound = "" if high is None else f", {high}"
        raise ValueError(f"{label} must be in [{low}{bound}], got {number}")
    return round(number, 5)


def _flag(value: Any, label: str) -> bool:
    if not isinstance(value, bool) and value not in (0, 1):
        raise TypeError(f"{label} must be a boolean, got {type(value).__name__}")
    return bool(value)


def _choice(value: Any, label: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{label} must be one of {sorted(allowed)}, got {value!r}")
    return value


@dataclass(frozen=True)
class EffectColor:
    """The colour of a graph effect: sRGB or theme colour plus transparency."""

    color_type: str = "rgb"
    color_value: str = "000000"
    transparency: float = 0.0

    def __init__(
        self,
        color_type: str = "rgb",
        color_value: str = "000000",
        transparency: Any = 0.0,
        *,
        rgb: Any = None,
        theme_color: Any = None,
    ) -> None:
        if rgb is not None and theme_color is not None:
            raise ValueError("cannot specify both rgb and theme_color on EffectColor")
        if rgb is not None:
            color_type, color_value = "rgb", _normalize_rgb(rgb)
        elif theme_color is not None:
            color_type, color_value = "scheme", _normalize_theme_color(theme_color)
        else:
            color_type = _choice(color_type, "color_type", VALID_SHADOW_COLOR_TYPES)
            color_value = (
                _normalize_rgb(color_value)
                if color_type == "rgb"
                else _normalize_theme_color(color_value)
            )
        object.__setattr__(self, "color_type", color_type)
        object.__setattr__(self, "color_value", color_value)
        object.__setattr__(self, "transparency", validate_transparency(transparency))

    @property
    def rgb(self) -> str | None:
        return self.color_value if self.color_type == "rgb" else None

    @property
    def theme_color(self) -> Any:
        return _theme_color_value(self.color_value) if self.color_type == "scheme" else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "color_type": self.color_type,
            "color_value": self.color_value,
            "transparency": self.transparency,
        }


def _effect_color(value: Any) -> EffectColor:
    if isinstance(value, EffectColor):
        return value
    if isinstance(value, Mapping):
        return EffectColor(**dict(value))
    raise TypeError(f"effect color must be an EffectColor or mapping, got {type(value).__name__}")


@dataclass(frozen=True)
class BlurEffect:
    """``a:blur``: blur the effect input by ``radius`` EMU, growing its bounds."""

    radius: int = 0
    grow: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "radius", validate_blur_radius(self.radius))
        object.__setattr__(self, "grow", _flag(self.grow, "grow"))

    def to_dict(self) -> dict[str, Any]:
        return {"radius": self.radius, "grow": self.grow}


@dataclass(frozen=True)
class FillOverlayEffect:
    """``a:fillOverlay``: a solid fill blended over the input with ``blend``."""

    blend: str = "over"
    color: EffectColor = EffectColor()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blend", _choice(self.blend, "blend", VALID_BLEND_MODES))
        object.__setattr__(self, "color", _effect_color(self.color))

    def to_dict(self) -> dict[str, Any]:
        return {"blend": self.blend, "color": self.color.to_dict()}


@dataclass(frozen=True)
class PresetShadowEffect:
    """``a:prstShdw``: one of the twenty gallery shadows at ``distance``/``direction``."""

    preset: str = "shdw1"
    distance: int = 0
    direction: float = 0.0
    color: EffectColor = EffectColor()

    def __post_init__(self) -> None:
        object.__setattr__(self, "preset", _choice(self.preset, "preset", VALID_PRESET_SHADOWS))
        object.__setattr__(self, "distance", validate_distance(self.distance))
        object.__setattr__(self, "direction", validate_direction(self.direction))
        object.__setattr__(self, "color", _effect_color(self.color))

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "distance": self.distance,
            "direction": self.direction,
            "color": self.color.to_dict(),
        }


@dataclass(frozen=True)
class AlphaBiLevelEffect:
    """``a:alphaBiLevel``: alpha below ``threshold`` becomes 0, the rest opaque."""

    threshold: float = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(self, "threshold", _fraction(self.threshold, "threshold"))

    def to_dict(self) -> dict[str, Any]:
        return {"threshold": self.threshold}


@dataclass(frozen=True)
class AlphaCeilingEffect:
    """``a:alphaCeiling``: every non-zero alpha becomes fully opaque."""

    def to_dict(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class AlphaFloorEffect:
    """``a:alphaFloor``: every alpha short of fully opaque becomes zero."""

    def to_dict(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class AlphaInverseEffect:
    """``a:alphaInv``: inverse alpha, optionally in ``color``."""

    color: EffectColor | None = None

    def __post_init__(self) -> None:
        if self.color is not None:
            object.__setattr__(self, "color", _effect_color(self.color))

    def to_dict(self) -> dict[str, Any]:
        return {"color": None if self.color is None else self.color.to_dict()}


@dataclass(frozen=True)
class AlphaModulateFixedEffect:
    """``a:alphaModFix``: alpha multiplied by ``amount`` (1.0 keeps it)."""

    amount: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _fraction(self.amount, "amount", high=None))

    def to_dict(self) -> dict[str, Any]:
        return {"amount": self.amount}


@dataclass(frozen=True)
class AlphaReplaceEffect:
    """``a:alphaRepl``: every alpha replaced by ``alpha``."""

    alpha: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "alpha", _fraction(self.alpha, "alpha"))

    def to_dict(self) -> dict[str, Any]:
        return {"alpha": self.alpha}


@dataclass(frozen=True)
class HslEffect:
    """``a:hsl``: hue turned by ``hue`` degrees, saturation and luminance shifted."""

    hue: float = 0.0
    saturation: float = 0.0
    luminance: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "hue", validate_direction(self.hue))
        for name in ("saturation", "luminance"):
            object.__setattr__(self, name, _fraction(getattr(self, name), name, low=-1.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "hue": self.hue,
            "saturation": self.saturation,
            "luminance": self.luminance,
        }


@dataclass(frozen=True)
class TintEffect:
    """``a:tint``: colours shifted towards (or away from) ``hue`` by ``amount``."""

    hue: float = 0.0
    amount: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "hue", validate_direction(self.hue))
        object.__setattr__(self, "amount", _fraction(self.amount, "amount", low=-1.0))

    def to_dict(self) -> dict[str, Any]:
        return {"hue": self.hue, "amount": self.amount}


@dataclass(frozen=True)
class ColorReplaceEffect:
    """``a:clrRepl``: every colour replaced by ``color``, alpha kept."""

    color: EffectColor = EffectColor()

    def __post_init__(self) -> None:
        object.__setattr__(self, "color", _effect_color(self.color))

    def to_dict(self) -> dict[str, Any]:
        return {"color": self.color.to_dict()}


@dataclass(frozen=True)
class EffectReference:
    """``a:effect``: the output of a named container or of an input stream.

    ``ref`` is a container name or one of ``fill``, ``line``, ``fillLine`` and
    ``children``.
    """

    ref: str = "fill"

    def __post_init__(self) -> None:
        if not isinstance(self.ref, str) or not self.ref.split():
            raise ValueError("effect reference needs a non-empty ref token")
        object.__setattr__(self, "ref", " ".join(self.ref.split()))

    def to_dict(self) -> dict[str, Any]:
        return {"ref": self.ref}


@dataclass(frozen=True)
class EffectContainer:
    """``a:cont``: effects applied as siblings (``sib``) or in sequence (``tree``)."""

    effects: tuple[Any, ...] = ()
    container_type: str = "sib"
    name: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.effects, (str, bytes, Mapping)) or not isinstance(
            self.effects, Sequence
        ):
            raise TypeError("container effects must be a sequence of effects")
        effects = tuple(_effect_node(effect) for effect in self.effects)
        if any(isinstance(effect, EffectListSpec) for effect in effects) or any(
            type(effect) is EffectDagSpec for effect in effects
        ):
            raise ValueError("effect containers hold graph effects, not roots")
        object.__setattr__(self, "effects", effects)
        object.__setattr__(
            self,
            "container_type",
            _choice(self.container_type, "container_type", VALID_CONTAINER_TYPES),
        )
        if self.name is not None:
            if not isinstance(self.name, str) or not self.name.split():
                raise ValueError("container name must be a non-empty token")
            object.__setattr__(self, "name", " ".join(self.name.split()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "effects": [effect_to_dict(effect) for effect in self.effects],
            "container_type": self.container_type,
            "name": self.name,
        }


@dataclass(frozen=True)
class EffectDagSpec(EffectContainer):
    """``a:effectDag``: a shape's effect graph, rooted in this container.

    Container names must be unique, references must name a container of the
    graph (or an input stream), and references must not form a cycle.
    """

    def __post_init__(self) -> None:
        EffectContainer.__post_init__(self)
        _walk_effect_dag(_container_element(self, "effectDag"))


@dataclass(frozen=True)
class AlphaModulateEffect:
    """``a:alphaMod``: alpha multiplied by the alpha of ``container``'s output."""

    container: EffectContainer = EffectContainer()

    def __post_init__(self) -> None:
        object.__setattr__(self, "container", _nested_container(self.container))

    def to_dict(self) -> dict[str, Any]:
        return {"container": self.container.to_dict()}


@dataclass(frozen=True)
class BlendEffect:
    """``a:blend``: ``container``'s output blended with the input by ``blend``."""

    blend: str = "over"
    container: EffectContainer = EffectContainer()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blend", _choice(self.blend, "blend", VALID_BLEND_MODES))
        object.__setattr__(self, "container", _nested_container(self.container))

    def to_dict(self) -> dict[str, Any]:
        return {"blend": self.blend, "container": self.container.to_dict()}


@dataclass(frozen=True)
class EffectListSpec:
    """``a:effectLst``: at most one of each list effect, in schema order.

    Holds blur, fill overlay, glow, inner shadow, outer shadow, preset shadow,
    reflection and soft edge.  An empty list states "no effects" and so
    overrides the theme effect style.
    """

    effects: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.effects, (str, bytes, Mapping)) or not isinstance(
            self.effects, Sequence
        ):
            raise TypeError("effect list effects must be a sequence of effects")
        effects = [_effect_node(effect) for effect in self.effects]
        kinds = [_effect_kind(effect) for effect in effects]
        foreign = sorted({kind for kind in kinds if kind not in _LIST_KINDS})
        if foreign:
            raise ValueError(f"an effect list cannot hold {foreign}; use an EffectDagSpec")
        repeated = sorted({kind for kind in kinds if kinds.count(kind) > 1})
        if repeated:
            raise ValueError(f"an effect list holds at most one of each: {repeated}")
        effects.sort(key=lambda effect: _LIST_KINDS.index(_effect_kind(effect)))
        object.__setattr__(self, "effects", tuple(effects))

    def to_dict(self) -> dict[str, Any]:
        return {"effects": [effect_to_dict(effect) for effect in self.effects]}


def _nested_container(value: Any) -> EffectContainer:
    if type(value) is EffectContainer:
        return value
    if isinstance(value, Mapping):
        values = {key: item for key, item in value.items() if key != "kind"}
        return EffectContainer(**values)
    raise TypeError("expected an EffectContainer")


# Kind -> (value type, DrawingML element).  CT_EffectList's children come first,
# in schema order.
_NODE_TYPES: dict[str, tuple[type, str]] = {
    "blur": (BlurEffect, "blur"),
    "fill_overlay": (FillOverlayEffect, "fillOverlay"),
    "glow": (GlowSpec, "glow"),
    "inner_shadow": (InnerShadowSpec, "innerShdw"),
    "outer_shadow": (OuterShadowSpec, "outerShdw"),
    "preset_shadow": (PresetShadowEffect, "prstShdw"),
    "reflection": (ReflectionSpec, "reflection"),
    "soft_edge": (SoftEdgeSpec, "softEdge"),
    "alpha_bi_level": (AlphaBiLevelEffect, "alphaBiLevel"),
    "alpha_ceiling": (AlphaCeilingEffect, "alphaCeiling"),
    "alpha_floor": (AlphaFloorEffect, "alphaFloor"),
    "alpha_inverse": (AlphaInverseEffect, "alphaInv"),
    "alpha_modulate": (AlphaModulateEffect, "alphaMod"),
    "alpha_modulate_fixed": (AlphaModulateFixedEffect, "alphaModFix"),
    "alpha_replace": (AlphaReplaceEffect, "alphaRepl"),
    "hsl": (HslEffect, "hsl"),
    "tint": (TintEffect, "tint"),
    "color_replace": (ColorReplaceEffect, "clrRepl"),
    "blend": (BlendEffect, "blend"),
    "reference": (EffectReference, "effect"),
    "container": (EffectContainer, "cont"),
}
_LIST_KINDS: tuple[str, ...] = (
    "blur",
    "fill_overlay",
    "glow",
    "inner_shadow",
    "outer_shadow",
    "preset_shadow",
    "reflection",
    "soft_edge",
)
_KIND_BY_TYPE: dict[type, str] = {cls: kind for kind, (cls, _) in _NODE_TYPES.items()}
_KIND_BY_TAG: dict[str, str] = {tag: kind for kind, (_, tag) in _NODE_TYPES.items()}
_ROOT_KINDS: dict[str, type] = {
    "effect_list": EffectListSpec,
    "effect_dag": EffectDagSpec,
}


def _effect_kind(effect: Any) -> str:
    kind = _KIND_BY_TYPE.get(type(effect))
    if kind is None:
        raise TypeError(f"{type(effect).__name__} is not a shape effect")
    return kind


def effect_to_dict(effect: Any) -> dict[str, Any]:
    """Serialize one effect, effect list or effect graph to a tagged mapping."""
    if type(effect) is EffectListSpec:
        return {"kind": "effect_list", **effect.to_dict()}
    if type(effect) is EffectDagSpec:
        return {"kind": "effect_dag", **effect.to_dict()}
    return {"kind": _effect_kind(effect), **effect.to_dict()}


def effect_from_dict(value: Mapping[str, Any]) -> Any:
    """Rebuild the value :func:`effect_to_dict` serialized, validating it."""
    if not isinstance(value, Mapping) or "kind" not in value:
        raise ValueError("a serialized effect needs a 'kind'")
    kind = value["kind"]
    values = {key: item for key, item in value.items() if key != "kind"}
    if kind in _ROOT_KINDS:
        return _ROOT_KINDS[kind](**values)
    if kind not in _NODE_TYPES:
        raise ValueError(f"unknown effect kind {kind!r}")
    if kind == "outer_shadow":
        return validate_outer_shadow_spec(values)
    if kind == "glow":
        return validate_glow_spec(values)
    return _NODE_TYPES[kind][0](**values)


def _effect_node(value: Any) -> Any:
    if isinstance(value, Mapping):
        return effect_from_dict(value)
    if type(value) in _KIND_BY_TYPE or type(value) in (EffectListSpec, EffectDagSpec):
        return value
    raise TypeError(f"{type(value).__name__} is not a shape effect")


def validate_effect_container(spec: Any) -> EffectListSpec | EffectDagSpec | None:
    """Validate a whole effect container; ``None`` removes the shape's own one."""
    if spec is None:
        return None
    value = _effect_node(spec)
    if type(value) not in (EffectListSpec, EffectDagSpec):
        raise TypeError("an effect container is an EffectListSpec or EffectDagSpec")
    return value


# -- XML authoring ---------------------------------------------------------- #


def _percent_text(value: float) -> str:
    return str(round(value * 100000))


def _angle_text(degrees: float) -> str:
    return str(round(degrees * 60000) % _ANGLE_UNITS)


def _color_element(color: EffectColor) -> ET.Element:
    tag = "srgbClr" if color.color_type == "rgb" else "schemeClr"
    element = ET.Element(f"{{{A_NS}}}{tag}", {"val": color.color_value})
    if color.transparency:
        ET.SubElement(element, f"{{{A_NS}}}alpha", {"val": _percent_text(1 - color.transparency)})
    return element


def _container_element(container: EffectContainer, tag: str = "cont") -> ET.Element:
    element = ET.Element(f"{{{A_NS}}}{tag}")
    if container.container_type != "sib":
        element.set("type", container.container_type)
    if container.name is not None:
        element.set("name", container.name)
    element.extend(_effect_node_element(effect) for effect in container.effects)
    return element


def _effect_node_element(effect: Any) -> ET.Element:
    """Build the DrawingML element of one effect value."""
    kind = _effect_kind(effect)
    tag = f"{{{A_NS}}}{_NODE_TYPES[kind][1]}"
    if kind == "outer_shadow":
        return _outer_shadow_element(effect)
    if kind in {"inner_shadow", "soft_edge", "reflection"}:
        return _advanced_effect_element(effect)
    if kind == "glow":
        return glow_element(effect)
    if kind == "container":
        return _container_element(effect)
    element = ET.Element(tag)
    if kind == "blur":
        element.set("rad", str(effect.radius))
        if not effect.grow:
            element.set("grow", "0")
    elif kind == "fill_overlay":
        element.set("blend", effect.blend)
        fill = ET.SubElement(element, f"{{{A_NS}}}solidFill")
        fill.append(_color_element(effect.color))
    elif kind == "preset_shadow":
        element.set("prst", effect.preset)
        if effect.distance:
            element.set("dist", str(effect.distance))
        if _angle_text(effect.direction) != "0":
            element.set("dir", _angle_text(effect.direction))
        element.append(_color_element(effect.color))
    elif kind == "alpha_bi_level":
        element.set("thresh", _percent_text(effect.threshold))
    elif kind == "alpha_inverse":
        if effect.color is not None:
            element.append(_color_element(effect.color))
    elif kind == "alpha_modulate":
        element.append(_container_element(effect.container))
    elif kind == "alpha_modulate_fixed":
        element.set("amt", _percent_text(effect.amount))
    elif kind == "alpha_replace":
        element.set("a", _percent_text(effect.alpha))
    elif kind == "hsl":
        element.set("hue", _angle_text(effect.hue))
        element.set("sat", _percent_text(effect.saturation))
        element.set("lum", _percent_text(effect.luminance))
    elif kind == "tint":
        element.set("hue", _angle_text(effect.hue))
        element.set("amt", _percent_text(effect.amount))
    elif kind == "color_replace":
        element.append(_color_element(effect.color))
    elif kind == "blend":
        element.set("blend", effect.blend)
        element.append(_container_element(effect.container))
    elif kind == "reference":
        element.set("ref", effect.ref)
    return element


def effect_container_element(
    spec: EffectListSpec | EffectDagSpec,
) -> ET.Element:
    """Build the ``a:effectLst`` or ``a:effectDag`` one container value authors."""
    if type(spec) is EffectDagSpec:
        return _container_element(spec, "effectDag")
    element = ET.Element(f"{{{A_NS}}}effectLst")
    element.extend(_effect_node_element(effect) for effect in spec.effects)
    return element


# -- XML reading ------------------------------------------------------------ #


def _refuse_text(element: ET.Element, label: str) -> None:
    for node in element.iter():
        if (node.text and node.text.strip()) or (
            node is not element and node.tail and node.tail.strip()
        ):
            raise ValueError(f"{label} contains unexpected text")


def _attributes(element: ET.Element, label: str, allowed: set[str]) -> None:
    unknown = set(element.attrib) - allowed
    if unknown:
        raise ValueError(f"{label} declares unsupported attribute(s): {sorted(unknown)}")


def _percentage(raw: str, label: str, *, low: float, high: float | None) -> float:
    try:
        value = float(raw[:-1]) / 100 if raw.endswith("%") else int(raw) / 100000
    except ValueError as exc:
        raise ValueError(f"{label} is not a percentage: {raw!r}") from exc
    if not math.isfinite(value) or value < low or (high is not None and value > high):
        raise ValueError(f"{label} is out of range: {raw!r}")
    return round(value, 5)


def _angle(raw: str, label: str) -> float:
    try:
        units = int(raw)
    except ValueError as exc:
        raise ValueError(f"{label} is not an angle: {raw!r}") from exc
    if not 0 <= units < _ANGLE_UNITS:
        raise ValueError(f"{label} is out of range [0, 21600000): {units}")
    return validate_direction(units / 60000)


def _length(raw: str, label: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{label} is not an EMU length: {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{label} must be non-negative: {value}")
    return value


def _boolean(raw: str, label: str) -> bool:
    if raw not in {"0", "1", "true", "false"}:
        raise ValueError(f"{label} is not a boolean: {raw!r}")
    return raw in {"1", "true"}


def _read_color(element: ET.Element, label: str) -> EffectColor:
    name = _xml_local_name(element.tag)
    if element.tag not in _SUPPORTED_COLOR_TAGS:
        raise ValueError(f"{label} declares unsupported color model {name!r}")
    _attributes(element, f"{label} {name}", {"val"})
    value = element.get("val")
    if not value:
        raise ValueError(f"{label} {name} is missing val")
    transparency = 0.0
    children = list(element)
    if children:
        alpha = children[0]
        if len(children) != 1 or alpha.tag != f"{{{A_NS}}}alpha":
            transform = _xml_local_name(children[-1].tag)
            raise ValueError(f"{label} color declares unsupported color transform {transform!r}")
        _attributes(alpha, f"{label} alpha", {"val"})
        if len(alpha) or "val" not in alpha.attrib:
            raise ValueError(f"{label} alpha is malformed")
        transparency = round(
            1 - _percentage(alpha.attrib["val"], f"{label} alpha", low=0, high=1), 6
        )
    if name == "srgbClr":
        return EffectColor(rgb=value, transparency=transparency)
    return EffectColor("scheme", value, transparency)


def _single_color(element: ET.Element, label: str, *, optional: bool = False) -> Any:
    children = list(element)
    if not children and optional:
        return None
    if len(children) != 1:
        raise ValueError(f"{label} needs exactly one color element")
    return _read_color(children[0], label)


def _read_container(element: ET.Element, cls: type = EffectContainer) -> Any:
    label = _xml_local_name(element.tag)
    _attributes(element, label, {"type", "name"})
    return cls(
        effects=tuple(_read_effect_node(child, graph=True) for child in element),
        container_type=element.get("type", "sib"),
        name=element.get("name", "").strip() or None,
    )


def _read_effect_node(element: ET.Element, *, graph: bool) -> Any:
    """Read one effect element of an effect list (``graph=False``) or graph."""
    name = _xml_local_name(element.tag)
    kind = _KIND_BY_TAG.get(name)
    if element.tag != f"{{{A_NS}}}{name}" or kind is None:
        raise ValueError(f"effect {name!r} is not representable by the effect API")
    if not graph and kind not in _LIST_KINDS:
        raise ValueError(f"effectLst cannot contain {name!r}")
    _refuse_text(element, name)
    if kind == "outer_shadow":
        return _inspect_outer_shadow_element(element)
    if kind in {"inner_shadow", "soft_edge", "reflection"}:
        return _inspect_advanced_element(element, kind)
    if kind == "glow":
        return inspect_glow_element(element)
    if kind == "container":
        return _read_container(element)
    allowed = {
        "blur": {"rad", "grow"},
        "fill_overlay": {"blend"},
        "preset_shadow": {"prst", "dist", "dir"},
        "alpha_bi_level": {"thresh"},
        "alpha_modulate_fixed": {"amt"},
        "alpha_replace": {"a"},
        "hsl": {"hue", "sat", "lum"},
        "tint": {"hue", "amt"},
        "blend": {"blend"},
        "reference": {"ref"},
    }.get(kind, set())
    _attributes(element, name, allowed)
    leaf = kind in {
        "blur",
        "alpha_bi_level",
        "alpha_ceiling",
        "alpha_floor",
        "alpha_modulate_fixed",
        "alpha_replace",
        "hsl",
        "tint",
        "reference",
    }
    if leaf and len(element):
        raise ValueError(f"{name} declares unexpected child elements")
    for required in {
        "fill_overlay": ("blend",),
        "preset_shadow": ("prst",),
        "alpha_bi_level": ("thresh",),
        "alpha_replace": ("a",),
        "blend": ("blend",),
        "reference": ("ref",),
    }.get(kind, ()):
        if required not in element.attrib:
            raise ValueError(f"{name} requires {required}")
    if kind == "blur":
        return BlurEffect(
            radius=_length(element.get("rad", "0"), "blur rad"),
            grow=_boolean(element.get("grow", "true"), "blur grow"),
        )
    if kind == "fill_overlay":
        fills = list(element)
        if len(fills) != 1:
            raise ValueError("fillOverlay needs exactly one fill")
        if fills[0].tag != f"{{{A_NS}}}solidFill":
            raise ValueError(f"fillOverlay {_xml_local_name(fills[0].tag)!r} is not representable")
        _attributes(fills[0], "fillOverlay solidFill", set())
        return FillOverlayEffect(
            blend=element.attrib["blend"],
            color=_single_color(fills[0], "fillOverlay"),
        )
    if kind == "preset_shadow":
        return PresetShadowEffect(
            preset=element.attrib["prst"],
            distance=_length(element.get("dist", "0"), "prstShdw dist"),
            direction=_angle(element.get("dir", "0"), "prstShdw dir"),
            color=_single_color(element, "prstShdw"),
        )
    if kind == "alpha_bi_level":
        return AlphaBiLevelEffect(
            _percentage(element.attrib["thresh"], "alphaBiLevel thresh", low=0, high=1)
        )
    if kind == "alpha_ceiling":
        return AlphaCeilingEffect()
    if kind == "alpha_floor":
        return AlphaFloorEffect()
    if kind == "alpha_inverse":
        return AlphaInverseEffect(_single_color(element, "alphaInv", optional=True))
    if kind in {"alpha_modulate", "blend"}:
        children = list(element)
        if len(children) != 1 or children[0].tag != f"{{{A_NS}}}cont":
            raise ValueError(f"{name} requires one effect container")
        container = _read_container(children[0])
        if kind == "blend":
            return BlendEffect(element.attrib["blend"], container)
        return AlphaModulateEffect(container)
    if kind == "alpha_modulate_fixed":
        return AlphaModulateFixedEffect(
            _percentage(element.get("amt", "100000"), "alphaModFix amt", low=0, high=None)
        )
    if kind == "alpha_replace":
        return AlphaReplaceEffect(_percentage(element.attrib["a"], "alphaRepl a", low=0, high=1))
    if kind == "hsl":
        return HslEffect(
            hue=_angle(element.get("hue", "0"), "hsl hue"),
            saturation=_percentage(element.get("sat", "0"), "hsl sat", low=-1, high=1),
            luminance=_percentage(element.get("lum", "0"), "hsl lum", low=-1, high=1),
        )
    if kind == "tint":
        return TintEffect(
            hue=_angle(element.get("hue", "0"), "tint hue"),
            amount=_percentage(element.get("amt", "0"), "tint amt", low=-1, high=1),
        )
    if kind == "color_replace":
        return ColorReplaceEffect(_single_color(element, "clrRepl"))
    return EffectReference(element.attrib["ref"])


def read_effect_container(element: ET.Element) -> EffectListSpec | EffectDagSpec:
    """Read one ``a:effectLst`` or ``a:effectDag`` into its typed value.

    Effects the API cannot represent are refused by name rather than dropped.
    """
    name = _xml_local_name(element.tag)
    _refuse_text(element, name)
    if element.tag == f"{{{A_NS}}}effectDag":
        _walk_effect_dag(element)
        return _read_container(element, EffectDagSpec)
    if element.tag != f"{{{A_NS}}}effectLst":
        raise ValueError(f"{name!r} is not an effect container")
    _attributes(element, name, set())
    effects = [_read_effect_node(child, graph=False) for child in element]
    kinds = [_effect_kind(effect) for effect in effects]
    if kinds != sorted(kinds, key=_LIST_KINDS.index):
        raise ValueError("effectLst children are out of schema order")
    return EffectListSpec(tuple(effects))


def _effect_containers(properties: ET.Element) -> list[ET.Element]:
    containers = [
        child
        for child in properties
        if child.tag in {f"{{{A_NS}}}effectLst", f"{{{A_NS}}}effectDag"}
    ]
    if len(containers) > 1:
        raise ValueError("shape declares ambiguous effectDag/effectLst containers")
    return containers


def inspect_effect_container(
    properties: ET.Element,
) -> EffectListSpec | EffectDagSpec | None:
    """The typed effect container a ``p:spPr`` states, or ``None``."""
    containers = _effect_containers(properties)
    return read_effect_container(containers[0]) if containers else None


def set_effect_container(
    properties: ET.Element,
    spec: EffectListSpec | EffectDagSpec | Mapping[str, Any] | None,
) -> None:
    """Replace the effect container of ``p:spPr`` in place (``None`` removes it)."""
    value = validate_effect_container(spec)
    containers = _effect_containers(properties)
    replacement = None if value is None else effect_container_element(value)
    if containers:
        index = list(properties).index(containers[0])
        if replacement is not None:
            replacement.tail = containers[0].tail
            properties.insert(index, replacement)
        properties.remove(containers[0])
        return
    if replacement is not None:
        insert_at = next(
            (
                index
                for index, child in enumerate(properties)
                if _xml_local_name(child.tag) in {"scene3d", "sp3d", "extLst"}
            ),
            len(properties),
        )
        properties.insert(insert_at, replacement)


# -- Shape API --------------------------------------------------------------- #


def _graph_effects(container: EffectContainer) -> list[Any]:
    """Every effect of a graph, nested containers included."""
    found: list[Any] = []
    pending = [container]
    while pending:
        current = pending.pop()
        for effect in current.effects:
            found.append(effect)
            if type(effect) is EffectContainer:
                pending.append(effect)
            elif type(effect) in (AlphaModulateEffect, BlendEffect):
                pending.append(effect.container)
    return found


def _queued_container(shape: Any) -> tuple[bool, Any]:
    presentation = getattr(getattr(shape, "_slide", None), "_presentation", None)
    queue = getattr(presentation, "_shape_effect_edits", None)
    if not isinstance(queue, dict):
        return (False, None)
    pending = queue.get((shape._slide._index, shape_edit_ref(shape)))
    if not isinstance(pending, Mapping) or "effects" not in pending:
        return (False, None)
    return (True, validate_effect_container(pending["effects"]))


def _queued_container_effect(shape: Any, effect: str) -> tuple[bool, Any]:
    """Read one per-kind effect from a queued whole-container replacement.

    Returns ``(False, None)`` when no container is queued.  Graph containers
    answer only the outer shadow, as the saved-graph readers do.
    """
    queued, container = _queued_container(shape)
    if not queued or container is None:
        return (queued, None)
    cls = _NODE_TYPES[effect][0]
    if type(container) is EffectDagSpec:
        if effect != "outer_shadow":
            raise ValueError(
                f"shape declares unsupported 'effectDag' element; cannot edit or read {effect}"
            )
        shadows = [node for node in _graph_effects(container) if type(node) is cls]
        if len(shadows) > 1:
            raise ValueError("effectDag declares multiple ambiguous outerShdw nodes")
        return (True, shadows[0] if shadows else None)
    return (
        True,
        next((node for node in container.effects if type(node) is cls), None),
    )


def get_shape_effects(shape: Any) -> EffectListSpec | EffectDagSpec | None:
    """The shape's own effect list or effect graph, queued edits included.

    ``None`` means the shape states no container and inherits its effects (see
    :func:`get_shape_effective_effects`).  Effects the API cannot represent are
    refused by name.
    """
    _assert_shape_editable(shape)
    if not _supports_shape_shadow(shape):
        return None
    queued, container = _queued_container(shape)
    if queued:
        return container
    presentation = shape._slide._presentation
    try:
        with zipfile.ZipFile(_canonical_source_path(presentation)) as package:
            root = ET.fromstring(package.read(shape._slide.partname))
    except (FileNotFoundError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"cannot read presentation effects: {exc}") from exc
    properties = _shape_properties_element_from_shape(_shape_xml_element(root, shape._payload))
    return None if properties is None else inspect_effect_container(properties)


def set_shape_effects(
    shape: Any,
    spec: EffectListSpec | EffectDagSpec | Mapping[str, Any] | None,
) -> None:
    """Queue a replacement of the shape's whole effect container.

    An :class:`EffectListSpec` or :class:`EffectDagSpec` becomes the shape's
    ``a:effectLst``/``a:effectDag``; ``None`` removes it so the theme effect
    style applies again.  Pending per-effect edits of the shape are superseded.
    """
    _assert_shape_editable(shape)
    if not _supports_shape_shadow(shape):
        raise ValueError("effects are authored on shapes, connectors and pictures")
    container = validate_effect_container(spec)
    presentation = shape._slide._presentation
    queue = getattr(presentation, "_queue_shape_effect", None)
    if not callable(queue):
        raise TypeError("presentation does not provide the shape-effect save queue")
    key = (shape._slide._index, shape_edit_ref(shape))
    pending = presentation._shape_effect_edits.get(key)
    if isinstance(pending, dict):
        for name in ("effects", "outer_shadow", *_ADVANCED_EFFECTS):
            pending.pop(name, None)
    presentation._shape_glow_edits.pop(key, None)
    presentation._shape_shadow_inherit_edits.pop(key, None)
    for cached in (
        "outer_shadow",
        "_outer_shadow_source_path",
        "glow",
        "_glow_source_path",
    ):
        shape._payload.pop(cached, None)
    shape._payload["shadow_inherit"] = container is None
    queue(
        shape._slide._index,
        shape_edit_ref(shape),
        "effects",
        None if container is None else effect_to_dict(container),
    )


_ADVANCED_EFFECTS = (
    "inner_shadow",
    "soft_edge",
    "reflection",
    "blur",
    "fill_overlay",
    "preset_shadow",
)


def _resolved_colors(container: ET.Element, scheme: Any) -> ET.Element:
    """A copy of ``container`` with every colour resolved to sRGB plus alpha."""
    from .render_theme import COLOR_TAGS, ThemeRefusal, resolve_color_element

    resolved = copy.deepcopy(container)
    colors = [
        child
        for parent in resolved.iter()
        if _xml_local_name(parent.tag) not in COLOR_TAGS
        for child in parent
        if _xml_local_name(child.tag) in COLOR_TAGS
    ]
    for color in colors:
        try:
            value = resolve_color_element(color, scheme)
        except ThemeRefusal as exc:
            raise ValueError(f"effect colour cannot be resolved: {exc}") from exc
        color.tag = f"{{{A_NS}}}srgbClr"
        color.attrib.clear()
        for child in list(color):
            color.remove(child)
        color.set("val", value.rgb)
        if value.alpha < 1:
            ET.SubElement(color, f"{{{A_NS}}}alpha", {"val": _percent_text(value.alpha)})
    return resolved


def _effective_effects(builder: Any, element: ET.Element, context: Any) -> Any:
    """Resolve a saved shape's effects through its inheritance chain.

    The nearest ``p:spPr`` stating an effect container wins (the shape, then
    its layout and master placeholders, then the theme object defaults); else
    the ``p:style`` ``a:effectRef`` selects a theme ``a:effectStyle`` with its
    ``phClr`` replaced by the reference colour.  Colours come back resolved.
    """
    from .editions import commercial_module

    EffectiveValue = commercial_module(
        "effective_format", "Reading effective effects"
    ).EffectiveValue
    from .render_theme import ThemeRefusal, resolve_scheme_paint
    from .shape_tree import _placeholder_key
    from .xml_helpers import find_ooxml

    kind = _xml_local_name(element.tag)
    if kind not in {"sp", "cxnSp", "pic"}:
        return EffectiveValue(None, "default", f"p:{kind} carries no shape effects")
    key = _placeholder_key(element)
    levels: list[tuple[ET.Element | None, str, str]] = [
        (find_ooxml(element, f"{{{P_NS}}}spPr"), "direct", "shape p:spPr")
    ]
    layout_match, master_match = builder._placeholder_elements(context, key)
    for placeholder, level in ((layout_match, "layout"), (master_match, "master")):
        if placeholder is not None:
            levels.append(
                (
                    find_ooxml(placeholder, f"{{{P_NS}}}spPr"),
                    level,
                    f"{level} placeholder p:spPr",
                )
            )
    default_properties = default_style = None
    if kind in {"sp", "cxnSp"}:
        default_properties, default_style, _line = builder._shape_defaults(
            context, element, kind, key
        )
    levels.append((default_properties, "theme", "theme a:objectDefaults p:spPr"))
    for properties, level, origin in levels:
        if properties is None:
            continue
        containers = _effect_containers(properties)
        if containers:
            value = read_effect_container(_resolved_colors(containers[0], context.scheme))
            return EffectiveValue(value, level, origin)
    style = find_ooxml(element, f"{{{P_NS}}}style")
    if style is None:
        style = builder._shape_style(context, key)
    if style is None:
        style = default_style
    reference = None if style is None else find_ooxml(style, f"{{{A_NS}}}effectRef")
    if reference is None or reference.get("idx", "0") == "0":
        return EffectiveValue(None, "default", "no effects stated")
    try:
        effect_style = resolve_scheme_paint(
            context.theme, context.scheme, "effectStyleLst", reference
        )
    except ThemeRefusal as exc:
        raise ValueError(f"effectRef cannot be resolved: {exc}") from exc
    origin = f"p:style a:effectRef idx={reference.get('idx')}: theme a:effectStyleLst"
    containers = [] if effect_style is None else _effect_containers(effect_style)
    if not containers:
        return EffectiveValue(None, "theme", origin)
    if containers[0].tag == f"{{{A_NS}}}effectLst" and not len(containers[0]):
        return EffectiveValue(EffectListSpec(), "theme", origin)
    if effect_style is not None and len(
        [child for child in effect_style if child is not containers[0]]
    ):
        origin += " (scene3d/sp3d not included)"
    value = read_effect_container(_resolved_colors(containers[0], context.scheme))
    return EffectiveValue(value, "theme", origin)


def get_shape_effective_effects(shape: Any) -> Any:
    """The effects a saved shape is drawn with and the level that states them.

    Returns an :class:`~wolfppt.effective_format.EffectiveValue` whose value is
    an :class:`EffectListSpec`, :class:`EffectDagSpec` (colours resolved to
    sRGB) or ``None``; ``source`` is ``direct``, ``layout``, ``master``,
    ``theme`` (object defaults or the theme effect style) or ``default``.
    """
    from .editions import commercial_module

    readback = commercial_module("effective_format_readback", "Reading effective effects")

    _assert_shape_editable(shape)
    deck, element, context = readback._saved_shape(shape)
    return _effective_effects(deck.builder, element, context)


__all__ = [
    "VALID_BLEND_MODES",
    "VALID_CONTAINER_TYPES",
    "VALID_PRESET_SHADOWS",
    "AlphaBiLevelEffect",
    "AlphaCeilingEffect",
    "AlphaFloorEffect",
    "AlphaInverseEffect",
    "AlphaModulateEffect",
    "AlphaModulateFixedEffect",
    "AlphaReplaceEffect",
    "BlendEffect",
    "BlurEffect",
    "ColorReplaceEffect",
    "EffectColor",
    "EffectContainer",
    "EffectDagSpec",
    "EffectListSpec",
    "EffectReference",
    "FillOverlayEffect",
    "HslEffect",
    "PresetShadowEffect",
    "TintEffect",
    "effect_container_element",
    "effect_from_dict",
    "effect_to_dict",
    "get_shape_effective_effects",
    "get_shape_effects",
    "inspect_effect_container",
    "read_effect_container",
    "set_effect_container",
    "set_shape_effects",
    "validate_effect_container",
]
