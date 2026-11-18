"""Structural linear-text and Presentation MathML exports of slide equations.

Display blocks retain separate rows and run overrides use MathML style scopes.
Matrix columns expose alignment, width and gap units; grow, box alignment and
break controls are exported explicitly. Frame-relative array distribution and
numbered break alignment have no faithful MathML mapping here and refuse by name.
Matrix baselines use first/last-row MathML baseline alignment. Explicit empty-cell
placeholders export squares, with hidden squares inside ``mphantom`` to retain space.
"""

from __future__ import annotations

import re
from dataclasses import replace
from xml.etree import ElementTree as ET

from . import math_text as math
from .math_text import (
    MATHML_NS,
    Accent,
    Bar,
    BorderBox,
    Box,
    Delimiter,
    Equation,
    EquationArray,
    Fraction,
    Function,
    GroupChr,
    LowerLimit,
    MathContent,
    MathNode,
    MathRun,
    Matrix,
    Nary,
    OpaqueMath,
    Phantom,
    PreSubSup,
    Radical,
    Sub,
    SubSup,
    Sup,
    UpperLimit,
    math_content,
)
from .render_refusals import RenderRefusal

_M = f"{{{math.M_NS}}}"
_A = f"{{{math.A_NS}}}"
_ZONE = f"{{{math.A14_NS}}}m"


_SPACING_ACCENTS = {
    "\u0300": "`",
    "\u0301": "´",
    "\u0302": "^",
    "\u0303": "~",
    "\u0304": "¯",
    "\u0305": "¯",
    "\u0306": "˘",
    "\u0307": "˙",
    "\u0308": "¨",
    "\u030c": "ˇ",
    "\u20d6": "←",
    "\u20d7": "→",
    "\u20e1": "↔",
}
_TOKEN = re.compile(r"\d+(?:\.\d+)?|[^\W\d_]|\s+|.", re.UNICODE)

_SUPPORTED_NODE_TYPES = (
    MathRun,
    Fraction,
    Radical,
    Nary,
    Matrix,
    Delimiter,
    Accent,
    Sub,
    Sup,
    SubSup,
    Function,
    Bar,
    Box,
    BorderBox,
    GroupChr,
    LowerLimit,
    UpperLimit,
    Phantom,
    EquationArray,
    PreSubSup,
)


class UnsupportedEquationError(RenderRefusal):
    """A construct cannot be exported, rendered or authored by the equation API.

    ``omml_name`` identifies the refused Office Math element without its namespace
    prefix. Raw OMML reading and serialization remain available for preservation.
    """

    def __init__(self, omml_name: str, capability: str = "supported export or mutation") -> None:
        self.omml_name = omml_name
        super().__init__(f"equation construct m:{omml_name} has no {capability}")


# A strict grammar protects against properties the public tree cannot represent.
_ARGUMENTS = {"e", "num", "den", "deg", "sub", "sup", "lim", "fName", "oMath"}
_NODES = set(math.MODELED_ELEMENTS)
_PROPERTIES = {
    "oMathParaPr": {"jc"},
    "rPr": {"sty"},
    "fPr": {"type"},
    "radPr": {"degHide"},
    "naryPr": {"chr", "limLoc", "subHide", "supHide", "grow"},
    "mPr": {"baseJc", "plcHide", "mcs", "cGpRule", "cGp", "cSp", "rSpRule", "rSp"},
    "mcPr": {"count", "mcJc"},
    "dPr": {"begChr", "endChr", "sepChr", "shp", "grow"},
    "accPr": {"chr"},
    "barPr": {"pos"},
    "boxPr": {"opEmu", "noBreak", "diff", "aln", "brk"},
    "borderBoxPr": {
        "hideTop",
        "hideBot",
        "hideLeft",
        "hideRight",
        "strikeH",
        "strikeV",
        "strikeBLTR",
        "strikeTLBR",
    },
    "groupChrPr": {"chr", "pos", "vertJc"},
    "phantPr": {"show", "zeroWid", "zeroAsc", "zeroDesc", "transp"},
    "eqArrPr": {"baseJc", "rSpRule", "rSp", "maxDist", "objDist"},
    **{
        f"{name}Pr": set()
        for name in (
            "sSub",
            "sSup",
            "sSubSup",
            "sPre",
            "func",
            "limLow",
            "limUpp",
        )
    },
}
_ENUM_PROPERTIES = {
    "jc": {"left", "right", "center", "centerGroup"},
    "sty": {"p", "b", "i", "bi"},
    "type": {"bar", "noBar", "skw", "lin"},
    "limLoc": {"undOvr", "subSup"},
    "shp": {"centered", "match"},
    "pos": {"top", "bot"},
    "vertJc": {"top", "bot"},
    "baseJc": {"top", "center", "bottom"},
    "mcJc": {"left", "center", "right"},
    "rSpRule": {"0", "1", "2", "3", "4"},
    "cGpRule": {"0", "1", "2", "3", "4"},
}
_BOOL_PROPERTIES = {
    "grow",
    "plcHide",
    "aln",
    "maxDist",
    "objDist",
    "degHide",
    "subHide",
    "supHide",
    "opEmu",
    "noBreak",
    "diff",
    "hideTop",
    "hideBot",
    "hideLeft",
    "hideRight",
    "strikeH",
    "strikeV",
    "strikeBLTR",
    "strikeTLBR",
    "show",
    "zeroWid",
    "zeroAsc",
    "zeroDesc",
    "transp",
}


