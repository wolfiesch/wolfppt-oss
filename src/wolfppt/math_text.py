"""Slide equations: an Office Math (OMML) tree for ``a14:m`` text paragraphs.

PowerPoint keeps an equation inside a text paragraph as ``a14:m`` holding ``m:oMathPara``
(a display equation) or ``m:oMath`` (an inline one). :class:`Equation` is the tree for one
such zone, built from :class:`MathRun` text and the structures fractions
(:class:`Fraction`), radicals (:class:`Radical`), n-ary operators (:class:`Nary`), matrices
(:class:`Matrix`), delimiters (:class:`Delimiter`), accents (:class:`Accent`), scripts
(:class:`Sub`, :class:`Sup`, :class:`SubSup`, :class:`PreSubSup`), function applications,
bars, boxes, grouping characters, limits, phantoms and equation arrays. Office Math
constructs outside that set read back as :class:`OpaqueMath`, which keeps their XML.

Every node shares the :class:`MathElement` interface: its OMML element name
(``omml_name``), its arguments (``children``), serialisation to OMML (``to_omml``) and
reading back (``from_omml``, :func:`math_element_from_omml`), and fluent composition
(``run("x").superscript("2").divide("2")``): joining into a :class:`MathBlock`,
enclosing, function application, fractions, radicals, scripts, n-ary operators and
integrals, matrices and arrays, delimiters, accents, bars, boxes, grouping characters,
limits and phantoms. Each node type has a module-level factory (:func:`run`,
:func:`block`, :func:`fraction` ...) returning exactly the node its typed constructor
builds; :data:`ELEMENT_FACTORIES` maps every node type to its factory.

Enumerations name the values Office Math stores: :class:`MathFunctionsOfOneArgument`
and :class:`MathFunctionsOfTwoArguments` (function names), :class:`MathIntegralTypes`
and :class:`MathNaryOperatorTypes` (large operators), :class:`MathDelimiterShape`,
:class:`MathFractionTypes`, :class:`MathLimitLocations` and :class:`MathJustification`.
Nodes accept them when written and report them when read.
:class:`MathHorizontalAlignment` names matrix column strings; :class:`MathSpacingRule`
names matrix/array spacing integers without changing their existing readback values.

``TextFrame.add_equation`` and ``TextParagraph.equation`` author whole paragraphs.
Use ``TextParagraph.add_equation``, ``set_equation``, ``equations`` and ``content_runs``
for ordered mixed-run insertion, indexed editing and readback. Inline assignment
retains ordinary text. :func:`slide_equations` lists equations, including saved
``mc:AlternateContent`` zones. :meth:`Equation.to_mathml` exports MathML;
``Equation.text`` exports grouped structural linear text. Strict mixed-run editing
and export refuse unsupported nodes by name; raw opaque OMML remains preservable.
The public PDF/PNG renderer draws supported equation zones alongside ordinary text,
including zones selected through markup compatibility. Unsupported equation content
raises ``UnsupportedEquationError`` before output publication; untouched source XML
remains byte-preserved.

Written runs follow PowerPoint's own form: each ``m:r`` carries ``a:rPr`` with Cambria
Math by default, or an explicit typeface, RGB color and point-size override. Italic
letters use Unicode mathematical italic letters (``x`` is written ``𝑥``), mapped
back on read. Runs split on alphabet changes (see :func:`_run_segments`) and merge
again only when all formatting matches. Uniform run-only sizes canonically hoist
to :attr:`Equation.size`; explicit sizes differing from structural control size
remain run overrides.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Union
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .text_facade import TextParagraph

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
MATHML_NS = "http://www.w3.org/1998/Math/MathML"

# Slide XML rewritten by the editors keeps PowerPoint's prefixes, which ``mc:Ignorable``
# and ``Requires`` name.
ET.register_namespace("m", M_NS)
ET.register_namespace("a14", A14_NS)
ET.register_namespace("mc", MC_NS)

_CAMBRIA_MATH = {
    "typeface": "Cambria Math",
    "panose": "02040503050406030204",
    "pitchFamily": "18",
    "charset": "0",
}

#: Run styles (``m:sty``): ``None`` is the default math italic for letters.
RUN_STYLES = (None, "p", "b", "i", "bi")


class MathFractionTypes(StrEnum):
    """Fraction types (``m:type``)."""

    BAR = "bar"
    SKEWED = "skw"
    LINEAR = "lin"
    NO_BAR = "noBar"


class MathLimitLocations(StrEnum):
    """Where an n-ary operator's limits sit (``m:limLoc``)."""

    UNDER_OVER = "undOvr"
    SUBSCRIPT_SUPERSCRIPT = "subSup"


class MathDelimiterShape(StrEnum):
    """Delimiter characters centred on the math axis or matching their content
    (``m:shp``)."""

    CENTERED = "centered"
    MATCH = "match"


class MathJustification(StrEnum):
    """Justification of a display equation (``m:oMathParaPr/m:jc``)."""

    LEFT_JUSTIFIED = "left"
    RIGHT_JUSTIFIED = "right"
    CENTERED = "center"
    CENTERED_AS_GROUP = "centerGroup"


