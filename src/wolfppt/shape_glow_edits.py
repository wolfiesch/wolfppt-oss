"""Shape glow effect authoring, inspection, and package applicator for DrawingML."""

from __future__ import annotations

import math
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
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
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .shape_edit_refs import ShapeEditRef, shape_edit_ref
from .shape_xml import _shape_xml_element
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .xml_helpers import STRICT_A_NS, find_ooxml, findall_ooxml, ooxml_namespace
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

VALID_GLOW_COLOR_TYPES: frozenset[str] = frozenset({"rgb", "scheme"})

# Schema child element ordering for DrawingML <a:effectLst> (CT_EffectList):
# 0: blur
# 1: fillOverlay
# 2: glow
# 3: innerShdw
# 4: outerShdw
# 5: prstShdw
# 6: reflection
# 7: softEdge
# 8: extLst
_EFFECT_LIST_CHILD_ORDER: dict[str, int] = {
    f"{{{A_NS}}}blur": 0,
    f"{{{A_NS}}}fillOverlay": 1,
    f"{{{A_NS}}}glow": 2,
    f"{{{A_NS}}}innerShdw": 3,
    f"{{{A_NS}}}outerShdw": 4,
    f"{{{A_NS}}}prstShdw": 5,
    f"{{{A_NS}}}reflection": 6,
    f"{{{A_NS}}}softEdge": 7,
    f"{{{A_NS}}}extLst": 8,
}

# DrawingML color choice tags
_SUPPORTED_COLOR_TAGS: frozenset[str] = frozenset(
    f"{{{namespace}}}{name}"
    for namespace in (A_NS, STRICT_A_NS)
    for name in ("srgbClr", "schemeClr")
)
_UNSUPPORTED_COLOR_TAGS: frozenset[str] = frozenset(
    f"{{{namespace}}}{name}"
    for namespace in (A_NS, STRICT_A_NS)
    for name in ("scrgbClr", "hslClr", "sysClr", "prstClr")
)

ALLOWED_GLOW_ATTRIBUTES: frozenset[str] = frozenset({"rad"})

_EMU_PER_PT = 12700


# --------------------------------------------------------------------------- #
# Canonical Source Path Helper                                                #
# --------------------------------------------------------------------------- #


def _canonical_source_path(prs: Any) -> Path:
    """Resolve authoritative presentation source path across save/reopen cycles."""
    source_path = getattr(prs, "_source_path", None)
    if source_path is not None:
        return Path(source_path)
    path_attr = getattr(prs, "path", None)
    if callable(path_attr):
        return Path(path_attr())
    if path_attr is not None:
        return Path(path_attr)
    raise ValueError("presentation source path is unavailable")


# --------------------------------------------------------------------------- #
# Value objects & Validation                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GlowSpec:
    """Immutable specification for a shape glow effect."""

    radius_pt: float = 0.0
    color_type: str = "rgb"
    color_value: str = "000000"
    transparency: float = 0.0

    def __init__(
        self,
        radius_pt: Any = 0.0,
        color_type: str = "rgb",
        color_value: str = "000000",
        transparency: Any = 0.0,
        *,
        rgb: Any = None,
        theme_color: Any = None,
    ) -> None:
        rad = validate_glow_radius(radius_pt)
        transp = validate_transparency(transparency)

        if rgb is not None and theme_color is not None:
            raise ValueError("cannot specify both rgb and theme_color on GlowSpec")
        if rgb is not None:
            c_type = "rgb"
            c_val = _normalize_rgb(rgb)
        elif theme_color is not None:
            c_type = "scheme"
            c_val = _normalize_theme_color(theme_color)
        else:
            if not isinstance(color_type, str) or color_type not in VALID_GLOW_COLOR_TYPES:
                raise ValueError(
                    f"color_type must be one of {sorted(VALID_GLOW_COLOR_TYPES)}, got {color_type!r}"
                )
            c_type = color_type
            if c_type == "rgb":
                c_val = _normalize_rgb(color_value)
            else:
                c_val = _normalize_theme_color(color_value)

        object.__setattr__(self, "radius_pt", rad)
        object.__setattr__(self, "color_type", c_type)
        object.__setattr__(self, "color_value", c_val)
        object.__setattr__(self, "transparency", transp)

    @property
    def rgb(self) -> str | None:
        """Six-character uppercase hex RGB color string, or None if theme-based."""
        return self.color_value if self.color_type == "rgb" else None

    @property
    def theme_color(self) -> Any:
        """Theme color value, or None if RGB-based."""
        return _theme_color_value(self.color_value) if self.color_type == "scheme" else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "radius_pt": self.radius_pt,
            "color_type": self.color_type,
            "color_value": self.color_value,
            "transparency": self.transparency,
        }


