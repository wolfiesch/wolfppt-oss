"""Shape outer shadow authoring, inspection, and package applicator for DrawingML."""

from __future__ import annotations

import math
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import (
    coerce_emu as _coerce_emu,
)
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

# Canonical DrawingML schema enums for CT_OuterShadowEffect
VALID_SHADOW_ALIGNMENTS: frozenset[str] = frozenset(
    {"tl", "t", "tr", "l", "ctr", "r", "bl", "b", "br"}
)
VALID_SHADOW_COLOR_TYPES: frozenset[str] = frozenset({"rgb", "scheme"})

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

ALLOWED_OUTER_SHADOW_ATTRIBUTES: frozenset[str] = frozenset(
    {"blurRad", "dist", "dir", "algn", "rotWithShape", "sx", "sy", "kx", "ky"}
)

# CT_EffectContainer children. Only cont, blend, and alphaMod contain further
# containers; other effect payloads are preserved without interpreting rendering.
_GRAPH_EFFECT_NAMES = frozenset(
    {
        "alphaBiLevel",
        "alphaCeiling",
        "alphaFloor",
        "alphaInv",
        "alphaMod",
        "alphaModFix",
        "alphaOutset",
        "alphaRepl",
        "biLevel",
        "blend",
        "blur",
        "clrChange",
        "clrRepl",
        "cont",
        "duotone",
        "effect",
        "fill",
        "fillOverlay",
        "glow",
        "grayscl",
        "hsl",
        "innerShdw",
        "lum",
        "outerShdw",
        "prstShdw",
        "reflection",
        "relOff",
        "softEdge",
        "tint",
        "xfrm",
    }
)
_GRAPH_INPUT_REFERENCES = frozenset({"fill", "line", "fillLine", "children"})


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
class OuterShadowSpec:
    """Immutable specification for an outer drop shadow effect."""

    blur_radius: int = 0
    distance: int = 0
    direction: float = 0.0
    alignment: str = "b"
    rotate_with_shape: bool = True
    color_type: str = "rgb"
    color_value: str = "000000"
    transparency: float = 0.0

    def __init__(
        self,
        blur_radius: Any = 0,
        distance: Any = 0,
        direction: Any = 0.0,
        alignment: Any = "b",
        rotate_with_shape: Any = True,
        color_type: str = "rgb",
        color_value: str = "000000",
        transparency: Any = 0.0,
        *,
        rgb: Any = None,
        theme_color: Any = None,
    ) -> None:
        b_rad = validate_blur_radius(blur_radius)
        dist = validate_distance(distance)
        direc = validate_direction(direction)
        algn = validate_alignment(alignment)
        rot = validate_rotate_with_shape(rotate_with_shape)
        transp = validate_transparency(transparency)

        if rgb is not None and theme_color is not None:
            raise ValueError("cannot specify both rgb and theme_color on OuterShadowSpec")
        if rgb is not None:
            c_type = "rgb"
            c_val = _normalize_rgb(rgb)
        elif theme_color is not None:
            c_type = "scheme"
            c_val = _normalize_theme_color(theme_color)
        else:
            if not isinstance(color_type, str) or color_type not in VALID_SHADOW_COLOR_TYPES:
                raise ValueError(
                    f"color_type must be one of {sorted(VALID_SHADOW_COLOR_TYPES)}, got {color_type!r}"
                )
            c_type = color_type
            if c_type == "rgb":
                c_val = _normalize_rgb(color_value)
            else:
                c_val = _normalize_theme_color(color_value)

        object.__setattr__(self, "blur_radius", b_rad)
        object.__setattr__(self, "distance", dist)
        object.__setattr__(self, "direction", direc)
        object.__setattr__(self, "alignment", algn)
        object.__setattr__(self, "rotate_with_shape", rot)
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
            "blur_radius": self.blur_radius,
            "distance": self.distance,
            "direction": self.direction,
            "alignment": self.alignment,
            "rotate_with_shape": self.rotate_with_shape,
            "color_type": self.color_type,
            "color_value": self.color_value,
            "transparency": self.transparency,
        }


def validate_blur_radius(blur_radius: Any) -> int:
    """Validate blur radius as non-negative EMU integer (ST_PositiveCoordinate)."""
    if isinstance(blur_radius, bool):
        raise TypeError("blur_radius cannot be a boolean")
    try:
        val = _coerce_emu(blur_radius, "blur_radius")
    except Exception as exc:
        raise TypeError(
            f"blur_radius must be an EMU integer, got {type(blur_radius).__name__}"
        ) from exc
    if val < 0:
        raise ValueError(f"blur_radius must be non-negative EMU, got {val}")
    return val


def validate_distance(distance: Any) -> int:
    """Validate shadow distance as non-negative EMU integer (ST_PositiveCoordinate)."""
    if isinstance(distance, bool):
        raise TypeError("distance cannot be a boolean")
    try:
        val = _coerce_emu(distance, "distance")
    except Exception as exc:
        raise TypeError(f"distance must be an EMU integer, got {type(distance).__name__}") from exc
    if val < 0:
        raise ValueError(f"distance must be non-negative EMU, got {val}")
    return val