class MathHorizontalAlignment(StrEnum):
    """Matrix column alignment; existing string values remain accepted."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class MathSpacingRule(IntEnum):
    """Matrix/array spacing rules; exact and multiple units follow the node."""

    SINGLE = 0
    ONE_AND_HALF = 1
    DOUBLE = 2
    EXACT = 3
    MULTIPLE = 4


class MathNaryOperatorTypes(StrEnum):
    """N-ary operators other than integrals (``m:chr``), as PowerPoint writes them."""

    SUMMATION = "∑"
    PRODUCT = "∏"
    COPRODUCT = "∐"
    INTERSECTION = "⋂"
    UNION = "⋃"
    LOGICAL_AND = "⋀"
    LOGICAL_OR = "⋁"


class MathIntegralTypes(StrEnum):
    """Integral operators (``m:chr``; ``∫`` is OMML's default and written as none)."""

    SIMPLE = "∫"
    DOUBLE = "∬"
    TRIPLE = "∭"
    CONTOUR = "∮"
    SURFACE = "∯"
    VOLUME = "∰"


class MathFunctionsOfOneArgument(StrEnum):
    """Function names applied to one argument, as the plain text of ``m:fName``."""

    SIN = "sin"
    COS = "cos"
    TAN = "tan"
    CSC = "csc"
    SEC = "sec"
    COT = "cot"
    HYPERBOLIC_SIN = "sinh"
    HYPERBOLIC_COS = "cosh"
    HYPERBOLIC_TAN = "tanh"
    HYPERBOLIC_CSC = "csch"
    HYPERBOLIC_SEC = "sech"
    HYPERBOLIC_COT = "coth"
    LG = "lg"
    LN = "ln"
    ARC_SIN = "arcsin"
    ARC_COS = "arccos"
    ARC_TAN = "arctan"
    ARC_CSC = "arccsc"
    ARC_SEC = "arcsec"
    ARC_COT = "arccot"
    HYPERBOLIC_ARC_SIN = "arcsinh"
    HYPERBOLIC_ARC_COS = "arccosh"
    HYPERBOLIC_ARC_TAN = "arctanh"
    HYPERBOLIC_ARC_CSC = "arccsch"
    HYPERBOLIC_ARC_SEC = "arcsech"
    HYPERBOLIC_ARC_COT = "arccoth"


class MathFunctionsOfTwoArguments(StrEnum):
    """Function names taking a second argument: ``log`` with its base as a subscript
    (``m:sSub``), ``lim``, ``min`` and ``max`` with theirs as a lower limit
    (``m:limLow``), in ``m:fName``."""

    LOG = "log"
    LIM = "lim"
    MIN = "min"
    MAX = "max"


#: Fraction types (``m:type``).
FRACTION_KINDS = tuple(MathFractionTypes)
#: N-ary limit placements (``m:limLoc``).
LIMIT_LOCATIONS = tuple(MathLimitLocations)
#: The operator type of each n-ary character; the binary forms ``∩ ∪ ∧ ∨`` (Aspose's
#: spelling of these types) read as the same types.
_NARY_OPERATOR_TYPES: dict[str, MathNaryOperatorTypes | MathIntegralTypes] = {
    **{member.value: member for member in MathNaryOperatorTypes},
    **{member.value: member for member in MathIntegralTypes},
    "∩": MathNaryOperatorTypes.INTERSECTION,
    "∪": MathNaryOperatorTypes.UNION,
    "∧": MathNaryOperatorTypes.LOGICAL_AND,
    "∨": MathNaryOperatorTypes.LOGICAL_OR,
}


def _enum(enum: type[StrEnum], value: Any, what: str) -> Any:
    try:
        return enum(value)
    except ValueError:
        raise ValueError(
            f"{what} must be one of {tuple(member.value for member in enum)}, got {value!r}"
        ) from None


def _m(name: str) -> str:
    return f"{{{M_NS}}}{name}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# --- Unicode mathematical alphanumerics -------------------------------------------------


def _alphabet(upper: int | None, lower: int | None, exceptions: dict[str, int]) -> dict[str, str]:
    table: dict[str, str] = {}
    for start, letters in (
        (upper, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        (lower, "abcdefghijklmnopqrstuvwxyz"),
    ):
        if start is None:
            continue
        for offset, letter in enumerate(letters):
            table[letter] = chr(start + offset)
    for letter, code in exceptions.items():
        table[letter] = chr(code)
    return table


_GREEK_LOWER = "αβγδεζηθικλμνξοπρςστυφχψω"
_ITALIC = _alphabet(0x1D434, 0x1D44E, {"h": 0x210E})
_ITALIC.update({g: chr(0x1D6FC + i) for i, g in enumerate(_GREEK_LOWER)})
_BOLD = _alphabet(0x1D400, 0x1D41A, {})
_BOLD_ITALIC = _alphabet(0x1D468, 0x1D482, {})
_STYLE_ALPHABET = {None: _ITALIC, "i": _ITALIC, "b": _BOLD, "bi": _BOLD_ITALIC, "p": {}}
_STYLE_PLAIN = {
    style: {styled: plain for plain, styled in table.items()}
    for style, table in _STYLE_ALPHABET.items()
}


def _to_styled(text: str, style: str | None) -> str:
    table = _STYLE_ALPHABET[style]
    return "".join(table.get(ch, ch) for ch in text)


def _to_plain(text: str, style: str | None) -> str:
    table = _STYLE_PLAIN[style]
    return "".join(table.get(ch, ch) for ch in text)


def _alphabet_of(ch: str) -> int:
    """The alphabet a character belongs to, for splitting written runs.

    Basic-plane characters are one alphabet; the supplementary-plane mathematical
    alphanumerics split into Latin letters, Greek letters and digits.
    """
    code = ord(ch)
    if code <= 0xFFFF:
        return 0
    if 0x1D400 <= code <= 0x1D6A3:
        return 1
    if 0x1D6A8 <= code <= 0x1D7CB:
        return 2
    if 0x1D7CE <= code <= 0x1D7FF:
        return 3
    return 4


def _run_segments(text: str) -> list[str]:
    """Split written ``m:t`` text where its alphabet changes.

    PowerPoint 16.113 drops the first supplementary-plane character that follows a change
    of alphabet inside one ``m:t``: ``𝑝+𝑞`` displays as ``𝑝+``, ``2𝑎`` as ``2`` and ``𝑖𝜋``
    as ``𝑖``. Its own files keep letters and operators in separate runs (``𝑎`` ``+`` ``𝑏``),
    which it displays whole, so each change of alphabet starts a new ``m:r``.
    """
    segments: list[str] = []
    for ch in text:
        if segments and _alphabet_of(segments[-1][-1]) == _alphabet_of(ch):
            segments[-1] += ch
        else:
            segments.append(ch)
    return segments


# --- The tree ---------------------------------------------------------------------------

MathNode = Union[
    "MathRun",
    "Fraction",
    "Radical",
    "Nary",
    "Matrix",
    "Delimiter",
    "Accent",
    "Sub",
    "Sup",
    "SubSup",
    "Function",
    "Bar",
    "Box",
    "BorderBox",
    "GroupChr",
    "LowerLimit",
    "UpperLimit",
    "Phantom",
    "EquationArray",
    "PreSubSup",
    "OpaqueMath",
]
MathContent = tuple[MathNode, ...]


def math_content(value: Any) -> MathContent:
    """Normalise ``value`` to a tuple of nodes.

    A string is one default-style :class:`MathRun`; a node is itself; any other iterable
    is flattened. Adjacent runs with identical style, font, color and size merge.
    """
    nodes: list[MathNode] = []
    for node in _flatten(value):
        if isinstance(node, MathRun) and nodes and isinstance(nodes[-1], MathRun):
            last = nodes[-1]
            if (last.style, last.font, last.color, last.size) == (
                node.style,
                node.font,
                node.color,
                node.size,
            ):
                nodes[-1] = MathRun(
                    last.text + node.text,
                    last.style,
                    font=last.font,
                    color=last.color,
                    size=last.size,
                )
                continue
        if isinstance(node, MathRun) and not node.text:
            continue
        nodes.append(node)
    return tuple(nodes)


def _flatten(value: Any) -> Iterator[MathNode]:
    if value is None:
        return
    if isinstance(value, str):
        yield MathRun(value)
    elif isinstance(value, _NODE_TYPES):
        yield value
    elif isinstance(value, Iterable):
        for item in value:
            yield from _flatten(item)
    else:
        raise TypeError(f"equation content must be text or math nodes, got {type(value).__name__}")


def _set(obj: Any, name: str, value: Any) -> None:
    object.__setattr__(obj, name, value)


class MathElement:
    """The interface every equation node shares.

    ``omml_name`` is the node's OMML element name and ``children`` its arguments in OMML
    order, an absent optional argument being empty. :meth:`to_omml` writes the node as an
    ``m:oMath`` and :meth:`from_omml` reads one back. The other methods compose equations
    fluently: each makes this node the base (numerator, function argument ...) of a new
    element, so ``run("x").superscript("2").divide("2")`` is
    ``Fraction(Sup("x", "2"), "2")``, and :meth:`join` strings nodes into a
    :class:`MathBlock`.

    Named argument edits use :meth:`insert_content` / :meth:`remove_content`;
    collections additionally expose indexed insertion/removal. These explicit
    methods mutate otherwise frozen nodes after complete-tree validation. Mutable
    structural nodes are unhashable. Trees are detached from paragraphs: reassign
    the edited equation with ``TextParagraph.set_equation`` to save the changes.
    """

    __slots__ = ()
    omml_name: ClassVar[str]
    #: The fields holding the node's arguments, in OMML order.
    _arguments: ClassVar[tuple[str, ...]] = ()

    @property
    def children(self) -> tuple[MathContent, ...]:
        return tuple(getattr(self, name) or () for name in self._arguments)

    def insert_content(self, argument: str, index: int, content: Any) -> None:
        """Insert nodes into a named argument, refusing opaque trees atomically."""
        from .math_text_builder import edit_argument

        edit_argument(self, argument, index, content, insert=True)

    def remove_content(self, argument: str, index: int) -> None:
        """Remove one indexed node from a named argument, validating before mutation."""
        from .math_text_builder import edit_argument

        edit_argument(self, argument, index, insert=False)

    def to_omml(self) -> ET.Element:
        """This node as an ``m:oMath`` element."""
        math = ET.Element(_m("oMath"))
        _write_node(math, self)  # type: ignore[arg-type]
        return math

    @classmethod
    def from_omml(cls, element: ET.Element) -> MathNode:
        """Read a node of this class from OMML (see :func:`math_element_from_omml`)."""
        node = math_element_from_omml(element)
        if not isinstance(node, cls):
            raise TypeError(
                f"m:{node.omml_name} reads as {type(node).__name__}, not {cls.__name__}"
            )
        return node

    def join(self, *others: Any) -> MathBlock:
        """This node followed by ``others`` (text, nodes or blocks), as one block."""
        return MathBlock((self, *others))

    def divide(
        self, denominator: Any, kind: MathFractionTypes | str = MathFractionTypes.BAR
    ) -> Fraction:
        return Fraction(self, denominator, kind)

    def radical(self, degree: Any = None) -> Radical:
        return Radical(self, degree)

    def nary(
        self,
        operator: MathNaryOperatorTypes | MathIntegralTypes | str,
        lower: Any = None,
        upper: Any = None,
        limits: MathLimitLocations | str = MathLimitLocations.UNDER_OVER,
        *,
        grow: bool = False,
    ) -> Nary:
        return Nary(operator, self, lower, upper, limits, grow=grow)

    def integral(
        self,
        kind: MathIntegralTypes | str = MathIntegralTypes.SIMPLE,
        lower: Any = None,
        upper: Any = None,
        limits: MathLimitLocations | str = MathLimitLocations.SUBSCRIPT_SUPERSCRIPT,
        *,
        grow: bool = False,
    ) -> Nary:
        """Integrate this node; limits default to scripts, as PowerPoint's integrals."""
        return Nary(
            _enum(MathIntegralTypes, kind, "integral"),
            self,
            lower,
            upper,
            limits,
            grow=grow,
        )

    def enclose(
        self,
        begin: str = "(",
        end: str = ")",
        shape: MathDelimiterShape | str = MathDelimiterShape.CENTERED,
        *,
        grow: bool = True,
    ) -> Delimiter:
        return Delimiter((self,), begin, end, shape=shape, grow=grow)

    def delimit(
        self,
        *others: Any,
        begin: str = "(",
        end: str = ")",
        separator: str = "|",
        shape: MathDelimiterShape | str = MathDelimiterShape.CENTERED,
        grow: bool = True,
    ) -> Delimiter:
        """This node and ``others`` as separate delimiter elements."""
        return Delimiter((self, *others), begin, end, separator, shape, grow=grow)

    def to_matrix(
        self,
        *cells: Any,
        columns: int | None = None,
        column_alignments: tuple[str, ...] = (),
        column_gap_rule: int = 0,
        column_gap: int = 0,
        minimum_column_width: int = 0,
        row_spacing_rule: int = 0,
        row_spacing: int = 0,
        base_justification: str = "center",
        hide_placeholders: bool | None = None,
    ) -> Matrix:
        """This node then ``cells``, ``columns`` to a row (all in one row by default)."""
        items = (self, *cells)
        width = len(items) if columns is None else columns
        if type(width) is not int or width < 1 or len(items) % width:
            raise ValueError(f"{len(items)} cells do not fill rows of {width!r}")
        return Matrix(
            tuple(items[start : start + width] for start in range(0, len(items), width)),
            column_alignments=column_alignments,
            column_gap_rule=column_gap_rule,
            column_gap=column_gap,
            minimum_column_width=minimum_column_width,
            row_spacing_rule=row_spacing_rule,
            row_spacing=row_spacing,
            base_justification=base_justification,
            hide_placeholders=hide_placeholders,
        )

    def to_math_array(
        self,
        *rows: Any,
        base_justification: str = "center",
        row_spacing_rule: int = 0,
        row_spacing: int = 0,
        maximum_distribution: bool = False,
        object_distribution: bool = False,
    ) -> EquationArray:
        """This node then ``rows``, stacked as an equation array."""
        return EquationArray(
            (self, *rows),
            base_justification,
            row_spacing_rule,
            row_spacing,
            maximum_distribution=maximum_distribution,
            object_distribution=object_distribution,
        )

    def accent(self, char: str = "\u0302") -> Accent:
        return Accent(self, char)

    def subscript(self, sub: Any) -> Sub:
        return Sub(self, sub)

    def superscript(self, sup: Any) -> Sup:
        return Sup(self, sup)

    def sub_superscript(self, sub: Any, sup: Any) -> SubSup:
        """Subscript and superscript on the right."""
        return SubSup(self, sub, sup)

    def pre_sub_superscript(self, sub: Any, sup: Any) -> PreSubSup:
        """Subscript and superscript on the left."""
        return PreSubSup(self, sub, sup)

    def function(self, argument: Any) -> Function:
        """Apply this node, as the function name, to ``argument``."""
        return Function(self, argument)

    def as_argument_of(
        self,
        name: MathFunctionsOfOneArgument | MathFunctionsOfTwoArguments | Any,
        argument: Any = None,
    ) -> Function:
        """Apply the function ``name`` (plain text when a string) to this node; a
        :class:`MathFunctionsOfTwoArguments` name takes its second ``argument``."""
        return Function(_function_name(name, argument), self)

    def overbar(self) -> Bar:
        return Bar(self, "top")

    def underbar(self) -> Bar:
        return Bar(self, "bottom")

    def to_box(
        self,
        operator_emulation: bool = False,
        no_break: bool = False,
        differential: bool = False,
        *,
        alignment_point: bool = False,
        break_before: bool = False,
        break_alignment: int | None = None,
    ) -> Box:
        return Box(
            self,
            operator_emulation,
            no_break,
            differential,
            alignment_point=alignment_point,
            break_before=break_before,
            break_alignment=break_alignment,
        )

    def to_border_box(self, **flags: bool) -> BorderBox:
        """A border box around this node; ``flags`` are :class:`BorderBox`'s."""
        return BorderBox(self, **flags)

    def group(
        self,
        char: str = "⏟",
        position: str = "bottom",
        vertical_justification: str = "top",
    ) -> GroupChr:
        return GroupChr(self, char, position, vertical_justification)

    def lower_limit(self, limit: Any) -> LowerLimit:
        return LowerLimit(self, limit)

    def upper_limit(self, limit: Any) -> UpperLimit:
        return UpperLimit(self, limit)

    def phantom(self, **flags: bool) -> Phantom:
        """This node as a phantom; ``flags`` are :class:`Phantom`'s."""
        return Phantom(self, **flags)


@dataclass(frozen=True)
class MathBlock(MathElement):
    """Nodes in sequence, as one argument holds them (an ``m:oMath``'s content).

    A block is not an Office Math element of its own: placed in an argument or an
    equation, its nodes are, so a block and its nodes write the same OMML.
    """

    content: MathContent
    omml_name: ClassVar[str] = "oMath"
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "content", math_content(self.content))

    def __iter__(self) -> Iterator[MathNode]:
        return iter(self.content)

    def __len__(self) -> int:
        return len(self.content)

    def __getitem__(self, index: int) -> MathNode:
        return self.content[index]

    def insert(self, index: int, content: Any) -> None:
        """Insert nodes at ``index`` (0 through length), validating before mutation."""
        from .math_text_builder import edit_sequence

        edit_sequence(self, "content", index, content, insert=True)

    def remove(self, index: int) -> None:
        """Remove one node at ``index``; opaque content refuses before any edit."""
        from .math_text_builder import edit_sequence

        edit_sequence(self, "content", index, insert=False)

    @property
    def children(self) -> tuple[MathContent, ...]:
        """Each node of the block."""
        return tuple((node,) for node in self.content)

    def to_omml(self) -> ET.Element:
        math = ET.Element(_m("oMath"))
        _write_content(math, self.content)
        return math

    @classmethod
    def from_omml(cls, element: ET.Element) -> MathBlock:
        """An ``m:oMath``'s nodes, or one Office Math element, as a block."""
        if element.tag == _m("oMath"):
            return cls(read_math_content(element))
        return cls((math_element_from_omml(element),))


def _function_name(name: Any, argument: Any = None) -> Any:
    """``m:fName`` content: a string or one-argument name is plain text; a two-argument
    name carries ``argument`` as its base's subscript (``log``) or lower limit."""
    if isinstance(name, MathFunctionsOfTwoArguments):
        if argument is None:
            raise ValueError(f"function {name.value} needs its second argument")
        text = MathRun(name.value, "p")
        if name is MathFunctionsOfTwoArguments.LOG:
            return Sub(text, argument)
        return LowerLimit(text, argument)
    if argument is not None:
        raise ValueError("only a MathFunctionsOfTwoArguments name takes a second argument")
    if isinstance(name, str):
        return MathRun(str(name), "p")
    return name


_ONE_ARGUMENT_NAMES = frozenset(member.value for member in MathFunctionsOfOneArgument)


def _function_type(
    name: MathContent,
) -> tuple[MathFunctionsOfOneArgument | MathFunctionsOfTwoArguments | None, Any]:
    if len(name) != 1:
        return None, None
    (node,) = name
    if isinstance(node, MathRun):
        if node.style == "p" and node.text in _ONE_ARGUMENT_NAMES:
            return MathFunctionsOfOneArgument(node.text), None
        return None, None
    if isinstance(node, Sub):
        base, argument, names = node.base, node.sub, ("log",)
    elif isinstance(node, LowerLimit):
        base, argument, names = node.base, node.limit, ("lim", "min", "max")
    else:
        return None, None
    if (
        len(base) == 1
        and isinstance(base[0], MathRun)
        and base[0].style == "p"
        and base[0].text in names
    ):
        return MathFunctionsOfTwoArguments(base[0].text), argument
    return None, None


@dataclass(frozen=True)
class MathRun(MathElement):
    """Text of an equation (``m:r``). ``style`` is ``m:sty``: ``None`` (math italic
    letters), ``"p"`` plain, ``"b"`` bold, ``"i"`` italic or ``"bi"`` bold italic.
    Keyword overrides ``font`` (typeface), ``color`` (six-digit RGB) and ``size``
    (points in hundredths, 1-4000) otherwise inherit the equation/paragraph."""

    text: str
    style: str | None = None
    font: str | None = field(default=None, kw_only=True)
    color: str | None = field(default=None, kw_only=True)
    size: float | None = field(default=None, kw_only=True)
    omml_name: ClassVar[str] = "r"

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("MathRun text must be a string")
        if self.style not in RUN_STYLES:
            raise ValueError(f"MathRun style must be one of {RUN_STYLES}, got {self.style!r}")
        _set(self, "text", _to_plain(self.text, self.style))
        if self.font is not None and (not isinstance(self.font, str) or not self.font.strip()):
            raise ValueError("MathRun font must be a nonempty typeface")
        if self.color is not None:
            if (
                not isinstance(self.color, str)
                or len(self.color) != 6
                or any(ch not in "0123456789abcdefABCDEF" for ch in self.color)
            ):
                raise ValueError("MathRun color must be six-digit RGB")
            _set(self, "color", self.color.upper())
        _set(self, "size", _size(self.size))


@dataclass(frozen=True)
class Fraction(MathElement):
    """``m:f``: ``kind`` (:class:`MathFractionTypes`) is ``bar`` (stacked), ``skw``
    (skewed), ``lin`` (linear) or ``noBar`` (stacked without a rule)."""

    numerator: MathContent
    denominator: MathContent
    kind: MathFractionTypes = MathFractionTypes.BAR
    omml_name: ClassVar[str] = "f"
    _arguments: ClassVar[tuple[str, ...]] = ("numerator", "denominator")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "kind", _enum(MathFractionTypes, self.kind, "Fraction kind"))
        _set(self, "numerator", math_content(self.numerator))
        _set(self, "denominator", math_content(self.denominator))