def validate_glow_radius(radius_pt: Any) -> float:
    """Validate glow radius as a non-negative finite number of points."""
    if isinstance(radius_pt, bool):
        raise TypeError("radius_pt cannot be a boolean")
    if not isinstance(radius_pt, (int, float)):
        raise TypeError(f"radius_pt must be a numeric value, got {type(radius_pt).__name__}")
    val = float(radius_pt)
    if not math.isfinite(val):
        raise ValueError(f"radius_pt must be a finite number, got {val}")
    if val < 0.0:
        raise ValueError(f"radius_pt must be non-negative, got {val}")
    return round(val, 4)


def validate_transparency(transparency: Any) -> float:
    """Validate fractional transparency in [0.0, 1.0]."""
    if isinstance(transparency, bool):
        raise TypeError("transparency cannot be a boolean")
    if not isinstance(transparency, (int, float)):
        raise TypeError(f"transparency must be a float, got {type(transparency).__name__}")
    val = float(transparency)
    if not math.isfinite(val):
        raise ValueError(f"transparency must be finite, got {val}")
    if val < 0.0 or val > 1.0:
        raise ValueError(f"transparency must be between 0.0 and 1.0, got {val}")
    return round(val, 6)


def validate_glow_spec(spec: Any) -> GlowSpec | None:
    """Validate a GlowSpec instance or mapping; None represents cleared glow."""
    if spec is None:
        return None
    if isinstance(spec, GlowSpec):
        return spec
    if isinstance(spec, Mapping):
        valid_keys = {
            "radius_pt",
            "color_type",
            "color_value",
            "rgb",
            "theme_color",
            "transparency",
        }
        unknown = set(spec.keys()) - valid_keys
        if unknown:
            raise ValueError(f"unknown glow property keys: {sorted(unknown)}")

        rad_val = spec.get("radius_pt", 0.0)
        transp_val = spec.get("transparency", 0.0)
        rgb = spec.get("rgb")
        theme_color = spec.get("theme_color")
        color_type = spec.get("color_type", "rgb")
        color_value = spec.get("color_value", "000000")

        return GlowSpec(
            radius_pt=rad_val,
            color_type=color_type,
            color_value=color_value,
            transparency=transp_val,
            rgb=rgb,
            theme_color=theme_color,
        )

    raise TypeError(f"glow spec must be a GlowSpec, Mapping, or None; got {type(spec).__name__}")


# --------------------------------------------------------------------------- #
# XML Refusal & Inspection                                                    #
# --------------------------------------------------------------------------- #


def _assert_shape_editable(shape: Any) -> None:
    """Refuse pending or deleted shapes before reading or authoring glow."""
    payload = getattr(shape, "_payload", {})
    if bool(payload.get("_deleted")):
        raise ValueError("cannot edit or read glow properties of a deleted shape")
    slide = getattr(shape, "_slide", None)
    if slide is not None and getattr(slide, "_deleted", False):
        raise ValueError("cannot edit or read glow properties on a deleted slide")
    if bool(payload.get("_pending_shape") or payload.get("_pending_group_child")):
        raise ValueError("cannot edit or read glow properties of an unsaved pending shape")


def _supports_shape_glow(shape: Any) -> bool:
    payload = getattr(shape, "_payload", {})
    return payload.get("kind") in {"shape", "connector", "picture"}


def _shape_properties_element_from_shape(
    shape_element: ET.Element,
) -> ET.Element | None:
    tag = _xml_local_name(shape_element.tag)
    if tag in {"sp", "cxnSp", "pic"}:
        return find_ooxml(shape_element, f"{{{P_NS}}}spPr")
    return None


def _assert_no_unsupported_effects(shape_properties: ET.Element) -> None:
    """Refuse shapes declaring effectDag or multiple effectLst elements."""
    if find_ooxml(shape_properties, f"{{{A_NS}}}effectDag") is not None:
        raise ValueError("shape declares unsupported 'effectDag' element; cannot edit or read glow")
    effect_lists = [c for c in list(shape_properties) if _xml_local_name(c.tag) == "effectLst"]
    if len(effect_lists) > 1:
        raise ValueError("shape declares multiple ambiguous 'effectLst' containers")