def validate_direction(direction: Any) -> float:
    """Validate direction as degrees (ST_PositiveFixedAngle). Normalized to [0.0, 360.0)."""
    if isinstance(direction, bool) or not isinstance(direction, (int, float)):
        raise TypeError(f"direction must be a numeric degree value, got {type(direction).__name__}")
    val = float(direction)
    if not math.isfinite(val):
        raise ValueError(f"direction must be a finite number, got {val}")
    normalized = val % 360.0
    return round(normalized, 4)


def validate_alignment(alignment: Any) -> str:
    """Validate alignment against DrawingML ST_RectAlignment enum."""
    if alignment is None:
        return "b"
    if not isinstance(alignment, str) or alignment not in VALID_SHADOW_ALIGNMENTS:
        raise ValueError(
            f"invalid shadow alignment {alignment!r}; expected one of {sorted(VALID_SHADOW_ALIGNMENTS)}"
        )
    return alignment


def validate_rotate_with_shape(rotate_with_shape: Any) -> bool:
    """Validate rotate_with_shape boolean flag."""
    if not isinstance(rotate_with_shape, bool) and rotate_with_shape not in (0, 1):
        raise TypeError(
            f"rotate_with_shape must be a boolean, got {type(rotate_with_shape).__name__}"
        )
    return bool(rotate_with_shape)


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


def validate_outer_shadow_spec(spec: Any) -> OuterShadowSpec | None:
    """Validate an OuterShadowSpec instance or mapping; None represents cleared shadow."""
    if spec is None:
        return None
    if isinstance(spec, OuterShadowSpec):
        return spec
    if isinstance(spec, Mapping):
        valid_keys = {
            "blur_radius",
            "blur",
            "distance",
            "dist",
            "direction",
            "dir",
            "alignment",
            "algn",
            "rotate_with_shape",
            "rot_with_shape",
            "color_type",
            "color_value",
            "rgb",
            "theme_color",
            "transparency",
        }
        unknown = set(spec.keys()) - valid_keys
        if unknown:
            raise ValueError(f"unknown outer shadow property keys: {sorted(unknown)}")

        blur_val = spec.get("blur_radius", spec.get("blur", 0))
        dist_val = spec.get("distance", spec.get("dist", 0))
        dir_val = spec.get("direction", spec.get("dir", 0.0))
        algn_val = spec.get("alignment", spec.get("algn", "b"))
        rot_val = spec.get("rotate_with_shape", spec.get("rot_with_shape", True))
        transp_val = spec.get("transparency", 0.0)

        rgb = spec.get("rgb")
        theme_color = spec.get("theme_color")
        color_type = spec.get("color_type", "rgb")
        color_value = spec.get("color_value", "000000")

        return OuterShadowSpec(
            blur_radius=blur_val,
            distance=dist_val,
            direction=dir_val,
            alignment=algn_val,
            rotate_with_shape=rot_val,
            color_type=color_type,
            color_value=color_value,
            transparency=transp_val,
            rgb=rgb,
            theme_color=theme_color,
        )

    raise TypeError(
        f"outer shadow spec must be an OuterShadowSpec, Mapping, or None; got {type(spec).__name__}"
    )


# --------------------------------------------------------------------------- #
# XML Refusal & Inspection                                                    #
# --------------------------------------------------------------------------- #


def _assert_shape_editable(shape: Any) -> None:
    """Refuse pending or deleted shapes before reading or authoring outer shadow."""
    payload = getattr(shape, "_payload", {})
    if bool(payload.get("_deleted")):
        raise ValueError("cannot edit or read shadow properties of a deleted shape")
    slide = getattr(shape, "_slide", None)
    if slide is not None and getattr(slide, "_deleted", False):
        raise ValueError("cannot edit or read shadow properties on a deleted slide")
    if bool(payload.get("_pending_shape") or payload.get("_pending_group_child")):
        raise ValueError("cannot edit or read shadow properties of an unsaved pending shape")


def _supports_shape_shadow(shape: Any) -> bool:
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
        raise ValueError(
            "shape declares unsupported 'effectDag' element; cannot edit or read outer shadow"
        )
    effect_lists = [c for c in list(shape_properties) if _xml_local_name(c.tag) == "effectLst"]
    if len(effect_lists) > 1:
        raise ValueError("shape declares multiple ambiguous 'effectLst' containers")


def _effect_dag_shadow(
    graph: ET.Element,
) -> tuple[ET.Element, ET.Element | None]:
    """Resolve one physical shadow, checking containment and reference edges.

    References name containers, not individual effects. Shared references to a
    single container therefore do not create multiple editable shadow nodes.
    Empty containers remain valid reference targets after clearing a shadow.
    """
    shadows = _walk_effect_dag(graph)
    if len(shadows) > 1:
        raise ValueError("effectDag declares multiple ambiguous outerShdw nodes")
    return shadows[0] if shadows else (graph, None)


