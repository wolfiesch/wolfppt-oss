"""Typed, package-backed read/edit access to shape DrawingML ``p:style``.

Import this module directly; it does not add properties to ``Shape``. For example::

    from dataclasses import replace
    from wolfppt.shape_style_refs import (
        StyleReference, StyleReferenceColor, read_shape_style_references,
        write_shape_style_references,
    )

    style = read_shape_style_references(shape)
    if style is not None:
        write_shape_style_references(
            shape,
            replace(style, fill_ref=StyleReference(
                1, StyleReferenceColor("scheme", "accent2"),
            )),
        )

Reads describe saved XML, not effective/inherited formatting. Writes replace the
complete set of four references (or remove ``p:style`` with ``None``), stage the
package through ``Presentation._rewrite_package``, and rebase the presentation.
Save queued facade edits first. Shapes, connectors, and pictures on saved slides,
including group children, are supported; groups and graphic frames are not.

RGB and scheme colors are supported, each with an ordered list of DrawingML color
transforms (``StyleColorTransform``: ``lumMod``, ``tint``, ``alpha``, ``comp`` and the
other ECMA-376 transform elements the renderer resolves). Transforms are read back
and written in document order; Strict-profile percentage values keep their ``%`` form.
Other color choices, unknown transforms, extensions, malformed/incomplete styles, and
unsupported targets raise ``StyleReferenceError`` rather than being silently discarded.
Fill indices from 1001 select the theme's background fill list (``bgFillStyleLst``
entry ``index - 1000``), and 1000 selects no background fill.
Unchanged references retain their original bytes; all bytes outside the changed
references/style, and all other ZIP parts, are preserved. Both namespace profiles
are kept in their source form. Explicit shape fill/line formatting still takes
precedence over theme references in the renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from xml.etree import ElementTree as ET
from xml.parsers.expat import ExpatError

from .package_parts import open_package_source
from .presentation_save_state import _element_spans, _tag_end
from .shape_xml import _shape_xml_element
from .xml_helpers import A_NS, P_NS, STRICT_A_NS, find_ooxml, ooxml_namespace

if TYPE_CHECKING:
    from .shape_core_facade import Shape

__all__ = [
    "FontStyleReference",
    "ShapeStyleReferences",
    "StyleColorTransform",
    "StyleReference",
    "StyleReferenceColor",
    "StyleReferenceError",
    "read_shape_style_references",
    "validate_shape_style_references",
    "write_shape_style_references",
]


class StyleReferenceError(ValueError):
    """Invalid input or an unsupported saved shape/style; no package edit occurs."""


#: Transforms with no ``val`` attribute.
_FLAG_TRANSFORMS = frozenset({"comp", "inv", "gray", "gamma", "invGamma"})
#: Valued transforms and their inclusive ECMA-376 domains (``None`` is unbounded).
_VALUED_TRANSFORMS: dict[str, tuple[int | None, int | None]] = {
    "alpha": (0, 100000),
    "alphaMod": (0, None),
    "alphaOff": (-100000, 100000),
    "hue": (0, 21599999),
    "hueMod": (0, None),
    "hueOff": (None, None),
    "sat": (None, None),
    "satMod": (None, None),
    "satOff": (None, None),
    "lum": (None, None),
    "lumMod": (None, None),
    "lumOff": (None, None),
    "red": (None, None),
    "redMod": (None, None),
    "redOff": (None, None),
    "green": (None, None),
    "greenMod": (None, None),
    "greenOff": (None, None),
    "blue": (None, None),
    "blueMod": (None, None),
    "blueOff": (None, None),
    "tint": (0, 100000),
    "shade": (0, 100000),
}
#: Strict-profile transforms whose value is an angle, not a ``%`` percentage.
_STRICT_ANGLE_TRANSFORMS = frozenset({"hue", "hueOff"})


@dataclass(frozen=True)
class StyleColorTransform:
    """One DrawingML color transform: ``name`` and its integer ``value``.

    Percentages use 1000ths of a percent (``lumMod`` 75000 is 75%), angles use
    60000ths of a degree. ``comp``, ``inv``, ``gray``, ``gamma`` and ``invGamma``
    carry no value (``None``).
    """

    name: str
    value: int | None = None


@dataclass(frozen=True)
class StyleReferenceColor:
    """A color: ``rgb`` (RRGGBB or #RRGGBB), or ``scheme``, and its transforms.

    Scheme values are DrawingML tokens: accent1..accent6, bg1, bg2, tx1, tx2,
    dk1, dk2, lt1, lt2, hlink, folHlink, or phClr. RGB is case-insensitive;
    readback uses uppercase hex without a leading hash. ``transforms`` apply in
    order, as DrawingML applies its color transform children.
    """

    kind: Literal["rgb", "scheme"]
    value: str
    transforms: tuple[StyleColorTransform, ...] = ()


@dataclass(frozen=True)
class StyleReference:
    """A fill, line, or effect style-matrix reference and its placeholder color.

    ``index`` is an unsigned 32-bit DrawingML index, not a zero-based Python
    position. Zero selects no style; ordinary entries start at one. Fill indices
    1001 and above select background fill ``index - 1000`` of the theme's
    ``bgFillStyleLst``, and 1000 selects no background fill. Writes check positive
    matrix indices against the slide's effective theme entries.
    """

    index: int
    color: StyleReferenceColor


@dataclass(frozen=True)
class FontStyleReference:
    """``a:fontRef``: major/minor theme fonts or none, and an optional color."""

    index: Literal["major", "minor", "none"]
    color: StyleReferenceColor | None = None


@dataclass(frozen=True)
class ShapeStyleReferences:
    """The complete ``p:style`` model, in DrawingML child order.

    Use ``dataclasses.replace`` to edit individual references without mutating
    the saved/read value. All four references are required when a style exists.
    """

    ln_ref: StyleReference
    fill_ref: StyleReference
    effect_ref: StyleReference
    font_ref: FontStyleReference


_REFERENCES = (
    ("lnRef", "ln_ref"),
    ("fillRef", "fill_ref"),
    ("effectRef", "effect_ref"),
    ("fontRef", "font_ref"),
)
_SCHEME_COLORS = frozenset(
    {
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "bg1",
        "bg2",
        "tx1",
        "tx2",
        "dk1",
        "dk2",
        "lt1",
        "lt2",
        "hlink",
        "folHlink",
        "phClr",
    }
)
_RGB = re.compile(r"#?[0-9a-fA-F]{6}\Z")
_INDEX = re.compile(r"\+?[0-9]+\Z")
_SAVED_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_SAVED_PERCENT = re.compile(r"([+-]?)([0-9]+)(?:\.([0-9]{1,3}))?%\Z")


def _transform_value(transform: StyleColorTransform, label: str) -> int | None:
    if not isinstance(transform, StyleColorTransform):
        raise StyleReferenceError(f"{label} must be a StyleColorTransform")
    name, value = transform.name, transform.value
    if name in _FLAG_TRANSFORMS:
        if value is not None:
            raise StyleReferenceError(f"{label}: {name} takes no value")
        return None
    if name not in _VALUED_TRANSFORMS:
        raise StyleReferenceError(f"{label}: unsupported color transform {name!r}")
    if type(value) is not int or not -(2**31) <= value < 2**31:
        raise StyleReferenceError(f"{label}: {name} needs a signed 32-bit integer value")
    lower, upper = _VALUED_TRANSFORMS[name]
    if (lower is not None and value < lower) or (upper is not None and value > upper):
        raise StyleReferenceError(
            f"{label}: {name} value {value} is outside {lower if lower is not None else '-'}"
            f"..{upper if upper is not None else '+'}"
        )
    return value


def _color_value(color: StyleReferenceColor, label: str) -> str:
    if not isinstance(color, StyleReferenceColor):
        raise StyleReferenceError(f"{label} must be a StyleReferenceColor")
    if not isinstance(color.value, str):
        raise StyleReferenceError(f"{label}.value must be a string")
    if not isinstance(color.transforms, tuple):
        raise StyleReferenceError(f"{label}.transforms must be a tuple")
    for position, transform in enumerate(color.transforms):
        _transform_value(transform, f"{label}.transforms[{position}]")
    if color.kind == "rgb":
        if _RGB.fullmatch(color.value) is None:
            raise StyleReferenceError(
                f"{label}: RGB must be six hex digits, optionally prefixed by #"
            )
        return color.value.removeprefix("#").upper()
    if color.kind == "scheme":
        if color.value not in _SCHEME_COLORS:
            raise StyleReferenceError(f"{label}: unsupported scheme color {color.value!r}")
        return color.value
    raise StyleReferenceError(f"{label}.kind must be 'rgb' or 'scheme'")


def _strict_percent(name: str, a_ns: str) -> bool:
    return a_ns == STRICT_A_NS and name not in _STRICT_ANGLE_TRANSFORMS


def _saved_transform_value(raw: str, name: str, a_ns: str, label: str) -> int:
    if _strict_percent(name, a_ns):
        match = _SAVED_PERCENT.fullmatch(raw)
        if match is None:
            raise StyleReferenceError(
                f"{label}: Strict {name} needs a percentage with at most three decimals"
            )
        sign, whole, fraction = match.groups()
        value = int(whole) * 1000 + int((fraction or "").ljust(3, "0"))
        return -value if sign == "-" else value
    if _SAVED_INTEGER.fullmatch(raw) is None:
        raise StyleReferenceError(f"{label}: {name} has a non-integer value")
    return int(raw)


def _transform_xml(transform: StyleColorTransform, a_ns: str) -> str:
    if transform.value is None:
        return f"<a:{transform.name}/>"
    value = transform.value
    if _strict_percent(transform.name, a_ns):
        whole, fraction = divmod(abs(value), 1000)
        decimals = f".{fraction:03d}".rstrip("0") if fraction else ""
        text = f"{'-' if value < 0 else ''}{whole}{decimals}%"
    else:
        text = str(value)
    return f'<a:{transform.name} val="{text}"/>'


def validate_shape_style_references(
    references: ShapeStyleReferences | None,
) -> ShapeStyleReferences | None:
    """Validate every field before package mutation; ``None`` removes the style.

    Invalid types (including bool indices), negative/overflow indices, invalid
    font tokens, and invalid colors all raise ``StyleReferenceError``.
    """
    if references is None:
        return None
    if not isinstance(references, ShapeStyleReferences):
        raise StyleReferenceError("references must be ShapeStyleReferences or None")
    for xml_name, field in _REFERENCES:
        reference = getattr(references, field)
        if xml_name == "fontRef":
            if not isinstance(reference, FontStyleReference):
                raise StyleReferenceError(f"{field} must be a FontStyleReference")
            if reference.index not in ("major", "minor", "none"):
                raise StyleReferenceError("font_ref.index must be 'major', 'minor', or 'none'")
        else:
            if not isinstance(reference, StyleReference):
                raise StyleReferenceError(f"{field} must be a StyleReference")
            if type(reference.index) is not int or not 0 <= reference.index <= 4294967295:
                raise StyleReferenceError(f"{field}.index must be an integer in 0..4294967295")
        if reference.color is None:
            if xml_name != "fontRef":
                raise StyleReferenceError(f"{field}.color is required")
        else:
            _color_value(reference.color, f"{field}.color")
    return references


def _target(shape: Shape) -> tuple[Any, str, dict[str, Any]]:
    from .shape_core_facade import Shape as ShapeFacade

    if not isinstance(shape, ShapeFacade):
        raise StyleReferenceError("expected a saved slide Shape")
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
        raise StyleReferenceError("expected a saved slide shape, connector, or picture")
    if getattr(presentation, "_disposed", False):
        raise StyleReferenceError("presentation is disposed")
    if (
        payload.get("id") is None
        or payload.get("_pending_shape")
        or payload.get("_pending_group_child")
        or getattr(slide, "_payload", {}).get("_pending_creation")
    ):
        raise StyleReferenceError(
            "save the pending shape and slide before accessing style references"
        )
    return presentation, str(slide.partname).lstrip("/"), payload


def _source(
    raw: bytes,
    payload: dict[str, Any],
) -> tuple[ET.Element, ET.Element | None, list[dict[str, Any]], dict[int, int]]:
    if b"\x00" in raw:
        raise StyleReferenceError("style byte-slice edits require ASCII-compatible XML encoding")
    try:
        root = ET.fromstring(raw)
        spans = _element_spans(raw)
        elements = list(root.iter())
        if len(spans) != len(elements):
            raise StyleReferenceError("cannot map saved XML elements to source byte slices")
        positions = {id(element): index for index, element in enumerate(elements)}
        shape_element = _shape_xml_element(root, payload)
    except (ET.ParseError, ExpatError, AttributeError, ValueError) as exc:
        if isinstance(exc, StyleReferenceError):
            raise
        raise StyleReferenceError("saved shape XML is unavailable or malformed") from exc
    p_ns = ooxml_namespace(shape_element, P_NS)
    identities = [
        node
        for node in root.iter()
        if node.tag == f"{{{p_ns}}}cNvPr" and node.get("id") == str(payload["id"])
    ]
    if len(identities) != 1:
        raise StyleReferenceError("saved shape identity is missing or ambiguous")
    if shape_element.tag not in {f"{{{p_ns}}}{name}" for name in ("sp", "cxnSp", "pic")}:
        raise StyleReferenceError("style references support only shapes, connectors, and pictures")
    if find_ooxml(shape_element, f"{{{P_NS}}}spPr") is None:
        raise StyleReferenceError("saved shape is missing p:spPr")
    styles = [child for child in shape_element if child.tag == f"{{{p_ns}}}style"]
    if len(styles) > 1:
        raise StyleReferenceError("saved shape has duplicate p:style elements")
    if any(
        isinstance(child.tag, str)
        and child.tag.rsplit("}", 1)[-1] == "style"
        and child.tag != f"{{{p_ns}}}style"
        for child in shape_element
    ):
        raise StyleReferenceError("saved p:style uses an unsupported namespace profile")
    return shape_element, styles[0] if styles else None, spans, positions


def _parse_color(element: ET.Element, label: str, a_ns: str) -> StyleReferenceColor:
    if element.tag == f"{{{a_ns}}}srgbClr":
        kind = "rgb"
        if re.fullmatch(r"[0-9a-fA-F]{6}", element.get("val", "")) is None:
            raise StyleReferenceError(f"{label}: invalid saved RGB color")
    elif element.tag == f"{{{a_ns}}}schemeClr":
        kind = "scheme"
    else:
        raise StyleReferenceError(f"{label}: unsupported color choice {element.tag!r}")
    if set(element.attrib) != {"val"}:
        raise StyleReferenceError(f"{label}: extra color attributes are unsupported")
    if element.text and element.text.strip():
        raise StyleReferenceError(f"{label}: unexpected color text")
    transforms: list[StyleColorTransform] = []
    for position, child in enumerate(element):
        where = f"{label}.transforms[{position}]"
        if not isinstance(child.tag, str) or not child.tag.startswith(f"{{{a_ns}}}"):
            raise StyleReferenceError(f"{where}: unsupported color transform element")
        name = child.tag.rsplit("}", 1)[-1]
        if len(child) or (child.text and child.text.strip()):
            raise StyleReferenceError(f"{where}: {name} must be empty")
        if child.tail and child.tail.strip():
            raise StyleReferenceError(f"{where}: unexpected color transform tail text")
        if name in _FLAG_TRANSFORMS:
            if child.attrib:
                raise StyleReferenceError(f"{where}: {name} takes no attributes")
            transforms.append(StyleColorTransform(name))
            continue
        if name not in _VALUED_TRANSFORMS:
            raise StyleReferenceError(f"{where}: unsupported color transform {name!r}")
        if set(child.attrib) != {"val"}:
            raise StyleReferenceError(f"{where}: {name} requires val and no other attributes")
        value = _saved_transform_value(child.get("val", ""), name, a_ns, where)
        transforms.append(StyleColorTransform(name, value))
    color = StyleReferenceColor(kind, element.get("val", ""), tuple(transforms))
    return StyleReferenceColor(kind, _color_value(color, label), tuple(transforms))


def _parse_style(style: ET.Element | None) -> ShapeStyleReferences | None:
    if style is None:
        return None
    a_ns = ooxml_namespace(style, A_NS)
    children = list(style)
    if style.attrib or [child.tag for child in children] != [
        f"{{{a_ns}}}{name}" for name, _ in _REFERENCES
    ]:
        raise StyleReferenceError(
            "p:style must contain exactly lnRef, fillRef, effectRef, fontRef in order, "
            "without extensions"
        )
    if style.text and style.text.strip():
        raise StyleReferenceError("p:style contains unexpected text")
    values: dict[str, Any] = {}
    for (name, field), element in zip(_REFERENCES, children, strict=True):
        if set(element.attrib) != {"idx"}:
            raise StyleReferenceError(f"{name} requires idx and supports no other attributes")
        if (element.text and element.text.strip()) or (element.tail and element.tail.strip()):
            raise StyleReferenceError(f"{name} contains unexpected text")
        if len(element) != 1 and not (name == "fontRef" and len(element) == 0):
            raise StyleReferenceError(f"{name} requires one color (fontRef may omit it)")
        if len(element) and element[0].tail and element[0].tail.strip():
            raise StyleReferenceError(f"{name} contains unexpected color tail text")
        color = _parse_color(element[0], field, a_ns) if len(element) else None
        index = element.get("idx", "")
        if name == "fontRef":
            values[field] = FontStyleReference(index, color)
        else:
            if _INDEX.fullmatch(index) is None or len(index.lstrip("+0")) > 10:
                raise StyleReferenceError(f"{name} has an invalid unsigned integer index")
            significant = index.lstrip("+0")
            values[field] = StyleReference(int(significant or "0"), color)
    result = ShapeStyleReferences(**values)
    validate_shape_style_references(result)
    return result


def read_shape_style_references(shape: Shape) -> ShapeStyleReferences | None:
    """Read a saved shape's complete style, or ``None`` if no p:style is present.

    Unsupported color transforms/choices are refused explicitly, never flattened.
    """
    presentation, part, payload = _target(shape)
    try:
        with open_package_source(presentation._source_path) as package:
            raw = package.read(part)
    except (KeyError, FileNotFoundError) as exc:
        raise StyleReferenceError("saved slide part is unavailable") from exc
    _, style, _, _ = _source(raw, payload)
    return _parse_style(style)


def _reference_xml(name: str, reference: Any, a_ns: str) -> bytes:
    color = reference.color
    body = ""
    if color is not None:
        color_name = "srgbClr" if color.kind == "rgb" else "schemeClr"
        value = _color_value(color, name)
        transforms = "".join(_transform_xml(transform, a_ns) for transform in color.transforms)
        if transforms:
            body = f'<a:{color_name} val="{value}">{transforms}</a:{color_name}>'
        else:
            body = f'<a:{color_name} val="{value}"/>'
    return (f'<a:{name} xmlns:a="{a_ns}" idx="{reference.index}">{body}</a:{name}>').encode("ascii")


def _rewrite(
    raw: bytes,
    payload: dict[str, Any],
    wanted: ShapeStyleReferences | None,
) -> bytes:
    element, style, spans, positions = _source(raw, payload)
    current = _parse_style(style)
    if current == wanted:
        return raw
    edits: list[tuple[int, int, bytes]] = []
    if style is not None:
        if wanted is None:
            span = spans[positions[id(style)]]
            edits.append((span["start"], span["end"], b""))
        else:
            a_ns = ooxml_namespace(style, A_NS)
            for (name, field), child in zip(_REFERENCES, style, strict=True):
                if getattr(current, field) != getattr(wanted, field):
                    span = spans[positions[id(child)]]
                    edits.append(
                        (
                            span["start"],
                            span["end"],
                            _reference_xml(name, getattr(wanted, field), a_ns),
                        )
                    )
    else:
        p_ns = ooxml_namespace(element, P_NS)
        a_ns = ooxml_namespace(element, A_NS)
        body = b"".join(
            _reference_xml(name, getattr(wanted, field), a_ns) for name, field in _REFERENCES
        )
        replacement = f'<p:style xmlns:p="{p_ns}">'.encode("ascii") + body + b"</p:style>"
        following = next(
            (
                child
                for child in element
                if child.tag
                in {
                    f"{{{p_ns}}}txBody",
                    f"{{{p_ns}}}extLst",
                }
            ),
            None,
        )
        if following is not None:
            offset = spans[positions[id(following)]]["start"]
        else:
            span = spans[positions[id(element)]]
            # The supported element has p:spPr, so cannot be a self-closing tag.
            offset = raw.rfind(b"</", _tag_end(raw, span["start"]), span["end"])
            if offset < 0:
                raise StyleReferenceError("cannot locate the saved shape's closing tag")
        edits.append((offset, offset, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    return raw


def _validate_theme_indices(
    shape: Shape,
    references: ShapeStyleReferences | None,
) -> None:
    if references is None:
        return
    selections = (
        ("ln_ref", "lnStyleLst"),
        ("fill_ref", "fillStyleLst"),
        ("effect_ref", "effectStyleLst"),
    )
    positive = []
    for field, listing in selections:
        index = getattr(references, field).index
        if field == "fill_ref" and index >= 1000:
            # 1000 selects no background fill; 1001 and above select bgFillStyleLst.
            listing, index = "bgFillStyleLst", index - 1000
        if index:
            positive.append((field, listing, index))
    if not positive:
        return
    try:
        # Reuse the existing slide/layout/master override resolver, without
        # materializing or editing any theme scheme.
        theme = shape._slide._presentation.theme_for(shape._slide)
        scheme = theme._scheme("fmtScheme", False)
        for field, listing, index in positive:
            entries = find_ooxml(scheme, f"{{{A_NS}}}{listing}")
            if entries is None or index > len(entries):
                count = 0 if entries is None else len(entries)
                raise StyleReferenceError(
                    f"{field}.index selects entry {index}, beyond the effective theme's "
                    f"{listing} ({count} entries)"
                )
    except (ValueError, KeyError, AttributeError, ET.ParseError) as exc:
        if isinstance(exc, StyleReferenceError):
            raise
        raise StyleReferenceError(
            "cannot resolve the saved slide's effective format scheme"
        ) from exc


def write_shape_style_references(
    shape: Shape,
    references: ShapeStyleReferences | None,
) -> None:
    """Replace all four references, or remove p:style with ``None``, atomically.

    Validation and source-model refusals happen before any package bytes are
    written. Existing unsupported color choices, transforms and extensions are
    refused even when replacing/removing the style, so they cannot be erased
    accidentally. Save queued edits first; that lifecycle refusal is also
    ``StyleReferenceError``. Positive matrix indices must select existing effective
    theme entries; fill indices from 1001 are checked against ``bgFillStyleLst``.
    """
    validate_shape_style_references(references)
    presentation, part, payload = _target(shape)

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        try:
            raw = package.read(part)
        except KeyError as exc:
            raise StyleReferenceError("saved slide part is unavailable") from exc
        rewritten = _rewrite(raw, payload, references)
        _validate_theme_indices(shape, references)
        return ({part: rewritten} if rewritten != raw else {}), set(), None

    try:
        presentation._rewrite_package("editing shape style references", plan)
    except ValueError as exc:
        if isinstance(exc, StyleReferenceError):
            raise
        raise StyleReferenceError(str(exc)) from exc