def _inspect_glow_from_properties(
    shape_properties: ET.Element,
) -> GlowSpec | None:
    """Parse GlowSpec from spPr XML element.

    Refuses unsupported effectDag, multiple effectLst, unsupported attributes,
    nested color transforms, foreign children, out-of-range alpha or radius, or ambiguous glow.
    """
    _assert_no_unsupported_effects(shape_properties)

    effect_list = find_ooxml(shape_properties, f"{{{A_NS}}}effectLst")
    if effect_list is None:
        return None

    glow_elements = findall_ooxml(effect_list, f"{{{A_NS}}}glow")
    if not glow_elements:
        return None
    if len(glow_elements) > 1:
        raise ValueError(
            f"shape declares {len(glow_elements)} glow elements; cannot ambiguously inspect or edit"
        )
    return inspect_glow_element(glow_elements[0])


def inspect_glow_element(elem: ET.Element) -> GlowSpec:
    """Read one ``a:glow`` from an effect list or effect graph.

    Refuses unsupported attributes, nested colour transforms other than one
    ``a:alpha``, foreign children, and out-of-range radius or alpha.
    """

    # Check for unknown or unsupported attributes on <a:glow>
    unknown_attrs = set(elem.attrib.keys()) - ALLOWED_GLOW_ATTRIBUTES
    if unknown_attrs:
        raise ValueError(f"glow declares unsupported attribute(s): {sorted(unknown_attrs)}")

    raw_rad = elem.attrib.get("rad", "0")
    try:
        rad_emu = int(raw_rad)
    except ValueError as exc:
        raise ValueError(f"glow rad is non-numeric: {raw_rad!r}") from exc
    if rad_emu < 0:
        raise ValueError(f"glow rad must be non-negative: {rad_emu}")
    radius_pt = round(rad_emu / _EMU_PER_PT, 4)

    # Inspect color choice children
    color_children = [
        c
        for c in list(elem)
        if (c.tag in _SUPPORTED_COLOR_TAGS or c.tag in _UNSUPPORTED_COLOR_TAGS)
        and c.tag.startswith(f"{{{ooxml_namespace(elem, A_NS)}}}")
    ]
    if len(color_children) != 1 or len(list(elem)) != 1:
        if len(color_children) == 0:
            raise ValueError("glow has no color child element; ambiguous effect structure")
        raise ValueError(
            f"glow declares {len(list(elem))} child elements; expected exactly one color element"
        )

    color_child = color_children[0]
    if color_child.tag in _UNSUPPORTED_COLOR_TAGS:
        raise ValueError(
            f"glow declares unsupported color model '{_xml_local_name(color_child.tag)}'"
        )

    if color_child.tag == f"{{{ooxml_namespace(elem, A_NS)}}}srgbClr":
        color_type = "rgb"
        val = color_child.attrib.get("val")
        if not val or len(val) != 6 or not all(c in "0123456789ABCDEFabcdef" for c in val):
            raise ValueError(f"srgbClr declares malformed hex color: {val!r}")
        color_value = val.upper()
    else:
        color_type = "scheme"
        val = color_child.attrib.get("val")
        if not val:
            raise ValueError("schemeClr element missing val attribute")
        color_value = val

    # Verify no unsupported color transform children
    for child in list(color_child):
        if child.tag != f"{{{ooxml_namespace(color_child, A_NS)}}}alpha":
            raise ValueError(
                f"glow color element declares unsupported color transform '{_xml_local_name(child.tag)}'"
            )

    # Inspect transparency via <a:alpha>
    alpha_elements = findall_ooxml(color_child, f"{{{A_NS}}}alpha")
    if len(alpha_elements) > 1:
        raise ValueError("color element declares multiple conflicting <a:alpha> modifiers")
    if alpha_elements:
        alpha_raw = alpha_elements[0].attrib.get("val")
        if alpha_raw is None:
            raise ValueError("alpha element missing val attribute")
        try:
            alpha_int = int(alpha_raw)
        except ValueError as exc:
            raise ValueError(f"alpha val attribute is non-numeric: {alpha_raw!r}") from exc
        if alpha_int < 0 or alpha_int > 100000:
            raise ValueError(f"alpha val must be in range [0, 100000], got {alpha_int}")
        transparency = round((100000 - alpha_int) / 100000.0, 6)
    else:
        transparency = 0.0

    return GlowSpec(
        radius_pt=radius_pt,
        color_type=color_type,
        color_value=color_value,
        transparency=transparency,
    )


# --------------------------------------------------------------------------- #
# XML Mutation                                                                #
# --------------------------------------------------------------------------- #