def _walk_effect_dag(graph: ET.Element) -> list[tuple[ET.Element, ET.Element]]:
    """Check a graph's containers, references and acyclicity; list its shadows."""
    names: dict[str, ET.Element] = {}
    dependencies: dict[ET.Element, list[ET.Element]] = {}
    references: list[tuple[ET.Element, str]] = []
    shadows: list[tuple[ET.Element, ET.Element]] = []
    pending = [graph]
    while pending:
        container = pending.pop()
        dependencies[container] = []
        if set(container.attrib) - {"name", "type"}:
            raise ValueError("effectDag container declares unsupported attributes")
        if container.get("type", "sib") not in {"sib", "tree"}:
            raise ValueError("effectDag container declares an invalid type")
        if container.text and container.text.strip():
            raise ValueError("effectDag container contains unexpected text")
        # An empty name (PowerPoint saves name="") leaves the container unnamed.
        name = " ".join(container.get("name", "").split())
        if name:
            if name in names or name in _GRAPH_INPUT_REFERENCES:
                raise ValueError("effectDag declares an ambiguous container name")
            names[name] = container
        for child in container:
            name = _xml_local_name(child.tag)
            if (
                child.tag != f"{{{ooxml_namespace(container, A_NS)}}}{name}"
                or name not in _GRAPH_EFFECT_NAMES
            ):
                raise ValueError(f"effectDag declares unsupported graph child {child.tag!r}")
            if child.tail and child.tail.strip():
                raise ValueError("effectDag container contains unexpected text")
            if name == "effect":
                ref = " ".join(child.get("ref", "").split())
                if (
                    not ref
                    or set(child.attrib) != {"ref"}
                    or len(child)
                    or (child.text and child.text.strip())
                ):
                    raise ValueError("effectDag declares a malformed effect reference")
                references.append((container, ref))
            elif name in {"cont", "blend", "alphaMod"}:
                nested = child
                if name != "cont":
                    allowed = {"blend"} if name == "blend" else set()
                    if set(child.attrib) != allowed or (
                        name == "blend"
                        and child.get("blend")
                        not in {"over", "mult", "screen", "darken", "lighten"}
                    ):
                        raise ValueError(f"effectDag {name} declares malformed attributes")
                    if (
                        len(child) != 1
                        or child[0].tag != f"{{{ooxml_namespace(child, A_NS)}}}cont"
                        or (child.text and child.text.strip())
                        or (child[0].tail and child[0].tail.strip())
                    ):
                        raise ValueError(f"effectDag {name} requires one effect container")
                    nested = child[0]
                dependencies[container].append(nested)
                pending.append(nested)
            else:
                # Do not mistake effects hidden in opaque/invalid payloads for
                # editable graph nodes, or overlook their references.
                for descendant in child.iter():
                    if descendant is child:
                        continue
                    if _xml_local_name(descendant.tag) in {
                        "cont",
                        "effectDag",
                        "effect",
                        "outerShdw",
                    }:
                        raise ValueError("effectDag contains a misplaced graph node")
                if name == "outerShdw":
                    shadows.append((container, child))
    for container, ref in references:
        if ref in _GRAPH_INPUT_REFERENCES:
            continue
        target = names.get(ref)
        if target is None:
            raise ValueError(f"effectDag reference {ref!r} has no local container target")
        dependencies[container].append(target)
    try:
        TopologicalSorter(dependencies).prepare()
    except CycleError as exc:
        raise ValueError("effectDag contains cyclic container references") from exc
    return shadows


def _outer_shadow_location(
    properties: ET.Element,
    *,
    effect_name: str = "outerShdw",
) -> tuple[ET.Element | None, ET.Element | None]:
    """Locate a shadow without flattening its effect container."""
    graphs = findall_ooxml(properties, f"{{{A_NS}}}effectDag")
    if graphs:
        if len(graphs) != 1 or find_ooxml(properties, f"{{{A_NS}}}effectLst") is not None:
            raise ValueError("shape declares ambiguous effectDag/effectLst containers")
        if effect_name != "outerShdw":
            _assert_no_unsupported_effects(properties)
        return _effect_dag_shadow(graphs[0])
    _assert_no_unsupported_effects(properties)
    effect_list = find_ooxml(properties, f"{{{A_NS}}}effectLst")
    if effect_list is None:
        return None, None
    elements = findall_ooxml(effect_list, f"{{{A_NS}}}{effect_name}")
    if len(elements) > 1:
        raise ValueError(
            f"shape declares {len(elements)} {effect_name} elements; cannot ambiguously inspect or edit"
        )
    return effect_list, elements[0] if elements else None