def preflight_omml(zone: ET.Element) -> None:
    """Refuse source elements and properties not represented by the public tree."""

    def visit(element: ET.Element) -> None:
        name = element.tag.rsplit("}", 1)[-1]
        if element.tag == _ZONE:
            if element.attrib or len(element) != 1:
                raise UnsupportedEquationError("a14:m", "native rendering (attributes or children)")
            if element[0].tag not in {_M + "oMath", _M + "oMathPara"}:
                raise UnsupportedEquationError("a14:m", "native rendering (missing Office Math)")
        elif element.tag.startswith(_M):
            if name in _PROPERTIES:
                allowed = {_M + prop for prop in _PROPERTIES[name]}
                if name != "oMathParaPr":
                    allowed.add(_M + "ctrlPr")
            elif name in _ARGUMENTS:
                allowed = {_M + node for node in _NODES}
            elif name == "oMathPara":
                allowed = {_M + "oMathParaPr", _M + "oMath"}
            elif name == "r":
                allowed = {_M + "rPr", _M + "t", _A + "rPr"}
            elif name in _NODES:
                arguments = {
                    "f": {"num", "den"},
                    "rad": {"deg", "e"},
                    "nary": {"sub", "sup", "e"},
                    "m": {"mr"},
                    "d": {"e"},
                    "acc": {"e"},
                    "sSub": {"e", "sub"},
                    "sSup": {"e", "sup"},
                    "sSubSup": {"e", "sub", "sup"},
                    "sPre": {"e", "sub", "sup"},
                    "func": {"fName", "e"},
                    "bar": {"e"},
                    "box": {"e"},
                    "borderBox": {"e"},
                    "groupChr": {"e"},
                    "limLow": {"e", "lim"},
                    "limUpp": {"e", "lim"},
                    "phant": {"e"},
                    "eqArr": {"e"},
                }
                allowed = {_M + arg for arg in arguments[name]} | {_M + name + "Pr"}
            elif name in {"mr", "mcs", "mc", "ctrlPr"}:
                allowed = {
                    "mr": {_M + "e"},
                    "mcs": {_M + "mc"},
                    "mc": {_M + "mcPr"},
                    "ctrlPr": {_A + "rPr"},
                }[name]
            elif name == "t":
                allowed = set()
            elif name in set().union(*_PROPERTIES.values()) - {"mcs"}:
                allowed = set()
                value = element.get(_M + "val", "on")
                if (
                    name in _ENUM_PROPERTIES
                    and _M + "val" in element.attrib
                    and value not in _ENUM_PROPERTIES[name]
                ):
                    raise UnsupportedEquationError(name, f"native rendering for value {value!r}")
                if name in _BOOL_PROPERTIES and value not in {
                    "on",
                    "off",
                    "1",
                    "0",
                    "true",
                    "false",
                }:
                    raise UnsupportedEquationError(name, f"native rendering for value {value!r}")
                if (
                    name in {"chr", "begChr", "endChr", "sepChr"}
                    and _M + "val" in element.attrib
                    and len(value) > 1
                ):
                    raise UnsupportedEquationError(name, f"native rendering for value {value!r}")
                if name in {"rSp", "cGp", "cSp", "count"}:
                    maximum = 4_294_967_295 if name == "cSp" else 65_535
                    if not value.isdigit() or not 0 <= int(value) <= maximum:
                        raise UnsupportedEquationError(
                            name, f"native rendering for value {value!r}"
                        )
            else:
                raise UnsupportedEquationError(name, "native rendering")
            attributes = (
                {_M + "val"}
                if name
                not in _NODES
                | _ARGUMENTS
                | set(_PROPERTIES)
                | {"oMathPara", "mr", "mcs", "mc", "ctrlPr", "t"}
                else set()
            )
            if name == "t":
                attributes.add("{http://www.w3.org/XML/1998/namespace}space")
            if name == "brk":
                attributes = {_M + "alnAt"}
                alignment = element.get(_M + "alnAt")
                if alignment is not None and (
                    not alignment.isdigit() or not 1 <= int(alignment) <= 255
                ):
                    raise UnsupportedEquationError("brk", "native rendering of its alignment index")
            if set(element.attrib) - attributes:
                raise UnsupportedEquationError(name, "native rendering of its attributes")
            for child in element:
                if child.tag not in allowed:
                    child_name = child.tag.rsplit("}", 1)[-1]
                    raise UnsupportedEquationError(child_name, f"native rendering inside m:{name}")
        elif element.tag == _A + "rPr":
            if set(element.attrib) - {"lang", "b", "i", "sz", "dirty", "smtClean"}:
                raise UnsupportedEquationError("a:rPr", "native rendering of its properties")
            if any(child.tag not in {_A + "latin", _A + "solidFill"} for child in element):
                raise UnsupportedEquationError(
                    "a:rPr", "native rendering of its drawing properties"
                )
        elif element.tag == _A + "latin":
            if not element.get("typeface"):
                raise UnsupportedEquationError(
                    "a:latin", "native rendering of an empty font family"
                )
            if set(element.attrib) - {"typeface", "panose", "pitchFamily", "charset"}:
                raise UnsupportedEquationError("a:latin", "native rendering of its font properties")
        elif element.tag == _A + "solidFill":
            if element.attrib or len(element) != 1 or element[0].tag != _A + "srgbClr":
                raise UnsupportedEquationError("a:solidFill", "native rendering of a non-RGB color")
        elif element.tag == _A + "srgbClr":
            if (
                set(element.attrib) != {"val"}
                or not re.fullmatch(r"[0-9A-Fa-f]{6}", element.get("val", ""))
                or len(element)
            ):
                raise UnsupportedEquationError("a:srgbClr", "native rendering of its color")
        else:
            raise UnsupportedEquationError(name, "native rendering")
        for child in element:
            visit(child)

    visit(zone)
    for control in zone.iter(_M + "ctrlPr"):
        properties = control.find(_A + "rPr")
        if properties is None:
            continue
        family = properties.find(_A + "latin")
        if properties.find(_A + "solidFill") is not None or (
            family is not None and family.get("typeface") != "Cambria Math"
        ):
            raise UnsupportedEquationError(
                "ctrlPr", "native rendering of structural font or color overrides"
            )
    for matrix in zone.iter(_M + "m"):
        for name in ("baseJc", "plcHide"):
            if len(matrix.findall(_M + "mPr/" + _M + name)) > 1:
                raise UnsupportedEquationError(name, "matrix layout with duplicate declarations")
        rows = matrix.findall(_M + "mr")
        columns = len(rows[0].findall(_M + "e")) if rows else 0
        descriptors = matrix.findall(_M + "mPr/" + _M + "mcs/" + _M + "mc")
        count = 0
        for descriptor in descriptors:
            value = descriptor.find(_M + "mcPr/" + _M + "count")
            raw = "1" if value is None else value.get(_M + "val", "")
            if not raw.isdigit() or int(raw) < 1:
                raise UnsupportedEquationError("count", "native rendering of its matrix columns")
            count += int(raw)
        if descriptors and count != columns:
            raise UnsupportedEquationError("mcs", "native rendering of inconsistent column counts")
    for run in zone.iter(_M + "r"):
        sty = run.find(_M + "rPr/" + _M + "sty")
        style = None if sty is None else sty.get(_M + "val")
        drawing = run.find(_A + "rPr")
        if drawing is not None:
            expected = {"b": style in {"b", "bi"}, "i": style not in {"p", "b"}}
            for attr, enabled in expected.items():
                value = drawing.get(attr)
                if value is not None and value not in {"0", "1", "true", "false", "on", "off"}:
                    raise UnsupportedEquationError("a:rPr", "native rendering of its boolean style")
                if value is not None and (value in {"1", "true", "on"}) != enabled:
                    raise UnsupportedEquationError(
                        "a:rPr", "native rendering of conflicting math style"
                    )
    sizes = {node.get("sz") for node in zone.iter(_A + "rPr")}
    if any(
        size is not None and (not size.isdigit() or not 100 <= int(size) <= 400000)
        for size in sizes
    ):
        raise UnsupportedEquationError("a:rPr", "native rendering of its font size")