@dataclass(frozen=True)
class Radical(MathElement):
    """``m:rad``: a square root, or an n-th root when ``degree`` is given."""

    base: MathContent
    degree: MathContent | None = None
    omml_name: ClassVar[str] = "rad"
    _arguments: ClassVar[tuple[str, ...]] = ("degree", "base")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "base", math_content(self.base))
        if self.degree is not None:
            degree = math_content(self.degree)
            _set(self, "degree", degree or None)


@dataclass(frozen=True)
class Nary(MathElement):
    """``m:nary``: a large operator (``∑``, ``∏``, ``∫`` ...) with optional limits.

    ``operator`` is the character, given as such or as a :class:`MathNaryOperatorTypes`
    or :class:`MathIntegralTypes` member; :attr:`operator_type` names it. ``limits``
    (:class:`MathLimitLocations`) is ``undOvr`` (limits under and over) or ``subSup``
    (as scripts); an absent ``lower`` or ``upper`` limit is hidden.
    ``grow`` lets the operator stretch to the height of its argument.
    """

    operator: str
    base: MathContent
    lower: MathContent | None = None
    upper: MathContent | None = None
    limits: MathLimitLocations = MathLimitLocations.UNDER_OVER
    grow: bool = field(default=False, kw_only=True)
    omml_name: ClassVar[str] = "nary"
    _arguments: ClassVar[tuple[str, ...]] = ("lower", "upper", "base")
    __hash__ = None

    def __post_init__(self) -> None:
        _booleans(self, ("grow",))
        if not isinstance(self.operator, str) or len(self.operator) != 1:
            raise ValueError("Nary operator must be one character")
        _set(self, "operator", str(self.operator))
        _set(self, "limits", _enum(MathLimitLocations, self.limits, "Nary limits"))
        _set(self, "base", math_content(self.base))
        for name in ("lower", "upper"):
            value = getattr(self, name)
            if value is not None:
                _set(self, name, math_content(value) or None)

    @property
    def operator_type(self) -> MathNaryOperatorTypes | MathIntegralTypes | None:
        """The operator's type, ``None`` for a character neither enumeration names."""
        return _NARY_OPERATOR_TYPES.get(self.operator)