def _inspect_outer_shadow_from_properties(
    shape_properties: ET.Element,
    *,
    effect_name: str = "outerShdw",
) -> OuterShadowSpec | None:
    """Parse OuterShadowSpec from spPr XML element.

    Refuses malformed or ambiguous graphs, unsupported attributes (sx, sy, kx, ky),
    nested color transforms, foreign children, out-of-range alpha or direction, or ambiguous outerShdw.
    """
    _, elem = _outer_shadow_location(shape_properties, effect_name=effect_name)
    if elem is None:
        return None
    return _inspect_outer_shadow_element(elem, effect_name=effect_name)


def _inspect_outer_shadow_element(
    elem: ET.Element,
    *,
    effect_name: str = "outerShdw",
) -> OuterShadowSpec:
    """Inspect the resolved node using the same contract for lists and graphs."""

    # Check for unknown or unsupported attributes on <a:outerShdw>
    allowed = (
        {"blurRad", "dist", "dir"}
        if effect_name == "innerShdw"
        else ALLOWED_OUTER_SHADOW_ATTRIBUTES
    )
    unknown_attrs = set(elem.attrib.keys()) - allowed
    if unknown_attrs:
        raise ValueError(
            f"{effect_name} declares unsupported attribute(s): {sorted(unknown_attrs)}"
        )

    sx = elem.attrib.get("sx", "100000")
    sy = elem.attrib.get("sy", "100000")
    kx = elem.attrib.get("kx", "0")
    ky = elem.attrib.get("ky", "0")
    if sx != "100000" or sy != "100000" or kx != "0" or ky != "0":
        raise ValueError(
            f"outerShdw declares unsupported scaling or skew (sx={sx!r}, sy={sy!r}, kx={kx!r}, ky={ky!r}); "
            "cannot safely edit or inspect without erasing content"
        )

    raw_blur = elem.attrib.get("blurRad", "0")
    try:
        blur_radius = int(raw_blur)
    except ValueError as exc:
        raise ValueError(f"outerShdw blurRad is non-numeric: {raw_blur!r}") from exc
    if blur_radius < 0:
        raise ValueError(f"outerShdw blurRad must be non-negative: {blur_radius}")

    raw_dist = elem.attrib.get("dist", "0")
    try:
        distance = int(raw_dist)
    except ValueError as exc:
        raise ValueError(f"outerShdw dist is non-numeric: {raw_dist!r}") from exc
    if distance < 0:
        raise ValueError(f"outerShdw dist must be non-negative: {distance}")

    raw_dir = elem.attrib.get("dir", "0")
    try:
        dir_units = int(raw_dir)
    except ValueError as exc:
        raise ValueError(f"outerShdw dir is non-numeric: {raw_dir!r}") from exc
    if dir_units < 0 or dir_units >= 21600000:
        raise ValueError(f"outerShdw dir is out of range [0, 21600000): {dir_units}")
    direction = dir_units / 60000.0

    alignment = elem.attrib.get("algn", "b")
    if alignment not in VALID_SHADOW_ALIGNMENTS:
        raise ValueError(f"outerShdw algn is invalid: {alignment!r}")

    rot_raw = elem.attrib.get("rotWithShape", "1")
    if rot_raw not in ("0", "1", "false", "true"):
        raise ValueError(f"outerShdw rotWithShape is invalid: {rot_raw!r}")
    rotate_with_shape = rot_raw not in ("0", "false")

    # Inspect color choice children
    color_children = [
        c
        for c in list(elem)
        if (c.tag in _SUPPORTED_COLOR_TAGS or c.tag in _UNSUPPORTED_COLOR_TAGS)
        and c.tag.startswith(f"{{{ooxml_namespace(elem, A_NS)}}}")
    ]
    if len(color_children) != 1 or len(list(elem)) != 1:
        if len(color_children) == 0:
            raise ValueError("outerShdw has no color child element; ambiguous effect structure")
        raise ValueError(
            f"outerShdw declares {len(list(elem))} child elements; expected exactly one color element"
        )

    color_child = color_children[0]
    if set(color_child.attrib) - {"val"}:
        raise ValueError("outerShdw color declares unsupported attributes")
    for node in elem.iter():
        if node.text and node.text.strip():
            raise ValueError("outerShdw contains unexpected text")
        if node is not elem and node.tail and node.tail.strip():
            raise ValueError("outerShdw contains unexpected text")
    if color_child.tag in _UNSUPPORTED_COLOR_TAGS:
        raise ValueError(
            f"outerShdw declares unsupported color model '{_xml_local_name(color_child.tag)}'"
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

    # Verify no unsupported color transform children (lumMod, tint, shade, etc.)
    for child in list(color_child):
        if child.tag != f"{{{ooxml_namespace(color_child, A_NS)}}}alpha":
            raise ValueError(
                f"outerShdw color element declares unsupported color transform '{_xml_local_name(child.tag)}'"
            )
        if set(child.attrib) - {"val"} or len(child):
            raise ValueError("outerShdw alpha declares unsupported attributes or children")

    # Inspect transparency via <a:alpha>
    alpha_elements = findall_ooxml(color_child, f"{{{A_NS}}}alpha")
    if len(alpha_elements) > 1:
        raise ValueError("color element declares multiple conflicting <a:alpha> modifiers")
    if alpha_elements:
        alpha_raw = alpha_elements[0].attrib.get("val")
        if alpha_raw is None:
            raise ValueError("alpha element missing val attribute")
        if effect_name == "innerShdw":
            transparency = round(1.0 - _effect_percentage(alpha_raw), 6)
        else:
            try:
                alpha_int = int(alpha_raw)
            except ValueError as exc:
                raise ValueError(f"alpha val attribute is non-numeric: {alpha_raw!r}") from exc
            if alpha_int < 0 or alpha_int > 100000:
                raise ValueError(f"alpha val must be in range [0, 100000], got {alpha_int}")
            transparency = round((100000 - alpha_int) / 100000.0, 6)
    else:
        transparency = 0.0

    return OuterShadowSpec(
        blur_radius=blur_radius,
        distance=distance,
        direction=direction,
        alignment=alignment,
        rotate_with_shape=rotate_with_shape,
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


def set_shape_outer_shadow(
    shape_properties: ET.Element,
    spec: OuterShadowSpec | Mapping[str, Any] | None,
) -> None:
    """Set or clear an outer shadow, preserving unrelated effects and references.

    Graph edits retain the target's position and every container, including an
    empty named container after clearing. Insertion into a graph without an
    existing shadow is refused because the public API has no branch selector.
    """
    effect_list, existing = _outer_shadow_location(shape_properties)
    if existing is not None:
        _inspect_outer_shadow_element(existing)
    validated_spec = validate_outer_shadow_spec(spec)
    graph = shape_properties.find(f"{{{A_NS}}}effectDag")
    if validated_spec is None:
        if effect_list is not None and existing is not None:
            effect_list.remove(existing)
        return
    if graph is not None and existing is None:
        raise ValueError(
            "unsupported 'effectDag' shadow insertion: no existing outerShdw "
            "node; the public shadow API cannot select a graph branch"
        )
    if effect_list is None:
        effect_list = _effect_list(shape_properties)

    outer_shdw = _outer_shadow_element(validated_spec)
    if existing is not None:
        index = list(effect_list).index(existing)
        outer_shdw.tail = existing.tail
        effect_list.remove(existing)
        if graph is not None:
            effect_list.insert(index, outer_shdw)
            return
    _insert_effect_list_child(effect_list, outer_shdw)


def _outer_shadow_element(validated_spec: OuterShadowSpec) -> ET.Element:
    """Build the ``a:outerShdw`` one validated outer shadow authors."""
    outer_shdw = ET.Element(f"{{{A_NS}}}outerShdw")
    if validated_spec.blur_radius > 0:
        outer_shdw.set("blurRad", str(validated_spec.blur_radius))
    if validated_spec.distance > 0:
        outer_shdw.set("dist", str(validated_spec.distance))

    dir_units = round(validated_spec.direction * 60000) % (360 * 60000)
    if dir_units != 0:
        outer_shdw.set("dir", str(dir_units))

    if validated_spec.alignment != "b":
        outer_shdw.set("algn", validated_spec.alignment)

    if not validated_spec.rotate_with_shape:
        outer_shdw.set("rotWithShape", "0")

    # Build color element with alpha modifier if transparency > 0
    if validated_spec.color_type == "rgb":
        color_elem = ET.Element(f"{{{A_NS}}}srgbClr", {"val": validated_spec.color_value})
    else:
        color_elem = ET.Element(f"{{{A_NS}}}schemeClr", {"val": validated_spec.color_value})

    if validated_spec.transparency > 0.0:
        alpha_val = round((1.0 - validated_spec.transparency) * 100000)
        alpha_elem = ET.Element(f"{{{A_NS}}}alpha", {"val": str(alpha_val)})
        color_elem.append(alpha_elem)

    outer_shdw.append(color_elem)
    return outer_shdw


# --------------------------------------------------------------------------- #
# Readback & Facade inspection                                                #
# --------------------------------------------------------------------------- #


def _get_active_queue_shadow(shape: Any) -> tuple[bool, OuterShadowSpec | None]:
    """Check presentation queue for queued outer shadow or inherit edits."""
    prs = getattr(getattr(shape, "_slide", None), "_presentation", None)
    if prs is None:
        return (False, None)
    queue = getattr(prs, "_shape_effect_edits", None)
    if isinstance(queue, dict):
        key = (shape._slide._index, shape_edit_ref(shape))
        pending = queue.get(key)
        if isinstance(pending, Mapping) and "outer_shadow" in pending:
            return (True, validate_outer_shadow_spec(pending["outer_shadow"]))
    from .shape_effect_containers import _queued_container_effect

    return _queued_container_effect(shape, "outer_shadow")


def get_shape_outer_shadow(shape: Any) -> OuterShadowSpec | None:
    """Get active or saved OuterShadowSpec for a shape.

    Surfaces malformed or unsupported state as refusal (ValueError), rather than None.
    """
    _assert_shape_editable(shape)
    if not _supports_shape_shadow(shape):
        return None

    # 1. Check active presentation edit queue first
    has_queued, queued_spec = _get_active_queue_shadow(shape)
    if has_queued:
        return queued_spec

    prs = getattr(getattr(shape, "_slide", None), "_presentation", None)
    curr_source = getattr(prs, "_source_path", None)

    # 2. Check cached payload if still bound to the same canonical source
    cached = shape._payload.get("outer_shadow")
    cached_source = shape._payload.get("_outer_shadow_source_path")
    if (
        cached is not None
        and cached_source is not None
        and curr_source is not None
        and Path(cached_source).resolve() == Path(curr_source).resolve()
    ):
        if cached == "__cleared__":
            return None
        if isinstance(cached, OuterShadowSpec):
            return cached
        return validate_outer_shadow_spec(cached)

    # 3. If inherit is True in queue, no local effectLst outerShdw applies
    inherit_queue = getattr(prs, "_shape_shadow_inherit_edits", None)
    if isinstance(inherit_queue, dict):
        inherit_val = inherit_queue.get((shape._slide._index, shape_edit_ref(shape)))
        if inherit_val is True:
            return None

    # 4. Inspect saved package XML using canonical source path
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

    # Refuse malformed graphs and unrepresentable shadow properties.
    spec = _inspect_outer_shadow_from_properties(shape_properties)
    shape._payload["outer_shadow"] = spec
    shape._payload["_outer_shadow_source_path"] = str(source_path)
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


@dataclass(frozen=True)
class InnerShadowSpec(OuterShadowSpec):
    """Typed authoring value for DrawingML ``a:innerShdw``."""

    def __post_init__(self) -> None:
        # The inherited dataclass fields retain the public constructor contract,
        # but CT_InnerShadowEffect has no alignment or rotation attributes.
        OuterShadowSpec.__init__(self, **self.to_dict())
        if self.alignment != "b":
            raise ValueError("inner shadow does not support alignment")
        if not self.rotate_with_shape:
            raise ValueError("inner shadow does not support rotate_with_shape=False")


@dataclass(frozen=True)
class SoftEdgeSpec:
    """Typed authoring value for DrawingML ``a:softEdge``."""

    radius: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "radius", validate_blur_radius(self.radius))

    def to_dict(self) -> dict[str, int]:
        return {"radius": self.radius}


@dataclass(frozen=True)
class ReflectionSpec:
    """Typed authoring value for DrawingML ``a:reflection``."""

    blur_radius: int = 0
    distance: int = 0
    direction: float = 90.0
    start_alpha: float = 0.5
    end_alpha: float = 0.0
    start_position: float = 0.0
    end_position: float = 1.0
    rotate_with_shape: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "blur_radius", validate_blur_radius(self.blur_radius))
        object.__setattr__(self, "distance", validate_distance(self.distance))
        object.__setattr__(self, "direction", validate_direction(self.direction))
        for attribute in ("start_alpha", "end_alpha", "start_position", "end_position"):
            object.__setattr__(
                self, attribute, validate_transparency(float(getattr(self, attribute)))
            )
        if self.start_position > self.end_position:
            raise ValueError("reflection start_position must not exceed end_position")
        object.__setattr__(
            self,
            "rotate_with_shape",
            validate_rotate_with_shape(self.rotate_with_shape),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "blur_radius": self.blur_radius,
            "distance": self.distance,
            "direction": self.direction,
            "start_alpha": self.start_alpha,
            "end_alpha": self.end_alpha,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "rotate_with_shape": self.rotate_with_shape,
        }