def _validate_content(
    content: MathContent,
    *,
    top_level: bool = True,
    array_row: bool = False,
) -> None:
    """Validate both representability and the formatting context of controls."""
    segments: list[list[MathNode]] = [[]]
    if top_level:
        for node in content:
            if isinstance(node, Box) and node.break_before and segments[-1]:
                segments.append([])
            segments[-1].append(node)
    isolated = {id(segment[0]) for segment in segments if len(segment) == 1} if top_level else set()
    alignment_markers = 0
    for node in content:
        if isinstance(node, OpaqueMath):
            if node.name == "m":
                # Preserve opaque matrices on read, but name their refused property
                # before a structured edit can discard it.
                preflight_omml(ET.fromstring(node.xml))
            raise UnsupportedEquationError(node.name)
        if type(node) not in _SUPPORTED_NODE_TYPES:
            raise UnsupportedEquationError(getattr(node, "omml_name", type(node).__name__))
        if isinstance(node, MathRun) and array_row:
            alignment_markers += node.text.count("&")
        if isinstance(node, Box):
            if node.break_alignment is not None:
                raise UnsupportedEquationError("brk", "supported layout of an alignment index")
            if node.break_before and node.no_break:
                raise UnsupportedEquationError("brk", "supported layout with noBreak")
            if node.break_before and not top_level:
                raise UnsupportedEquationError("brk", "supported layout in a nested argument")
            if node.alignment_point:
                if not array_row:
                    raise UnsupportedEquationError("aln", "supported layout outside an array row")
                if alignment_markers % 2:
                    raise UnsupportedEquationError(
                        "aln", "supported layout after an unmatched point"
                    )
                alignment_markers += 1
        if isinstance(node, EquationArray):
            if node.maximum_distribution and id(node) not in isolated:
                raise UnsupportedEquationError("maxDist", "supported layout in a nested argument")
            for row in node.rows:
                _validate_content(row, top_level=False, array_row=True)
        else:
            for child in node.children:
                _validate_content(child, top_level=False)