@dataclass(frozen=True)
class Matrix(MathElement):
    """``m:m``: rectangular rows of cell content. Column alignments are ``left``,
    ``center`` or ``right``. ``column_gap_rule``: 0 single, 1 one-and-a-half,
    2 double, 3 exact (``column_gap`` in twips), 4 multiple (half-em units).
    ``minimum_column_width`` is twips. Row spacing follows :class:`EquationArray`.
    Indexed edits stay rectangular. ``base_justification`` aligns the first/last row
    baseline for top/bottom, or centers on the math axis. ``hide_placeholders`` writes
    ``plcHide``: False draws empty cells as squares, True hides them, None retains
    the absent declaration and existing empty-cell layout."""

    rows: tuple[tuple[MathContent, ...], ...]
    column_alignments: tuple[str, ...] = field(default=(), kw_only=True)
    column_gap_rule: int = field(default=0, kw_only=True)
    column_gap: int = field(default=0, kw_only=True)
    minimum_column_width: int = field(default=0, kw_only=True)
    row_spacing_rule: int = field(default=0, kw_only=True)
    row_spacing: int = field(default=0, kw_only=True)
    base_justification: str = field(default="center", kw_only=True)
    hide_placeholders: bool | None = field(default=None, kw_only=True)
    omml_name: ClassVar[str] = "m"
    __hash__ = None

    def __post_init__(self) -> None:
        from .math_text_builder import validate_matrix_properties

        validate_matrix_properties(self)
        rows = tuple(tuple(math_content(cell) for cell in row) for row in self.rows)
        if not rows or not rows[0]:
            raise ValueError("Matrix needs at least one row and one column")
        if any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("Matrix rows must have the same number of cells")
        _set(self, "rows", rows)
        alignments = tuple(self.column_alignments) or ("center",) * len(rows[0])
        if len(alignments) != len(rows[0]) or any(
            value not in ("left", "center", "right") for value in alignments
        ):
            raise ValueError("Matrix needs one left/center/right alignment per column")
        _set(self, "column_alignments", alignments)
        _spacing(self, "column_gap_rule", "column_gap")
        _spacing(self, "row_spacing_rule", "row_spacing")
        if (
            type(self.minimum_column_width) is not int
            or not 0 <= self.minimum_column_width <= 4_294_967_295
        ):
            raise ValueError("Matrix minimum_column_width must be unsigned 32-bit twips")

    @property
    def children(self) -> tuple[MathContent, ...]:
        """The cells, row by row."""
        return tuple(cell for row in self.rows for cell in row)

    def insert_row(self, index: int, cells: Iterable[Any]) -> None:
        """Insert a complete row at ``index``; cell count must match the columns."""
        from .math_text_builder import edit_matrix

        edit_matrix(self, "row", index, cells, insert=True)

    def remove_row(self, index: int) -> None:
        """Remove an indexed row; the last row cannot be removed."""
        from .math_text_builder import edit_matrix

        edit_matrix(self, "row", index, insert=False)

    def insert_column(self, index: int, cells: Iterable[Any], *, alignment: str = "center") -> None:
        """Insert one cell per row and its column alignment atomically."""
        from .math_text_builder import edit_matrix

        edit_matrix(self, "column", index, cells, insert=True, alignment=alignment)

    def remove_column(self, index: int) -> None:
        """Remove an indexed column and alignment; retain at least one column."""
        from .math_text_builder import edit_matrix

        edit_matrix(self, "column", index, insert=False)