# Per-effect kinds whose typed values and codec live in ``shape_effect_containers``
# (imported lazily: that module imports this one).
_CONTAINER_EFFECT_TAGS: dict[str, str] = {
    "blur": "blur",
    "fill_overlay": "fillOverlay",
    "preset_shadow": "prstShdw",
}
_ADVANCED_EFFECT_TAGS: dict[str, str] = {
    "inner_shadow": "innerShdw",
    "soft_edge": "softEdge",
    "reflection": "reflection",
    **_CONTAINER_EFFECT_TAGS,
}


def _validate_advanced_effect(effect: str, spec: Any) -> Any:
    if effect not in _ADVANCED_EFFECT_TAGS:
        raise ValueError(f"unsupported shape effect {effect!r}")
    if effect in _CONTAINER_EFFECT_TAGS:
        from .shape_effect_containers import _NODE_TYPES

        cls = _NODE_TYPES[effect][0]
    else:
        cls = {
            "inner_shadow": InnerShadowSpec,
            "soft_edge": SoftEdgeSpec,
            "reflection": ReflectionSpec,
        }[effect]
    if spec is None:
        return None
    values = spec.to_dict() if hasattr(spec, "to_dict") else dict(spec)
    return cls(**values)


def _effect_percentage(raw: str) -> float:
    value = float(raw[:-1]) / 100 if raw.endswith("%") else int(raw) / 100000
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"effect percentage is out of range: {raw!r}")
    return value


