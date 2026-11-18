"""Read and author InkML content parts without rewriting unrelated PPTX members.

Public coordinates and circular brush diameters are integer EMU. InkML coordinates
use physical units (mm, cm, m, in or pt); the Wolf default trace format is X/Y in
mm and the default brush is black with a 0.5 mm circular tip. Explicit XY samples,
local context/brush references, nested trace groups and pen-up traces are admitted.
Device units, pressure/variable-width channels, differential samples, continuation,
canvas mappings and non-circular tips raise :class:`InkRefusal` before publication.

Brush admission is explicitly opaque-only: ``rasterOp`` is absent or ``copyPen``,
and ``transparency`` is absent or the literal ``0``. ``InkBrush`` exposes only RGB
and diameter, not an unqualified opacity control. W3C InkML section 4.3.2 defines
zero transparency as opaque and ``copyPen`` as overwriting the background;
MS-ODRAWXML's Ink Content Part defines the transparency range as integers 0-255.
Neither statement alone qualifies a PDF/PNG alpha-compositing implementation.
Nonzero transparency remains refused until a real ink fixture and its
specification-supported expected paint establish the admitted brush combination.
Other raster operations, including ``maskPen``, remain refused rather than being
approximated as transparency. Appending ink validates existing slide-owned ink
before opening the destination, including in-place saves.

Use ``author_ink(source, destination, traces, slide_number=1)`` to append a content
part, then ``read_ink(destination)`` to inspect it after reopening. For PDF/PNG use
``wolfppt.render_ink.resolve_ink_deck`` with the existing scene output backends.
"""

from __future__ import annotations

import math
import posixpath
import re
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements, rels_part_for_package_part
from .render_package import (
    Package,
    PackageRefusal,
    read_package,
    refuse_unsupported_must_understand,
    resolve_target,
)
from .render_refusals import RenderRefusal
from .xml_helpers import (
    STRICT_A_NS,
    STRICT_P_NS,
    STRICT_R_NS,
    content_types_xml,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
    ooxml_path,
)

INK_NS = "http://www.w3.org/2003/InkML"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
INK_CONTENT_TYPE = "application/inkml+xml"
INK_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml"
_UNITS = {"mm": 36000, "cm": 360000, "m": 36000000, "in": 914400, "pt": 12700}
_MAX_EMU = 2147483647
_RENDER_NAMESPACES = frozenset(
    {
        P_NS,
        R_NS,
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        STRICT_A_NS,
        STRICT_P_NS,
        STRICT_R_NS,
    }
)
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _selected_xml(package: Package, part: str) -> ET.Element:
    root, scopes = package.xml_with_namespace_scopes(part)
    refuse_unsupported_must_understand(part, root, scopes, _RENDER_NAMESPACES)
    return root


class InkRefusal(RenderRefusal):
    """Ink cannot be read, authored or rendered with the admitted semantics."""


def _emu(value: object, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or abs(value) > _MAX_EMU or (positive and value <= 0):
        raise InkRefusal(f"{label} must be an integer EMU within +/-{_MAX_EMU}")
    return value


@dataclass(frozen=True)
class InkBrush:
    """Constant circular brush; RGB is six hexadecimal digits without '#'."""

    color: str = "000000"
    width_emu: int = 18000

    def __post_init__(self) -> None:
        if not isinstance(self.color, str) or re.fullmatch(r"[0-9A-Fa-f]{6}", self.color) is None:
            raise InkRefusal("ink brush color must be six RGB hexadecimal digits")
        object.__setattr__(self, "color", self.color.upper())
        _emu(self.width_emu, "ink brush diameter", positive=True)


@dataclass(frozen=True)
class InkTrace:
    """Ordered absolute XY samples; pen-up samples are retained but not painted."""

    points: tuple[tuple[int, int], ...]
    brush: InkBrush = InkBrush()
    pen_down: bool = True
    identifier: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.brush, InkBrush) or type(self.pen_down) is not bool:
            raise InkRefusal("ink traces require an InkBrush and a boolean pen_down")
        if not isinstance(self.identifier, str) or (
            self.identifier and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", self.identifier) is None
        ):
            raise InkRefusal("ink trace identifier must be an XML identifier")
        try:
            points = tuple(tuple(point) for point in self.points)
        except TypeError as exc:
            raise InkRefusal("ink points must be XY pairs") from exc
        if not points:
            raise InkRefusal("an ink trace must contain at least one sample")
        for point in points:
            if len(point) != 2:
                raise InkRefusal("ink points must contain exactly X and Y")
            for value in point:
                _emu(value, "ink coordinate")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True)