@dataclass(frozen=True)
class Delimiter(MathElement):
    """``m:d``: elements between ``begin`` and ``end`` characters, separated by
    ``separator``. An empty ``begin`` or ``end`` draws no character. ``shape``
    (:class:`MathDelimiterShape`) centres the characters on the math axis or matches
    them to the content. ``grow=False`` retains the delimiters' natural size."""

    elements: tuple[MathContent, ...]
    begin: str = "("
    end: str = ")"
    separator: str = "|"
    shape: MathDelimiterShape = MathDelimiterShape.CENTERED
    grow: bool = field(default=True, kw_only=True)
    omml_name: ClassVar[str] = "d"
    __hash__ = None

    def __post_init__(self) -> None:
        _booleans(self, ("grow",))
        elements = self.elements
        if isinstance(elements, (str, MathBlock, *_NODE_TYPES)):
            elements = (elements,)
        normalized = tuple(math_content(element) for element in elements)
        if not normalized:
            raise ValueError("Delimiter needs at least one element")
        _set(self, "elements", normalized)
        for name in ("begin", "end", "separator"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > 1:
                raise ValueError(f"Delimiter {name} must be one character or empty")
        _set(self, "shape", _enum(MathDelimiterShape, self.shape, "Delimiter shape"))

    @property
    def children(self) -> tuple[MathContent, ...]:
        return self.elements

    def insert(self, index: int, content: Any) -> None:
        """Insert a separate delimiter argument, not nodes within an argument."""
        from .math_text_builder import edit_sequence

        edit_sequence(self, "elements", index, content, insert=True, grouped=True)

    def remove(self, index: int) -> None:
        """Remove an argument while retaining at least one delimiter element."""
        from .math_text_builder import edit_sequence

        edit_sequence(self, "elements", index, insert=False, grouped=True)


@dataclass(frozen=True)
class Accent(MathElement):
    """``m:acc``: ``char`` (a combining mark, hat by default) over ``base``."""

    base: MathContent
    char: str = "\u0302"
    omml_name: ClassVar[str] = "acc"
    _arguments: ClassVar[tuple[str, ...]] = ("base",)
    __hash__ = None

    def __post_init__(self) -> None:
        if not isinstance(self.char, str) or len(self.char) != 1:
            raise ValueError("Accent char must be one character")
        _set(self, "base", math_content(self.base))


@dataclass(frozen=True)
class Sub(MathElement):
    """``m:sSub``."""

    base: MathContent
    sub: MathContent
    omml_name: ClassVar[str] = "sSub"
    _arguments: ClassVar[tuple[str, ...]] = ("base", "sub")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "base", math_content(self.base))
        _set(self, "sub", math_content(self.sub))


@dataclass(frozen=True)
class Sup(MathElement):
    """``m:sSup``."""

    base: MathContent
    sup: MathContent
    omml_name: ClassVar[str] = "sSup"
    _arguments: ClassVar[tuple[str, ...]] = ("base", "sup")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "base", math_content(self.base))
        _set(self, "sup", math_content(self.sup))


@dataclass(frozen=True)
class SubSup(MathElement):
    """``m:sSubSup``."""

    base: MathContent
    sub: MathContent
    sup: MathContent
    omml_name: ClassVar[str] = "sSubSup"
    _arguments: ClassVar[tuple[str, ...]] = ("base", "sub", "sup")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "base", math_content(self.base))
        _set(self, "sub", math_content(self.sub))
        _set(self, "sup", math_content(self.sup))


@dataclass(frozen=True)
class Function(MathElement):
    """``m:func``: a function name applied to ``base``.

    A string or :class:`MathFunctionsOfOneArgument` name is plain text; a
    :class:`MathFunctionsOfTwoArguments` name needs its second argument, so it is
    written through :func:`function` or :meth:`MathElement.as_argument_of`.
    :attr:`function_type` and :attr:`second_argument` read either kind back.
    """

    name: MathContent
    base: MathContent
    omml_name: ClassVar[str] = "func"
    _arguments: ClassVar[tuple[str, ...]] = ("name", "base")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "name", math_content(_function_name(self.name)))
        _set(self, "base", math_content(self.base))

    @property
    def function_type(
        self,
    ) -> MathFunctionsOfOneArgument | MathFunctionsOfTwoArguments | None:
        """The enumerated function this name is (plain-text ``sin``, ``log`` with a
        subscripted base, ``lim`` with a lower limit ...), else ``None``."""
        return _function_type(self.name)[0]

    @property
    def second_argument(self) -> MathContent | None:
        """A two-argument function's second argument (``log``'s base, ``lim``'s limit)."""
        return _function_type(self.name)[1]


@dataclass(frozen=True)
class Bar(MathElement):
    """``m:bar``: a rule above or below ``base`` (ECMA-376 §22.1.2.7)."""

    base: MathContent
    position: str = "top"
    omml_name: ClassVar[str] = "bar"
    _arguments: ClassVar[tuple[str, ...]] = ("base",)
    __hash__ = None

    def __post_init__(self) -> None:
        _position(self.position)
        _set(self, "base", math_content(self.base))


@dataclass(frozen=True)
class Box(MathElement):
    """``m:box``: group content, optionally emulate an operator or differential.
    ``alignment_point`` writes ``m:aln``; ``break_before`` writes ``m:brk``.
    Optional ``break_alignment`` is ``m:brk/@m:alnAt`` (1-255), requiring a break."""

    base: MathContent
    operator_emulation: bool = False
    no_break: bool = False
    differential: bool = False
    alignment_point: bool = field(default=False, kw_only=True)
    break_before: bool = field(default=False, kw_only=True)
    break_alignment: int | None = field(default=None, kw_only=True)
    omml_name: ClassVar[str] = "box"
    _arguments: ClassVar[tuple[str, ...]] = ("base",)
    __hash__ = None

    def __post_init__(self) -> None:
        _booleans(
            self,
            (
                "operator_emulation",
                "no_break",
                "differential",
                "alignment_point",
                "break_before",
            ),
        )
        if self.break_alignment is not None:
            if type(self.break_alignment) is not int or not 1 <= self.break_alignment <= 255:
                raise ValueError("Box break_alignment must be an integer from 1 to 255")
            if not self.break_before:
                raise ValueError("Box break_alignment requires break_before")
        _set(self, "base", math_content(self.base))


@dataclass(frozen=True)
class BorderBox(MathElement):
    """``m:borderBox``: four independently hidden borders and four strike lines."""

    base: MathContent
    hide_top: bool = False
    hide_bottom: bool = False
    hide_left: bool = False
    hide_right: bool = False
    strike_horizontal: bool = False
    strike_vertical: bool = False
    strike_bottom_left_top_right: bool = False
    strike_top_left_bottom_right: bool = False
    omml_name: ClassVar[str] = "borderBox"
    _arguments: ClassVar[tuple[str, ...]] = ("base",)
    __hash__ = None

    def __post_init__(self) -> None:
        _booleans(self, tuple(name for name, _ in _BORDER_FLAGS))
        _set(self, "base", math_content(self.base))


@dataclass(frozen=True)
class GroupChr(MathElement):
    """``m:groupChr``: stretch ``char`` above/below ``base``; set baseline alignment."""

    base: MathContent
    char: str = "⏟"
    position: str = "bottom"
    vertical_justification: str = "top"
    omml_name: ClassVar[str] = "groupChr"
    _arguments: ClassVar[tuple[str, ...]] = ("base",)
    __hash__ = None

    def __post_init__(self) -> None:
        if not isinstance(self.char, str) or len(self.char) != 1:
            raise ValueError("GroupChr char must be one character")
        _position(self.position)
        _position(self.vertical_justification)
        _set(self, "base", math_content(self.base))


@dataclass(frozen=True)
class LowerLimit(MathElement):
    """``m:limLow``: a limit below ``base``."""

    base: MathContent
    limit: MathContent
    omml_name: ClassVar[str] = "limLow"
    _arguments: ClassVar[tuple[str, ...]] = ("base", "limit")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "base", math_content(self.base))
        _set(self, "limit", math_content(self.limit))


@dataclass(frozen=True)
class UpperLimit(MathElement):
    """``m:limUpp``: a limit above ``base``."""

    base: MathContent
    limit: MathContent
    omml_name: ClassVar[str] = "limUpp"
    _arguments: ClassVar[tuple[str, ...]] = ("base", "limit")
    __hash__ = None

    def __post_init__(self) -> None:
        _set(self, "base", math_content(self.base))
        _set(self, "limit", math_content(self.limit))


