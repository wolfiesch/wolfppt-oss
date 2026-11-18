"""Rewrite a saved PresentationML package to a conformance class and zip level.

ECMA-376 (5th edition, 2016) Part 1 defines the Strict conformance class and
Part 4 the Transitional additions. The two classes share content types and
part names; they differ in:

- namespace URIs (``http://schemas.openxmlformats.org/...`` against
  ``http://purl.oclc.org/ooxml/...``), also used by ``a:graphicData/@uri``;
- relationship types, including the renamed extended/custom property and
  thumbnail relationships;
- the lexical form of percentage attributes. Transitional allows integer
  thousandths (DrawingML/PresentationML) beside the ``N%`` string that Strict
  requires, and ``on``/``off`` for math ``val``;
- Transitional-only markup (VML, legacy write-protection hashes, HTML
  publishing properties, ``spid`` shape links), which Strict cannot carry.

The attribute table below was derived by comparing every attribute type in the
Strict (Part 1) and Transitional (Part 4) XML schemas, plus ``a:buSzPct``
whose Transitional decimal form is defined in Part 4 §17.2.2.14. Edits are
applied to the exact attribute spans, so every other byte of a part survives;
a value without an exact representation in the target class is refused rather
than rounded, and so is Transitional-only markup on the way to Strict.

Chart whole-number percentages (``c:lblOffset``, ``c:gapWidth``,
``c:bubbleScale`` and the rest of ``_CHART_WHOLE_PERCENT``) are the exception:
the Strict schema types them as ``N%`` strings, but PowerPoint reads only the
integer form (a Strict deck whose ``c:lblOffset`` or ``c:bubbleScale`` says
``100%`` never opens; the same deck with ``100`` opens cleanly), and the Open
XML SDK models them as integers too. Both targets therefore write the integer
form, and an ``N%`` value read from another producer is normalized to it.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from decimal import Decimal
from xml.etree import ElementTree as ET
from xml.parsers import expat

CONFORMANCE_CLASSES = ("transitional", "strict")

_T = "http://schemas.openxmlformats.org/"
_S = "http://purl.oclc.org/ooxml/"
_TRANSITIONAL_TO_STRICT_NS = {
    _T + "presentationml/2006/main": _S + "presentationml/main",
    _T + "presentationml/2006/ole": _S + "presentationml/ole",
    _T + "drawingml/2006/main": _S + "drawingml/main",
    _T + "drawingml/2006/chart": _S + "drawingml/chart",
    _T + "drawingml/2006/chartDrawing": _S + "drawingml/chartDrawing",
    _T + "drawingml/2006/diagram": _S + "drawingml/diagram",
    _T + "drawingml/2006/picture": _S + "drawingml/picture",
    _T + "drawingml/2006/lockedCanvas": _S + "drawingml/lockedCanvas",
    _T + "drawingml/2006/table": _S + "drawingml/table",
    _T + "drawingml/2006/spreadsheetDrawing": _S + "drawingml/spreadsheetDrawing",
    _T + "drawingml/2006/wordprocessingDrawing": (_S + "drawingml/wordprocessingDrawing"),
    _T + "officeDocument/2006/relationships": _S + "officeDocument/relationships",
    _T + "officeDocument/2006/sharedTypes": _S + "officeDocument/sharedTypes",
    _T + "officeDocument/2006/extended-properties": (_S + "officeDocument/extendedProperties"),
    _T + "officeDocument/2006/custom-properties": (_S + "officeDocument/customProperties"),
    _T + "officeDocument/2006/docPropsVTypes": _S + "officeDocument/docPropsVTypes",
    _T + "officeDocument/2006/math": _S + "officeDocument/math",
    _T + "officeDocument/2006/bibliography": _S + "officeDocument/bibliography",
    _T + "officeDocument/2006/customXml": _S + "officeDocument/customXml",
    _T + "officeDocument/2006/characteristics": _S + "officeDocument/characteristics",
    _T + "schemaLibrary/2006/main": _S + "schemaLibrary/main",
    _T + "spreadsheetml/2006/main": _S + "spreadsheetml/main",
    _T + "wordprocessingml/2006/main": _S + "wordprocessingml/main",
}
_STRICT_TO_TRANSITIONAL_NS = {
    strict: transitional for transitional, strict in _TRANSITIONAL_TO_STRICT_NS.items()
}
_T_REL = _T + "officeDocument/2006/relationships/"
_S_REL = _S + "officeDocument/relationships/"
_RENAMED_REL_TYPES = {
    _T_REL + "extended-properties": _S_REL + "extendedProperties",
    _T_REL + "custom-properties": _S_REL + "customProperties",
    _T + "package/2006/relationships/metadata/thumbnail": _S_REL + "metadata/thumbnail",
}
_RENAMED_REL_TYPES_BACK = {
    strict: transitional for transitional, strict in _RENAMED_REL_TYPES.items()
}
_PACKAGE_REL_NS = _T + "package/2006/relationships"
_CONTENT_TYPES_NS = _T + "package/2006/content-types"
_P = _T + "presentationml/2006/main"
_A = _T + "drawingml/2006/main"
_C = _T + "drawingml/2006/chart"
_DGM = _T + "drawingml/2006/diagram"
_M = _T + "officeDocument/2006/math"

# Lexical kinds: "pct" thousandths -> N%, "pct2" thousandths -> N% with at most
# two decimals (ST_FixedPercentage family), "pct0" thousandths -> whole N%,
# "whole" chart N% -> N in both directions, "onoff" on/off -> true/false.
_CHART_WHOLE_PERCENT = (
    "bubbleScale",
    "depthPercent",
    "gapDepth",
    "gapWidth",
    "hPercent",
    "holeSize",
    "lblOffset",
    "overlap",
    "secondPieSize",
    "thickness",
)
_PERCENT_ATTRIBUTES: dict[str, dict[str, dict[str, str]]] = {
    _P: {
        "by": {"x": "pct", "y": "pct"},
        "cMediaNode": {"vol": "pct2"},
        "cTn": {"spd": "pct", "accel": "pct2", "decel": "pct2"},
        "from": {"x": "pct", "y": "pct"},
        "hsl": {"s": "pct2", "l": "pct2"},
        "presentation": {"serverZoom": "pct"},
        "rCtr": {"x": "pct", "y": "pct"},
        "restoredLeft": {"sz": "pct2"},
        "restoredTop": {"sz": "pct2"},
        "rgb": {"r": "pct2", "g": "pct2", "b": "pct2"},
        "tav": {"tm": "pct2"},
        "tmPct": {"val": "pct"},
        "to": {"x": "pct", "y": "pct"},
    },
    _C: {name: {"val": "whole"} for name in _CHART_WHOLE_PERCENT},
    _A: {
        "alpha": {"val": "pct2"},
        "alphaBiLevel": {"thresh": "pct2"},
        "alphaMod": {"val": "pct"},
        "alphaModFix": {"amt": "pct"},
        "alphaOff": {"val": "pct2"},
        "alphaRepl": {"a": "pct2"},
        "biLevel": {"thresh": "pct2"},
        "blue": {"val": "pct"},
        "blueMod": {"val": "pct"},
        "blueOff": {"val": "pct"},
        "buSzPct": {"val": "pct0"},
        "camera": {"zoom": "pct"},
        "defRPr": {"baseline": "pct"},
        "ds": {"d": "pct", "sp": "pct"},
        "endParaRPr": {"baseline": "pct"},
        "fillRect": {"l": "pct", "t": "pct", "r": "pct", "b": "pct"},
        "fillToRect": {"l": "pct", "t": "pct", "r": "pct", "b": "pct"},
        "green": {"val": "pct"},
        "greenMod": {"val": "pct"},
        "greenOff": {"val": "pct"},
        "gs": {"pos": "pct2"},
        "hsl": {"sat": "pct2", "lum": "pct2"},
        "hslClr": {"sat": "pct", "lum": "pct"},
        "hueMod": {"val": "pct"},
        "lum": {"bright": "pct2", "contrast": "pct2", "val": "pct"},
        "lumMod": {"val": "pct"},
        "lumOff": {"val": "pct"},
        "miter": {"lim": "pct"},
        "normAutofit": {"fontScale": "pct", "lnSpcReduction": "pct"},
        "outerShdw": {"sx": "pct", "sy": "pct"},
        "rPr": {"baseline": "pct"},
        "red": {"val": "pct"},
        "redMod": {"val": "pct"},
        "redOff": {"val": "pct"},
        "reflection": {
            "stA": "pct2",
            "stPos": "pct2",
            "endA": "pct2",
            "endPos": "pct2",
            "sx": "pct",
            "sy": "pct",
        },
        "relOff": {"tx": "pct", "ty": "pct"},
        "rtl": {"val": "onoff"},
        "sat": {"val": "pct"},
        "satMod": {"val": "pct"},
        "satOff": {"val": "pct"},
        "scrgbClr": {"r": "pct", "g": "pct", "b": "pct"},
        "shade": {"val": "pct2"},
        "spcPct": {"val": "pct"},
        "srcRect": {"l": "pct", "t": "pct", "r": "pct", "b": "pct"},
        "tile": {"sx": "pct", "sy": "pct"},
        "tileRect": {"l": "pct", "t": "pct", "r": "pct", "b": "pct"},
        "tint": {"val": "pct2", "amt": "pct2"},
        "xfrm": {"sx": "pct", "sy": "pct"},
    },
    _DGM: {
        "prSet": {
            name: "pct"
            for name in (
                "custScaleX",
                "custScaleY",
                "custLinFactX",
                "custLinFactY",
                "custLinFactNeighborX",
                "custLinFactNeighborY",
                "custRadScaleRad",
                "custRadScaleInc",
            )
        }
    },
    _M: {
        name: {"val": "onoff"}
        for name in (
            "aln",
            "alnScr",
            "degHide",
            "diff",
            "dispDef",
            "grow",
            "hideBot",
            "hideLeft",
            "hideRight",
            "hideTop",
            "lit",
            "maxDist",
            "noBreak",
            "nor",
            "objDist",
            "opEmu",
            "plcHide",
            "show",
            "smallFrac",
            "strikeBLTR",
            "strikeH",
            "strikeTLBR",
            "strikeV",
            "subHide",
            "supHide",
            "transp",
            "wrapRight",
            "zeroAsc",
            "zeroDesc",
            "zeroWid",
        )
    },
}
# Part 4 §16.3-16.4 and §18.1.2: markup with no Strict representation.
_TRANSITIONAL_ONLY_ELEMENTS = {
    (_P, "webPr"),
    (_P, "htmlPubPr"),
    (_C, "legacyDrawingHF"),
}
_TRANSITIONAL_ONLY_ATTRIBUTES = {
    (_P, "oleObj"): frozenset({"spid"}),
    (_P, "control"): frozenset({"spid"}),
    (_P, "modifyVerifier"): frozenset(
        {
            "algIdExt",
            "algIdExtSource",
            "cryptAlgorithmClass",
            "cryptAlgorithmSid",
            "cryptAlgorithmType",
            "cryptProvider",
            "cryptProviderType",
            "cryptProviderTypeExt",
            "cryptProviderTypeExtSource",
            "hashData",
            "saltData",
            "spinCount",
        }
    ),
}
_VML_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.vmlDrawing"
_INTEGER = re.compile(r"[+-]?[0-9]+")
_PERCENT = re.compile(r"-?[0-9]+(?:\.[0-9]+)?%")
_ATTRIBUTE = re.compile(rb"""(\s+)([^\s=/>]+)(\s*=\s*)(["'])(.*?)\4""", re.DOTALL)


def normalize_conformance(conformance: object) -> str:
    """Return ``"transitional"`` or ``"strict"`` for a case-insensitive name."""
    if not isinstance(conformance, str) or (conformance.casefold() not in CONFORMANCE_CLASSES):
        raise ValueError("conformance must be 'transitional' or 'strict'")
    return conformance.casefold()


def normalize_compression_level(level: object) -> int:
    """Return a zip compression level from 0 (stored) to 9 (smallest)."""
    if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 9:
        raise ValueError("compression_level must be an integer from 0 to 9")
    return level


def rewrite_package(
    payload: bytes,
    *,
    conformance: str | None = None,
    compression_level: int | None = None,
) -> bytes:
    """Return ``payload`` in ``conformance`` with entries at ``compression_level``.

    ``conformance=None`` keeps every part's bytes; ``compression_level=None``
    keeps the package unchanged when no part changes, and otherwise deflates
    changed packages at level 1, the level ordinary saves use. Level 0 stores
    every entry; levels 1-9 deflate the entries the source deflated.
    """
    target = None if conformance is None else normalize_conformance(conformance)
    level = None if compression_level is None else normalize_compression_level(compression_level)
    with zipfile.ZipFile(io.BytesIO(payload)) as source:
        content_types = _content_types(source.read("[Content_Types].xml"))
        parts: list[tuple[zipfile.ZipInfo, bytes]] = []
        changed = False
        for info in source.infolist():
            data = source.read(info.filename)
            if target is not None and _is_xml_part(info.filename, content_types):
                rewritten = _rewrite_part(info.filename, data, target, content_types)
                changed = changed or rewritten != data
                data = rewritten
            parts.append((info, data))
    if not changed and level is None:
        return payload
    deflate_level = 1 if level is None else level
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as target_zip:
        for info, data in parts:
            entry = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            entry.external_attr = info.external_attr
            entry.create_system = info.create_system
            entry.compress_type = (
                zipfile.ZIP_STORED
                if deflate_level == 0 or info.compress_type == zipfile.ZIP_STORED
                else zipfile.ZIP_DEFLATED
            )
            target_zip.writestr(entry, data, compresslevel=deflate_level or None)
    return output.getvalue()


def _content_types(data: bytes) -> tuple[dict[str, str], dict[str, str]]:
    root = ET.fromstring(data)
    defaults = {
        item.get("Extension", "").casefold(): item.get("ContentType", "")
        for item in root.findall(f"{{{_CONTENT_TYPES_NS}}}Default")
    }
    overrides = {
        item.get("PartName", "").lstrip("/"): item.get("ContentType", "")
        for item in root.findall(f"{{{_CONTENT_TYPES_NS}}}Override")
    }
    return defaults, overrides


def _content_type(name: str, content_types: tuple[dict[str, str], dict[str, str]]):
    defaults, overrides = content_types
    if name in overrides:
        return overrides[name]
    return defaults.get(name.rsplit(".", 1)[-1].casefold(), "")


def _is_xml_part(name: str, content_types: tuple[dict[str, str], dict[str, str]]):
    if name == "[Content_Types].xml":
        return False
    if name.endswith(".rels"):
        return True
    content_type = _content_type(name, content_types).split(";", 1)[0].strip()
    return content_type.endswith("+xml") or content_type in {
        "application/xml",
        "text/xml",
    }


def _rewrite_part(
    name: str,
    data: bytes,
    target: str,
    content_types: tuple[dict[str, str], dict[str, str]],
) -> bytes:
    if target == "strict" and _content_type(name, content_types).startswith(_VML_CONTENT_TYPE):
        raise ValueError(f"Strict conformance cannot carry the VML part /{name}")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ValueError(f"part /{name} is not UTF-8 encoded")
    to_strict = target == "strict"
    namespaces = _TRANSITIONAL_TO_STRICT_NS if to_strict else _STRICT_TO_TRANSITIONAL_NS
    edits: list[tuple[int, int, bytes]] = []
    scopes: list[dict[str, str]] = [{}]
    parser = expat.ParserCreate()

    def start(qname: str, attributes: dict[str, str]) -> None:
        scope = dict(scopes[-1])
        for attribute, value in attributes.items():
            if attribute == "xmlns":
                scope[""] = value
            elif attribute.startswith("xmlns:"):
                scope[attribute[6:]] = value
        scopes.append(scope)
        prefix, _, local = qname.rpartition(":")
        namespace = scope.get(prefix, "")
        transitional_ns = _STRICT_TO_TRANSITIONAL_NS.get(namespace, namespace)
        offset = parser.CurrentByteIndex
        end = _tag_end(data, offset)
        rewrite = _attribute_rewriter(
            name, transitional_ns, local, len(scopes) == 2, namespaces, to_strict
        )
        tag = data[offset:end]
        new_tag = _ATTRIBUTE.sub(rewrite, tag)
        if (
            to_strict
            and transitional_ns == _P
            and local == "presentation"
            and len(scopes) == 2
            and b"conformance" not in _attribute_names(new_tag)
        ):
            new_tag = _insert_attribute(new_tag, b' conformance="strict"')
        if new_tag != tag:
            edits.append((offset, end, new_tag))

    parser.StartElementHandler = start
    parser.EndElementHandler = lambda _qname: scopes.pop()
    parser.Parse(data, True)
    if not edits:
        return data
    pieces: list[bytes] = []
    cursor = 0
    for begin, end, replacement in edits:
        pieces.extend((data[cursor:begin], replacement))
        cursor = end
    pieces.append(data[cursor:])
    return b"".join(pieces)


def _attribute_rewriter(
    part: str,
    namespace: str,
    local: str,
    is_root: bool,
    namespaces: dict[str, str],
    to_strict: bool,
) -> Callable[[re.Match[bytes]], bytes]:
    if to_strict and (namespace, local) in _TRANSITIONAL_ONLY_ELEMENTS:
        raise ValueError(
            f"Strict conformance has no {local} element (part /{part}); "
            "remove it before saving as Strict"
        )
    forbidden = _TRANSITIONAL_ONLY_ATTRIBUTES.get((namespace, local), frozenset())
    percent = _PERCENT_ATTRIBUTES.get(namespace, {}).get(local, {})
    is_relationship = namespace == _PACKAGE_REL_NS and local == "Relationship"
    is_graphic_data = namespace == _A and local == "graphicData"

    def rewrite(match: re.Match[bytes]) -> bytes:
        attribute = match.group(2).decode("utf-8", "surrogateescape")
        value = match.group(5).decode("utf-8", "surrogateescape")
        if (
            attribute == "xmlns"
            or attribute.startswith("xmlns:")
            or (is_graphic_data and attribute == "uri")
        ):
            new = namespaces.get(value, value)
        elif is_relationship and attribute == "Type":
            new = _relationship_type(value, to_strict)
        elif to_strict and attribute in forbidden:
            raise ValueError(
                f"Strict conformance has no {local}/@{attribute} (part /{part}); "
                "remove it before saving as Strict"
            )
        elif attribute in percent:
            new = _convert_value(part, local, attribute, value, percent[attribute], to_strict)
        elif is_root and namespace == _P and local == "presentation" and attribute == "conformance":
            if not to_strict and value == "strict":
                return b""
            new = "strict" if to_strict else value
        else:
            return match.group(0)
        if new == value:
            return match.group(0)
        return (
            b"".join((match.group(1), match.group(2), match.group(3), match.group(4)))
            + new.encode()
            + match.group(4)
        )

    return rewrite


def _relationship_type(value: str, to_strict: bool) -> str:
    if to_strict:
        if value in _RENAMED_REL_TYPES:
            return _RENAMED_REL_TYPES[value]
        if value.startswith(_T_REL):
            if value == _T_REL + "vmlDrawing":
                raise ValueError("Strict conformance cannot carry VML relationships")
            return _S_REL + value[len(_T_REL) :]
        return value
    if value in _RENAMED_REL_TYPES_BACK:
        return _RENAMED_REL_TYPES_BACK[value]
    if value.startswith(_S_REL):
        return _T_REL + value[len(_S_REL) :]
    return value


def _convert_value(
    part: str, element: str, attribute: str, value: str, kind: str, to_strict: bool
) -> str:
    if kind == "onoff":
        if to_strict:
            return {"on": "true", "off": "false"}.get(value, value)
        return value
    if to_strict and kind != "whole":
        if _INTEGER.fullmatch(value.strip()) is None:
            return value
        number = int(value)
        step = {"pct": 1, "pct2": 10, "pct0": 1000}[kind]
        if number % step:
            raise ValueError(
                f"{element}/@{attribute}={value} in part /{part} has no exact Strict "
                f"percentage (steps of {step / 1000:g}%); choose a representable value"
            )
        return f"{_plain(Decimal(number) / 1000)}%"
    if _PERCENT.fullmatch(value) is None:
        return value
    number = Decimal(value[:-1]) * (1 if kind == "whole" else 1000)
    if number != number.to_integral_value():
        return value
    return str(int(number))


def _plain(number: Decimal) -> str:
    text = format(number.normalize(), "f")
    return "0" if text in {"-0", "0"} else text


def _tag_end(data: bytes, start: int) -> int:
    quote = 0
    for index in range(start + 1, len(data)):
        byte = data[index]
        if quote:
            if byte == quote:
                quote = 0
        elif byte in (0x22, 0x27):
            quote = byte
        elif byte == 0x3E:
            return index + 1
    raise ValueError("unterminated start tag")


def _attribute_names(tag: bytes) -> set[bytes]:
    return {match.group(2) for match in _ATTRIBUTE.finditer(tag)}


def _insert_attribute(tag: bytes, attribute: bytes) -> bytes:
    close = 2 if tag.endswith(b"/>") else 1
    body = tag[:-close].rstrip()
    return body + attribute + tag[len(body) :]