def _inspect_advanced_effect(properties: ET.Element, effect: str) -> Any:
    _assert_no_unsupported_effects(properties)
    if effect == "inner_shadow":
        outer = _inspect_outer_shadow_from_properties(properties, effect_name="innerShdw")
        return None if outer is None else InnerShadowSpec(**outer.to_dict())
    name = _ADVANCED_EFFECT_TAGS[effect]
    elements = findall_ooxml(properties, f"{{{A_NS}}}effectLst/{{{A_NS}}}{name}")
    if not elements:
        return None
    if len(elements) != 1:
        raise ValueError(f"shape declares multiple ambiguous {name} elements")
    return _inspect_advanced_element(elements[0], effect)


def _inspect_advanced_element(element: ET.Element, effect: str) -> Any:
    """Read one ``a:innerShdw``, ``a:softEdge``, ``a:reflection``, ``a:blur``,
    ``a:fillOverlay`` or ``a:prstShdw`` element."""
    if effect in _CONTAINER_EFFECT_TAGS:
        from .shape_effect_containers import _read_effect_node

        return _read_effect_node(element, graph=False)
    if effect == "inner_shadow":
        outer = _inspect_outer_shadow_element(element, effect_name="innerShdw")
        return InnerShadowSpec(**outer.to_dict())
    name = _ADVANCED_EFFECT_TAGS[effect]
    allowed = (
        {"rad"}
        if effect == "soft_edge"
        else {
            "blurRad",
            "dist",
            "dir",
            "stA",
            "endA",
            "stPos",
            "endPos",
            "rotWithShape",
            "fadeDir",
            "sx",
            "sy",
            "kx",
            "ky",
            "algn",
        }
    )
    if set(element.attrib) - allowed or len(element):
        raise ValueError(f"{name} declares unsupported attributes or children")
    if effect == "soft_edge":
        if "rad" not in element.attrib:
            raise ValueError("softEdge requires rad")
        return SoftEdgeSpec(radius=int(element.attrib["rad"]))
    # Refuse values this public spec cannot represent rather than losing them
    # when a caller assigns the readback value to another shape.
    for attribute in ("sx", "sy"):
        if _effect_percentage(element.get(attribute, "100000")) != 1:
            raise ValueError(f"reflection declares unsupported {attribute}")
    for attribute, default in (("kx", 0), ("ky", 0), ("fadeDir", 5400000)):
        if int(element.get(attribute, str(default))) != default:
            raise ValueError(f"reflection declares unsupported {attribute}")
    if element.get("algn", "b") != "b":
        raise ValueError("reflection declares unsupported algn")
    direction = int(element.get("dir", "0"))
    if not 0 <= direction < 21600000:
        raise ValueError("reflection dir is out of range")
    rotation = element.get("rotWithShape", "true")
    if rotation not in {"true", "false", "1", "0"}:
        raise ValueError("reflection rotWithShape is invalid")
    return ReflectionSpec(
        blur_radius=int(element.get("blurRad", "0")),
        distance=int(element.get("dist", "0")),
        direction=direction / 60000,
        start_alpha=_effect_percentage(element.get("stA", "100000")),
        end_alpha=_effect_percentage(element.get("endA", "0")),
        start_position=_effect_percentage(element.get("stPos", "0")),
        end_position=_effect_percentage(element.get("endPos", "100000")),
        rotate_with_shape=rotation in {"true", "1"},
    )