@dataclass(frozen=True)
class Phantom(MathElement):
    """``m:phant``: retain independently its width/ascent/descent, optionally draw it.

    ``transparent`` preserves the base's spacing classes, not its visibility.
    The authoring default hides the base; OMML without ``m:show`` shows it.
    """

    base: MathContent
    show: bool = False
    zero_width: bool = False
    zero_ascent: bool = False
    zero_descent: bool = False
    transparent: bool = False
    omml_name: ClassVar[str] = "phant"
    _arguments: ClassVar[tuple[str, ...]] = ("base",)
    __hash__ = None

    def __post_init__(self) -> None:
        _booleans(self, tuple(name for name, _ in _PHANTOM_FLAGS))
        _set(self, "base", math_content(self.base))


@dataclass(frozen=True)
class EquationArray(MathElement):
    """``m:eqArr``: stacked rows with top/center/bottom baseline justification.

    ``row_spacing_rule``: 0 single, 1 one-and-a-half, 2 double, 3 exact
    (``row_spacing`` in points), 4 multiple (half-line units).
    ``maximum_distribution`` / ``object_distribution`` control OMML maxDist/objDist.
    """

    rows: tuple[MathContent, ...]
    base_justification: str = "center"
    row_spacing_rule: int = 0
    row_spacing: int = 0
    maximum_distribution: bool = field(default=False, kw_only=True)
    object_distribution: bool = field(default=False, kw_only=True)
    omml_name: ClassVar[str] = "eqArr"
    __hash__ = None

    def __post_init__(self) -> None:
        _booleans(self, ("maximum_distribution", "object_distribution"))
        rows = tuple(math_content(row) for row in self.rows)
        if not rows:
            raise ValueError("EquationArray needs at least one row")
        if self.base_justification not in ("top", "center", "bottom"):
            raise ValueError("EquationArray base_justification must be top, center or bottom")
        _spacing(self, "row_spacing_rule", "row_spacing")
        _set(self, "rows", rows)

    @property
    def children(self) -> tuple[MathContent, ...]:
        return self.rows

    def insert(self, index: int, content: Any) -> None:
        """Insert one equation row at ``index``."""
        from .math_text_builder import edit_sequence

        edit_sequence(self, "rows", index, content, insert=True, grouped=True)

    def remove(self, index: int) -> None:
        """Remove one row while retaining at least one row."""
        from .math_text_builder import edit_sequence

        edit_sequence(self, "rows", index, insert=False, grouped=True)


@dataclass(frozen=True)
class PreSubSup(MathElement):
    """``m:sPre``: subscript and superscript preceding ``base``."""

    base: MathContent
    sub: MathContent
    sup: MathContent
    omml_name: ClassVar[str] = "sPre"
    _arguments: ClassVar[tuple[str, ...]] = ("sub", "sup", "base")
    __hash__ = None

    def __post_init__(self) -> None:
        for name in ("base", "sub", "sup"):
            _set(self, name, math_content(getattr(self, name)))


def _position(value: str) -> None:
    if value not in ("top", "bottom"):
        raise ValueError("position must be top or bottom")


def _booleans(node: Any, names: tuple[str, ...]) -> None:
    for name in names:
        if type(getattr(node, name)) is not bool:
            raise TypeError(f"{type(node).__name__} {name} must be a bool")


