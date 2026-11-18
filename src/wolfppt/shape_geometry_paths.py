"""Saved-deck text warp authoring for ECMA-376 preset text warps.

Import this module directly; it adds no properties to the shape facade. The
supported presets are the affine ``textPlain``, ``textSlantUp`` and
``textSlantDown``; the two-path envelope presets in ``TEXT_WARP_ENVELOPES``
(``textTriangle``, ``textChevron``, ``textStop``, ``textFade*``, ``textInflate*``,
``textDeflate*``, ``textCurveUp``/``Down``, ``textCascadeUp``/``Down`` and their
inverted forms); and ``textNoShape``, an explicit normal-text declaration.
``None`` removes the declaration altogether. Arch, circle, ring, button, can,
wave and multi-band presets are refused by name, never approximated.

Reads describe the saved XML, not queued facade edits or inherited formatting.
Save pending facade edits before writing. Writes use the guarded, atomic package
rewrite and rebase lifecycle, and change only the warp's byte slice. Insertion
into a self-closing body-properties tag necessarily expands that tag. All other
slide bytes, including unrelated body properties and children, remain untouched.
Saved slide shapes and connectors with text bodies, including group children,
are supported in both Strict and Transitional namespace profiles.

Warps require horizontal, unrotated, single-column text without WordArt,
upright text, equations or effective bullets. These combinations and malformed,
extended or unsupported existing warp declarations raise ``TextWarpError`` even
when the caller requests replacement or removal. Normal ``textNoShape`` text
retains the renderer's ordinary text admission rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET
from xml.parsers.expat import ExpatError

from .package_parts import open_package_source
from .presentation_save_state import _element_spans, _tag_end
from .shape_xml import _shape_xml_element
from .xml_helpers import A_NS, P_NS, STRICT_A_NS, STRICT_P_NS, ooxml_namespace

if TYPE_CHECKING:
    from .shape_core_facade import Shape

__all__ = [
    "TEXT_WARP_ENVELOPES",
    "TextWarp",
    "TextWarpEnvelope",
    "TextWarpError",
    "validate_text_warp",
    "parse_text_warp",
    "read_text_warp",
    "write_text_warp",
]


class TextWarpError(ValueError):
    """Invalid input, unsupported saved warp or unsafe authoring lifecycle."""


@dataclass(frozen=True)
class TextWarp:
    """One supported preset and its optional ``adj`` guide value.

    ``textPlain`` permits 30000..70000 (default 50000); ``textSlantUp`` permits
    0..71431 (default 55555); ``textSlantDown`` permits 28569..100000 (default
    44445). Envelope presets permit their ``TEXT_WARP_ENVELOPES`` pin range.
    Values are integer DrawingML adjustment units, not degrees or EMU. ``None``
    leaves the preset's default implicit in XML. ``textNoShape`` takes no
    adjustment. Construction is inert; public operations validate the model.
    """

    preset: str
    adjustment: int | None = None


@dataclass(frozen=True)
class TextWarpEnvelope:
    """One two-path envelope preset: its ``adj`` pin range, default and formulas.

    ``guides`` are the preset's ``gdLst`` formulas in order (``pin``, ``*/`` and
    ``+-`` over the shape guides ``l t r b w h hc vc ss wd3``); ``paths`` are the
    top and bottom envelope edges as ``M``/``L``/``Q``/``C`` point commands.
    Text ink fills the band between them, interpolated by horizontal position.
    """

    low: int
    high: int
    default: int
    guides: tuple[tuple[str, str], ...]
    paths: tuple[str, str]


#: Two-path envelope presets, transcribed from ECMA-376 Part 1
#: presetTextWarpDefinitions.xml (sha256
#: 89640bd4aeedfa2c578d1d1acc50d569865ebdef315fd4b468087c25e36acada).
TEXT_WARP_ENVELOPES: dict[str, TextWarpEnvelope] = {
    "textCascadeDown": TextWarpEnvelope(
        28570,
        100000,
        44444,
        (
            ("a", "pin 28570 adj 100000"),
            ("dy", "*/ a h 100000"),
            ("y1", "+- t dy 0"),
            ("dy2", "+- h 0 dy"),
            ("dy3", "*/ dy2 1 4"),
            ("y2", "+- t dy3 0"),
        ),
        ("M l t L r y2", "M l y1 L r b"),
    ),
    "textCascadeUp": TextWarpEnvelope(
        28570,
        100000,
        44444,
        (
            ("a", "pin 28570 adj 100000"),
            ("dy", "*/ a h 100000"),
            ("y1", "+- t dy 0"),
            ("dy2", "+- h 0 dy"),
            ("dy3", "*/ dy2 1 4"),
            ("y2", "+- t dy3 0"),
        ),
        ("M l y2 L r t", "M l b L r y1"),
    ),
    "textChevron": TextWarpEnvelope(
        0,
        50000,
        25000,
        (
            ("a", "pin 0 adj 50000"),
            ("y", "*/ a h 100000"),
            ("y1", "+- t b y"),
        ),
        ("M l y L hc t L r y", "M l b L hc y1 L r b"),
    ),
    "textChevronInverted": TextWarpEnvelope(
        50000,
        100000,
        75000,
        (
            ("a", "pin 50000 adj 100000"),
            ("y", "*/ a h 100000"),
            ("y1", "+- b 0 y"),
        ),
        ("M l t L hc y1 L r t", "M l y L hc b L r y"),
    ),
    "textCurveDown": TextWarpEnvelope(
        0,
        56338,
        45977,
        (
            ("a", "pin 0 adj 56338"),
            ("dy", "*/ a h 100000"),
            ("gd1", "*/ dy 3 4"),
            ("gd2", "*/ dy 5 4"),
            ("gd3", "*/ dy 3 8"),
            ("gd4", "*/ dy 1 8"),
            ("gd5", "+- h 0 gd3"),
            ("gd6", "+- gd4 h 0"),
            ("y0", "+- t dy 0"),
            ("y1", "+- t gd1 0"),
            ("y2", "+- t gd2 0"),
            ("y3", "+- t gd3 0"),
            ("y4", "+- t gd4 0"),
            ("y5", "+- t gd5 0"),
            ("y6", "+- t gd6 0"),
            ("x1", "+- l wd3 0"),
            ("x2", "+- r 0 wd3"),
        ),
        ("M l t C x1 y1 x2 y2 r y0", "M l y5 C x1 y6 x2 y6 r y5"),
    ),
    "textCurveUp": TextWarpEnvelope(
        0,
        56338,
        45977,
        (
            ("a", "pin 0 adj 56338"),
            ("dy", "*/ a h 100000"),
            ("gd1", "*/ dy 3 4"),
            ("gd2", "*/ dy 5 4"),
            ("gd3", "*/ dy 3 8"),
            ("gd4", "*/ dy 1 8"),
            ("gd5", "+- h 0 gd3"),
            ("gd6", "+- gd4 h 0"),
            ("y0", "+- t dy 0"),
            ("y1", "+- t gd1 0"),
            ("y2", "+- t gd2 0"),
            ("y3", "+- t gd3 0"),
            ("y4", "+- t gd4 0"),
            ("y5", "+- t gd5 0"),
            ("y6", "+- t gd6 0"),
            ("x1", "+- l wd3 0"),
            ("x2", "+- r 0 wd3"),
        ),
        ("M l y0 C x1 y2 x2 y1 r t", "M l y5 C x1 y6 x2 y6 r y5"),
    ),
    "textDeflate": TextWarpEnvelope(
        0,
        37500,
        18750,
        (
            ("a", "pin 0 adj 37500"),
            ("dy", "*/ a ss 100000"),
            ("gd0", "*/ dy 4 3"),
            ("gd1", "+- h 0 gd0"),
            ("adjY", "+- t dy 0"),
            ("y0", "+- t gd0 0"),
            ("y1", "+- t gd1 0"),
            ("x0", "+- l wd3 0"),
            ("x1", "+- r 0 wd3"),
        ),
        ("M l t C x0 y0 x1 y0 r t", "M l b C x0 y1 x1 y1 r b"),
    ),
    "textDeflateBottom": TextWarpEnvelope(
        6250,
        100000,
        50000,
        (
            ("a", "pin 6250 adj 100000"),
            ("dy", "*/ a ss 100000"),
            ("dy2", "+- h 0 dy"),
            ("y1", "+- t dy 0"),
            ("cp", "+- y1 0 dy2"),
        ),
        ("M l t L r t", "M l b Q hc cp r b"),
    ),
    "textDeflateTop": TextWarpEnvelope(
        0,
        93750,
        50000,
        (
            ("a", "pin 0 adj 93750"),
            ("dy", "*/ a h 100000"),
            ("y1", "+- t dy 0"),
            ("cp", "+- y1 dy 0"),
        ),
        ("M l t Q hc cp r t", "M l b L r b"),
    ),
    "textFadeDown": TextWarpEnvelope(
        0,
        49999,
        33333,
        (
            ("a", "pin 0 adj 49999"),
            ("dx", "*/ a w 100000"),
            ("x1", "+- l dx 0"),
            ("x2", "+- r 0 dx"),
        ),
        ("M l t L r t", "M x1 b L x2 b"),
    ),
    "textFadeLeft": TextWarpEnvelope(
        0,
        49999,
        33333,
        (
            ("a", "pin 0 adj 49999"),
            ("dy", "*/ a h 100000"),
            ("y1", "+- t dy 0"),
            ("y2", "+- b 0 dy"),
        ),
        ("M l y1 L r t", "M l y2 L r b"),
    ),
    "textFadeRight": TextWarpEnvelope(
        0,
        49999,
        33333,
        (
            ("a", "pin 0 adj 49999"),
            ("dy", "*/ a h 100000"),
            ("y1", "+- t dy 0"),
            ("y2", "+- b 0 dy"),
        ),
        ("M l t L r y1", "M l b L r y2"),
    ),
    "textFadeUp": TextWarpEnvelope(
        0,
        49999,
        33333,
        (
            ("a", "pin 0 adj 49999"),
            ("dx", "*/ a w 100000"),
            ("x1", "+- l dx 0"),
            ("x2", "+- r 0 dx"),
        ),
        ("M x1 t L x2 t", "M l b L r b"),
    ),
    "textInflate": TextWarpEnvelope(
        0,
        20000,
        18750,
        (
            ("a", "pin 0 adj 20000"),
            ("dy", "*/ a h 100000"),
            ("gd", "*/ dy 1 3"),
            ("gd0", "+- 0 0 gd"),
            ("gd1", "+- h 0 gd0"),
            ("ty", "+- t dy 0"),
            ("by", "+- b 0 dy"),
            ("y0", "+- t gd0 0"),
            ("y1", "+- t gd1 0"),
            ("x0", "+- l wd3 0"),
            ("x1", "+- r 0 wd3"),
        ),
        ("M l ty C x0 y0 x1 y0 r ty", "M l by C x0 y1 x1 y1 r by"),
    ),
    "textInflateBottom": TextWarpEnvelope(
        60000,
        100000,
        60000,
        (
            ("a", "pin 60000 adj 100000"),
            ("dy", "*/ a h 100000"),
            ("ty", "+- t dy 0"),
        ),
        ("M l t L r t", "M l ty Q hc b r ty"),
    ),
    "textInflateTop": TextWarpEnvelope(
        0,
        50000,
        40000,
        (
            ("a", "pin 0 adj 50000"),
            ("dy", "*/ a h 100000"),
            ("ty", "+- t dy 0"),
        ),
        ("M l ty Q hc t r ty", "M l b L r b"),
    ),
    "textStop": TextWarpEnvelope(
        14286,
        50000,
        25000,
        (
            ("a", "pin 14286 adj 50000"),
            ("dx", "*/ w 1 3"),
            ("dy", "*/ a h 100000"),
            ("x1", "+- l dx 0"),
            ("x2", "+- r 0 dx"),
            ("y1", "+- t dy 0"),
            ("y2", "+- b 0 dy"),
        ),
        ("M l y1 L x1 t L x2 t L r y1", "M l y2 L x1 b L x2 b L r y2"),
    ),
    "textTriangle": TextWarpEnvelope(
        0,
        100000,
        50000,
        (
            ("a", "pin 0 adj 100000"),
            ("y", "*/ a h 100000"),
        ),
        ("M l y L hc t L r y", "M l b L r b"),
    ),
    "textTriangleInverted": TextWarpEnvelope(
        0,
        100000,
        50000,
        (
            ("a", "pin 0 adj 100000"),
            ("y", "*/ a h 100000"),
        ),
        ("M l t L r t", "M l y L hc b L r y"),
    ),
}
_AFFINE_LIMITS = {
    "textPlain": (30000, 70000),
    "textSlantUp": (0, 71431),
    "textSlantDown": (28569, 100000),
}
_LIMITS = {
    **_AFFINE_LIMITS,
    **{name: (envelope.low, envelope.high) for name, envelope in TEXT_WARP_ENVELOPES.items()},
}
_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_VALUE_FORMULA = re.compile(r"val[ \t\r\n]+([+-]?[0-9]+)\Z")
_BODY_CHILD_ORDER = {
    "prstTxWarp": 0,
    "noAutofit": 1,
    "normAutofit": 1,
    "spAutoFit": 1,
    "scene3d": 2,
    "sp3d": 3,
    "flatTx": 3,
    "extLst": 4,
}


def validate_text_warp(warp: TextWarp | None) -> TextWarp | None:
    """Validate a complete requested model without mutating a package.

    Return the input unchanged. Booleans, floats, unknown presets, out-of-range
    adjustments and adjustments on ``textNoShape`` raise ``TextWarpError``.
    """
    if warp is None:
        return None
    if not isinstance(warp, TextWarp):
        raise TextWarpError("expected TextWarp or None")
    if not isinstance(warp.preset, str):
        raise TextWarpError("text warp preset must be a string")
    if warp.preset not in _LIMITS and warp.preset != "textNoShape":
        raise TextWarpError(f"unsupported text warp preset {warp.preset!r}")
    adjustment = warp.adjustment
    if warp.preset == "textNoShape":
        if adjustment is not None:
            raise TextWarpError("text warp textNoShape accepts no adjustment")
    elif adjustment is not None:
        if type(adjustment) is not int:
            raise TextWarpError("text warp adjustment must be an integer or None")
        low, high = _LIMITS[warp.preset]
        if not low <= adjustment <= high:
            raise TextWarpError(
                f"text warp {warp.preset} adjustment must be between {low} and {high}"
            )
    return warp


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""


def _empty_text(element: ET.Element, label: str) -> None:
    if element.text is not None and element.text.strip():
        raise TextWarpError(f"{label} has unsupported character content")
    for child in element:
        if child.tail is not None and child.tail.strip():
            raise TextWarpError(f"{label} has unsupported character content")


def _warp_element(body_pr: ET.Element) -> ET.Element | None:
    a_ns = ooxml_namespace(body_pr, A_NS)
    candidates = [child for child in body_pr if _local(child) == "prstTxWarp"]
    if len(candidates) > 1:
        raise TextWarpError("text body has duplicate prstTxWarp declarations")
    if candidates and candidates[0].tag != f"{{{a_ns}}}prstTxWarp":
        raise TextWarpError("text warp uses an unsupported namespace profile")
    return candidates[0] if candidates else None


def _validate_body_order(body_pr: ET.Element) -> None:
    """Refuse ambiguous body child models rather than inserting out of order."""
    a_ns = ooxml_namespace(body_pr, A_NS)
    previous = -1
    seen: set[int] = set()
    for child in body_pr:
        name = _local(child)
        if name not in _BODY_CHILD_ORDER or child.tag != f"{{{a_ns}}}{name}":
            raise TextWarpError(f"text body has unsupported child {name!r}")
        position = _BODY_CHILD_ORDER[name]
        if position < previous or position in seen:
            raise TextWarpError("text body children are duplicated or out of schema order")
        previous = position
        seen.add(position)


def parse_text_warp(bodyPr: ET.Element) -> TextWarp | None:
    """Parse one ``a:bodyPr`` without editing or resolving inheritance.

    Both namespace profiles are supported, but a declaration cannot mix them.
    Only one optional ``a:avLst`` containing one optional ``a:gd`` named ``adj``
    with an integer ``val`` formula is accepted. Explicit defaults remain
    explicit; absent defaults remain ``None``. Duplicate declarations, custom
    guides/formulas, extensions, attributes or presets are named refusals.
    Ordinary body properties without a warp return ``None`` unchanged.
    """
    if not isinstance(bodyPr, ET.Element) or bodyPr.tag not in {
        f"{{{A_NS}}}bodyPr",
        f"{{{STRICT_A_NS}}}bodyPr",
    }:
        raise TextWarpError("expected DrawingML bodyPr in a supported namespace profile")
    warp = _warp_element(bodyPr)
    if warp is None:
        return None
    _validate_body_order(bodyPr)
    _empty_text(warp, "text warp")
    if set(warp.attrib) != {"prst"}:
        raise TextWarpError("text warp requires only the prst attribute")
    preset = warp.get("prst", "")
    validate_text_warp(TextWarp(preset))
    a_ns = ooxml_namespace(bodyPr, A_NS)
    children = list(warp)
    if len(children) > 1 or any(child.tag != f"{{{a_ns}}}avLst" for child in children):
        raise TextWarpError("text warp has unsupported or duplicate adjustment-list children")
    adjustment = None
    if children:
        av_list = children[0]
        _empty_text(av_list, "text warp adjustment list")
        if av_list.attrib:
            raise TextWarpError("text warp adjustment list has unsupported attributes")
        guides = list(av_list)
        if len(guides) > 1 or any(guide.tag != f"{{{a_ns}}}gd" for guide in guides):
            raise TextWarpError("text warp supports only one adj guide without extensions")
        if guides:
            guide = guides[0]
            _empty_text(guide, "text warp adjustment guide")
            if list(guide) or set(guide.attrib) != {"name", "fmla"} or guide.get("name") != "adj":
                raise TextWarpError("text warp supports only the adj value guide")
            formula = _VALUE_FORMULA.fullmatch(guide.get("fmla", "").strip(" \t\r\n"))
            if formula is None:
                raise TextWarpError("text warp adj formula must be 'val INTEGER'")
            try:
                adjustment = int(formula.group(1))
            except ValueError as exc:
                raise TextWarpError("text warp adjustment is not a supported integer") from exc
    return validate_text_warp(TextWarp(preset, adjustment))


def _target(shape: Shape) -> tuple[Any, str, dict[str, Any]]:
    from .shape_core_facade import Shape as ShapeFacade

    if not isinstance(shape, ShapeFacade):
        raise TextWarpError("expected a saved slide Shape")
    payload = getattr(shape, "_payload", None)
    slide = getattr(shape, "_slide", None)
    presentation = getattr(slide, "_presentation", None)
    if (
        not isinstance(payload, dict)
        or slide is None
        or presentation is None
        or not hasattr(presentation, "_rewrite_package")
        or hasattr(shape, "_master")
    ):
        raise TextWarpError("expected a saved slide shape with a text body")
    if getattr(presentation, "_disposed", False):
        raise TextWarpError("presentation is disposed")
    partname = getattr(slide, "partname", None)
    if (
        not partname
        or payload.get("id") is None
        or payload.get("_pending_shape")
        or payload.get("_pending_group_child")
        or getattr(slide, "_payload", {}).get("_pending_creation")
    ):
        raise TextWarpError("save the pending shape and slide before accessing text warp")
    return presentation, str(partname).lstrip("/"), payload


def _source(
    raw: bytes, payload: dict[str, Any]
) -> tuple[ET.Element, ET.Element, ET.Element, list[dict[str, Any]], dict[int, int]]:
    if b"\x00" in raw:
        raise TextWarpError("text warp byte-slice edits require ASCII-compatible XML encoding")
    try:
        root = ET.fromstring(raw)
        spans = _element_spans(raw)
        elements = list(root.iter())
        if len(spans) != len(elements):
            raise TextWarpError("cannot map saved XML elements to source byte slices")
        positions = {id(element): index for index, element in enumerate(elements)}
        shape_element = _shape_xml_element(root, payload)
    except (ET.ParseError, ExpatError, AttributeError, ValueError) as exc:
        if isinstance(exc, TextWarpError):
            raise
        raise TextWarpError("saved shape XML is unavailable or malformed") from exc
    if root.tag not in {f"{{{P_NS}}}sld", f"{{{STRICT_P_NS}}}sld"}:
        raise TextWarpError("saved target part is not a supported slide")
    p_ns = ooxml_namespace(root, P_NS)
    a_ns = ooxml_namespace(root, A_NS)
    identities = [
        node
        for node in root.iter()
        if _local(node) == "cNvPr" and node.get("id") == str(payload["id"])
    ]
    if len(identities) != 1 or identities[0].tag != f"{{{p_ns}}}cNvPr":
        raise TextWarpError("saved shape identity is missing or ambiguous")
    if shape_element.tag not in {f"{{{p_ns}}}sp", f"{{{p_ns}}}cxnSp"}:
        raise TextWarpError("text warp supports only saved shapes and connectors with text bodies")
    bodies = [child for child in shape_element if _local(child) == "txBody"]
    if len(bodies) != 1 or bodies[0].tag != f"{{{p_ns}}}txBody":
        raise TextWarpError("saved shape requires exactly one supported text body")
    text_body = bodies[0]
    properties = [child for child in text_body if _local(child) == "bodyPr"]
    if len(properties) != 1 or properties[0].tag != f"{{{a_ns}}}bodyPr":
        raise TextWarpError("saved text body requires exactly one supported bodyPr")
    body_pr = properties[0]
    if list(text_body)[0] is not body_pr:
        raise TextWarpError("saved text body properties are out of schema order")
    return shape_element, text_body, body_pr, spans, positions


def read_text_warp(shape: Shape) -> TextWarp | None:
    """Read a saved slide shape's warp, or ``None`` if no warp is declared.

    Queued text/formatting edits are not included. Pending targets, disposed
    presentations and unsupported/malformed existing warp models are refused
    with ``TextWarpError``. Readback does not materialize preset defaults.
    """
    presentation, part, payload = _target(shape)
    try:
        with open_package_source(presentation._source_path) as package:
            raw = package.read(part)
    except (KeyError, FileNotFoundError) as exc:
        raise TextWarpError("saved slide part is unavailable") from exc
    _, _, body_pr, _, _ = _source(raw, payload)
    return parse_text_warp(body_pr)


def _body_integer(body_pr: ET.Element, name: str, default: int) -> int:
    raw = body_pr.get(name)
    if raw is None:
        return default
    if _INTEGER.fullmatch(raw.strip(" \t\r\n")) is None:
        raise TextWarpError(f"text warp body property {name} must be an integer")
    try:
        return int(raw)
    except ValueError as exc:
        raise TextWarpError(f"text warp body property {name} is not a supported integer") from exc


def _validate_warp_body(text_body: ET.Element, body_pr: ET.Element) -> None:
    if body_pr.get("vert", "horz") != "horz":
        raise TextWarpError("text warp requires horizontal text")
    if _body_integer(body_pr, "rot", 0) != 0:
        raise TextWarpError("text warp does not support nonzero body rotation")
    if _body_integer(body_pr, "numCol", 1) != 1:
        raise TextWarpError("text warp requires a single text column")
    for name in ("fromWordArt", "upright", "rtlCol"):
        if body_pr.get(name) not in (None, "0", "false"):
            raise TextWarpError(f"text warp does not support body property {name}")
    for child in body_pr:
        if _local(child) not in {"prstTxWarp", "noAutofit", "normAutofit", "spAutoFit"}:
            raise TextWarpError(f"text warp does not support body child {_local(child)!r}")
    for node in text_body.iter():
        if _local(node) in {"m", "oMath", "oMathPara"}:
            raise TextWarpError("text warp does not support equations")


def _validate_effective_bullets(shape: Shape, element: ET.Element, text_body: ET.Element) -> None:
    """Use the existing saved-deck resolver, without measuring or drawing text.

    The resolver lives in commercial modules, reached only through
    ``commercial_module``; the community edition raises ``CommercialFeatureError``.
    """
    from .editions import commercial_module

    feature = "Validating text warp formatting"
    effective = commercial_module("effective_format", feature)
    readback = commercial_module("effective_format_readback", feature)
    from .render_refusals import RenderRefusal
    from .shape_tree import _placeholder_key
    from .xml_helpers import findall_ooxml

    try:
        deck = readback._SavedDeck(shape._slide._presentation)
        context = deck.slide(shape._slide.partname)
        text_context = deck.builder._text_context(
            element, context, context.slide_part, _placeholder_key(element)
        )
        for paragraph in findall_ooxml(text_body, f"{{{A_NS}}}p"):
            style = effective._effective_paragraph_style(
                paragraph,
                text_body,
                text_context,
                context.scheme,
                level=effective._paragraph_level(paragraph, "text warp paragraph"),
                label="text warp paragraph",
            )
            if not style.bullet_none and any(
                value is not None
                for value in (
                    style.bullet_char,
                    style.bullet_auto,
                    style.bullet_picture,
                )
            ):
                raise TextWarpError("text warp does not support effective paragraph bullets")
    except (RenderRefusal, ValueError, KeyError, AttributeError, ET.ParseError) as exc:
        if isinstance(exc, TextWarpError):
            raise
        raise TextWarpError("cannot admit the saved text's effective warp formatting") from exc


def _warp_xml(warp: TextWarp, a_ns: str) -> bytes:
    opening = f'<a:prstTxWarp xmlns:a="{a_ns}" prst="{warp.preset}">'.encode("ascii")
    guide = (
        b"<a:avLst/>"
        if warp.adjustment is None
        else f'<a:avLst><a:gd name="adj" fmla="val {warp.adjustment}"/></a:avLst>'.encode("ascii")
    )
    return opening + guide + b"</a:prstTxWarp>"


def _rewrite(raw: bytes, shape: Shape, payload: dict[str, Any], wanted: TextWarp | None) -> bytes:
    element, text_body, body_pr, spans, positions = _source(raw, payload)
    current = parse_text_warp(body_pr)
    # Validate the saved model even for removal or an otherwise identical edit.
    active = any(warp is not None and warp.preset != "textNoShape" for warp in (current, wanted))
    if active:
        _validate_warp_body(text_body, body_pr)
        _validate_effective_bullets(shape, element, text_body)
    if current == wanted:
        return raw
    _validate_body_order(body_pr)
    warp_element = _warp_element(body_pr)
    replacement = b"" if wanted is None else _warp_xml(wanted, ooxml_namespace(body_pr, A_NS))
    if warp_element is not None:
        span = spans[positions[id(warp_element)]]
        return raw[: span["start"]] + replacement + raw[span["end"] :]
    span = spans[positions[id(body_pr)]]
    opening_end = _tag_end(raw, span["start"])
    if raw[opening_end - 2 : opening_end] == b"/>":
        opening = raw[span["start"] : opening_end]
        match = re.match(rb"<([^ \t\r\n/>]+)", opening)
        if match is None:
            raise TextWarpError("cannot locate the saved bodyPr qualified name")
        expanded = opening[:-2] + b">" + replacement + b"</" + match.group(1) + b">"
        return raw[: span["start"]] + expanded + raw[span["end"] :]
    children = list(body_pr)
    if children:
        offset = spans[positions[id(children[0])]]["start"]
    else:
        offset = raw.rfind(b"</", opening_end, span["end"])
        if offset < 0:
            raise TextWarpError("cannot locate the saved bodyPr closing tag")
    return raw[:offset] + replacement + raw[offset:]


def write_text_warp(shape: Shape, warp: TextWarp | None) -> None:
    """Atomically replace or remove a saved slide shape's text warp.

    Validate the requested model before entering the rewrite lifecycle, and the
    existing model before generating replacement bytes. Unsupported existing
    declarations cannot be erased by replacement/removal. Save pending facade
    edits first; lifecycle refusals are ``TextWarpError``. Successful writes
    rebase the presentation on the saved result, just like other package-backed
    authoring APIs. Reacquire facade objects after a package rewrite.
    """
    validate_text_warp(warp)
    presentation, part, payload = _target(shape)

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        try:
            raw = package.read(part)
        except KeyError as exc:
            raise TextWarpError("saved slide part is unavailable") from exc
        rewritten = _rewrite(raw, shape, payload, warp)
        return ({part: rewritten} if rewritten != raw else {}), set(), None

    try:
        presentation._rewrite_package("editing text warp", plan)
    except ValueError as exc:
        if isinstance(exc, TextWarpError):
            raise
        raise TextWarpError(str(exc)) from exc