class InkContentPart:
    """One slide-linked content part with resolved traces and reusable brushes."""

    owner_part: str
    relationship_id: str
    part: str
    traces: tuple[InkTrace, ...]
    brushes: tuple[tuple[str, InkBrush], ...]


def _number(value: str, label: str) -> float:
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise InkRefusal(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise InkRefusal(f"{label} must be finite")
    return result


def _physical(value: str, units: str, label: str) -> int:
    if units not in _UNITS:
        raise InkRefusal(f"{label}: unsupported units {units!r}; use physical length units")
    scaled = _number(value, label) * _UNITS[units]
    if not math.isfinite(scaled) or abs(scaled) > _MAX_EMU:
        raise InkRefusal(f"{label} exceeds the {_MAX_EMU} EMU limit")
    return round(scaled)


class _InkReader:
    def __init__(self, payload: bytes) -> None:
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise InkRefusal("ink DTDs and entities are unsupported")
        try:
            self.root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise InkRefusal("ink content is not well-formed XML") from exc
        if self.root.tag != f"{{{INK_NS}}}ink":
            raise InkRefusal("content part must contain an InkML ink root")
        self.ids: dict[str, ET.Element] = {}
        attributes = {
            "ink": {XML_ID, "documentID"},
            "definitions": {XML_ID},
            "traceFormat": {XML_ID},
            "channel": {XML_ID, "name", "type", "units", "min", "max", "orientation"},
            "brush": {XML_ID, "brushRef"},
            "brushProperty": {XML_ID, "name", "value", "units"},
            "context": {XML_ID, "contextRef", "brushRef", "traceFormatRef"},
            "traceGroup": {XML_ID, "contextRef", "brushRef"},
            "trace": {XML_ID, "brushRef", "contextRef", "type"},
            "annotation": set(),
            "annotationXML": set(),
        }
        children = {
            "ink": {
                "definitions",
                "context",
                "traceFormat",
                "brush",
                "traceGroup",
                "trace",
                "annotation",
                "annotationXML",
            },
            "definitions": {"context", "traceFormat", "brush", "annotation", "annotationXML"},
            "context": {"traceFormat", "brush", "annotation", "annotationXML"},
            "brush": {"brushProperty", "annotation", "annotationXML"},
            "brushProperty": {"annotation", "annotationXML"},
            "traceFormat": {"channel"},
            "channel": set(),
            "traceGroup": {"trace", "traceGroup", "annotation", "annotationXML"},
            "trace": set(),
        }

        # Foreign markup is permitted only inside opaque annotations.
        def index(node: ET.Element, depth: int = 0) -> None:
            if depth > 64:
                raise InkRefusal("ink nesting exceeds 64 levels")
            kind = node.tag.rsplit("}", 1)[-1]
            if node.tag != f"{{{INK_NS}}}{kind}" or kind not in attributes:
                raise InkRefusal(f"unsupported ink element {node.tag!r}")
            identifier = node.get(XML_ID)
            if identifier:
                if identifier in self.ids:
                    raise InkRefusal(f"duplicate ink identifier {identifier!r}")
                self.ids[identifier] = node
            if node.tag in {f"{{{INK_NS}}}annotation", f"{{{INK_NS}}}annotationXML"}:
                return
            if any(key not in attributes[kind] for key in node.attrib):
                raise InkRefusal(f"unsupported ink {kind} attribute (including continuation)")
            for child in node:
                if child.tag.rsplit("}", 1)[-1] not in children[kind]:
                    raise InkRefusal(f"unsupported ink {kind} child {child.tag!r}")
                index(child, depth + 1)

        index(self.root)
        self.brushes: dict[str, InkBrush] = {}

    def ref(self, value: str, kind: str) -> ET.Element:
        if not value.startswith("#") or value[1:] not in self.ids:
            raise InkRefusal(f"ink {kind} reference {value!r} must resolve within its part")
        result = self.ids[value[1:]]
        if result.tag != f"{{{INK_NS}}}{kind}":
            raise InkRefusal(f"ink reference {value!r} does not identify {kind}")
        return result

    def _brush_properties(
        self, node: ET.Element, stack: tuple[int, ...] = ()
    ) -> dict[str, ET.Element]:
        if id(node) in stack:
            raise InkRefusal("cyclic ink brush reference")
        if len(stack) > 64:
            raise InkRefusal("ink brush reference chain exceeds 64 levels")
        values: dict[str, ET.Element] = {}
        reference = node.get("brushRef", "#DefaultBrush")
        if reference != "#DefaultBrush":
            values.update(self._brush_properties(self.ref(reference, "brush"), (*stack, id(node))))
        authored: set[str] = set()
        for prop in node:
            if prop.tag in {f"{{{INK_NS}}}annotation", f"{{{INK_NS}}}annotationXML"}:
                continue
            if prop.tag != f"{{{INK_NS}}}brushProperty":
                raise InkRefusal("unsupported ink brush child")
            name = prop.get("name", "")
            if name in authored:
                raise InkRefusal(f"duplicate ink brush property {name!r}")
            authored.add(name)
            values[name] = prop
        return values

    def brush(self, node: ET.Element) -> InkBrush:
        # Merge authored properties before deriving defaults. An explicitly
        # inherited height remains fixed when a child changes only its width.
        values = self._brush_properties(node)
        base = InkBrush()
        for name, prop in values.items():
            value = prop.get("value", "")
            if name not in {"width", "height"} and prop.get("units"):
                raise InkRefusal(f"unsupported units for ink brush property {name!r}")
            if name == "color":
                if not value.startswith("#"):
                    raise InkRefusal("ink brush color must be #RRGGBB")
                base = replace(base, color=value[1:])
            elif name == "width":
                base = replace(base, width_emu=_physical(value, prop.get("units", "mm"), name))
            elif name == "height":
                continue
            elif (name, value) not in {
                ("tip", "ellipse"),
                ("rasterOp", "copyPen"),
                ("transparency", "0"),
                ("fitToCurve", "false"),
                ("fitToCurve", "0"),
                ("ignorePressure", "true"),
                ("ignorePressure", "1"),
                ("ignorePressure", "false"),
                ("ignorePressure", "0"),
                ("antiAliased", "true"),
                ("antiAliased", "1"),
            }:
                raise InkRefusal(f"unsupported ink brush property {name}={value!r}")
        if "height" in values:
            height = values["height"]
            if (
                _physical(height.get("value", ""), height.get("units", "mm"), "height")
                != base.width_emu
            ):
                raise InkRefusal("non-circular ink tips are unsupported")
        identifier = node.get(XML_ID)
        if identifier:
            self.brushes[identifier] = base
        return base

    def context(
        self,
        node: ET.Element,
        inherited: tuple[InkBrush, ET.Element | None],
        stack: tuple[int, ...] = (),
    ) -> tuple[InkBrush, ET.Element | None]:
        if id(node) in stack:
            raise InkRefusal("cyclic ink context reference")
        if len(stack) > 64:
            raise InkRefusal("ink context reference chain exceeds 64 levels")
        if any(
            key not in {XML_ID, "contextRef", "brushRef", "traceFormatRef"} for key in node.attrib
        ):
            raise InkRefusal("unsupported ink context attribute")
        brush, trace_format = inherited
        reference = node.get("contextRef")
        if reference and reference != "#DefaultContext":
            brush, trace_format = self.context(
                self.ref(reference, "context"), inherited, (*stack, id(node))
            )
        elif reference:
            brush, trace_format = InkBrush(), None
        for kind in ("brush", "traceFormat"):
            children = node.findall(f"{{{INK_NS}}}{kind}")
            if len(children) > 1 or (children and node.get(f"{kind}Ref")):
                raise InkRefusal(f"ambiguous ink context {kind}")
            reference = node.get(f"{kind}Ref")
            if children or reference:
                target = children[0] if children else self.ref(reference, kind)
                if kind == "brush":
                    brush = self.brush(target)
                else:
                    trace_format = target
        return brush, trace_format

    def trace(self, node: ET.Element, state: tuple[InkBrush, ET.Element | None]) -> InkTrace:
        if any(key not in {XML_ID, "brushRef", "contextRef", "type"} for key in node.attrib):
            raise InkRefusal("unsupported ink trace attribute (including continuation)")
        brush, trace_format = self.state(node, state)
        channels = [] if trace_format is None else list(trace_format)
        if trace_format is not None and (
            len(channels) != 2
            or [c.get("name") for c in channels] != ["X", "Y"]
            or any(c.tag != f"{{{INK_NS}}}channel" for c in channels)
        ):
            raise InkRefusal("only regular ink X/Y channels are supported")
        for channel in channels:
            if (
                list(channel)
                or channel.get("type", "decimal") not in {"decimal", "integer", "double"}
                or channel.get("orientation", "+ve") != "+ve"
                or channel.get("respectTo")
            ):
                raise InkRefusal("unsupported ink channel mapping or orientation")
        contact = node.get("type", "penDown")
        if contact not in {"penDown", "penUp"}:
            raise InkRefusal(f"unsupported ink contact state {contact!r}")
        if list(node):
            raise InkRefusal("ink trace samples must be text")
        points = []
        for sample in (node.text or "").split(","):
            values = sample.split()
            if len(values) != 2:
                raise InkRefusal("ink samples require explicit X/Y pairs")
            point = tuple(
                _physical(
                    value.removeprefix("!"),
                    channels[i].get("units", "mm") if channels else "mm",
                    "coordinate",
                )
                for i, value in enumerate(values)
            )
            points.append(point)
        return InkTrace(tuple(points), brush, contact == "penDown", node.get(XML_ID, ""))

    def state(self, node: ET.Element, inherited: tuple[InkBrush, ET.Element | None]):
        state = inherited
        if node.get("contextRef"):
            state = (
                (InkBrush(), None)
                if node.get("contextRef") == "#DefaultContext"
                else self.context(self.ref(node.get("contextRef"), "context"), inherited)
            )
        if node.get("brushRef"):
            brush = (
                InkBrush()
                if node.get("brushRef") == "#DefaultBrush"
                else self.brush(self.ref(node.get("brushRef"), "brush"))
            )
            state = brush, state[1]
        return state

    def read(self) -> tuple[tuple[InkTrace, ...], tuple[tuple[str, InkBrush], ...]]:
        traces: list[InkTrace] = []
        for node in self.ids.values():
            if node.tag == f"{{{INK_NS}}}brush":
                self.brush(node)

        def walk(container: ET.Element, inherited: tuple[InkBrush, ET.Element | None]) -> None:
            state = inherited
            for child in container:
                kind = child.tag.rsplit("}", 1)[-1]
                if kind == "trace":
                    traces.append(self.trace(child, state))
                elif kind == "traceGroup":
                    if any(key not in {XML_ID, "contextRef", "brushRef"} for key in child.attrib):
                        raise InkRefusal("unsupported ink trace-group attribute")
                    walk(child, self.state(child, state))
                elif kind == "context":
                    state = self.context(child, state)
                elif kind == "traceFormat":
                    state = state[0], child
                elif kind == "brush":
                    state = self.brush(child), state[1]
                elif kind not in {"definitions", "annotation", "annotationXML"}:
                    raise InkRefusal(f"unsupported ink container child {kind!r}")

        walk(self.root, (InkBrush(), None))
        return tuple(traces), tuple(self.brushes.items())


def _content_part(package: Package, owner: str, element: ET.Element) -> InkContentPart:
    if len(element) or any(key != ooxml_path(element, f"{{{R_NS}}}id") for key in element.attrib):
        raise InkRefusal("content-part extensions and local transforms are unsupported")
    rid = element.get(ooxml_path(element, f"{{{R_NS}}}id"))
    relation = next((r for r in package.part_rels(owner) if r.identifier == rid), None)
    if relation is None or relation.external or relation.kind != "customXml":
        raise InkRefusal("ink content part requires an internal customXml relationship")
    part = resolve_target(owner, relation.target)
    if package.content_type(part) != INK_CONTENT_TYPE:
        raise InkRefusal(f"content part {part!r} is not declared InkML")
    try:
        traces, brushes = _InkReader(package.read(part)).read()
    except PackageRefusal as exc:
        raise InkRefusal(str(exc)) from exc
    return InkContentPart(owner, rid, part, traces, brushes)


def _slides(package: Package) -> tuple[str, ...]:
    root = package.xml("ppt/presentation.xml")
    relationships = {r.identifier: r for r in package.part_rels("ppt/presentation.xml")}
    parts = []
    for element in findall_ooxml(root, f"{{{P_NS}}}sldIdLst/{{{P_NS}}}sldId"):
        relation = relationships.get(element.get(ooxml_path(element, f"{{{R_NS}}}id")))
        if relation is None or relation.external or relation.kind != "slide":
            raise InkRefusal("presentation slide relationship is invalid")
        parts.append(resolve_target("ppt/presentation.xml", relation.target))
    return tuple(parts)


def read_ink(source: str | Path, *, slide_number: int | None = None) -> tuple[InkContentPart, ...]:
    """Reopen a deck and read slide-owned ink parts, in slide/tree order."""
    package = read_package(Path(source))
    parts = _slides(package)
    if slide_number is not None:
        if type(slide_number) is not int or not 1 <= slide_number <= len(parts):
            raise InkRefusal("ink slide_number is outside the deck")
        parts = (parts[slide_number - 1],)
    result = []
    for owner in parts:
        root = _selected_xml(package, owner)
        tree = find_ooxml(root, f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if tree is not None:
            for element in tree.iter():
                if element.tag == f"{{{ooxml_namespace(root, P_NS)}}}contentPart":
                    result.append(_content_part(package, owner, element))
    return tuple(result)


def author_ink(
    source: str | Path,
    destination: str | Path,
    traces: tuple[InkTrace, ...],
    *,
    slide_number: int = 1,
) -> None:
    """Append native InkML traces to a slide, atomically saving only changed parts.

    Existing slide objects precede the new ink in paint order. No source part is
    removed; all unrelated ZIP members retain their payload and compressed bytes.
    Validation completes before the destination is opened, including in-place saves.
    """
    try:
        traces = tuple(traces)
    except TypeError as exc:
        raise InkRefusal("author_ink requires a sequence of InkTrace values") from exc
    if not traces or any(not isinstance(trace, InkTrace) for trace in traces):
        raise InkRefusal("author_ink requires a nonempty sequence of InkTrace values")
    identifiers = [trace.identifier or f"trace{index}" for index, trace in enumerate(traces, 1)]
    if len(set(identifiers)) != len(identifiers):
        raise InkRefusal("authored ink trace identifiers must be unique")
    package = read_package(Path(source))
    parts = _slides(package)
    if type(slide_number) is not int or not 1 <= slide_number <= len(parts):
        raise InkRefusal("ink slide_number is outside the deck")
    owner = parts[slide_number - 1]
    root = package.xml(owner)
    tree = find_ooxml(root, f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if any(
        node.tag.startswith(f"{{{_MC_NS}}}")
        or any(key.startswith(f"{{{_MC_NS}}}") for key in node.attrib)
        for node in root.iter()
    ):
        raise InkRefusal("authoring beside prefix-dependent compatibility markup is unsupported")
    for element in root.iter():
        if element.tag == f"{{{ooxml_namespace(root, P_NS)}}}contentPart":
            _content_part(package, owner, element)
    if tree is None:
        raise InkRefusal("slide has no shape tree for ink")
    ink = ET.Element(f"{{{INK_NS}}}ink")
    context = ET.SubElement(ink, f"{{{INK_NS}}}context")
    trace_format = ET.SubElement(context, f"{{{INK_NS}}}traceFormat")
    for name in ("X", "Y"):
        ET.SubElement(
            trace_format, f"{{{INK_NS}}}channel", {"name": name, "type": "decimal", "units": "mm"}
        )
    definitions = ET.SubElement(ink, f"{{{INK_NS}}}definitions")
    brushes = dict.fromkeys(trace.brush for trace in traces)
    brush_ids = {}
    for index, brush in enumerate(brushes, 1):
        identifier = f"brush{index}"
        while identifier in identifiers or identifier in brush_ids.values():
            identifier += "_"
        brush_ids[brush] = identifier
        element = ET.SubElement(definitions, f"{{{INK_NS}}}brush", {XML_ID: identifier})
        for name, value, units in (
            ("color", f"#{brush.color}", ""),
            ("width", format(brush.width_emu / 36000, ".15g"), "mm"),
        ):
            attributes = {"name": name, "value": value}
            if units:
                attributes["units"] = units
            ET.SubElement(element, f"{{{INK_NS}}}brushProperty", attributes)
    for identifier, trace in zip(identifiers, traces, strict=True):
        element = ET.SubElement(
            ink,
            f"{{{INK_NS}}}trace",
            {
                XML_ID: identifier,
                "brushRef": f"#{brush_ids[trace.brush]}",
                "type": "penDown" if trace.pen_down else "penUp",
            },
        )
        element.text = ", ".join(
            " ".join(format(value / 36000, ".15g") for value in point) for point in trace.points
        )
    number = 1
    while f"ppt/ink/ink{number}.xml" in package.parts:
        number += 1
    part = f"ppt/ink/ink{number}.xml"
    rels_part = rels_part_for_package_part(owner)
    payload = package.read_optional(rels_part)
    rels = ET.Element(f"{{{REL_NS}}}Relationships") if payload is None else ET.fromstring(payload)
    number = 1
    used = {element.get("Id") for element in rels}
    while f"rId{number}" in used:
        number += 1
    rid = f"rId{number}"
    ET.SubElement(
        rels,
        f"{{{REL_NS}}}Relationship",
        {
            "Id": rid,
            "Type": ooxml_namespace(root, R_NS) + "/customXml",
            "Target": posixpath.relpath(part, posixpath.dirname(owner)),
        },
    )
    content = ET.Element(
        f"{{{ooxml_namespace(root, P_NS)}}}contentPart",
        {f"{{{ooxml_namespace(root, R_NS)}}}id": rid},
    )
    extension = find_ooxml(tree, f"{{{P_NS}}}extLst")
    tree.insert(len(tree) if extension is None else list(tree).index(extension), content)
    content_types = package.xml("[Content_Types].xml")
    ET.SubElement(
        content_types,
        f"{{{CT_NS}}}Override",
        {
            "PartName": f"/{part}",
            "ContentType": INK_CONTENT_TYPE,
        },
    )
    replacements = {
        name: ET.tostring(element, encoding="utf-8", xml_declaration=True)
        for name, element in (
            (owner, root),
            (rels_part, rels),
            (part, ink),
            ("[Content_Types].xml", content_types),
        )
    }
    replacements["[Content_Types].xml"] = content_types_xml(content_types)
    copy_package_with_replacements(Path(source), Path(destination), replacements)


__all__ = ["InkBrush", "InkTrace", "InkContentPart", "InkRefusal", "read_ink", "author_ink"]