def _insert_effect_list_child(effect_list: ET.Element, child: ET.Element) -> None:
    """Insert a child element into <a:effectLst> maintaining DrawingML schema element order."""
    child_bucket = _EFFECT_LIST_CHILD_ORDER.get(child.tag, 99)
    insert_at = len(effect_list)
    for index, existing in enumerate(list(effect_list)):
        existing_bucket = _EFFECT_LIST_CHILD_ORDER.get(existing.tag, 99)
        if existing_bucket > child_bucket:
            insert_at = index
            break
    effect_list.insert(insert_at, child)


def clear_shape_glow(shape_properties: ET.Element) -> None:
    """Clear <a:glow> within <a:effectLst> on shape_properties (spPr).

    Preserves other effectLst siblings (blur, outerShdw, softEdge, reflection, etc.) and foreign children.
    Refuses unsupported effectDag, foreign children, or ambiguous multiple glow elements.
    """
    _assert_no_unsupported_effects(shape_properties)
    _ = _inspect_glow_from_properties(shape_properties)

    effect_list = shape_properties.find(f"{{{A_NS}}}effectLst")
    if effect_list is not None:
        for child in list(effect_list):
            if _xml_local_name(child.tag) == "glow":
                effect_list.remove(child)


def set_shape_glow(
    shape_properties: ET.Element,
    spec: GlowSpec | Mapping[str, Any] | None,
) -> None:
    """Set or clear <a:glow> within <a:effectLst> on shape_properties (spPr).

    Preserves other effectLst siblings (blur, outerShdw, softEdge, reflection, etc.) and foreign children.
    Refuses unsupported effectDag, unsupported transforms, or ambiguous multiple glow elements.
    """
    _assert_no_unsupported_effects(shape_properties)

    # First inspect existing glow to ensure no unsupported state is silently erased
    _ = _inspect_glow_from_properties(shape_properties)

    validated_spec = validate_glow_spec(spec)
    effect_list = shape_properties.find(f"{{{A_NS}}}effectLst")

    if validated_spec is None:
        clear_shape_glow(shape_properties)
        return

    # Ensure <a:effectLst> exists in proper schema position in spPr
    if effect_list is None:
        effect_list = ET.Element(f"{{{A_NS}}}effectLst")
        insert_at = len(shape_properties)
        for index, child in enumerate(list(shape_properties)):
            if _xml_local_name(child.tag) in {"scene3d", "sp3d", "extLst"}:
                insert_at = index
                break
        shape_properties.insert(insert_at, effect_list)
    else:
        for child in list(effect_list):
            if _xml_local_name(child.tag) == "glow":
                effect_list.remove(child)

    _insert_effect_list_child(effect_list, glow_element(validated_spec))


def glow_element(spec: GlowSpec | Mapping[str, Any]) -> ET.Element:
    """Build the ``a:glow`` element one glow value authors."""
    validated_spec = validate_glow_spec(spec)
    if validated_spec is None:
        raise ValueError("a glow element needs a glow value")
    glow_elem = ET.Element(f"{{{A_NS}}}glow")
    rad_emu = round(validated_spec.radius_pt * _EMU_PER_PT)
    glow_elem.set("rad", str(rad_emu))

    # Build color element with alpha modifier if transparency > 0
    if validated_spec.color_type == "rgb":
        color_elem = ET.Element(f"{{{A_NS}}}srgbClr", {"val": validated_spec.color_value})
    else:
        color_elem = ET.Element(f"{{{A_NS}}}schemeClr", {"val": validated_spec.color_value})

    if validated_spec.transparency > 0.0:
        alpha_val = round((1.0 - validated_spec.transparency) * 100000)
        alpha_elem = ET.Element(f"{{{A_NS}}}alpha", {"val": str(alpha_val)})
        color_elem.append(alpha_elem)

    glow_elem.append(color_elem)
    return glow_elem


# --------------------------------------------------------------------------- #
# Readback & Facade inspection                                                #
# --------------------------------------------------------------------------- #


def _get_active_queue_glow(shape: Any) -> tuple[bool, GlowSpec | None]:
    """Check presentation queue for queued glow edits.

    The glow queue is applied after the effect-container queue, so a queued glow
    wins; otherwise a queued whole-container replacement decides the glow.
    """
    prs = getattr(getattr(shape, "_slide", None), "_presentation", None)
    if prs is None:
        return (False, None)
    queue = getattr(prs, "_shape_glow_edits", None)
    if isinstance(queue, dict):
        key = (shape._slide._index, shape_edit_ref(shape))
        if key in queue:
            raw = queue[key]
            return (True, validate_glow_spec(raw))
    from .shape_effect_containers import _queued_container_effect

    return _queued_container_effect(shape, "glow")


