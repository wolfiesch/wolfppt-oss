"""Ordered slide paragraph equations, queued through the existing text-frame writer.

Ordinary runs keep their native run indexes. Equation positions count ordinary
content children, so changing an equation never rewrites adjacent run formatting.
Matrix ``baseJc`` and ``plcHide`` read as structured declarations. Center and absent
placeholder controls keep legacy serialization; explicit booleans write on/off.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any
from xml.etree import ElementTree as ET

from .math_text import (
    _BORDER_FLAGS,
    _CAMBRIA_MATH,
    _PHANTOM_FLAGS,
    A14_NS,
    A_NS,
    M_NS,
    MC_NS,
    P_NS,
    RUN_STYLES,
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
    MathBlock,
    MathContent,
    MathDelimiterShape,
    MathElement,
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
    _is_slide_shape,
    _local,
    _m,
    _run_segments,
    _set,
    _shape_candidates,
    _shape_id,
    _to_plain,
    _to_styled,
    math_content,
)


def validate_matrix_properties(node: Matrix) -> None:
    """Validate newly modeled declarations before authoring or mutation."""
    from .math_mathml import UnsupportedEquationError

    if node.base_justification not in ("top", "center", "bottom"):
        raise UnsupportedEquationError("baseJc", "matrix baseline justification")
    if node.hide_placeholders is not None and type(node.hide_placeholders) is not bool:
        raise UnsupportedEquationError("plcHide", "matrix placeholder visibility")


@dataclass(frozen=True)
class ParagraphEquations:
    """Equation zones anchored before an ordinary run, break, or field."""

    slots: tuple[tuple[int, Equation], ...]
    replace_text: bool = False


def _saved_paragraph(paragraph: Any) -> ET.Element | None:
    from .text_facade_xml_inspection import _shape_text_part_root

    shape = paragraph._shape
    if not getattr(shape._slide._presentation, "path", None) or not shape._slide.partname:
        return None
    root = _shape_text_part_root(shape)
    for candidate in _shape_candidates(root):
        if str(_shape_id(candidate)[0]) == str(shape._payload.get("id")):
            body = candidate.find(f"{{{P_NS}}}txBody")
            items = [] if body is None else body.findall(f"{{{A_NS}}}p")
            return items[paragraph._index] if paragraph._index < len(items) else None
    return None


def ordinary_content(paragraph: Any) -> list[str]:
    """Exclude native summary math runs without changing native edit indexes."""
    from .shape_payloads import _shape_paragraph_runs

    shape = paragraph._shape
    values = _shape_paragraph_runs(shape)[paragraph._index]
    presentation = shape._slide._presentation
    key = (shape._slide._index, shape._index, paragraph._index)
    if key in presentation._paragraph_text_edits or key in presentation._paragraph_clear_edits:
        return list(values)
    element = _saved_paragraph(paragraph)
    if element is None:
        return list(values)
    native_runs = list(element.iter())
    native_runs = [node for node in native_runs if node.tag.rsplit("}", 1)[-1] == "r"]
    positions = {id(node): index for index, node in enumerate(native_runs)}
    ordinary = [
        values[positions[id(child)]]
        for child in element
        if child.tag == f"{{{A_NS}}}r" and positions[id(child)] < len(values)
    ]
    ordinary.extend(values[len(native_runs) :])
    return ordinary


def paragraph_plan(paragraph: Any) -> ParagraphEquations:
    pending = paragraph._shape._payload.get("_equations", {})
    if paragraph._index in pending:
        value = pending[paragraph._index]
        if isinstance(value, ParagraphEquations):
            return value
        return ParagraphEquations(() if value is None else ((0, value),), value is not None)
    element = _saved_paragraph(paragraph)
    if element is None:
        return ParagraphEquations(())
    slots = []
    position = 0
    for child in element:
        if child.tag == f"{{{A14_NS}}}m":
            slots.append((position, equation_from_omml(child)))
        elif child.tag == f"{{{MC_NS}}}AlternateContent":
            # Prefer the supported branch; a fallback is not a second equation.
            choice = child.find(f"{{{MC_NS}}}Choice")
            branch = child if choice is None else choice
            slots.extend(
                (position, equation_from_omml(zone)) for zone in branch.iter(f"{{{A14_NS}}}m")
            )
        elif child.tag in {f"{{{A_NS}}}{name}" for name in ("r", "br", "fld")}:
            position += 1
    return ParagraphEquations(tuple(slots))


def _preflight_matrix_sources(plan: ParagraphEquations) -> None:
    """Do not discard unmodeled matrix declarations during a paragraph edit."""
    from .math_mathml import preflight_omml

    def visit(content: MathContent) -> None:
        for node in content:
            if isinstance(node, OpaqueMath) and node.name == "m":
                preflight_omml(ET.fromstring(node.xml))
            for child in node.children:
                visit(child)

    for _, equation in plan.slots:
        for content in equation.blocks:
            visit(content)


def paragraph_content(paragraph: Any) -> tuple[str | Equation, ...]:
    """Read ordinary text and equation trees in their paragraph order."""
    from .shape_payloads import _shape_paragraph_line_breaks

    shape = paragraph._shape
    plan = paragraph_plan(paragraph)
    ordinary = ordinary_content(paragraph)
    breaks = _shape_paragraph_line_breaks(shape)[paragraph._index]
    for index in sorted(breaks, reverse=True):
        ordinary.insert(index, "\v")
    result = []
    slots = list(plan.slots)
    for position in range(len(ordinary) + 1):
        result.extend(equation for slot, equation in slots if slot == position)
        if position < len(ordinary):
            result.append(ordinary[position])
    result.extend(equation for slot, equation in slots if slot > len(ordinary))
    return tuple(result)


def _queue(paragraph: Any, plan: ParagraphEquations) -> None:
    shape = paragraph._shape
    if not _is_slide_shape(shape):
        from .math_mathml import UnsupportedEquationError

        raise UnsupportedEquationError("equation editing requires a top-level slide text shape")
    pending = shape._payload.setdefault("_equations", {})
    pending[paragraph._index] = plan
    shape._slide._presentation._queue_text_frame_advanced(
        shape._slide._index, shape._index, "equations", dict(pending)
    )


def assign_equation(paragraph: Any, equation: Equation | None) -> None:
    """Replace a display paragraph; replace only its first zone for inline math.

    Explicit OpaqueMath serialization remains a preservation API. New ordered
    insertion and indexed edits use strict validation; rendering/export always
    refuse opaque content rather than inventing an interpretation.
    """
    from .shape_payloads import (
        _shape_paragraph_line_breaks,
        _shape_paragraph_runs,
        _sync_shape_text_from_paragraph_runs,
    )

    if equation is not None and not isinstance(equation, Equation):
        raise TypeError(f"equation must be an Equation, got {type(equation).__name__}")
    if not _is_slide_shape(paragraph._shape):
        from .math_mathml import UnsupportedEquationError

        raise UnsupportedEquationError("equation editing requires a top-level slide text shape")
    old = paragraph_plan(paragraph)
    _preflight_matrix_sources(old)
    if equation is None:
        plan = ParagraphEquations((), old.replace_text)
    elif equation.display:
        # Empty paragraphs need only the equation edit. Rewriting empty text
        # adds a native package pass and changes otherwise stable fixture bytes.
        shape = paragraph._shape
        runs = _shape_paragraph_runs(shape)
        breaks = _shape_paragraph_line_breaks(shape)
        has_content = bool(runs[paragraph._index] or breaks[paragraph._index])
        runs[paragraph._index] = []
        breaks[paragraph._index] = []
        from .text_facade_queue import _queue_paragraph_state

        _sync_shape_text_from_paragraph_runs(shape, runs)
        if has_content:
            _queue_paragraph_state(shape, paragraph._index)
        plan = ParagraphEquations(((0, equation),), True)
    else:
        slots = list(old.slots)
        if slots:
            slots[0] = (slots[0][0], equation)
        else:
            position = sum(isinstance(item, str) for item in paragraph_content(paragraph))
            slots.append((position, equation))
        plan = ParagraphEquations(tuple(slots), old.replace_text)
    _queue(paragraph, plan)


def insert_equation(paragraph: Any, equation: Equation, index: int | None = None) -> None:
    """Insert before ``content_runs[index]``; omit index to append."""
    from .math_mathml import validate_equation

    validate_equation(equation)
    _preflight_matrix_sources(paragraph_plan(paragraph))
    content = paragraph_content(paragraph)
    if index is None:
        index = len(content)
    if type(index) is not int or not 0 <= index <= len(content):
        raise IndexError("content run index out of range")
    position = sum(isinstance(item, str) for item in content[:index])
    equation_index = sum(isinstance(item, Equation) for item in content[:index])
    old = paragraph_plan(paragraph)
    slots = list(old.slots)
    slots.insert(equation_index, (position, equation))
    _queue(paragraph, ParagraphEquations(tuple(slots), old.replace_text))


def edit_equation(paragraph: Any, index: int, equation: Equation | None) -> None:
    """Replace/remove the equation at its equation-only index."""
    from .math_mathml import validate_equation

    if equation is not None:
        validate_equation(equation)
    old = paragraph_plan(paragraph)
    _preflight_matrix_sources(old)
    if type(index) is not int or not 0 <= index < len(old.slots):
        raise IndexError("equation index out of range")
    slots = list(old.slots)
    if equation is None:
        del slots[index]
    else:
        slots[index] = (slots[index][0], equation)
    _queue(paragraph, ParagraphEquations(tuple(slots), old.replace_text))


def apply_paragraph_plan(paragraph: ET.Element, plan: ParagraphEquations) -> None:
    for child in list(paragraph):
        if (
            child.tag == f"{{{A14_NS}}}m"
            or (
                child.tag == f"{{{MC_NS}}}AlternateContent"
                and next(child.iter(f"{{{A14_NS}}}m"), None) is not None
            )
            or (plan.replace_text and child.tag == f"{{{A_NS}}}r" and not "".join(child.itertext()))
        ):
            paragraph.remove(child)
    ordinary = [
        child
        for child in paragraph
        if child.tag in {f"{{{A_NS}}}{name}" for name in ("r", "br", "fld")}
    ]
    end = paragraph.find(f"{{{A_NS}}}endParaRPr")
    for position, equation in plan.slots:
        anchor = ordinary[position] if position < len(ordinary) else end
        if anchor is None:
            paragraph.append(equation.to_omml())
        else:
            paragraph.insert(list(paragraph).index(anchor), equation.to_omml())


# --- OMML writing -----------------------------------------------------------------------


def _ctrl_pr(parent: ET.Element) -> None:
    ctrl = ET.SubElement(parent, _m("ctrlPr"))
    _run_drawing_properties(ctrl, None)


def _run_drawing_properties(
    parent: ET.Element,
    style: str | None,
    node: MathRun | None = None,
) -> None:
    attrs = {"lang": "en-US"}
    if style in ("b", "bi"):
        attrs["b"] = "1"
    attrs["i"] = "0" if style in ("p", "b") else "1"
    if node is not None and node.size is not None:
        attrs["sz"] = str(round(node.size * 100))
    rpr = ET.SubElement(parent, f"{{{A_NS}}}rPr", attrs)
    if node is not None and node.color is not None:
        fill = ET.SubElement(rpr, f"{{{A_NS}}}solidFill")
        ET.SubElement(fill, f"{{{A_NS}}}srgbClr", {"val": node.color})
    font = _CAMBRIA_MATH if node is None or node.font is None else {"typeface": node.font}
    ET.SubElement(rpr, f"{{{A_NS}}}latin", font)


def _val(parent: ET.Element, name: str, value: str) -> None:
    ET.SubElement(parent, _m(name), {_m("val"): str(value)})


def _write_content(parent: ET.Element, content: MathContent) -> None:
    for node in content:
        _write_node(parent, node)


def _arg(parent: ET.Element, name: str, content: MathContent | None) -> None:
    _write_content(ET.SubElement(parent, _m(name)), content or ())


def _write_node(parent: ET.Element, node: MathNode) -> None:
    if isinstance(node, MathRun):
        for segment in _run_segments(_to_styled(node.text, node.style)):
            run = ET.SubElement(parent, _m("r"))
            if node.style is not None:
                _val(ET.SubElement(run, _m("rPr")), "sty", node.style)
            _run_drawing_properties(run, node.style, node)
            ET.SubElement(run, _m("t")).text = segment
    elif isinstance(node, Fraction):
        element = ET.SubElement(parent, _m("f"))
        props = ET.SubElement(element, _m("fPr"))
        if node.kind != "bar":
            _val(props, "type", node.kind)
        _ctrl_pr(props)
        _arg(element, "num", node.numerator)
        _arg(element, "den", node.denominator)
    elif isinstance(node, Radical):
        element = ET.SubElement(parent, _m("rad"))
        props = ET.SubElement(element, _m("radPr"))
        if node.degree is None:
            _val(props, "degHide", "on")
        _ctrl_pr(props)
        _arg(element, "deg", node.degree)
        _arg(element, "e", node.base)
    elif isinstance(node, Nary):
        element = ET.SubElement(parent, _m("nary"))
        props = ET.SubElement(element, _m("naryPr"))
        if node.operator != "∫":
            _val(props, "chr", node.operator)
        _val(props, "limLoc", node.limits)
        if node.grow:
            _val(props, "grow", "on")
        if node.lower is None:
            _val(props, "subHide", "on")
        if node.upper is None:
            _val(props, "supHide", "on")
        _ctrl_pr(props)
        _arg(element, "sub", node.lower)
        _arg(element, "sup", node.upper)
        _arg(element, "e", node.base)
    elif isinstance(node, Matrix):
        element = ET.SubElement(parent, _m("m"))
        props = ET.SubElement(element, _m("mPr"))
        if node.base_justification != "center":
            _val(props, "baseJc", node.base_justification)
        if node.hide_placeholders is not None:
            _val(props, "plcHide", "on" if node.hide_placeholders else "off")
        for attr, prop in (
            ("row_spacing_rule", "rSpRule"),
            ("column_gap_rule", "cGpRule"),
            ("row_spacing", "rSp"),
            ("minimum_column_width", "cSp"),
            ("column_gap", "cGp"),
        ):
            if getattr(node, attr):
                _val(props, prop, str(getattr(node, attr)))
        columns = ET.SubElement(props, _m("mcs"))
        start = 0
        while start < len(node.column_alignments):
            alignment = node.column_alignments[start]
            end = start + 1
            while (
                end < len(node.column_alignments)
                and end - start < 255
                and node.column_alignments[end] == alignment
            ):
                end += 1
            column_props = ET.SubElement(ET.SubElement(columns, _m("mc")), _m("mcPr"))
            _val(column_props, "count", str(end - start))
            _val(column_props, "mcJc", alignment)
            start = end
        _ctrl_pr(props)
        for row in node.rows:
            row_element = ET.SubElement(element, _m("mr"))
            for cell in row:
                _arg(row_element, "e", cell)
    elif isinstance(node, Delimiter):
        element = ET.SubElement(parent, _m("d"))
        props = ET.SubElement(element, _m("dPr"))
        if node.begin != "(":
            _val(props, "begChr", node.begin)
        if node.separator != "|":
            _val(props, "sepChr", node.separator)
        if node.end != ")":
            _val(props, "endChr", node.end)
        if not node.grow:
            _val(props, "grow", "off")
        if node.shape is not MathDelimiterShape.CENTERED:
            _val(props, "shp", node.shape)
        _ctrl_pr(props)
        for item in node.elements:
            _arg(element, "e", item)
    elif isinstance(node, Accent):
        element = ET.SubElement(parent, _m("acc"))
        props = ET.SubElement(element, _m("accPr"))
        _val(props, "chr", node.char)
        _ctrl_pr(props)
        _arg(element, "e", node.base)
    elif isinstance(node, (Sub, Sup, SubSup)):
        name = node.omml_name
        element = ET.SubElement(parent, _m(name))
        _ctrl_pr(ET.SubElement(element, _m(f"{name}Pr")))
        _arg(element, "e", node.base)
        if not isinstance(node, Sup):
            _arg(element, "sub", node.sub)
        if not isinstance(node, Sub):
            _arg(element, "sup", node.sup)
    elif isinstance(node, Function):
        element = ET.SubElement(parent, _m("func"))
        _ctrl_pr(ET.SubElement(element, _m("funcPr")))
        _arg(element, "fName", node.name)
        _arg(element, "e", node.base)
    elif isinstance(
        node,
        (
            Bar,
            Box,
            BorderBox,
            GroupChr,
            LowerLimit,
            UpperLimit,
            Phantom,
            EquationArray,
            PreSubSup,
        ),
    ):
        name = node.omml_name
        element = ET.SubElement(parent, _m(name))
        props = ET.SubElement(element, _m(f"{name}Pr"))
        if isinstance(node, Bar):
            _val(props, "pos", "bot" if node.position == "bottom" else "top")
        elif isinstance(node, Box):
            for attr, prop in (
                ("operator_emulation", "opEmu"),
                ("no_break", "noBreak"),
                ("differential", "diff"),
            ):
                if getattr(node, attr):
                    _val(props, prop, "on")
            if node.break_before:
                attrs = (
                    {} if node.break_alignment is None else {_m("alnAt"): str(node.break_alignment)}
                )
                ET.SubElement(props, _m("brk"), attrs)
            if node.alignment_point:
                _val(props, "aln", "on")
        elif isinstance(node, BorderBox):
            for attr, prop in _BORDER_FLAGS:
                if getattr(node, attr):
                    _val(props, prop, "on")
        elif isinstance(node, GroupChr):
            _val(props, "chr", node.char)
            _val(props, "pos", "bot" if node.position == "bottom" else "top")
            _val(
                props,
                "vertJc",
                "bot" if node.vertical_justification == "bottom" else "top",
            )
        elif isinstance(node, Phantom):
            for attr, prop in _PHANTOM_FLAGS:
                _val(props, prop, "on" if getattr(node, attr) else "off")
        elif isinstance(node, EquationArray):
            _val(props, "baseJc", node.base_justification)
            if node.maximum_distribution:
                _val(props, "maxDist", "on")
            if node.object_distribution:
                _val(props, "objDist", "on")
            _val(props, "rSpRule", str(node.row_spacing_rule))
            _val(props, "rSp", str(node.row_spacing))
        _ctrl_pr(props)
        if isinstance(node, EquationArray):
            for row in node.rows:
                _arg(element, "e", row)
        elif isinstance(node, PreSubSup):
            _arg(element, "sub", node.sub)
            _arg(element, "sup", node.sup)
            _arg(element, "e", node.base)
        else:
            _arg(element, "e", node.base)
            if isinstance(node, (LowerLimit, UpperLimit)):
                _arg(element, "lim", node.limit)
    elif isinstance(node, OpaqueMath):
        parent.append(ET.fromstring(node.xml))
    else:  # pragma: no cover - math_content admits only node types
        raise TypeError(type(node).__name__)


def equation_to_omml(equation: Equation) -> ET.Element:
    """Build native OMML, inheriting size without replacing explicit run overrides."""
    if not equation.display and len(equation.blocks) != 1:
        from .math_mathml import UnsupportedEquationError

        raise UnsupportedEquationError("oMathPara", "multiple blocks require display math")
    zone = ET.Element(f"{{{A14_NS}}}m")
    if equation.display:
        holder = ET.SubElement(zone, _m("oMathPara"))
        if equation.justification is not None:
            _val(ET.SubElement(holder, _m("oMathParaPr")), "jc", equation.justification)
    else:
        holder = zone
    for block in equation.blocks:
        _write_content(ET.SubElement(holder, _m("oMath")), block)
    if equation.size is not None:
        for properties in zone.iter(f"{{{A_NS}}}rPr"):
            if properties.get("sz") is None:
                properties.set("sz", str(round(equation.size * 100)))
    return zone


# --- OMML reading -----------------------------------------------------------------------


def _on(element: ET.Element | None) -> bool:
    if element is None:
        return False
    return element.get(_m("val"), "on") in ("on", "1", "true")


def _prop(element: ET.Element, props: str, name: str) -> ET.Element | None:
    holder = element.find(_m(props))
    return None if holder is None else holder.find(_m(name))


def _prop_val(element: ET.Element, props: str, name: str, default: str) -> str:
    found = _prop(element, props, name)
    if found is None:
        return default
    return found.get(_m("val"), "")


def _read_arg(element: ET.Element, name: str) -> MathContent:
    child = element.find(_m(name))
    return () if child is None else read_math_content(child)


def read_math_content(parent: ET.Element) -> MathContent:
    """Read the nodes of an OMML argument (``m:e``, ``m:num``, ``m:oMath`` ...)."""
    nodes: list[MathNode] = []
    for child in parent:
        if not child.tag.startswith(f"{{{M_NS}}}"):
            continue
        name = _local(child.tag)
        if name.endswith("Pr") or name == "ctrlPr":
            continue
        nodes.append(_read_node(child))
    return math_content(nodes)


def _read_node(element: ET.Element) -> MathNode:
    from .math_mathml import UnsupportedEquationError, preflight_omml

    try:
        preflight_omml(element)
    except UnsupportedEquationError:
        return OpaqueMath(ET.tostring(element, encoding="unicode"))
    name = _local(element.tag)
    if name == "r":
        style_element = _prop(element, "rPr", "sty")
        style = None if style_element is None else style_element.get(_m("val"))
        if style not in RUN_STYLES:
            style = None
        text = "".join(t.text or "" for t in element.findall(_m("t")))
        drawing = element.find(f"{{{A_NS}}}rPr")
        font, color, size = None, None, None
        if drawing is not None:
            latin = drawing.find(f"{{{A_NS}}}latin")
            if latin is not None and latin.attrib != _CAMBRIA_MATH:
                font = latin.get("typeface")
            fill = drawing.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
            if fill is not None:
                color = fill.get("val")
            if drawing.get("sz") is not None:
                size = int(drawing.get("sz")) / 100
        return MathRun(_to_plain(text, style), style, font=font, color=color, size=size)
    if name == "f":
        return Fraction(
            _read_arg(element, "num"),
            _read_arg(element, "den"),
            _prop_val(element, "fPr", "type", "bar") or "bar",
        )
    if name == "rad":
        hidden = _on(_prop(element, "radPr", "degHide"))
        degree = None if hidden else (_read_arg(element, "deg") or None)
        return Radical(_read_arg(element, "e"), degree)
    if name == "nary":
        lower = None if _on(_prop(element, "naryPr", "subHide")) else _read_arg(element, "sub")
        upper = None if _on(_prop(element, "naryPr", "supHide")) else _read_arg(element, "sup")
        return Nary(
            _prop_val(element, "naryPr", "chr", "∫") or "∫",
            _read_arg(element, "e"),
            lower or None,
            upper or None,
            _prop_val(element, "naryPr", "limLoc", "undOvr") or "undOvr",
            grow=_on(_prop(element, "naryPr", "grow")),
        )
    if name == "m":
        rows = tuple(
            tuple(read_math_content(cell) for cell in row.findall(_m("e")))
            for row in element.findall(_m("mr"))
        )
        alignments: list[str] = []
        for column in element.findall(f"{_m('mPr')}/{_m('mcs')}/{_m('mc')}"):
            count = int(_prop_val(column, "mcPr", "count", "1"))
            alignments.extend([_prop_val(column, "mcPr", "mcJc", "center")] * count)
        return Matrix(
            rows,
            column_alignments=tuple(alignments),
            column_gap_rule=int(_prop_val(element, "mPr", "cGpRule", "0")),
            column_gap=int(_prop_val(element, "mPr", "cGp", "0")),
            minimum_column_width=int(_prop_val(element, "mPr", "cSp", "0")),
            row_spacing_rule=int(_prop_val(element, "mPr", "rSpRule", "0")),
            row_spacing=int(_prop_val(element, "mPr", "rSp", "0")),
            base_justification=_prop_val(element, "mPr", "baseJc", "center") or "center",
            hide_placeholders=None
            if _prop(element, "mPr", "plcHide") is None
            else _on(_prop(element, "mPr", "plcHide")),
        )
    if name == "d":
        return Delimiter(
            tuple(read_math_content(item) for item in element.findall(_m("e"))),
            _prop_val(element, "dPr", "begChr", "("),
            _prop_val(element, "dPr", "endChr", ")"),
            _prop_val(element, "dPr", "sepChr", "|"),
            _prop_val(element, "dPr", "shp", "centered") or "centered",
            grow=True
            if _prop(element, "dPr", "grow") is None
            else _on(_prop(element, "dPr", "grow")),
        )
    if name == "acc":
        return Accent(
            _read_arg(element, "e"),
            _prop_val(element, "accPr", "chr", "\u0302") or "\u0302",
        )
    if name == "sSub":
        return Sub(_read_arg(element, "e"), _read_arg(element, "sub"))
    if name == "sSup":
        return Sup(_read_arg(element, "e"), _read_arg(element, "sup"))
    if name == "sSubSup":
        return SubSup(
            _read_arg(element, "e"),
            _read_arg(element, "sub"),
            _read_arg(element, "sup"),
        )
    if name == "func":
        return Function(_read_arg(element, "fName"), _read_arg(element, "e"))
    if name == "bar":
        return Bar(
            _read_arg(element, "e"),
            "top" if _prop_val(element, "barPr", "pos", "bot") == "top" else "bottom",
        )
    if name == "box":
        brk = _prop(element, "boxPr", "brk")
        alignment = None if brk is None else brk.get(_m("alnAt"))
        return Box(
            _read_arg(element, "e"),
            _on(_prop(element, "boxPr", "opEmu")),
            _on(_prop(element, "boxPr", "noBreak")),
            _on(_prop(element, "boxPr", "diff")),
            alignment_point=_on(_prop(element, "boxPr", "aln")),
            break_before=brk is not None,
            break_alignment=None if alignment is None else int(alignment),
        )
    if name == "borderBox":
        return BorderBox(
            _read_arg(element, "e"),
            **{attr: _on(_prop(element, "borderBoxPr", prop)) for attr, prop in _BORDER_FLAGS},
        )
    if name == "groupChr":
        return GroupChr(
            _read_arg(element, "e"),
            _prop_val(element, "groupChrPr", "chr", "⏟") or "⏟",
            "top" if _prop_val(element, "groupChrPr", "pos", "bot") == "top" else "bottom",
            "bottom" if _prop_val(element, "groupChrPr", "vertJc", "top") in ("bot", "") else "top",
        )
    if name in ("limLow", "limUpp"):
        cls = LowerLimit if name == "limLow" else UpperLimit
        return cls(_read_arg(element, "e"), _read_arg(element, "lim"))
    if name == "phant":
        flags = {attr: _on(_prop(element, "phantPr", prop)) for attr, prop in _PHANTOM_FLAGS}
        if _prop(element, "phantPr", "show") is None:
            flags["show"] = True
        return Phantom(_read_arg(element, "e"), **flags)
    if name == "eqArr":
        return EquationArray(
            tuple(read_math_content(row) for row in element.findall(_m("e"))),
            _prop_val(element, "eqArrPr", "baseJc", "center") or "center",
            int(_prop_val(element, "eqArrPr", "rSpRule", "0") or "0"),
            int(_prop_val(element, "eqArrPr", "rSp", "0") or "0"),
            maximum_distribution=_on(_prop(element, "eqArrPr", "maxDist")),
            object_distribution=_on(_prop(element, "eqArrPr", "objDist")),
        )
    if name == "sPre":
        return PreSubSup(
            _read_arg(element, "e"),
            _read_arg(element, "sub"),
            _read_arg(element, "sup"),
        )
    return OpaqueMath(ET.tostring(element, encoding="unicode"))


def equation_from_omml(zone: ET.Element) -> Equation:
    """Read blocks and native inherited formatting; uniform legacy sizes hoist."""
    if zone.tag == f"{{{A14_NS}}}m":
        inner = [child for child in zone if child.tag in (_m("oMathPara"), _m("oMath"))]
        if len(inner) != 1:
            raise ValueError("a14:m must hold one m:oMathPara or m:oMath")
        zone = inner[0]
    controls = [control.find(f"{{{A_NS}}}rPr") for control in zone.iter(_m("ctrlPr"))]
    control_sizes = {props.get("sz") for props in controls if props is not None}
    sizes = {properties.get("sz") for properties in zone.iter(f"{{{A_NS}}}rPr")}
    inherited_sizes = control_sizes if controls else sizes
    raw_size = (
        next(iter(inherited_sizes))
        if len(inherited_sizes) == 1 and None not in inherited_sizes
        else None
    )
    size = int(raw_size) / 100 if raw_size is not None and raw_size.isdigit() else None
    if size is not None:
        zone = copy.deepcopy(zone)
        for properties in zone.iter(f"{{{A_NS}}}rPr"):
            if properties.get("sz") == raw_size:
                del properties.attrib["sz"]
    if zone.tag == _m("oMathPara"):
        justification = _prop_val(zone, "oMathParaPr", "jc", "") or None
        return Equation.from_blocks(
            *(read_math_content(math) for math in zone.findall(_m("oMath"))),
            display=True,
            justification=justification,
            size=size,
        )
    if zone.tag == _m("oMath"):
        return Equation(read_math_content(zone), False, size=size)
    raise ValueError(f"not an equation element: {zone.tag}")


def math_element_from_omml(element: ET.Element) -> MathNode | MathBlock:
    """Read one equation element: an Office Math element (``m:f``, ``m:r`` ...) as its
    node, or an ``m:oMath`` as :meth:`MathElement.to_omml` writes it: its one node, or
    a :class:`MathBlock` of any other number."""
    name = _local(element.tag)
    if not element.tag.startswith(f"{{{M_NS}}}") or name == "oMathPara" or name.endswith("Pr"):
        raise ValueError(f"not an Office Math element: {element.tag}")
    if name != "oMath":
        return _read_node(element)
    content = read_math_content(element)
    return content[0] if len(content) == 1 else MathBlock(content)


def _index(index: int, length: int, *, insert: bool) -> None:
    if type(index) is not int:
        raise TypeError("math collection index must be an integer")
    if not 0 <= index < length + int(insert):
        raise IndexError("math collection index out of range")


def _node_content(node: MathElement) -> MathContent:
    return node.content if isinstance(node, MathBlock) else (node,)


def _reject_cycle(content: MathContent, target: MathElement) -> None:
    for node in content:
        if node is target:
            raise ValueError("math collection mutation cannot introduce a cycle")
        for child in node.children:
            _reject_cycle(child, target)


def _commit(node: MathElement, candidate: MathElement, names: tuple[str, ...]) -> None:
    from .math_mathml import validate_node

    # Validate the source too: removing an opaque subtree is not a strict edit.
    validate_node(node)
    content = _node_content(candidate)
    _reject_cycle(content, node)
    validate_node(candidate)
    for name in names:
        _set(node, name, getattr(candidate, name))


def edit_argument(
    node: MathElement,
    argument: str,
    index: int,
    content: Any = None,
    *,
    insert: bool,
) -> None:
    if argument not in node._arguments:
        raise ValueError(f"{type(node).__name__} has no content argument {argument!r}")
    edit_sequence(node, argument, index, content, insert=insert)


def edit_sequence(
    node: MathElement,
    name: str,
    index: int,
    content: Any = None,
    *,
    insert: bool,
    grouped: bool = False,
) -> None:
    sequence = getattr(node, name) or ()
    _index(index, len(sequence), insert=insert)
    if insert:
        normalized = math_content(content)
        additions = (normalized,) if grouped else normalized
        sequence = sequence[:index] + additions + sequence[index:]
    else:
        sequence = sequence[:index] + sequence[index + 1 :]
    candidate = replace(node, **{name: sequence})
    _commit(node, candidate, (name,))


def edit_matrix(
    node: Matrix,
    axis: str,
    index: int,
    cells: Any = None,
    *,
    insert: bool,
    alignment: str = "center",
) -> None:
    rows, alignments = node.rows, node.column_alignments
    length = len(rows) if axis == "row" else len(alignments)
    _index(index, length, insert=insert)
    if insert:
        normalized = tuple(math_content(cell) for cell in cells)
        expected = len(alignments) if axis == "row" else len(rows)
        if len(normalized) != expected:
            raise ValueError(f"Matrix {axis} insertion needs {expected} cells")
        if axis == "row":
            rows = rows[:index] + (normalized,) + rows[index:]
        else:
            rows = tuple(
                row[:index] + (cell,) + row[index:]
                for row, cell in zip(rows, normalized, strict=True)
            )
            alignments = alignments[:index] + (alignment,) + alignments[index:]
    elif axis == "row":
        rows = rows[:index] + rows[index + 1 :]
    else:
        rows = tuple(row[:index] + row[index + 1 :] for row in rows)
        alignments = alignments[:index] + alignments[index + 1 :]
    candidate = replace(node, rows=rows, column_alignments=alignments)
    _commit(node, candidate, ("rows", "column_alignments"))


def edit_equation_blocks(
    equation: Equation,
    index: int,
    content: Any = None,
    *,
    operation: str,
) -> None:
    from .math_mathml import validate_equation

    _index(index, len(equation.blocks), insert=operation == "insert")
    blocks = equation.blocks
    if operation == "insert":
        blocks = blocks[:index] + (math_content(content),) + blocks[index:]
    elif operation == "set":
        blocks = blocks[:index] + (math_content(content),) + blocks[index + 1 :]
    else:
        blocks = blocks[:index] + blocks[index + 1 :]
    candidate = Equation.from_blocks(
        *blocks,
        display=equation.display,
        justification=equation.justification,
        size=equation.size,
    )
    validate_equation(equation)
    validate_equation(candidate)
    _set(equation, "blocks", candidate.blocks)