def validate_node(node: MathNode) -> None:
    """Validate a detached mutation target without assuming its eventual owner.

    A detached box may be a direct array alignment marker; full equation
    validation checks that placement before a supported paragraph write.
    """
    if isinstance(node, math.MathBlock):
        _validate_content(node.content)
    else:
        _validate_content((node,), array_row=isinstance(node, Box))


def validate_equation(equation: Equation) -> None:
    """Preflight the complete tree before supported export, rendering or mutation.

    Modeled constructs require a supported layout context as well as validated
    properties. Unknown nodes and nested layout controls refuse by OMML name
    before callers change a paragraph, queue an edit or emit output. This gate
    does not restrict the explicit raw-OMML preservation path.
    """
    if not isinstance(equation, Equation):
        raise TypeError("equation must be an Equation")
    if not equation.display and len(equation.blocks) != 1:
        raise UnsupportedEquationError("oMathPara", "inline export or rendering of multiple blocks")
    for block in equation.blocks:
        _validate_content(block)


def _linear_content(content: MathContent | None) -> str:
    parts: list[str] = []
    previous: MathNode | None = None
    for node in content or ():
        text = _linear_node(node)
        if not text:
            continue
        if (
            parts
            and not (isinstance(previous, MathRun) and isinstance(node, MathRun))
            and not parts[-1][-1].isspace()
            and not text[0].isspace()
        ):
            parts.append(" ")
        parts.append(text)
        previous = node
    return "".join(parts)


def _linear_flags(name: str, base: MathContent, flags: tuple[tuple[str, bool], ...]) -> str:
    enabled = ", ".join(flag for flag, value in flags if value)
    options = f"[{enabled}]" if enabled else ""
    return f"{name}{options}({_linear_content(base)})"


def _linear_rows(rows: tuple[tuple[MathContent, ...], ...]) -> str:
    return "; ".join(
        "[" + ", ".join(f"({_linear_content(cell)})" for cell in row) + "]" for row in rows
    )


