"""Atomic saved-deck slide resizing with real shape and text geometry scaling.

``resize_slide_size(deck, width, height, mode="fit")`` uses integral EMU. Fit
uniformly scales authored slide, layout, and master content into the new canvas,
centering the old canvas. Maximize uses the larger uniform scale and centers
overflow for cropping at the canvas edges. Stretch scales each axis separately;
font sizes and scalar effects follow the vertical factor. Stretch is not glyph
distortion and refuses rotated content when the factors differ.

Groups scale only their outer frame: child coordinate systems and descendant
transforms stay unchanged, while text and stroke dimensions scale once. Explicit
and inherited text styles are scaled. Referenced theme line/effect styles are
materialized locally, leaving themes and notes pages byte-preserved.

``set_slide_size_preset(deck, SlideSizeType.A4)`` selects a landscape preset.
Paper presets use full sheet dimensions; projection presets use Wolf's authored
canvas sizes. ``slide_size_type(deck)`` reads the saved XML type without guessing
from its aspect ratio. CUSTOM is a type, not a preset with invented dimensions.
``set_slide_orientation(deck, SlideOrientation.PORTRAIT)`` swaps the saved canvas
axes and applies the selected resize mode, preserving the type and notes canvas.
It does not rotate shapes. Square canvases read as LANDSCAPE.

Save pending facade edits first, call the resize function, then save normally.
A successful rewrite rebases the presentation; reacquire slides and shapes after
it. Unsupported constructs raise SlideSizeScalingRefusal before package writes.
"""

from __future__ import annotations

import zipfile
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from numbers import Integral
from typing import Any
from xml.etree import ElementTree as ET

from .chart_workbook import serialize_xml_preserving_namespaces
from .package_parts import rels_part_for_package_part, resolve_package_target
from .presentation_size import (
    MAX_PAGE_COORDINATE_EMU,
    MAX_SLIDE_SIZE_EMU,
    MIN_SLIDE_SIZE_EMU,
    PresentationSizeRefusal,
    _page_presentation_root,
    _page_size_values,
    _unique_page_size_element,
)
from .slide_metadata import presentation_partname
from .xml_helpers import (
    A_NS,
    P_NS,
    STRICT_A_NS,
    STRICT_P_NS,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
)

__all__ = [
    "SlideSizeScalingRefusal",
    "slide_size_preset",
    "resize_slide_size",
    "set_slide_size_preset",
    "SlideSizeType",
    "SlideOrientation",
    "slide_size_type",
    "slide_orientation",
    "set_slide_orientation",
]

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_REL_BASES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/",
}


class SlideSizeType(StrEnum):
    """PresentationML slide-size types; CUSTOM requires explicit dimensions."""

    SCREEN_4X3 = "screen4x3"
    LETTER = "letter"
    A4 = "A4"
    FILM_35MM = "35mm"
    OVERHEAD = "overhead"
    BANNER = "banner"
    CUSTOM = "custom"
    LEDGER = "ledger"
    A3 = "A3"
    B4_ISO = "B4ISO"
    B5_ISO = "B5ISO"
    B4_JIS = "B4JIS"
    B5_JIS = "B5JIS"
    HAGAKI_CARD = "hagakiCard"
    SCREEN_16X9 = "screen16x9"
    SCREEN_16X10 = "screen16x10"


class SlideOrientation(StrEnum):
    """Canvas orientation; changing it swaps axes, without rotating content."""

    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


# Paper presets use full physical paper sizes, landscape, in integral EMU.
# Projection presets retain Wolf's existing 4:3 and widescreen dimensions.
_PRESETS = {
    SlideSizeType.SCREEN_4X3: (9144000, 6858000),
    SlideSizeType.SCREEN_16X9: (12192000, 6858000),
    SlideSizeType.SCREEN_16X10: (9144000, 5715000),
    SlideSizeType.LETTER: (10058400, 7772400),
    SlideSizeType.LEDGER: (15544800, 10058400),
    SlideSizeType.A3: (15120000, 10692000),
    SlideSizeType.A4: (10692000, 7560000),
    SlideSizeType.B4_ISO: (12708000, 9000000),
    SlideSizeType.B5_ISO: (9000000, 6336000),
    SlideSizeType.B4_JIS: (13104000, 9252000),
    SlideSizeType.B5_JIS: (9252000, 6552000),
    SlideSizeType.HAGAKI_CARD: (5328000, 3600000),
    SlideSizeType.FILM_35MM: (10287000, 6858000),
    SlideSizeType.OVERHEAD: (9144000, 6858000),
    SlideSizeType.BANNER: (7315200, 914400),
}
_SHAPES = {"sp", "pic", "cxnSp", "grpSp", "graphicFrame"}
_SAFE_EXTENSIONS = {"creationId", "modId", "compatExt", "useLocalDpi"}


class SlideSizeScalingRefusal(ValueError):
    """Slide content cannot be resized safely under the requested policy."""


def _preset_type(name: SlideSizeType | str) -> SlideSizeType:
    if not isinstance(name, str):
        raise SlideSizeScalingRefusal("slide preset must be a SlideSizeType or XML type string")
    aliases = {"4:3": SlideSizeType.SCREEN_4X3, "16:9": SlideSizeType.SCREEN_16X9}
    try:
        kind = aliases[name] if name in aliases else SlideSizeType(name)
    except ValueError as exc:
        raise SlideSizeScalingRefusal(f"unsupported slide preset {name!r}") from exc
    if kind == SlideSizeType.CUSTOM:
        raise SlideSizeScalingRefusal("custom slide size requires explicit width and height")
    return kind