def _size(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("size must be a number of points")
    if not 1 <= value <= 4000 or round(value * 100) != value * 100:
        raise ValueError("size must be 1-4000 points in hundredths")
    return float(value)


def _spacing(node: Any, rule_name: str, value_name: str) -> None:
    rule, value = getattr(node, rule_name), getattr(node, value_name)
    if isinstance(rule, MathSpacingRule):
        _set(node, rule_name, int(rule))
    elif type(rule) is not int or not 0 <= rule <= 4:
        raise ValueError(f"{type(node).__name__} {rule_name} must be an integer from 0 to 4")
    if type(value) is not int or not 0 <= value <= 65_535:
        raise ValueError(f"{type(node).__name__} {value_name} must be an unsigned 16-bit integer")


_BORDER_FLAGS = (
    ("hide_top", "hideTop"),
    ("hide_bottom", "hideBot"),
    ("hide_left", "hideLeft"),
    ("hide_right", "hideRight"),
    ("strike_horizontal", "strikeH"),
    ("strike_vertical", "strikeV"),
    ("strike_bottom_left_top_right", "strikeBLTR"),
    ("strike_top_left_bottom_right", "strikeTLBR"),
)
_PHANTOM_FLAGS = (
    ("show", "show"),
    ("zero_width", "zeroWid"),
    ("zero_ascent", "zeroAsc"),
    ("zero_descent", "zeroDesc"),
    ("transparent", "transp"),
)


@dataclass(frozen=True)
class OpaqueMath(MathElement):
    """An Office Math element outside this tree's constructs, kept verbatim.

    ``name`` (also ``omml_name``) is its OMML element name (for example ``aln``). Its
    arguments are not modelled, so ``children`` is empty. Like every run's, its
    ``a:rPr`` sizes are the :class:`Equation`'s ``size``: a sized equation writes them
    and reads them back into ``size``, not into this XML.
    """

    xml: str
    name: str = field(init=False)

    def __post_init__(self) -> None:
        element = ET.fromstring(self.xml)
        if not element.tag.startswith(f"{{{M_NS}}}"):
            raise ValueError("OpaqueMath must hold one Office Math element")
        _set(self, "name", _local(element.tag))

    @property  # type: ignore[override]
    def omml_name(self) -> str:  # type: ignore[override]
        return self.name


_NODE_TYPES = (
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
    OpaqueMath,
)

#: OMML element names this tree models; any other reads back as :class:`OpaqueMath`.
MODELED_ELEMENTS = tuple(node.omml_name for node in _NODE_TYPES if node is not OpaqueMath)

#: ``m:jc`` values of a display equation (:class:`MathJustification`).
JUSTIFICATIONS = (None, *MathJustification)


@dataclass(frozen=True, init=False)
class Equation:
    """One ``a14:m`` zone with separate ``m:oMath`` blocks.

    ``Equation(content)`` creates one block; :meth:`from_blocks` creates several.
    ``content`` is the flattened compatibility view. ``display=False`` writes one
    inline block; multiple blocks require display math. ``justification`` controls
    display ``m:jc``. ``size`` is inherited uniformly in points (1-4000, hundredths)
    without replacing explicit run sizes. Readback canonicalizes run sizes equal
    to inherited size to ``None``; uniformly sized run-only zones hoist size.
    """

    blocks: tuple[MathContent, ...]
    display: bool = True
    justification: MathJustification | None = None
    size: float | None = None
    __hash__ = None

    def __init__(
        self,
        content: Any,
        display: bool = True,
        justification: MathJustification | str | None = None,
        size: float | None = None,
    ) -> None:
        normalized = math_content(content)
        if not normalized:
            raise ValueError("Equation needs content")
        if type(display) is not bool:
            raise TypeError("Equation display must be a bool")
        if justification is not None:
            justification = _enum(MathJustification, justification, "justification")
        if justification is not None and not display:
            raise ValueError("only a display equation has a justification")
        _set(self, "blocks", (normalized,))
        _set(self, "display", display)
        _set(self, "justification", justification)
        _set(self, "size", _size(size))

    @classmethod
    def from_blocks(
        cls,
        *blocks: Any,
        display: bool = True,
        justification: MathJustification | str | None = None,
        size: float | None = None,
    ) -> Equation:
        """Construct separate nonempty blocks, retaining each block boundary."""
        normalized = tuple(math_content(block) for block in blocks)
        if not normalized or any(not block for block in normalized):
            raise ValueError("Equation needs at least one nonempty block")
        equation = cls(normalized[0], display, justification, size)
        if not display and len(normalized) > 1:
            from .math_mathml import UnsupportedEquationError

            raise UnsupportedEquationError("oMathPara", "multiple blocks require display math")
        _set(equation, "blocks", normalized)
        return equation

    @property
    def content(self) -> MathContent:
        """All blocks flattened, retaining runs' explicit formatting."""
        return tuple(node for block in self.blocks for node in block)

    def insert_block(self, index: int, content: Any) -> None:
        """Insert a separate nonempty block, validating the complete tree first."""
        from .math_text_builder import edit_equation_blocks

        edit_equation_blocks(self, index, content, operation="insert")

    def set_block(self, index: int, content: Any) -> None:
        """Replace an indexed block atomically."""
        from .math_text_builder import edit_equation_blocks

        edit_equation_blocks(self, index, content, operation="set")

    def remove_block(self, index: int) -> None:
        """Remove an indexed block while retaining one nonempty block."""
        from .math_text_builder import edit_equation_blocks

        edit_equation_blocks(self, index, operation="remove")

    def to_omml(self) -> ET.Element:
        """The ``a14:m`` element for this equation."""
        return equation_to_omml(self)

    def to_mathml(self) -> str:
        """Presentation MathML for this equation (``<math>`` with ``display="block"``
        for a display equation)."""
        from .math_mathml import equation_to_mathml

        return equation_to_mathml(self)

    @property
    def text(self) -> str:
        """Structure-preserving linear text; unsupported math raises by name."""
        from .math_mathml import equation_to_linear_text

        return equation_to_linear_text(self)


def _write_node(parent: ET.Element, node: MathNode) -> None:
    from .math_text_builder import _write_node as write_node

    write_node(parent, node)


def _write_content(parent: ET.Element, content: MathContent) -> None:
    from .math_text_builder import _write_content as write_content

    write_content(parent, content)


def equation_to_omml(equation: Equation) -> ET.Element:
    """Build the ``a14:m`` element, preserving separate equation blocks."""
    from .math_text_builder import equation_to_omml as write_equation

    return write_equation(equation)


def read_math_content(parent: ET.Element) -> MathContent:
    """Read the nodes of an OMML argument (``m:e``, ``m:num``, ``m:oMath`` ...)."""
    from .math_text_builder import read_math_content as read_content

    return read_content(parent)


def equation_from_omml(zone: ET.Element) -> Equation:
    """Read an ``a14:m`` element or bare ``m:oMathPara`` / ``m:oMath``."""
    from .math_text_builder import equation_from_omml as read_equation

    return read_equation(zone)


def math_element_from_omml(element: ET.Element) -> MathNode | MathBlock:
    """Read an Office Math node or an ``m:oMath`` sequence of nodes."""
    from .math_text_builder import math_element_from_omml as read_element

    return read_element(element)


# --- Factories --------------------------------------------------------------------------
# Each returns exactly the node its typed constructor builds from the same arguments.


def run(
    text: str,
    style: str | None = None,
    *,
    font: str | None = None,
    color: str | None = None,
    size: float | None = None,
) -> MathRun:
    """Equation text with optional typeface, six-digit RGB and point-size overrides."""
    return MathRun(text, style, font=font, color=color, size=size)


def block(*items: Any) -> MathBlock:
    """``items`` (text, nodes or blocks) in sequence; see :class:`MathBlock`."""
    return MathBlock(items)


def fraction(
    numerator: Any,
    denominator: Any,
    kind: MathFractionTypes | str = MathFractionTypes.BAR,
) -> Fraction:
    """A fraction (``m:f``) of type ``kind``; see :class:`Fraction`."""
    return Fraction(numerator, denominator, kind)


def radical(base: Any, degree: Any = None) -> Radical:
    """A square root, or an n-th root with ``degree`` (``m:rad``)."""
    return Radical(base, degree)


def nary(
    operator: MathNaryOperatorTypes | MathIntegralTypes | str,
    base: Any,
    lower: Any = None,
    upper: Any = None,
    limits: MathLimitLocations | str = MathLimitLocations.UNDER_OVER,
    *,
    grow: bool = False,
) -> Nary:
    """A large operator over ``base`` (``m:nary``); see :class:`Nary`."""
    return Nary(operator, base, lower, upper, limits, grow=grow)


def integral(
    base: Any,
    kind: MathIntegralTypes | str = MathIntegralTypes.SIMPLE,
    lower: Any = None,
    upper: Any = None,
    limits: MathLimitLocations | str = MathLimitLocations.SUBSCRIPT_SUPERSCRIPT,
    *,
    grow: bool = False,
) -> Nary:
    """An integral of ``base`` (``m:nary``), limits as scripts by default."""
    return Nary(
        _enum(MathIntegralTypes, kind, "integral"),
        base,
        lower,
        upper,
        limits,
        grow=grow,
    )


def matrix(
    rows: Iterable[Iterable[Any]],
    *,
    column_alignments: tuple[str, ...] = (),
    column_gap_rule: int = 0,
    column_gap: int = 0,
    minimum_column_width: int = 0,
    row_spacing_rule: int = 0,
    row_spacing: int = 0,
    base_justification: str = "center",
    hide_placeholders: bool | None = None,
) -> Matrix:
    """A rectangular matrix; alignment and gap/width units are in :class:`Matrix`."""
    return Matrix(
        tuple(tuple(row) for row in rows),
        column_alignments=column_alignments,
        column_gap_rule=column_gap_rule,
        column_gap=column_gap,
        minimum_column_width=minimum_column_width,
        row_spacing_rule=row_spacing_rule,
        row_spacing=row_spacing,
        base_justification=base_justification,
        hide_placeholders=hide_placeholders,
    )


def delimiter(
    *elements: Any,
    begin: str = "(",
    end: str = ")",
    separator: str = "|",
    shape: MathDelimiterShape | str = MathDelimiterShape.CENTERED,
    grow: bool = True,
) -> Delimiter:
    """``elements`` between ``begin`` and ``end``, separated by ``separator`` (``m:d``)."""
    return Delimiter(elements, begin, end, separator, shape, grow=grow)


def accent(base: Any, char: str = "\u0302") -> Accent:
    """``char`` (a combining mark) over ``base`` (``m:acc``)."""
    return Accent(base, char)


def subscript(base: Any, sub: Any) -> Sub:
    """``base`` with a subscript (``m:sSub``)."""
    return Sub(base, sub)


def superscript(base: Any, sup: Any) -> Sup:
    """``base`` with a superscript (``m:sSup``)."""
    return Sup(base, sup)


def sub_superscript(base: Any, sub: Any, sup: Any) -> SubSup:
    """``base`` with a subscript and a superscript on its right (``m:sSubSup``)."""
    return SubSup(base, sub, sup)


def pre_sub_superscript(base: Any, sub: Any, sup: Any) -> PreSubSup:
    """``base`` with a subscript and a superscript on its left (``m:sPre``)."""
    return PreSubSup(base, sub, sup)


def function(
    name: MathFunctionsOfOneArgument | MathFunctionsOfTwoArguments | Any,
    base: Any,
    argument: Any = None,
) -> Function:
    """The function ``name`` applied to ``base`` (``m:func``): a string or
    :class:`MathFunctionsOfOneArgument` is plain text, a
    :class:`MathFunctionsOfTwoArguments` takes its second ``argument``."""
    return Function(_function_name(name, argument), base)


def bar(base: Any, position: str = "top") -> Bar:
    """A bar over (``top``) or under (``bottom``) ``base`` (``m:bar``)."""
    return Bar(base, position)


def box(
    base: Any,
    operator_emulation: bool = False,
    no_break: bool = False,
    differential: bool = False,
    *,
    alignment_point: bool = False,
    break_before: bool = False,
    break_alignment: int | None = None,
) -> Box:
    """``base`` as one unit (``m:box``); see :class:`Box`."""
    return Box(
        base,
        operator_emulation,
        no_break,
        differential,
        alignment_point=alignment_point,
        break_before=break_before,
        break_alignment=break_alignment,
    )


def border_box(base: Any, **flags: bool) -> BorderBox:
    """A border around ``base`` (``m:borderBox``); ``flags`` are :class:`BorderBox`'s."""
    return BorderBox(base, **flags)


def group_char(
    base: Any,
    char: str = "⏟",
    position: str = "bottom",
    vertical_justification: str = "top",
) -> GroupChr:
    """A grouping character (an under brace by default) over or under ``base``
    (``m:groupChr``); see :class:`GroupChr`."""
    return GroupChr(base, char, position, vertical_justification)


def lower_limit(base: Any, limit: Any) -> LowerLimit:
    """``limit`` under ``base`` (``m:limLow``)."""
    return LowerLimit(base, limit)


def upper_limit(base: Any, limit: Any) -> UpperLimit:
    """``limit`` over ``base`` (``m:limUpp``)."""
    return UpperLimit(base, limit)


def phantom(base: Any, **flags: bool) -> Phantom:
    """``base`` as a phantom (``m:phant``); ``flags`` are :class:`Phantom`'s."""
    return Phantom(base, **flags)


def equation_array(
    *rows: Any,
    base_justification: str = "center",
    row_spacing_rule: int = 0,
    row_spacing: int = 0,
    maximum_distribution: bool = False,
    object_distribution: bool = False,
) -> EquationArray:
    """Equations stacked one per row (``m:eqArr``); see :class:`EquationArray`."""
    return EquationArray(
        rows,
        base_justification,
        row_spacing_rule,
        row_spacing,
        maximum_distribution=maximum_distribution,
        object_distribution=object_distribution,
    )


def opaque(xml: str) -> OpaqueMath:
    """An Office Math element outside the tree, kept verbatim; see :class:`OpaqueMath`."""
    return OpaqueMath(xml)


#: The factory of every node type.
ELEMENT_FACTORIES: dict[type[MathElement], Callable[..., MathElement]] = {
    MathRun: run,
    MathBlock: block,
    Fraction: fraction,
    Radical: radical,
    Nary: nary,
    Matrix: matrix,
    Delimiter: delimiter,
    Accent: accent,
    Sub: subscript,
    Sup: superscript,
    SubSup: sub_superscript,
    PreSubSup: pre_sub_superscript,
    Function: function,
    Bar: bar,
    Box: box,
    BorderBox: border_box,
    GroupChr: group_char,
    LowerLimit: lower_limit,
    UpperLimit: upper_limit,
    Phantom: phantom,
    EquationArray: equation_array,
    OpaqueMath: opaque,
}


# --- Paragraph XML ----------------------------------------------------------------------

_PARAGRAPH_CONTENT = {"r", "br", "fld"}


def paragraph_equations(paragraph: ET.Element) -> list[Equation]:
    """The equations of one ``a:p`` element, in document order."""
    return [equation_from_omml(zone) for zone in paragraph.iter(f"{{{A14_NS}}}m")]


def set_paragraph_equation(paragraph: ET.Element, equation: Equation | None) -> None:
    """Set display math as paragraph content; inline math retains ordinary runs.

    ``None`` removes equations only. Paragraph properties remain unchanged.
    """
    insertion = None
    for child in list(paragraph):
        equation_zone = child.tag == f"{{{A14_NS}}}m" or (
            child.tag == f"{{{MC_NS}}}AlternateContent"
            and next(child.iter(f"{{{A14_NS}}}m"), None) is not None
        )
        if equation_zone and insertion is None:
            insertion = list(paragraph).index(child)
        replaced = (
            equation is not None
            and equation.display
            and child.tag.startswith(f"{{{A_NS}}}")
            and _local(child.tag) in _PARAGRAPH_CONTENT
        )
        if equation_zone or replaced:
            paragraph.remove(child)
    if equation is None:
        return
    zone = equation_to_omml(equation)
    end = paragraph.find(f"{{{A_NS}}}endParaRPr")
    if insertion is not None:
        paragraph.insert(insertion, zone)
    elif end is None:
        paragraph.append(zone)
    else:
        paragraph.insert(list(paragraph).index(end), zone)


def declare_ignorable_a14(root: ET.Element) -> None:
    """Mark the ``a14`` namespace ignorable on a part root (``mc:Ignorable``).

    An ``a14:m`` directly inside ``a:p`` is an extension element: consumers that know
    ``a14`` (PowerPoint 2010 and later) read the equation; others skip it.
    """
    attribute = f"{{{MC_NS}}}Ignorable"
    prefixes = root.get(attribute, "").split()
    if "a14" not in prefixes:
        root.set(attribute, " ".join([*prefixes, "a14"]))


def apply_shape_equations(
    root: ET.Element,
    shape_element: ET.Element,
    equations: dict[int, Equation | None],
) -> None:
    """Write queued equation changes through the existing slide part editor."""
    from .math_text_builder import ParagraphEquations, apply_paragraph_plan

    body = shape_element.find(f"{{{P_NS}}}txBody")
    if body is None:
        raise AttributeError("shape text body is unavailable")
    paragraphs = body.findall(f"{{{A_NS}}}p")
    for index, equation in sorted(equations.items()):
        if index < 0 or index >= len(paragraphs):
            raise IndexError("paragraph index out of range")
        if isinstance(equation, ParagraphEquations):
            apply_paragraph_plan(paragraphs[index], equation)
        else:
            set_paragraph_equation(paragraphs[index], equation)
    if any(equations.values()):
        declare_ignorable_a14(root)


# --- Inspection -------------------------------------------------------------------------


@dataclass(frozen=True)
class SlideEquation:
    """One equation found on a slide."""

    shape_id: int
    shape_name: str
    paragraph_index: int
    equation: Equation


def _shape_candidates(root: ET.Element) -> Iterator[ET.Element]:
    """Every ``p:sp`` of the part, preferring an ``mc:Choice`` over its fallback."""
    tree = root.find(f".//{{{P_NS}}}spTree")
    if tree is None:
        return
    yield from _walk_shapes(tree)


def _walk_shapes(container: ET.Element) -> Iterator[ET.Element]:
    for child in container:
        if child.tag == f"{{{P_NS}}}sp":
            yield child
        elif child.tag == f"{{{P_NS}}}grpSp":
            yield from _walk_shapes(child)
        elif child.tag == f"{{{MC_NS}}}AlternateContent":
            choice = next(
                (
                    branch
                    for branch in child.findall(f"{{{MC_NS}}}Choice")
                    if branch.find(f".//{{{A14_NS}}}m") is not None
                ),
                None,
            )
            branch = choice if choice is not None else child.find(f"{{{MC_NS}}}Fallback")
            if branch is not None:
                yield from _walk_shapes(branch)


def _shape_id(shape: ET.Element) -> tuple[int, str]:
    nv = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
    if nv is None:
        return -1, ""
    try:
        return int(nv.get("id", "-1")), nv.get("name", "")
    except ValueError:
        return -1, nv.get("name", "")


def part_equations(root: ET.Element) -> list[SlideEquation]:
    """Every equation in a slide-like part's shape tree, in document order."""
    found: list[SlideEquation] = []
    for shape in _shape_candidates(root):
        body = shape.find(f"{{{P_NS}}}txBody")
        if body is None:
            continue
        shape_id, name = _shape_id(shape)
        for index, paragraph in enumerate(body.findall(f"{{{A_NS}}}p")):
            for equation in paragraph_equations(paragraph):
                found.append(SlideEquation(shape_id, name, index, equation))
    return found


def _slide_root(slide: Any) -> ET.Element:
    presentation = slide._presentation
    partname = str(slide.partname).lstrip("/")
    with zipfile.ZipFile(presentation.path) as package:
        return ET.fromstring(package.read(partname))


def slide_equations(slide: Any) -> list[SlideEquation]:
    """Every equation on a saved slide, including PowerPoint's ``mc:AlternateContent``
    equation shapes (whose ``mc:Choice`` holds the equation)."""
    return part_equations(_slide_root(slide))


def paragraph_equation(paragraph: TextParagraph) -> Equation | None:
    """Read the first equation, including queued ordered-run edits."""
    from .math_text_builder import paragraph_plan

    slots = paragraph_plan(paragraph).slots
    return slots[0][1] if slots else None


def _is_slide_shape(shape: Any) -> bool:
    from .text_facade_queue import (
        _is_group_child_text_shape,
        _is_part_scoped_text_shape,
        _is_pending_group_child_text_shape,
    )

    return not (
        _is_part_scoped_text_shape(shape)
        or _is_group_child_text_shape(shape)
        or _is_pending_group_child_text_shape(shape)
    )


def _queue_equations(shape: Any, index: int, equation: Equation | None) -> None:
    pending = shape._payload.setdefault("_equations", {})
    pending[index] = equation
    shape._slide._presentation._queue_text_frame_advanced(
        shape._slide._index, shape._index, "equations", dict(pending)
    )


def queue_paragraph_equation(paragraph: TextParagraph, equation: Equation | None) -> None:
    """Assign through the ordered paragraph mutation plan."""
    from .math_text_builder import assign_equation

    assign_equation(paragraph, equation)


def forget_paragraph_equation(paragraph: TextParagraph) -> None:
    """Drop a paragraph's equation when its text is replaced, so the save keeps the text."""
    from .math_text_builder import paragraph_plan

    shape = paragraph._shape
    if _is_slide_shape(shape) and paragraph_plan(paragraph).slots:
        _queue_equations(shape, paragraph._index, None)