def get_shape_glow(shape: Any) -> GlowSpec | None:
    """Get active or saved GlowSpec for a shape.

    Surfaces malformed or unsupported state as refusal (ValueError), rather than None.
    """
    _assert_shape_editable(shape)
    if not _supports_shape_glow(shape):
        return None

    # 1. Check active presentation edit queue first
    has_queued, queued_spec = _get_active_queue_glow(shape)
    if has_queued:
        return queued_spec

    prs = getattr(getattr(shape, "_slide", None), "_presentation", None)
    curr_source = getattr(prs, "_source_path", None)

    # 2. Check cached payload if still bound to the same canonical source
    cached = shape._payload.get("glow")
    cached_source = shape._payload.get("_glow_source_path")
    if (
        cached is not None
        and cached_source is not None
        and curr_source is not None
        and Path(cached_source).resolve() == Path(curr_source).resolve()
    ):
        if cached == "__cleared__":
            return None
        if isinstance(cached, GlowSpec):
            return cached
        return validate_glow_spec(cached)

    # 3. Inspect saved package XML using canonical source path
    source_path = _canonical_source_path(prs)
    try:
        with zipfile.ZipFile(source_path) as package:
            root = ET.fromstring(package.read(shape._slide.partname))
        shape_element = _shape_xml_element(root, shape._payload)
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        raise ValueError(f"cannot read presentation package: {exc}") from exc
    except KeyError as exc:
        raise ValueError(f"slide part {shape._slide.partname!r} not found in package") from exc

    shape_properties = _shape_properties_element_from_shape(shape_element)
    if shape_properties is None:
        return None

    spec = _inspect_glow_from_properties(shape_properties)
    shape._payload["glow"] = spec
    shape._payload["_glow_source_path"] = str(source_path)
    return spec


# --------------------------------------------------------------------------- #
# Save Applicator                                                             #
# --------------------------------------------------------------------------- #


def _shape_payload(
    slide_payload: dict[str, Any],
    shape_ref: ShapeEditRef,
) -> dict[str, Any]:
    """Resolve shape payload for top-level or group child shape refs."""
    if isinstance(shape_ref, tuple):
        try:
            child_payload = slide_payload["shapes"][shape_ref[0]]
            for child_index in shape_ref[1:]:
                child_payload = child_payload["children"][child_index]
        except IndexError as exc:
            raise IndexError("group child shape index out of range") from exc
        except KeyError as exc:
            raise AttributeError("group child shape payload is unavailable") from exc
        return child_payload
    try:
        return slide_payload["shapes"][shape_ref]
    except IndexError as exc:
        raise IndexError("shape index out of range") from exc


def apply_shape_glow_edits(
    input_path: str | Path,
    output_path: str | Path,
    glow_edits: Sequence[tuple[tuple[int, ShapeEditRef], Any]]
    | dict[tuple[int, ShapeEditRef], Any],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    """Apply glow edits to PPTX package during save pipeline."""
    if isinstance(glow_edits, dict):
        edits_list = list(glow_edits.items())
    else:
        edits_list = list(glow_edits)

    if not edits_list:
        shutil.copyfile(input_path, output_path)
        return

    slides = slide_payloads if slide_payloads is not None else _load_slide_payloads(input_path)

    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeEditRef], Any]] = {}
    for (slide_index, shape_ref), spec in edits_list:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, spec))

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            if slide_index < 0 or slide_index >= len(slides):
                raise IndexError(f"slide index {slide_index} out of range")
            slide_payload = slides[slide_index]
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, raw_spec in slide_edits:
                shape_payload_item = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload_item)
                shape_properties = _shape_properties_element_from_shape(shape_element)
                if shape_properties is None:
                    shape_tag = _xml_local_name(shape_element.tag)
                    if shape_tag not in {"sp", "cxnSp", "pic"}:
                        raise AttributeError(
                            f"shape glow editing is not supported for <p:{shape_tag}> elements"
                        )
                    shape_properties = ET.Element(f"{{{P_NS}}}spPr")
                    shape_element.append(shape_properties)

                set_shape_glow(shape_properties, raw_spec)

            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    _copy_package_with_replacements(input_path, output_path, replacements)


__all__ = [
    "ALLOWED_GLOW_ATTRIBUTES",
    "VALID_GLOW_COLOR_TYPES",
    "GlowSpec",
    "apply_shape_glow_edits",
    "clear_shape_glow",
    "get_shape_glow",
    "glow_element",
    "inspect_glow_element",
    "set_shape_glow",
    "validate_glow_radius",
    "validate_glow_spec",
    "validate_transparency",
]