def _get_shape_advanced_effect(shape: Any, effect: str) -> Any:
    _assert_shape_editable(shape)
    if not _supports_shape_shadow(shape):
        return None
    presentation = shape._slide._presentation
    queue = getattr(presentation, "_shape_effect_edits", {})
    pending = queue.get((shape._slide._index, shape_edit_ref(shape)), {})
    if effect in pending:
        return _validate_advanced_effect(effect, pending[effect])
    from .shape_effect_containers import _queued_container_effect

    queued, value = _queued_container_effect(shape, effect)
    if queued:
        return value
    source_path = _canonical_source_path(presentation)
    try:
        with zipfile.ZipFile(source_path) as package:
            root = ET.fromstring(package.read(shape._slide.partname))
    except (FileNotFoundError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"cannot read presentation effect: {exc}") from exc
    properties = _shape_properties_element_from_shape(_shape_xml_element(root, shape._payload))
    return None if properties is None else _inspect_advanced_effect(properties, effect)


def _effect_list(shape_properties: ET.Element) -> ET.Element:
    _assert_no_unsupported_effects(shape_properties)
    effect_list = shape_properties.find(f"{{{A_NS}}}effectLst")
    if effect_list is not None:
        return effect_list
    effect_list = ET.Element(f"{{{A_NS}}}effectLst")
    insert_at = next(
        (
            index
            for index, child in enumerate(shape_properties)
            if _xml_local_name(child.tag) in {"scene3d", "sp3d", "extLst"}
        ),
        len(shape_properties),
    )
    shape_properties.insert(insert_at, effect_list)
    return effect_list