def _linear_node(node: MathNode) -> str:
    if isinstance(node, MathRun):
        return node.text
    if isinstance(node, Fraction):
        numerator = _linear_content(node.numerator)
        denominator = _linear_content(node.denominator)
        if node.kind == "noBar":
            return f"stack(({numerator}); ({denominator}))"
        return f"({numerator})/({denominator})"
    if isinstance(node, Radical):
        base = _linear_content(node.base)
        if node.degree is None:
            return f"sqrt({base})"
        return f"root(({_linear_content(node.degree)}); ({base}))"
    if isinstance(node, Nary):
        operator = node.operator + ("[grow]" if node.grow else "")
        if node.limits == "undOvr":
            limits = [
                f"{name}=({_linear_content(content)})"
                for name, content in (("lower", node.lower), ("upper", node.upper))
                if content is not None
            ]
            if limits:
                operator += "[" + "; ".join(limits) + "]"
        else:
            if node.lower is not None:
                operator += f"_({_linear_content(node.lower)})"
            if node.upper is not None:
                operator += f"^({_linear_content(node.upper)})"
        return f"{operator}({_linear_content(node.base)})"
    if isinstance(node, Matrix):
        options = []
        if node.base_justification != "center":
            options.append(f"base_justification={node.base_justification!r}")
        if node.hide_placeholders is not None:
            options.append(f"hide_placeholders={node.hide_placeholders!r}")
        if any(value != "center" for value in node.column_alignments):
            options.append(f"column_alignments={node.column_alignments!r}")
        for name in (
            "column_gap_rule",
            "column_gap",
            "minimum_column_width",
            "row_spacing_rule",
            "row_spacing",
        ):
            if getattr(node, name):
                options.append(f"{name}={getattr(node, name)}")
        suffix = "[" + ", ".join(options) + "]" if options else ""
        return f"matrix{suffix}({_linear_rows(node.rows)})"
    if isinstance(node, Delimiter):
        elements = "; ".join(f"({_linear_content(item)})" for item in node.elements)
        return (
            f"delimiter(begin={node.begin!r}, end={node.end!r}, "
            f"separator={node.separator!r}, shape={str(node.shape)!r}"
            f"{', grow=False' if not node.grow else ''}; {elements})"
        )
    if isinstance(node, Accent):
        return f"accent({node.char!r}; ({_linear_content(node.base)}))"
    if isinstance(node, (Sub, Sup, SubSup)):
        text = f"({_linear_content(node.base)})"
        if not isinstance(node, Sup):
            text += f"_({_linear_content(node.sub)})"
        if not isinstance(node, Sub):
            text += f"^({_linear_content(node.sup)})"
        return text
    if isinstance(node, Function):
        name = _linear_content(node.name)
        if not node.name or not all(isinstance(item, MathRun) for item in node.name):
            name = f"({name})"
        return f"{name}({_linear_content(node.base)})"
    if isinstance(node, Bar):
        name = "overline" if node.position == "top" else "underline"
        return f"{name}({_linear_content(node.base)})"
    if isinstance(node, Box):
        text = _linear_flags(
            "box",
            node.base,
            (
                ("operator_emulation", node.operator_emulation),
                ("no_break", node.no_break),
                ("differential", node.differential),
                ("alignment_point", node.alignment_point),
                ("break_before", node.break_before),
            ),
        )
        if node.break_alignment is not None:
            text = f"break_alignment[{node.break_alignment}]({text})"
        return text
    if isinstance(node, BorderBox):
        return _linear_flags(
            "border_box",
            node.base,
            (
                ("hide_top", node.hide_top),
                ("hide_bottom", node.hide_bottom),
                ("hide_left", node.hide_left),
                ("hide_right", node.hide_right),
                ("strike_horizontal", node.strike_horizontal),
                ("strike_vertical", node.strike_vertical),
                ("strike_bottom_left_top_right", node.strike_bottom_left_top_right),
                ("strike_top_left_bottom_right", node.strike_top_left_bottom_right),
            ),
        )
    if isinstance(node, GroupChr):
        return (
            f"group_char(char={node.char!r}, position={node.position!r}, "
            f"baseline={node.vertical_justification!r}; ({_linear_content(node.base)}))"
        )
    if isinstance(node, (LowerLimit, UpperLimit)):
        name = "lower_limit" if isinstance(node, LowerLimit) else "upper_limit"
        return f"{name}(({_linear_content(node.base)}); ({_linear_content(node.limit)}))"
    if isinstance(node, Phantom):
        return _linear_flags(
            "phantom",
            node.base,
            (
                ("shown", node.show),
                ("hidden", not node.show),
                ("zero_width", node.zero_width),
                ("zero_ascent", node.zero_ascent),
                ("zero_descent", node.zero_descent),
                ("transparent", node.transparent),
            ),
        )
    if isinstance(node, EquationArray):
        options = (
            f"baseline={node.base_justification!r}, "
            f"row_spacing_rule={node.row_spacing_rule}, row_spacing={node.row_spacing}"
            + (", maximum_distribution=True" if node.maximum_distribution else "")
            + (", object_distribution=True" if node.object_distribution else "")
        )
        rows = tuple(_array_cells(row) for row in node.rows)
        return f"array[{options}]({_linear_rows(rows)})"
    if isinstance(node, PreSubSup):
        return (
            f"_({_linear_content(node.sub)})^({_linear_content(node.sup)})"
            f"({_linear_content(node.base)})"
        )
    raise UnsupportedEquationError(getattr(node, "omml_name", type(node).__name__))


