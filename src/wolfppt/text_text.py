"""Element-backed ``pptx.text.text`` proxies over standalone DrawingML text XML.

Construct these over a ``p:txBody``, ``a:p``, ``a:r`` or ``a:rPr`` element
(stdlib :mod:`xml.etree.ElementTree`) to read and edit text, paragraphs, runs,
and run bold/italic. Only those contracts are implemented here. Shape text
frames from an opened presentation are the subclasses in
:mod:`wolfppt.text_facade` and :mod:`wolfppt.text_run_facade`, which edit
through WolfPPT's package writer and cover the wider formatting surface.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = f"{{{A_NS}}}p"
_R = f"{{{A_NS}}}r"
_BR = f"{{{A_NS}}}br"
_FLD = f"{{{A_NS}}}fld"
_T = f"{{{A_NS}}}t"
_RPR = f"{{{A_NS}}}rPr"
_END_PARA_RPR = f"{{{A_NS}}}endParaRPr"
_CONTENT = (_R, _BR, _FLD)
# x09 (tab) and x0A (line feed) are valid XML text; other C0 controls are not.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0B-\x1F]")
_XSD_BOOLEAN = {"1": True, "true": True, "0": False, "false": False}


def _escape_control_characters(text: str) -> str:
    """Store each XML-invalid control character as its ``_xHHHH_`` text escape."""
    return _CONTROL_CHARACTERS.sub(lambda match: f"_x{ord(match[0]):04X}_", text)


def _append_content(p: ET.Element, tag: str) -> ET.Element:
    """Append a run, break, or field before any trailing ``a:endParaRPr``."""
    child = p.makeelement(tag, {})
    end = p.find(_END_PARA_RPR)
    if end is None:
        p.append(child)
    else:
        p.insert(list(p).index(end), child)
    return child


def _append_run(p: ET.Element, text: str = "") -> ET.Element:
    r = _append_content(p, _R)
    t = r.makeelement(_T, {})
    if text:
        t.text = _escape_control_characters(text)
    r.append(t)
    return r


def _clear_paragraph(p: ET.Element) -> None:
    for child in [child for child in p if child.tag in _CONTENT]:
        p.remove(child)


def _append_paragraph_text(p: ET.Element, text: str) -> None:
    """Append runs for ``text``; line feed and vertical tab become ``a:br``."""
    for index, run_text in enumerate(re.split("\n|\v", text)):
        if index:
            _append_content(p, _BR)
        if run_text:
            _append_run(p, run_text)


def _child_text(element: ET.Element) -> str:
    if element.tag == _BR:
        return "\v"
    t = element.find(_T)
    return "" if t is None or t.text is None else t.text


class TextFrame:
    """Text of a ``p:txBody`` element."""

    def __init__(self, txBody: ET.Element, parent: object) -> None:
        self._element = self._txBody = txBody
        self._parent = parent

    @property
    def paragraphs(self) -> tuple[_Paragraph, ...]:
        return tuple(_Paragraph(p, self) for p in self._txBody.findall(_P))

    def add_paragraph(self) -> _Paragraph:
        p = self._txBody.makeelement(_P, {})
        self._txBody.append(p)
        return _Paragraph(p, self)

    def clear(self) -> None:
        """Keep only the first paragraph, emptied of runs, breaks, and fields."""
        paragraphs = self._txBody.findall(_P)
        for p in paragraphs[1:]:
            self._txBody.remove(p)
        self.paragraphs[0].clear()

    @property
    def text(self) -> str:
        """Paragraph texts joined by line feed; a line break reads as vertical tab."""
        return "\n".join(paragraph.text for paragraph in self.paragraphs)

    @text.setter
    def text(self, text: str) -> None:
        for p in self._txBody.findall(_P):
            self._txBody.remove(p)
        for paragraph_text in text.split("\n"):
            _append_paragraph_text(self.add_paragraph()._p, paragraph_text)


class _Paragraph:
    """Text of an ``a:p`` element."""

    def __init__(self, p: ET.Element, parent: object) -> None:
        self._element = self._p = p
        self._parent = parent

    def add_line_break(self) -> None:
        _append_content(self._p, _BR)

    def add_run(self) -> _Run:
        return _Run(_append_run(self._p), self)

    def clear(self) -> _Paragraph:
        """Remove runs, line breaks, and fields; keep paragraph properties."""
        _clear_paragraph(self._p)
        return self

    @property
    def runs(self) -> tuple[_Run, ...]:
        return tuple(_Run(r, self) for r in self._p.findall(_R))

    @property
    def text(self) -> str:
        return "".join(_child_text(child) for child in self._p if child.tag in _CONTENT)

    @text.setter
    def text(self, text: str) -> None:
        _clear_paragraph(self._p)
        _append_paragraph_text(self._p, text)


class _Run:
    """Text and character properties of an ``a:r`` element."""

    def __init__(self, r: ET.Element, parent: object) -> None:
        self._element = self._r = r
        self._parent = parent

    @property
    def font(self) -> Font:
        rPr = self._r.find(_RPR)
        if rPr is None:
            rPr = self._r.makeelement(_RPR, {})
            self._r.insert(0, rPr)
        return Font(rPr)

    @property
    def text(self) -> str:
        return _child_text(self._r)

    @text.setter
    def text(self, text: str) -> None:
        t = self._r.find(_T)
        if t is None:
            t = self._r.makeelement(_T, {})
            self._r.append(t)
        t.text = _escape_control_characters(text)


class Font:
    """Bold and italic of an ``a:rPr`` (or ``a:defRPr``/``a:endParaRPr``) element."""

    def __init__(self, rPr: ET.Element) -> None:
        self._element = self._rPr = rPr

    def _flag(self, name: str) -> bool | None:
        value = self._rPr.get(name)
        if value is None:
            return None
        if value not in _XSD_BOOLEAN:
            raise ValueError(f"a:rPr/@{name} is not an xsd:boolean: {value!r}")
        return _XSD_BOOLEAN[value]

    def _set_flag(self, name: str, value: bool | None) -> None:
        if value is None:
            self._rPr.attrib.pop(name, None)
        else:
            self._rPr.set(name, "1" if value else "0")

    @property
    def bold(self) -> bool | None:
        """True or False when set directly; None when inherited."""
        return self._flag("b")

    @bold.setter
    def bold(self, value: bool | None) -> None:
        self._set_flag("b", value)

    @property
    def italic(self) -> bool | None:
        """True or False when set directly; None when inherited."""
        return self._flag("i")

    @italic.setter
    def italic(self, value: bool | None) -> None:
        self._set_flag("i", value)