def slide_size_preset(name: SlideSizeType | str) -> tuple[int, int]:
    """Return landscape EMU dimensions for a standard type or '4:3'/'16:9'.

    Paper types use their full physical sheet dimensions, not a print-margin
    inset. CUSTOM has no predefined dimensions; use ``resize_slide_size``.
    """
    return _PRESETS[_preset_type(name)]


def set_slide_size_preset(
    presentation: Any, name: SlideSizeType | str, *, mode: str = "fit"
) -> None:
    """Resize saved content to a preset and persist its PresentationML size type."""
    kind = _preset_type(name)
    width, height = _PRESETS[kind]
    _resize(presentation, width, height, mode, kind.value)


def _saved_slide_canvas(presentation: Any) -> tuple[int, int, SlideSizeType]:
    from .package_parts import open_package_source
    from .presentation import Presentation

    if not isinstance(presentation, Presentation):
        raise SlideSizeScalingRefusal("target must be a Presentation")
    try:
        with open_package_source(presentation._source_path) as package:
            root = _page_presentation_root(
                package.read(presentation_partname(presentation._source_path))
            )
        element = _unique_page_size_element(root, "sldSz")
        if element is None:
            raise SlideSizeScalingRefusal("saved presentation has no sldSz")
        size = _page_size_values(element, "sldSz")
        kind = SlideSizeType(element.get("type", "custom"))
        return (
            _dimension(size["cx"], "saved slide width"),
            _dimension(size["cy"], "saved slide height"),
            kind,
        )
    except (PresentationSizeRefusal, ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        raise SlideSizeScalingRefusal(f"unsupported saved slide canvas: {exc}") from exc


def slide_size_type(presentation: Any) -> SlideSizeType:
    """Read the saved size type, without inferring a preset from dimensions."""
    return _saved_slide_canvas(presentation)[2]


def slide_orientation(presentation: Any) -> SlideOrientation:
    """Read saved canvas orientation; a square canvas is landscape."""
    cx, cy, _kind = _saved_slide_canvas(presentation)
    return SlideOrientation.LANDSCAPE if cx >= cy else SlideOrientation.PORTRAIT


def set_slide_orientation(
    presentation: Any, orientation: SlideOrientation | str, *, mode: str = "fit"
) -> None:
    """Swap saved canvas axes when needed, preserving its type and notes canvas.

    Content follows the existing fit/maximize/stretch policy, not a rotation.
    Save pending edits first and reacquire shapes after the atomic rewrite.
    """
    if not isinstance(orientation, str):
        raise SlideSizeScalingRefusal("orientation must be landscape or portrait")
    try:
        requested = SlideOrientation(orientation)
    except ValueError as exc:
        raise SlideSizeScalingRefusal("orientation must be landscape or portrait") from exc
    from .presentation import Presentation

    if not isinstance(presentation, Presentation):
        raise SlideSizeScalingRefusal("target must be a Presentation")
    with presentation._mutation_lock:
        cx, cy, kind = _saved_slide_canvas(presentation)
        current = SlideOrientation.LANDSCAPE if cx >= cy else SlideOrientation.PORTRAIT
        if requested != current:
            cx, cy = cy, cx
        _resize(presentation, cx, cy, mode, kind.value)


def resize_slide_size(presentation: Any, width: Any, height: Any, *, mode: str = "fit") -> None:
    """Resize saved slides/layouts/masters; custom dimensions use size type custom.

    Fit preserves aspect ratio and centers content inside the canvas. Maximize
    preserves aspect ratio and fills the canvas with centered overflow cropped
    at its edges. Stretch changes each axis separately and scales fonts by the
    vertical factor. Notes canvas and notes shapes are not changed.
    Charts, diagrams, embedded objects, media playback,
    custom geometry, animation, advanced effects, and unsupported extensions are
    named refusals, not silent partial resizes. Unstyled tables with explicit
    font sizes are supported. Shared table styles and grouped tables are refused.
    """
    _resize(presentation, width, height, mode, "custom")


def _dimension(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise SlideSizeScalingRefusal(f"{name} must be an integral EMU value")
    result = int(value)
    if not MIN_SLIDE_SIZE_EMU <= result <= MAX_SLIDE_SIZE_EMU:
        raise SlideSizeScalingRefusal(f"{name} is outside the slide dimension range")
    return result


def _resize(presentation: Any, width: Any, height: Any, mode: str, kind: str) -> None:
    from .presentation import Presentation

    if not isinstance(presentation, Presentation):
        raise SlideSizeScalingRefusal("target must be a Presentation")
    cx, cy = _dimension(width, "slide width"), _dimension(height, "slide height")
    if not isinstance(mode, str) or mode not in {"fit", "maximize", "stretch"}:
        raise SlideSizeScalingRefusal("resize mode must be 'fit', 'maximize' or 'stretch'")
    with presentation._mutation_lock:
        try:
            presentation._require_saved_package("resizing slide content")
        except (ValueError, RuntimeError) as exc:
            raise SlideSizeScalingRefusal(str(exc)) from exc
        main_part = presentation_partname(presentation._source_path)

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            return _resize_plan(package, main_part, cx, cy, mode, kind), set(), None

        presentation._rewrite_package("resizing slide content", plan)


@dataclass(frozen=True)
class _Scale:
    x: Fraction
    y: Fraction
    dx: Fraction
    dy: Fraction

    @property
    def anisotropic(self) -> bool:
        return self.x != self.y


def _resize_plan(
    package: Any, main_part: str, cx: int, cy: int, mode: str, kind: str
) -> dict[str, bytes]:
    main_source = _read_part(package, main_part)
    try:
        main_root = _page_presentation_root(main_source)
        size = _unique_page_size_element(main_root, "sldSz")
        if size is None:
            raise SlideSizeScalingRefusal("saved presentation has no sldSz")
        previous = _page_size_values(size, "sldSz")
    except PresentationSizeRefusal as exc:
        raise SlideSizeScalingRefusal(str(exc)) from exc
    old_cx, old_cy = previous["cx"], previous["cy"]
    _dimension(old_cx, "saved slide width")
    _dimension(old_cy, "saved slide height")
    if (cx, cy) == (old_cx, old_cy):
        if size.get("type") == kind:
            return {}
        size.set("type", kind)
        return {main_part: serialize_xml_preserving_namespaces(main_root, main_source)}
    sx, sy = Fraction(cx, old_cx), Fraction(cy, old_cy)
    if mode == "fit":
        sx = sy = min(sx, sy)
    elif mode == "maximize":
        sx = sy = max(sx, sy)
    scale = _Scale(sx, sy, (cx - old_cx * sx) / 2, (cy - old_cy * sy) / 2)
    roots, sources, relations = _content_graph(package, main_part, main_root)
    themes = _themes_by_part(package, roots, relations)
    replacements: dict[str, bytes] = {}
    original_trees = {part: ET.tostring(root) for part, root in roots.items()}
    _materialize_body_dimensions(roots, relations)
    for part, root in roots.items():
        _preflight_xml(root, scale, part)
        theme = themes.get(part)
        tree = find_ooxml(root, f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if tree is None:
            raise SlideSizeScalingRefusal(f"{part}: shape tree is unavailable")
        _preflight_root_frame(tree, part)
        _scale_shapes(tree, scale, theme, part, grouped=False)
        _scale_text_and_effects(root, scale, part)
        # Empty content parts and unmodified styles remain exact ZIP payloads.
        if ET.tostring(root) != original_trees[part]:
            replacements[part] = serialize_xml_preserving_namespaces(root, sources[part])
    _preflight_xml(main_root, scale, main_part)
    _ensure_default_text_style(main_root)
    default_style = find_ooxml(main_root, f"{{{P_NS}}}defaultTextStyle")
    if default_style is not None:
        _scale_text_and_effects(default_style, scale, main_part)
    size.set("cx", str(cx))
    size.set("cy", str(cy))
    size.set("type", kind)
    replacements[main_part] = serialize_xml_preserving_namespaces(main_root, main_source)
    return replacements


def _read_part(package: Any, part: str) -> bytes:
    try:
        return package.read(part)
    except KeyError as exc:
        raise SlideSizeScalingRefusal(f"required package part is unavailable: {part}") from exc


def _xml_root(source: bytes, part: str) -> ET.Element:
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        return ET.fromstring(source, parser=parser)
    except ET.ParseError as exc:
        raise SlideSizeScalingRefusal(f"{part}: XML is malformed") from exc


def _relationships(package: Any, part: str) -> dict[str, tuple[str, str]]:
    rels_part = rels_part_for_package_part(part)
    if rels_part not in package.namelist():
        return {}
    root = _xml_root(package.read(rels_part), rels_part)
    if root.tag != f"{{{_REL_NS}}}Relationships":
        raise SlideSizeScalingRefusal(f"{rels_part}: unsupported relationship XML")
    result = {}
    ids = set()
    for rel in root:
        if not isinstance(rel.tag, str):
            continue
        if rel.tag != f"{{{_REL_NS}}}Relationship":
            raise SlideSizeScalingRefusal(f"{rels_part}: unsupported relationship record")
        identifier = rel.get("Id", "")
        if not identifier or identifier in ids:
            raise SlideSizeScalingRefusal(f"{rels_part}: ambiguous relationship identity")
        ids.add(identifier)
        raw_type = rel.get("Type", "")
        role = next((raw_type[len(base) :] for base in _REL_BASES if raw_type.startswith(base)), "")
        if role not in {"slide", "slideLayout", "slideMaster", "theme", "themeOverride"}:
            continue
        if rel.get("TargetMode", "Internal") != "Internal":
            raise SlideSizeScalingRefusal(f"{part}: external {role} is unsupported")
        target = rel.get("Target", "")
        if not target or "\\" in target or "?" in target or "#" in target:
            raise SlideSizeScalingRefusal(f"{part}: unsupported {role} target")
        resolved = resolve_package_target(part, target)
        if resolved.startswith("../") or resolved.startswith("/"):
            raise SlideSizeScalingRefusal(f"{part}: {role} escapes the package")
        result[identifier] = role, resolved
    return result


def _content_graph(
    package: Any, main_part: str, main_root: ET.Element
) -> tuple[dict[str, ET.Element], dict[str, bytes], dict[str, dict[str, tuple[str, str]]]]:
    roots: dict[str, ET.Element] = {}
    sources: dict[str, bytes] = {}
    relations = {main_part: _relationships(package, main_part)}
    expected_namespace = ooxml_namespace(main_root, P_NS)
    queue = [
        (role, part)
        for role, part in relations[main_part].values()
        if role in {"slide", "slideMaster"}
    ]
    expected_roles: dict[str, str] = {}
    while queue:
        role, part = queue.pop()
        if part in expected_roles:
            if expected_roles[part] != role:
                raise SlideSizeScalingRefusal(f"{part}: ambiguous content role")
            continue
        expected_roles[part] = role
        source = _read_part(package, part)
        root = _xml_root(source, part)
        tag = {"slide": "sld", "slideLayout": "sldLayout", "slideMaster": "sldMaster"}[role]
        if root.tag != f"{{{expected_namespace}}}{tag}":
            raise SlideSizeScalingRefusal(f"{part}: mixed or unsupported content namespace")
        roots[part], sources[part] = root, source
        relations[part] = _relationships(package, part)
        for child_role, child_part in relations[part].values():
            if child_role in {"slideLayout", "slideMaster"}:
                queue.append((child_role, child_part))
    return roots, sources, relations


def _themes_by_part(
    package: Any,
    roots: dict[str, ET.Element],
    relations: dict[str, dict[str, tuple[str, str]]],
) -> dict[str, ET.Element]:
    theme_roots: dict[str, ET.Element] = {}
    result: dict[str, ET.Element] = {}

    def resolve(part: str, visiting: set[str]) -> ET.Element | None:
        if part in result:
            return result[part]
        if part in visiting:
            return None
        visiting = visiting | {part}
        links = list(relations[part].values())
        if any(role == "themeOverride" for role, _target in links):
            raise SlideSizeScalingRefusal(f"{part}: theme overrides are unsupported")
        theme_parts = [target for role, target in links if role == "theme"]
        if len(theme_parts) > 1:
            raise SlideSizeScalingRefusal(f"{part}: ambiguous theme")
        if theme_parts:
            target = theme_parts[0]
            if target not in theme_roots:
                root = _xml_root(_read_part(package, target), target)
                a_ns = ooxml_namespace(roots[part], A_NS)
                if root.tag != f"{{{a_ns}}}theme":
                    raise SlideSizeScalingRefusal(f"{target}: unsupported theme namespace")
                defaults = find_ooxml(root, f"{{{A_NS}}}objectDefaults")
                if defaults is not None:
                    for node in defaults.iter():
                        if isinstance(node.tag, str) and any(
                            key in node.attrib
                            for key in (
                                "sz",
                                "spc",
                                "kern",
                                "marL",
                                "marR",
                                "indent",
                                "defTabSz",
                                "lIns",
                                "rIns",
                                "tIns",
                                "bIns",
                                "spcCol",
                                "w",
                                "h",
                                "blurRad",
                                "rad",
                                "dist",
                            )
                        ):
                            raise SlideSizeScalingRefusal(
                                f"{target}: dimensional theme object defaults are unsupported"
                            )
                theme_roots[target] = root
            result[part] = theme_roots[target]
            return result[part]
        parents = [target for role, target in links if role in {"slideLayout", "slideMaster"}]
        if len(parents) > 1 and roots[part].tag.endswith("}sld"):
            raise SlideSizeScalingRefusal(f"{part}: ambiguous slide layout")
        for parent in parents:
            if parent in roots:
                theme = resolve(parent, visiting)
                if theme is not None:
                    result[part] = theme
                    return theme
        return None

    for part in roots:
        resolve(part, set())
    return result


def _preflight_xml(root: ET.Element, scale: _Scale, part: str) -> None:
    p_ns, a_ns = ooxml_namespace(root, P_NS), ooxml_namespace(root, A_NS)
    unsupported_p = {"timing", "oleObj", "control", "contentPart", "videoFile", "audioFile"}
    unsupported_a = {
        "custGeom",
        "scene3d",
        "sp3d",
        "cell3D",
        "effectDag",
        "tile",
        "audioFile",
        "videoFile",
        "wavAudioFile",
        "quickTimeFile",
        "buBlip",
        "prstTxWarp",
    }
    supported_namespaces = {p_ns, a_ns}
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        namespace, _, local = (
            node.tag[1:].partition("}") if node.tag.startswith("{") else ("", "", node.tag)
        )
        if namespace == _MC_NS and local == "AlternateContent":
            raise SlideSizeScalingRefusal(f"{part}: AlternateContent cannot be scaled safely")
        if (
            namespace in {P_NS, STRICT_P_NS, A_NS, STRICT_A_NS}
            and namespace not in supported_namespaces
        ):
            raise SlideSizeScalingRefusal(f"{part}: mixed DrawingML profile")
        if namespace == p_ns and local in unsupported_p:
            raise SlideSizeScalingRefusal(f"{part}: unsupported {local}")
        if namespace == a_ns and local in unsupported_a:
            if local == "prstTxWarp" and node.get("prst", "textNoShape") == "textNoShape":
                continue
            raise SlideSizeScalingRefusal(f"{part}: unsupported {local}")
        if (
            namespace not in supported_namespaces
            and namespace != _MC_NS
            and local not in _SAFE_EXTENSIONS
        ):
            raise SlideSizeScalingRefusal(f"{part}: unsupported extension {local}")
        if local in {"xfrm", "bodyPr"} and namespace in supported_namespaces:
            rotation = _integer(node, "rot", part, default=0)
            if scale.anisotropic and rotation % 21600000:
                raise SlideSizeScalingRefusal(
                    f"{part}: anisotropic resize of rotated content is unsupported"
                )
            if local == "xfrm":
                _validate_transform(node, part)
            if local == "bodyPr" and scale.anisotropic and node.get("vert", "horz") != "horz":
                raise SlideSizeScalingRefusal(
                    f"{part}: anisotropic resize of vertical text is unsupported"
                )
        if namespace == a_ns and local == "graphicData":
            table_uris = {
                "http://schemas.openxmlformats.org/drawingml/2006/table",
                "http://purl.oclc.org/ooxml/drawingml/table",
            }
            if node.get("uri") not in table_uris:
                raise SlideSizeScalingRefusal(f"{part}: unsupported graphic frame content")


def _preflight_root_frame(tree: ET.Element, part: str) -> None:
    transform = find_ooxml(tree, f"{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm")
    if transform is None:
        return
    if _integer(transform, "rot", part, default=0) % 21600000 or any(
        transform.get(key, "0") not in {"0", "false"} for key in ("flipH", "flipV")
    ):
        raise SlideSizeScalingRefusal(f"{part}: transformed root shape tree is unsupported")
    for child in transform:
        if isinstance(child.tag, str) and any(
            _integer(child, key, part) != 0 for key in child.attrib
        ):
            raise SlideSizeScalingRefusal(f"{part}: nonzero root coordinate frame is unsupported")


def _scale_shapes(
    container: ET.Element, scale: _Scale, theme: ET.Element | None, part: str, *, grouped: bool
) -> None:
    p_ns = ooxml_namespace(container, P_NS)
    for shape in container:
        if not isinstance(shape.tag, str):
            continue
        local = shape.tag.rsplit("}", 1)[-1]
        if shape.tag not in {f"{{{p_ns}}}{name}" for name in _SHAPES}:
            if local not in {"nvGrpSpPr", "grpSpPr", "extLst"}:
                raise SlideSizeScalingRefusal(f"{part}: unsupported shape-tree child {local}")
            continue
        if local == "graphicFrame":
            if grouped:
                raise SlideSizeScalingRefusal(f"{part}: grouped table grids are unsupported")
            transform = find_ooxml(shape, f"{{{P_NS}}}xfrm")
            _scale_table(shape, scale, part)
        else:
            properties_name = "grpSpPr" if local == "grpSp" else "spPr"
            properties = find_ooxml(shape, f"{{{P_NS}}}{properties_name}")
            transform = (
                find_ooxml(properties, f"{{{A_NS}}}xfrm") if properties is not None else None
            )
            if properties is not None and local != "grpSp":
                _materialize_theme_styles(shape, properties, theme, scale, part)
        if grouped and find_ooxml(shape, f".//{{{P_NS}}}ph") is not None:
            raise SlideSizeScalingRefusal(f"{part}: grouped placeholder inheritance is unsupported")
        if transform is None:
            placeholder = find_ooxml(shape, f".//{{{P_NS}}}ph")
            if (placeholder is None or grouped) and (
                local != "grpSp"
                or any(
                    isinstance(child.tag, str) and child.tag.rsplit("}", 1)[-1] in _SHAPES
                    for child in shape
                )
            ):
                raise SlideSizeScalingRefusal(f"{part}: shape lacks an explicit transform")
        elif not grouped:
            _scale_transform(transform, scale, part, group=local == "grpSp")
        if local == "grpSp":
            _validate_group(transform, shape, part)
            _scale_shapes(shape, scale, theme, part, grouped=True)


def _validate_group(transform: ET.Element | None, group: ET.Element, part: str) -> None:
    has_children = any(
        isinstance(child.tag, str) and child.tag.rsplit("}", 1)[-1] in _SHAPES for child in group
    )
    if not has_children:
        return
    if transform is None:
        raise SlideSizeScalingRefusal(f"{part}: group transform is unavailable")
    for name in ("off", "ext", "chOff", "chExt"):
        child = find_ooxml(transform, f"{{{A_NS}}}{name}")
        if child is None:
            raise SlideSizeScalingRefusal(f"{part}: group {name} is unavailable")
        attrs = ("x", "y") if name.endswith("Off") or name == "off" else ("cx", "cy")
        for attr in attrs:
            value = _integer(child, attr, part)
            if name in {"ext", "chExt"} and value <= 0:
                raise SlideSizeScalingRefusal(f"{part}: group coordinate extent is not positive")


def _validate_transform(transform: ET.Element, part: str) -> None:
    a_ns = ooxml_namespace(transform, A_NS)
    seen = set()
    for child in transform:
        if not isinstance(child.tag, str):
            continue
        local = child.tag.rsplit("}", 1)[-1]
        if child.tag not in {f"{{{a_ns}}}{name}" for name in ("off", "ext", "chOff", "chExt")}:
            raise SlideSizeScalingRefusal(f"{part}: unsupported transform field {local}")
        if local in seen:
            raise SlideSizeScalingRefusal(f"{part}: duplicate transform field {local}")
        seen.add(local)
        for key in ("x", "y") if local in {"off", "chOff"} else ("cx", "cy"):
            value = _integer(child, key, part)
            if abs(value) > MAX_PAGE_COORDINATE_EMU or (key in {"cx", "cy"} and value < 0):
                raise SlideSizeScalingRefusal(f"{part}: invalid transform coordinate {key}")


def _scale_transform(transform: ET.Element, scale: _Scale, part: str, *, group: bool) -> None:
    # Child frames deliberately remain in their original group coordinate units.
    # Only the outer frame maps that space onto the resized slide.
    off = find_ooxml(transform, f"{{{A_NS}}}off")
    ext = find_ooxml(transform, f"{{{A_NS}}}ext")
    if off is not None:
        _set_scaled(off, "x", scale.x, part, offset=scale.dx)
        _set_scaled(off, "y", scale.y, part, offset=scale.dy)
    if ext is not None:
        _set_scaled(ext, "cx", scale.x, part, nonnegative=True)
        _set_scaled(ext, "cy", scale.y, part, nonnegative=True)
    if off is None and ext is None:
        raise SlideSizeScalingRefusal(f"{part}: empty shape transform is unsupported")
    if not group and (
        find_ooxml(transform, f"{{{A_NS}}}chOff") is not None
        or find_ooxml(transform, f"{{{A_NS}}}chExt") is not None
    ):
        raise SlideSizeScalingRefusal(f"{part}: child coordinate frame on nongroup shape")


def _scale_table(shape: ET.Element, scale: _Scale, part: str) -> None:
    table = find_ooxml(shape, f"{{{A_NS}}}graphic/{{{A_NS}}}graphicData/{{{A_NS}}}tbl")
    if table is None:
        raise SlideSizeScalingRefusal(f"{part}: only table graphic frames are supported")
    properties = find_ooxml(table, f"{{{A_NS}}}tblPr")
    style_id = find_ooxml(properties, f"{{{A_NS}}}tableStyleId") if properties is not None else None
    if (
        style_id is None
        or (style_id.text or "").strip() != "{00000000-0000-0000-0000-000000000000}"
    ):
        raise SlideSizeScalingRefusal(f"{part}: shared or implicit table styles are unsupported")
    if properties is not None and find_ooxml(properties, f"{{{A_NS}}}tableStyle") is not None:
        raise SlideSizeScalingRefusal(f"{part}: inline table styles are unsupported")
    grid = find_ooxml(table, f"{{{A_NS}}}tblGrid")
    if grid is None:
        raise SlideSizeScalingRefusal(f"{part}: table grid is unavailable")
    for column in grid:
        _set_scaled(column, "w", scale.x, part, positive=True)
    for row in findall_ooxml(table, f"{{{A_NS}}}tr"):
        _set_scaled(row, "h", scale.y, part, positive=True)
        for cell in findall_ooxml(row, f"{{{A_NS}}}tc"):
            properties = find_ooxml(cell, f"{{{A_NS}}}tcPr")
            if properties is None:
                raise SlideSizeScalingRefusal(f"{part}: table cell properties are unavailable")
            for key, default in (
                ("marL", 91440),
                ("marR", 91440),
                ("marT", 45720),
                ("marB", 45720),
            ):
                if key not in properties.attrib:
                    properties.set(key, str(default))
            # Table styles can carry independent point-size defaults. Explicit
            # run sizes avoid guessing or mutating shared table-style parts.
            for paragraph in findall_ooxml(cell, f"{{{A_NS}}}txBody/{{{A_NS}}}p"):
                default = find_ooxml(paragraph, f"{{{A_NS}}}pPr/{{{A_NS}}}defRPr")
                for run in paragraph:
                    if run.tag not in {
                        f"{{{ooxml_namespace(table, A_NS)}}}{name}" for name in ("r", "fld", "br")
                    }:
                        continue
                    properties = find_ooxml(run, f"{{{A_NS}}}rPr")
                    if (properties is None or properties.get("sz") is None) and (
                        default is None or default.get("sz") is None
                    ):
                        raise SlideSizeScalingRefusal(
                            f"{part}: table text needs an explicit font size"
                        )


def _materialize_theme_styles(
    shape: ET.Element,
    properties: ET.Element,
    theme: ET.Element | None,
    scale: _Scale,
    part: str,
) -> None:
    style = find_ooxml(shape, f"{{{P_NS}}}style")
    if style is None:
        return
    a_ns = ooxml_namespace(shape, A_NS)
    for ref_name, list_name, element_names in (
        ("lnRef", "lnStyleLst", ("ln",)),
        ("effectRef", "effectStyleLst", ("effectLst", "effectDag", "scene3d", "sp3d")),
    ):
        reference = find_ooxml(style, f"{{{A_NS}}}{ref_name}")
        if reference is None:
            continue
        index = _integer(reference, "idx", part)
        existing = next(
            (
                node
                for name in element_names
                if (node := find_ooxml(properties, f"{{{A_NS}}}{name}")) is not None
            ),
            None,
        )
        if index == 0 or (
            existing is not None and (ref_name != "lnRef" or existing.get("w") is not None)
        ):
            continue
        if theme is None:
            raise SlideSizeScalingRefusal(f"{part}: referenced theme styles are unavailable")
        styles = find_ooxml(
            theme, f"{{{A_NS}}}themeElements/{{{A_NS}}}fmtScheme/{{{A_NS}}}{list_name}"
        )
        if styles is None or not 1 <= index <= len(styles):
            raise SlideSizeScalingRefusal(f"{part}: unsupported {ref_name} style index")
        selected = styles[index - 1]
        if existing is not None:
            existing.set("w", selected.get("w", "12700"))
            continue
        nodes = [selected] if ref_name == "lnRef" else list(selected)
        color = next((node for node in reference if isinstance(node.tag, str)), None)
        for original in nodes:
            if original.tag not in {f"{{{a_ns}}}{name}" for name in element_names}:
                raise SlideSizeScalingRefusal(f"{part}: unsupported inherited {ref_name} style")
            if original.tag in {f"{{{a_ns}}}effectDag", f"{{{a_ns}}}scene3d", f"{{{a_ns}}}sp3d"}:
                raise SlideSizeScalingRefusal(f"{part}: unsupported inherited advanced effects")
            cloned = deepcopy(original)
            _substitute_style_color(cloned, color, part)
            _preflight_xml(cloned, scale, part)
            _insert_shape_property(properties, cloned)


def _substitute_style_color(root: ET.Element, color: ET.Element | None, part: str) -> None:
    a_ns = ooxml_namespace(root, A_NS)
    for parent in root.iter():
        for index, node in enumerate(list(parent)):
            if node.tag == f"{{{a_ns}}}schemeClr" and node.get("val") == "phClr":
                if color is None:
                    raise SlideSizeScalingRefusal(
                        f"{part}: inherited style placeholder color is unavailable"
                    )
                replacement = deepcopy(color)
                replacement.extend(deepcopy(list(node)))
                parent.remove(node)
                parent.insert(index, replacement)


def _insert_shape_property(properties: ET.Element, node: ET.Element) -> None:
    # CT_ShapeProperties orders geometry, fills, line, effects, then 3D/extensions.
    ranks = {
        "xfrm": 0,
        "prstGeom": 1,
        "custGeom": 1,
        "noFill": 2,
        "solidFill": 2,
        "gradFill": 2,
        "blipFill": 2,
        "pattFill": 2,
        "grpFill": 2,
        "ln": 3,
        "effectLst": 4,
        "effectDag": 4,
        "scene3d": 5,
        "sp3d": 6,
        "extLst": 7,
    }
    rank = ranks[node.tag.rsplit("}", 1)[-1]]
    at = len(properties)
    for index, child in enumerate(properties):
        if isinstance(child.tag, str) and ranks.get(child.tag.rsplit("}", 1)[-1], 8) > rank:
            at = index
            break
    properties.insert(at, node)


def _materialize_body_dimensions(
    roots: dict[str, ET.Element],
    relations: dict[str, dict[str, tuple[str, str]]],
) -> None:
    """Freeze effective placeholder insets before any ancestor is scaled."""
    keys = ("lIns", "rIns", "tIns", "bIns", "spcCol")
    snapshots: dict[int, dict[str, str]] = {}
    bodies: dict[int, ET.Element] = {}
    for root in roots.values():
        for body in findall_ooxml(root, f".//{{{A_NS}}}bodyPr"):
            bodies[id(body)] = body
            snapshots[id(body)] = {key: body.get(key, "") for key in keys if key in body.attrib}
    frozen: dict[int, dict[str, str]] = {}

    def placeholder(shape: ET.Element) -> ET.Element | None:
        return find_ooxml(shape, f".//{{{P_NS}}}ph")

    def candidates(part: str) -> list[ET.Element]:
        tree = find_ooxml(roots[part], f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        return (
            []
            if tree is None
            else [
                shape
                for shape in tree
                if isinstance(shape.tag, str)
                and shape.tag.rsplit("}", 1)[-1]
                in {
                    "sp",
                    "pic",
                    "cxnSp",
                    "graphicFrame",
                }
                and placeholder(shape) is not None
            ]
        )

    def master_kind(kind: str) -> str:
        if kind in {"title", "ctrTitle"}:
            return "title"
        return kind if kind in {"dt", "ftr", "sldNum", "hdr"} else "body"

    def inherited_shape(part: str, shape: ET.Element) -> tuple[str, ET.Element] | None:
        ph = placeholder(shape)
        if ph is None:
            return None
        role = "slideLayout" if roots[part].tag.endswith("}sld") else "slideMaster"
        if roots[part].tag.endswith("}sldMaster"):
            return None
        parents = [
            target
            for relation_role, target in relations[part].values()
            if relation_role == role and target in roots
        ]
        if len(parents) > 1:
            raise SlideSizeScalingRefusal(f"{part}: ambiguous placeholder parent")
        if not parents:
            return None
        parent = parents[0]
        kind, index = ph.get("type", "obj"), ph.get("idx", "0")
        matches = []
        if role == "slideLayout":
            for candidate in candidates(parent):
                candidate_ph = placeholder(candidate)
                assert candidate_ph is not None
                candidate_kind = candidate_ph.get("type", "obj")
                compatible = (
                    candidate_kind == kind
                    or kind == "obj"
                    or candidate_kind == "obj"
                    or (candidate_kind == "body" and kind not in {"title", "ctrTitle"})
                )
                if candidate_ph.get("idx", "0") == index and compatible:
                    matches.append(candidate)
            if not matches:
                matches = [
                    candidate
                    for candidate in candidates(parent)
                    if placeholder(candidate).get("type", "obj") == kind
                ]
        else:
            matches = [
                candidate
                for candidate in candidates(parent)
                if master_kind(placeholder(candidate).get("type", "obj")) == master_kind(kind)
            ]
        if len(matches) > 1:
            raise SlideSizeScalingRefusal(f"{part}: ambiguous placeholder body inheritance")
        return (parent, matches[0]) if matches else None

    def effective(part: str, shape: ET.Element, visiting: set[int]) -> dict[str, str]:
        if id(shape) in visiting:
            raise SlideSizeScalingRefusal(f"{part}: cyclic placeholder inheritance")
        result: dict[str, str] = {}
        inherited = inherited_shape(part, shape)
        if inherited is not None:
            result.update(effective(*inherited, visiting | {id(shape)}))
        body = find_ooxml(shape, f"{{{P_NS}}}txBody/{{{A_NS}}}bodyPr")
        if body is not None:
            result.update(snapshots[id(body)])
        return result

    for part, root in roots.items():
        for shape in root.iter():
            if not isinstance(shape.tag, str) or shape.tag not in {
                f"{{{ooxml_namespace(root, P_NS)}}}{name}" for name in ("sp", "pic", "cxnSp")
            }:
                continue
            body = find_ooxml(shape, f"{{{P_NS}}}txBody/{{{A_NS}}}bodyPr")
            if body is not None:
                frozen[id(body)] = effective(part, shape, set())
    for identifier, values in frozen.items():
        body = bodies[identifier]
        for key, value in values.items():
            if key not in body.attrib:
                body.set(key, value)


def _ensure_default_text_style(root: ET.Element) -> None:
    # An absent size falls back to the engine's ordinary text size. Materialize
    # that fallback at the bottom of inheritance, never on individual runs.
    a_ns, p_ns = ooxml_namespace(root, A_NS), ooxml_namespace(root, P_NS)
    style = find_ooxml(root, f"{{{P_NS}}}defaultTextStyle")
    if style is None:
        style = ET.Element(f"{{{p_ns}}}defaultTextStyle")
        at = next(
            (
                index
                for index, child in enumerate(root)
                if child.tag in {f"{{{p_ns}}}modifyVerifier", f"{{{p_ns}}}extLst"}
            ),
            len(root),
        )
        root.insert(at, style)
    paragraph = find_ooxml(style, f"{{{A_NS}}}defPPr")
    if paragraph is None:
        paragraph = ET.Element(f"{{{a_ns}}}defPPr")
        style.insert(0, paragraph)
    if paragraph.get("defTabSz") is None:
        paragraph.set("defTabSz", "914400")
    properties = find_ooxml(paragraph, f"{{{A_NS}}}defRPr")
    if properties is None:
        properties = ET.Element(f"{{{a_ns}}}defRPr")
        at = next(
            (index for index, child in enumerate(paragraph) if child.tag == f"{{{a_ns}}}extLst"),
            len(paragraph),
        )
        paragraph.insert(at, properties)
    if properties.get("sz") is None:
        properties.set("sz", "1800")


def _scale_text_and_effects(root: ET.Element, scale: _Scale, part: str) -> None:
    a_ns = ooxml_namespace(root, A_NS)
    for node in root.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith(f"{{{a_ns}}}"):
            continue
        local = node.tag.rsplit("}", 1)[-1]
        if local == "bodyPr":
            for key, default in (
                ("lIns", 91440),
                ("rIns", 91440),
                ("tIns", 45720),
                ("bIns", 45720),
            ):
                if key not in node.attrib:
                    node.set(key, str(default))
            for key in ("lIns", "rIns", "spcCol"):
                _optional_scale(node, key, scale.x, part)
            for key in ("tIns", "bIns"):
                _optional_scale(node, key, scale.y, part)
        elif local in {"rPr", "defRPr", "endParaRPr"}:
            for key in ("sz", "kern"):
                _optional_scale(node, key, scale.y, part, font=key == "sz")
            _optional_scale(node, "spc", scale.x, part)
        elif local in {"defPPr", "pPr"} or (local.startswith("lvl") and local.endswith("pPr")):
            for key in ("marL", "marR", "indent", "defTabSz"):
                _optional_scale(node, key, scale.x, part)
        elif local == "tab":
            _optional_scale(node, "pos", scale.x, part)
        elif local in {"spcPts", "buSzPts"}:
            _optional_scale(node, "val", scale.y, part)
        elif local == "ln" or local in {"lnL", "lnR", "lnT", "lnB", "lnTlToBr", "lnBlToTr", "uLn"}:
            if "w" not in node.attrib:
                node.set("w", "12700")
            _optional_scale(node, "w", scale.y, part)
        elif local == "tcPr":
            for key in ("marL", "marR"):
                _optional_scale(node, key, scale.x, part)
            for key in ("marT", "marB"):
                _optional_scale(node, key, scale.y, part)
        elif local in {"outerShdw", "innerShdw", "glow", "softEdge", "blur"}:
            for key in ("blurRad", "rad", "dist"):
                _optional_scale(node, key, scale.y, part)
        elif local == "reflection":
            raise SlideSizeScalingRefusal(f"{part}: reflected geometry is unsupported")


def _integer(node: ET.Element, attribute: str, part: str, *, default: int | None = None) -> int:
    raw = node.get(attribute)
    if raw is None:
        if default is not None:
            return default
        raise SlideSizeScalingRefusal(
            f"{part}: missing {attribute} on {node.tag.rsplit('}', 1)[-1]}"
        )
    try:
        return int(raw)
    except ValueError as exc:
        raise SlideSizeScalingRefusal(f"{part}: invalid integral {attribute}") from exc


def _optional_scale(
    node: ET.Element, attribute: str, factor: Fraction, part: str, *, font: bool = False
) -> None:
    if attribute in node.attrib:
        _set_scaled(node, attribute, factor, part, font=font)


def _set_scaled(
    node: ET.Element,
    attribute: str,
    factor: Fraction,
    part: str,
    *,
    offset: Fraction = Fraction(0),
    nonnegative: bool = False,
    positive: bool = False,
    font: bool = False,
) -> None:
    previous = _integer(node, attribute, part)
    if (nonnegative and previous < 0) or (positive and previous <= 0):
        raise SlideSizeScalingRefusal(f"{part}: invalid source {attribute}")
    value = round(previous * factor + offset)
    if abs(value) > MAX_PAGE_COORDINATE_EMU or (positive and value <= 0):
        raise SlideSizeScalingRefusal(f"{part}: scaled {attribute} is outside its coordinate range")
    if previous > 0 and value == 0 and (nonnegative or positive or font):
        raise SlideSizeScalingRefusal(f"{part}: resize collapses a positive {attribute}")
    if font and not 100 <= value <= 400000:
        raise SlideSizeScalingRefusal(f"{part}: scaled font size is outside the text size range")
    _validate_scalar_range(node, attribute, previous, part)
    _validate_scalar_range(node, attribute, value, part)
    node.set(attribute, str(value))


def _validate_scalar_range(node: ET.Element, attribute: str, value: int, part: str) -> None:
    local = node.tag.rsplit("}", 1)[-1]
    bounds: tuple[int, int] | None = None
    if attribute == "sz" and local in {"rPr", "defRPr", "endParaRPr"}:
        bounds = (100, 400000)
    elif attribute == "kern":
        bounds = (0, 400000)
    elif attribute == "spc" and local in {"rPr", "defRPr", "endParaRPr"}:
        bounds = (-400000, 400000)
    elif attribute == "w" and local in {
        "ln",
        "lnL",
        "lnR",
        "lnT",
        "lnB",
        "lnTlToBr",
        "lnBlToTr",
        "uLn",
    }:
        bounds = (0, 20116800)
    elif local == "spcPts" and attribute == "val":
        bounds = (0, 158400)
    elif local == "buSzPts" and attribute == "val":
        bounds = (100, 400000)
    elif (
        attribute in {"lIns", "rIns", "tIns", "bIns", "spcCol", "pos"}
        or local == "tcPr"
        and attribute in {"marL", "marR", "marT", "marB"}
    ):
        bounds = (-2147483648, 2147483647)
    elif attribute in {"marL", "marR", "indent"}:
        bounds = (-51206400 if attribute == "indent" else 0, 51206400)
    elif attribute == "defTabSz" or local == "blur" and attribute == "rad":
        bounds = (0, 2147483647)
    if bounds is not None and not bounds[0] <= value <= bounds[1]:
        raise SlideSizeScalingRefusal(f"{part}: {local} {attribute} is outside its scalar range")