def equation_to_linear_text(equation: Equation) -> str:
    """Export structure, not just OMML's run characters, as predictable linear text.

    Run text is unchanged (adjacent runs stay contiguous); structural neighbours
    receive a separating space. Bar, skewed and linear fractions all use
    ``(numerator)/(denominator)``; barless stacks use ``stack((upper); (lower))``.
    Roots use ``sqrt(base)`` or
    ``root((degree); (base))``. Scripts always parenthesize their arguments;
    prescripts precede the parenthesized base. N-ary bodies are parenthesized,
    with ``[lower=(...); upper=(...)]`` for under/over limits or ``_(...)^(...)``
    for script limits. Functions apply their name to a parenthesized argument,
    grouping structured names.

    Matrices and arrays contain bracketed rows separated by semicolons and
    parenthesized cells separated by commas; array ``&`` alignment markers split
    cells, preserving empty cells. Delimiters explicitly name their characters
    and shape, so absent fences/separators cannot collapse distinct arguments.
    Accent/group characters are repr-quoted; bars, limits, boxes and phantoms use
    named wrappers. Box/phantom flags and array layout properties are explicit.
    Run styling and equation-level size/display/justification are not text.
    Blocks are newline-separated; additional layout controls are named explicitly.
    This is a readable export, not a lossless serialization or a parser grammar.
    Unsupported content raises :class:`UnsupportedEquationError` before export.
    """
    validate_equation(equation)
    return "\n".join(_linear_content(block) for block in equation.blocks)


def _mml(name: str, attrs: dict[str, str] | None = None) -> ET.Element:
    return ET.Element(name, attrs or {})


def _mml_child(parent: ET.Element, name: str, text: str | None = None, **attrs: str) -> ET.Element:
    child = ET.SubElement(parent, name, attrs)
    if text is not None:
        child.text = text
    return child


def _mml_row(content: MathContent | None) -> ET.Element:
    row = _mml("mrow")
    for node in content or ():
        _mml_node(row, node)
    return row


def _mml_tokens(parent: ET.Element, run: MathRun, function_name: bool = False) -> None:
    attrs = {}
    if run.font is not None:
        attrs["fontfamily"] = run.font
    if run.color is not None:
        attrs["mathcolor"] = "#" + run.color
    if run.size is not None:
        attrs["mathsize"] = f"{run.size:g}pt"
    if attrs:
        parent = _mml_child(parent, "mstyle", **attrs)
    if function_name or (run.style == "p" and run.text.isalpha()):
        _mml_child(
            parent,
            "mi",
            run.text,
            **({} if len(run.text) > 1 else {"mathvariant": "normal"}),
        )
        return
    variant = {"b": "bold", "bi": "bold-italic", "p": "normal"}.get(run.style or "")
    for token in _TOKEN.findall(run.text):
        if token.isspace():
            continue
        if token[0].isdigit():
            _mml_child(parent, "mn", token)
        elif token.isalpha():
            attrs = {"mathvariant": variant} if variant else {}
            _mml_child(parent, "mi", token, **attrs)
        else:
            _mml_child(parent, "mo", token)


def _array_cells(content: MathContent) -> tuple[MathContent, ...]:
    """Office's odd/even ampersand alignment markers split equation-array columns."""
    cells: list[list[MathNode]] = [[]]
    for node in content:
        if isinstance(node, MathRun):
            parts = node.text.split("&")
            for index, part in enumerate(parts):
                if index:
                    cells.append([])
                if part:
                    cells[-1].append(replace(node, text=part))
        elif isinstance(node, Box) and node.alignment_point:
            cells.append([])
            cells[-1].append(replace(node, alignment_point=False))
        else:
            cells[-1].append(node)
    return tuple(math_content(cell) for cell in cells)