def _replace_effect(effect_list: ET.Element, name: str, value: ET.Element | None) -> None:
    for child in list(effect_list):
        if _xml_local_name(child.tag) == name:
            effect_list.remove(child)
    if value is not None:
        _insert_effect_list_child(effect_list, value)


def set_shape_effect(
    shape_properties: ET.Element, effect: str, spec: Mapping[str, Any] | None
) -> None:
    """Apply one discriminated 2-D effect, preserving all effect-list siblings.

    ``effects`` replaces the whole effect container (see
    :func:`~wolfppt.shape_effect_containers.set_effect_container`).
    """
    if effect == "effects":
        from .shape_effect_containers import set_effect_container

        set_effect_container(shape_properties, spec)
        return
    if effect == "outer_shadow":
        set_shape_outer_shadow(shape_properties, spec)
        return
    if effect not in _ADVANCED_EFFECT_TAGS:
        raise ValueError(f"unsupported shape effect {effect!r}")
    value = _validate_advanced_effect(effect, spec)
    if spec is None:
        _replace_effect(_effect_list(shape_properties), _ADVANCED_EFFECT_TAGS[effect], None)
        return
    _replace_effect(
        _effect_list(shape_properties),
        _ADVANCED_EFFECT_TAGS[effect],
        _advanced_effect_element(value),
    )


def _advanced_effect_element(value: Any) -> ET.Element:
    """Build the element one validated per-effect value authors."""
    from .shape_effect_containers import _KIND_BY_TYPE, _effect_node_element

    if _KIND_BY_TYPE.get(type(value)) in _CONTAINER_EFFECT_TAGS:
        return _effect_node_element(value)
    if isinstance(value, InnerShadowSpec):
        element = ET.Element(f"{{{A_NS}}}innerShdw")
        for attr, raw in (
            ("blurRad", value.blur_radius),
            ("dist", value.distance),
            ("dir", round(value.direction * 60000) % 21600000),
        ):
            if raw:
                element.set(attr, str(raw))
        color = ET.SubElement(
            element,
            f"{{{A_NS}}}{'srgbClr' if value.color_type == 'rgb' else 'schemeClr'}",
            {"val": value.color_value},
        )
        if value.transparency:
            ET.SubElement(
                color,
                f"{{{A_NS}}}alpha",
                {"val": str(round((1 - value.transparency) * 100000))},
            )
    elif isinstance(value, SoftEdgeSpec):
        element = ET.Element(f"{{{A_NS}}}softEdge", {"rad": str(value.radius)})
    else:
        element = ET.Element(f"{{{A_NS}}}reflection")
        for attr, raw in (
            ("blurRad", value.blur_radius),
            ("dist", value.distance),
            ("dir", round(value.direction * 60000) % 21600000),
            ("stA", round(value.start_alpha * 100000)),
            ("endA", round(value.end_alpha * 100000)),
            ("stPos", round(value.start_position * 100000)),
            ("endPos", round(value.end_position * 100000)),
        ):
            element.set(attr, str(raw))
        if not value.rotate_with_shape:
            element.set("rotWithShape", "0")
    return element


def apply_shape_effect_edits(
    input_path: str | Path,
    output_path: str | Path,
    effect_edits: Sequence[tuple[tuple[int, ShapeEditRef], Mapping[str, Mapping[str, Any] | None]]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    """Apply the one discriminated advanced-effect queue during package save."""
    if not effect_edits:
        shutil.copyfile(input_path, output_path)
        return
    slides = slide_payloads if slide_payloads is not None else _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    by_slide: dict[int, list[tuple[ShapeEditRef, Mapping[str, Mapping[str, Any] | None]]]] = {}
    for (slide_index, shape_ref), effects in effect_edits:
        by_slide.setdefault(slide_index, []).append((shape_ref, effects))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in by_slide.items():
            root = ET.fromstring(package.read(str(slides[slide_index]["part"])))
            for shape_ref, effects in slide_edits:
                element = _shape_xml_element(root, _shape_payload(slides[slide_index], shape_ref))
                properties = _shape_properties_element_from_shape(element)
                if properties is None:
                    properties = ET.Element(f"{{{P_NS}}}spPr")
                    element.append(properties)
                for effect, spec in effects.items():
                    set_shape_effect(properties, effect, spec)
            replacements[str(slides[slide_index]["part"])] = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


__all__ = [
    "VALID_SHADOW_ALIGNMENTS",
    "VALID_SHADOW_COLOR_TYPES",
    "InnerShadowSpec",
    "OuterShadowSpec",
    "ReflectionSpec",
    "SoftEdgeSpec",
    "apply_shape_effect_edits",
    "get_shape_outer_shadow",
    "set_shape_effect",
    "set_shape_outer_shadow",
    "validate_alignment",
    "validate_blur_radius",
    "validate_direction",
    "validate_distance",
    "validate_outer_shadow_spec",
    "validate_rotate_with_shape",
    "validate_transparency",
]