def _mml_node(parent: ET.Element, node: MathNode) -> None:
    if isinstance(node, MathRun):
        _mml_tokens(parent, node)
    elif isinstance(node, Fraction):
        if node.kind == "lin":
            row = _mml_child(parent, "mrow")
            row.append(_mml_row(node.numerator))
            _mml_child(row, "mo", "/")
            row.append(_mml_row(node.denominator))
            return
        attrs = {"noBar": {"linethickness": "0"}, "skw": {"bevelled": "true"}}.get(node.kind, {})
        frac = _mml_child(parent, "mfrac", **attrs)
        frac.append(_mml_row(node.numerator))
        frac.append(_mml_row(node.denominator))
    elif isinstance(node, Radical):
        if node.degree is None:
            _mml_child(parent, "msqrt").append(_mml_row(node.base))
        else:
            root = _mml_child(parent, "mroot")
            root.append(_mml_row(node.base))
            root.append(_mml_row(node.degree))
    elif isinstance(node, Nary):
        row = _mml_child(parent, "mrow")
        operator = _mml(
            "mo",
            {
                "largeop": "true",
                "movablelimits": "false",
                "stretchy": "true" if node.grow else "false",
            },
        )
        operator.text = node.operator
        lower, upper = node.lower, node.upper
        if lower is None and upper is None:
            row.append(operator)
        else:
            if node.limits == "undOvr":
                name = "munderover" if lower and upper else ("munder" if lower else "mover")
            else:
                name = "msubsup" if lower and upper else ("msub" if lower else "msup")
            script = _mml_child(row, name)
            script.append(operator)
            for limit in (lower, upper):
                if limit is not None:
                    script.append(_mml_row(limit))
        row.append(_mml_row(node.base))
    elif isinstance(node, Matrix):
        gap = {0: "1em", 1: "1.5em", 2: "2em"}.get(node.column_gap_rule)
        if gap is None:
            gap = (
                f"{node.column_gap / 20:g}pt"
                if node.column_gap_rule == 3
                else f"{node.column_gap / 2:g}em"
            )
        attrs = {}
        if node.base_justification != "center":
            attrs["align"] = "baseline 1" if node.base_justification == "top" else "baseline -1"
        if any(value != "center" for value in node.column_alignments):
            attrs["columnalign"] = " ".join(node.column_alignments)
        if node.column_gap_rule or node.column_gap:
            attrs["columnspacing"] = gap
        if node.minimum_column_width:
            attrs["columnwidth"] = f"{node.minimum_column_width / 20:g}pt"
        if node.row_spacing_rule or node.row_spacing:
            attrs["rowspacing"] = _mml_row_spacing(node.row_spacing_rule, node.row_spacing)
        table = _mml_child(parent, "mtable", **attrs)
        for cells in node.rows:
            row = _mml_child(table, "mtr")
            for cell in cells:
                holder = _mml_child(row, "mtd")
                if not cell and node.hide_placeholders is not None:
                    target = _mml_child(holder, "mphantom") if node.hide_placeholders else holder
                    _mml_child(target, "mo", "□")
                else:
                    holder.append(_mml_row(cell))
    elif isinstance(node, Delimiter):
        row = _mml_child(parent, "mrow")
        if node.begin:
            _mml_child(row, "mo", node.begin, fence="true", stretchy=str(node.grow).lower())
        for index, element in enumerate(node.elements):
            if index and node.separator:
                _mml_child(
                    row, "mo", node.separator, separator="true", stretchy=str(node.grow).lower()
                )
            row.append(_mml_row(element))
        if node.end:
            _mml_child(row, "mo", node.end, fence="true", stretchy=str(node.grow).lower())
    elif isinstance(node, Accent):
        over = _mml_child(parent, "mover", accent="true")
        over.append(_mml_row(node.base))
        _mml_child(over, "mo", _SPACING_ACCENTS.get(node.char, node.char), stretchy="false")
    elif isinstance(node, (Sub, Sup, SubSup)):
        name = {Sub: "msub", Sup: "msup", SubSup: "msubsup"}[type(node)]
        script = _mml_child(parent, name)
        script.append(_mml_row(node.base))
        if not isinstance(node, Sup):
            script.append(_mml_row(node.sub))
        if not isinstance(node, Sub):
            script.append(_mml_row(node.sup))
    elif isinstance(node, Function):
        row = _mml_child(parent, "mrow")
        for name_node in node.name:
            if isinstance(name_node, MathRun):
                _mml_tokens(row, name_node, function_name=True)
            else:
                _mml_node(row, name_node)
        _mml_child(row, "mo", "\u2061")
        row.append(_mml_row(node.base))
    elif isinstance(node, Bar):
        wrap = _mml_child(
            parent,
            "mover" if node.position == "top" else "munder",
            **({"accent": "true"} if node.position == "top" else {"accentunder": "true"}),
        )
        wrap.append(_mml_row(node.base))
        _mml_child(wrap, "mo", "¯" if node.position == "top" else "_", stretchy="true")
    elif isinstance(node, Box):
        if node.break_alignment is not None:
            raise UnsupportedEquationError("brk", "MathML export of an alignment index")
        row = _mml_child(parent, "mrow")
        if node.break_before:
            _mml_child(row, "mspace", linebreak="newline")
        if node.alignment_point:
            _mml_child(row, "malignmark", edge="left")
        row.append(_mml_row(node.base))
    elif isinstance(node, BorderBox):
        notation = [
            side
            for side, hidden in (
                ("top", node.hide_top),
                ("bottom", node.hide_bottom),
                ("left", node.hide_left),
                ("right", node.hide_right),
            )
            if not hidden
        ]
        notation.extend(
            mark
            for mark, strike in (
                ("horizontalstrike", node.strike_horizontal),
                ("verticalstrike", node.strike_vertical),
                ("updiagonalstrike", node.strike_bottom_left_top_right),
                ("downdiagonalstrike", node.strike_top_left_bottom_right),
            )
            if strike
        )
        _mml_child(parent, "menclose", notation=" ".join(notation)).append(_mml_row(node.base))
    elif isinstance(node, GroupChr):
        if node.position == node.vertical_justification:
            # The grouping character owns the baseline; its argument is a limit.
            wrap = _mml_child(parent, "munder" if node.position == "top" else "mover")
            _mml_child(wrap, "mo", node.char, stretchy="false")
            wrap.append(_mml_row(node.base))
        else:
            name = "mover" if node.position == "top" else "munder"
            wrap = _mml_child(
                parent,
                name,
                **({"accent": "true"} if node.position == "top" else {"accentunder": "true"}),
            )
            wrap.append(_mml_row(node.base))
            _mml_child(wrap, "mo", node.char, stretchy="true")
    elif isinstance(node, (LowerLimit, UpperLimit)):
        wrap = _mml_child(parent, "munder" if isinstance(node, LowerLimit) else "mover")
        wrap.append(_mml_row(node.base))
        wrap.append(_mml_row(node.limit))
    elif isinstance(node, Phantom):
        attrs = {}
        for attr, dimension in (
            ("zero_width", "width"),
            ("zero_ascent", "height"),
            ("zero_descent", "depth"),
        ):
            if getattr(node, attr):
                attrs[dimension] = "0"
        holder = _mml_child(parent, "mpadded", **attrs) if attrs else parent
        if not node.show:
            holder = _mml_child(holder, "mphantom")
        holder.append(_mml_row(node.base))
    elif isinstance(node, EquationArray):
        if node.maximum_distribution or node.object_distribution:
            name = "maxDist" if node.maximum_distribution else "objDist"
            raise UnsupportedEquationError(name, "MathML export of frame-relative distribution")
        spacing = _mml_row_spacing(node.row_spacing_rule, node.row_spacing)
        table = _mml_child(
            parent,
            "mtable",
            align=node.base_justification,
            columnalign=(
                " ".join(
                    "right" if column % 2 == 0 else "left"
                    for column in range(max(len(_array_cells(row)) for row in node.rows))
                )
                if any(len(_array_cells(row)) > 1 for row in node.rows)
                else "center"
            ),
            rowspacing=spacing,
        )
        for content in node.rows:
            row = _mml_child(table, "mtr")
            for cell in _array_cells(content):
                _mml_child(row, "mtd").append(_mml_row(cell))
    elif isinstance(node, PreSubSup):
        wrap = _mml_child(parent, "mmultiscripts")
        wrap.append(_mml_row(node.base))
        _mml_child(wrap, "mprescripts")
        wrap.append(_mml_row(node.sub))
        wrap.append(_mml_row(node.sup))
    else:  # pragma: no cover - public exports preflight the complete tree
        raise UnsupportedEquationError(
            getattr(node, "omml_name", type(node).__name__), "MathML export"
        )


def _mml_row_spacing(rule: int, spacing: int) -> str:
    return {0: "1ex", 1: "1.5ex", 2: "2ex"}.get(rule) or (
        f"{spacing}pt" if rule == 3 else f"{spacing / 2:g}ex"
    )


def equation_to_mathml(equation: Equation) -> str:
    """Presentation MathML for ``equation``."""
    try:
        validate_equation(equation)
    except UnsupportedEquationError as error:
        # Keep the existing ValueError message contract while naming the refusal.
        raise UnsupportedEquationError(error.omml_name, "MathML export") from None
    math = _mml(
        "math",
        {"xmlns": MATHML_NS, "display": "block" if equation.display else "inline"},
    )
    if len(equation.blocks) == 1:
        math.append(_mml_row(equation.blocks[0]))
    else:
        table = _mml_child(
            math,
            "mtable",
            columnalign="left"
            if equation.justification in {None, "left", "centerGroup"}
            else equation.justification,
        )
        for block in equation.blocks:
            _mml_child(_mml_child(table, "mtr"), "mtd").append(_mml_row(block))
    return ET.tostring(math, encoding="unicode")
