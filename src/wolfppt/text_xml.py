"""Shared DrawingML text XML mutation helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import emu_to_centipoints as _emu_to_centipoints
from .xml_helpers import find_ooxml, ooxml_namespace
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_TEXT_FRAME_AUTO_SIZE_TAGS = {"noAutofit", "spAutoFit", "normAutofit"}


_TEXT_VERTICAL_VALUES = {"horz", "vert", "vert270", "wordArtVert"}
_TAB_ALIGNMENTS = {"l", "ctr", "r", "dec"}
# Friendly tab stop alignment names (Aspose TabAlignment / Word wording).
_TAB_ALIGNMENT_ALIASES = {
    "left": "l",
    "center": "ctr",
    "centre": "ctr",
    "right": "r",
    "decimal": "dec",
}


def _integer_value(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return value


def _clear_text_frame_auto_size_children(body_properties: ET.Element) -> None:
    for child in list(body_properties):
        if _xml_local_name(child.tag) in _TEXT_FRAME_AUTO_SIZE_TAGS:
            body_properties.remove(child)


def _text_frame_auto_size_insert_index(body_properties: ET.Element) -> int:
    trailing_tags = {"scene3d", "sp3d", "flatTx", "extLst"}
    for index, child in enumerate(list(body_properties)):
        if _xml_local_name(child.tag) in trailing_tags:
            return index
    return len(body_properties)


def _apply_text_body_auto_size(
    body_properties: ET.Element,
    auto_size: str | None,
    autofit_scale: dict[str, float | None] | None = None,
) -> None:
    if auto_size is None:
        _clear_text_frame_auto_size_children(body_properties)
        return

    existing_element: ET.Element | None = None
    for child in list(body_properties):
        if _xml_local_name(child.tag) in _TEXT_FRAME_AUTO_SIZE_TAGS:
            if existing_element is None:
                existing_element = child
            else:
                body_properties.remove(child)

    if existing_element is not None and _xml_local_name(existing_element.tag) == auto_size:
        target_element = existing_element
    else:
        if existing_element is not None:
            body_properties.remove(existing_element)
        target_element = ET.Element(f"{{{A_NS}}}{auto_size}")
        body_properties.insert(
            _text_frame_auto_size_insert_index(body_properties),
            target_element,
        )

    if auto_size == "normAutofit" and autofit_scale is not None:
        font_scale = autofit_scale.get("font_scale")
        if font_scale is None:
            target_element.attrib.pop("fontScale", None)
        else:
            target_element.set("fontScale", str(round(font_scale * 100000)))
        line_spacing_reduction = autofit_scale.get("line_spacing_reduction")
        if line_spacing_reduction is None or line_spacing_reduction == 0.0:
            target_element.attrib.pop("lnSpcReduction", None)
        else:
            target_element.set("lnSpcReduction", str(round(line_spacing_reduction * 100000)))


def _text_character_properties_element(text_child: ET.Element) -> ET.Element:
    run_properties = text_child.find(f"{{{A_NS}}}rPr")
    if run_properties is not None:
        return run_properties
    run_properties = ET.Element(f"{{{A_NS}}}rPr")
    insert_at = 0
    for index, child in enumerate(list(text_child)):
        if _xml_local_name(child.tag) in {"t", "fldData", "extLst"}:
            insert_at = index
            break
    text_child.insert(insert_at, run_properties)
    return run_properties


def _end_paragraph_run_properties_element(paragraph: ET.Element) -> ET.Element:
    run_properties = paragraph.find(f"{{{A_NS}}}endParaRPr")
    if run_properties is not None:
        return run_properties
    run_properties = ET.Element(f"{{{A_NS}}}endParaRPr")
    insert_at = len(paragraph)
    for index, child in enumerate(list(paragraph)):
        if _xml_local_name(child.tag) == "extLst":
            insert_at = index
            break
    paragraph.insert(insert_at, run_properties)
    return run_properties


def _set_fit_font_properties(run_properties: ET.Element, fit: dict[str, Any]) -> None:
    _set_font_size(run_properties, int(fit["size"]))
    _set_font_bool_attribute(run_properties, "b", bool(fit["bold"]))
    _set_font_bool_attribute(run_properties, "i", bool(fit["italic"]))
    _set_font_name(run_properties, str(fit["font_family"]))


def _set_font_bool_attribute(
    run_properties: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if value else "0")


# ST_TextUnderlineType tokens (ECMA-376 Part 1, 21.1.10.82).
_UNDERLINE_TOKENS = frozenset(
    {
        "none",
        "words",
        "sng",
        "dbl",
        "heavy",
        "dotted",
        "dottedHeavy",
        "dash",
        "dashHeavy",
        "dashLong",
        "dashLongHeavy",
        "dotDash",
        "dotDashHeavy",
        "dotDotDash",
        "dotDotDashHeavy",
        "wavy",
        "wavyHeavy",
        "wavyDbl",
    }
)


def _set_font_underline(run_properties: ET.Element, value: bool | str | None) -> None:
    """Write a ``u`` attribute: booleans map to ``sng``/``none``; strings must
    be ``ST_TextUnderlineType`` tokens and are written verbatim."""
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    if isinstance(value, str):
        if value not in _UNDERLINE_TOKENS:
            raise ValueError(f"unsupported underline value: {value!r}")
        run_properties.set("u", value)
        return
    run_properties.set("u", "sng" if value else "none")


# ST_TextStrikeType tokens (ECMA-376 Part 1, 21.1.10.79).
_STRIKE_TOKENS = frozenset({"noStrike", "sngStrike", "dblStrike"})


def _set_font_strike(run_properties: ET.Element, value: bool | str | None) -> None:
    """Write a ``strike`` attribute: booleans map to ``sngStrike``/``noStrike``;
    strings must be ``ST_TextStrikeType`` tokens (``dblStrike`` included)."""
    if value is None:
        run_properties.attrib.pop("strike", None)
        return
    if isinstance(value, str):
        if value not in _STRIKE_TOKENS:
            raise ValueError(f"unsupported strikethrough value: {value!r}")
        run_properties.set("strike", value)
        return
    run_properties.set("strike", "sngStrike" if value else "noStrike")


def _set_font_size(run_properties: ET.Element, value: int | None) -> None:
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def _set_font_name(run_properties: ET.Element, value: str | None) -> None:
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        insert_at = len(run_properties)
        trailing_tags = {
            "ea",
            "cs",
            "sym",
            "hlinkClick",
            "hlinkMouseOver",
            "rtl",
            "extLst",
        }
        for index, child in enumerate(list(run_properties)):
            if _xml_local_name(child.tag) in trailing_tags:
                insert_at = index
                break
        run_properties.insert(insert_at, latin)
    latin.set("typeface", value)


def _set_font_baseline(run_properties: ET.Element, value: int | None) -> None:
    if value is None:
        run_properties.attrib.pop("baseline", None)
        return
    baseline = _integer_value(value, "baseline")
    if not -100000 <= baseline <= 100000:
        raise ValueError("baseline must be between -100000 and 100000")
    run_properties.set("baseline", str(baseline))


def _set_font_spacing(run_properties: ET.Element, value: int | None) -> None:
    if value is None:
        run_properties.attrib.pop("spc", None)
        return
    run_properties.set("spc", str(_integer_value(value, "spacing")))


def _set_font_caps(run_properties: ET.Element, value: str | bool | None) -> None:
    if value is None or value is False:
        run_properties.attrib.pop("cap", None)
        return
    if value is True:
        run_properties.set("cap", "all")
        return
    if value not in {"all", "small"}:
        raise ValueError("capitalisation must be 'all' or 'small'")
    run_properties.set("cap", value)


def _set_font_highlight(run_properties: ET.Element, value: str | None) -> None:
    existing = run_properties.find(f"{{{A_NS}}}highlight")
    if value is None:
        if existing is not None:
            run_properties.remove(existing)
        return
    if not isinstance(value, str):
        raise TypeError("highlight color must be a six-digit RGB string")
    clean_rgb = value.removeprefix("#").upper()
    if len(clean_rgb) != 6 or any(char not in "0123456789ABCDEF" for char in clean_rgb):
        raise ValueError("highlight color must be a six-digit RGB string")
    if existing is None:
        existing = ET.Element(f"{{{A_NS}}}highlight")
        trailing_tags = {
            "uLnTx",
            "uLn",
            "uFillTx",
            "uFill",
            "latin",
            "ea",
            "cs",
            "sym",
            "hlinkClick",
            "hlinkMouseOver",
            "rtl",
            "extLst",
        }
        insert_at = len(run_properties)
        for index, child in enumerate(list(run_properties)):
            if _xml_local_name(child.tag) in trailing_tags:
                insert_at = index
                break
        run_properties.insert(insert_at, existing)
    for child in list(existing):
        existing.remove(child)
    srgb = ET.SubElement(existing, f"{{{A_NS}}}srgbClr")
    srgb.set("val", clean_rgb)


def _set_text_body_vertical(body_properties: ET.Element, value: str | None) -> None:
    if value is None or value == "horz":
        body_properties.attrib.pop("vert", None)
        return
    if value not in _TEXT_VERTICAL_VALUES:
        raise ValueError("vertical text must be one of 'horz', 'vert', 'vert270', or 'wordArtVert'")
    body_properties.set("vert", value)


def _set_text_body_columns(
    body_properties: ET.Element,
    num_col: int | None,
    spc_col: int | None = None,
) -> None:
    if num_col is None:
        body_properties.attrib.pop("numCol", None)
    else:
        columns = _integer_value(num_col, "column count", minimum=1)
        if columns == 1:
            body_properties.attrib.pop("numCol", None)
        else:
            body_properties.set("numCol", str(columns))
    if spc_col is None:
        body_properties.attrib.pop("spcCol", None)
    else:
        spacing = _integer_value(spc_col, "column spacing", minimum=0)
        if spacing == 0:
            body_properties.attrib.pop("spcCol", None)
        else:
            body_properties.set("spcCol", str(spacing))


# ST_TextVertOverflowType / ST_TextHorzOverflowType (ECMA-376 Part 1, 21.1.10.83/.69).
_TEXT_OVERFLOW_VALUES = {
    "vertOverflow": frozenset({"overflow", "ellipsis", "clip"}),
    "horzOverflow": frozenset({"overflow", "clip"}),
}


def _set_text_body_overflow(body_properties: ET.Element, overflow: dict[str, str | None]) -> None:
    """Write ``vertOverflow``/``horzOverflow`` on ``a:bodyPr``; ``None`` removes."""
    for attr, value in overflow.items():
        allowed = _TEXT_OVERFLOW_VALUES.get(attr)
        if allowed is None:
            raise ValueError(f"unknown text overflow attribute: {attr!r}")
        if value is None:
            body_properties.attrib.pop(attr, None)
        elif value not in allowed:
            raise ValueError(f"{attr} must be one of {sorted(allowed)}, got {value!r}")
        else:
            body_properties.set(attr, value)


def _text_body_overflow(body_properties: ET.Element | None) -> dict[str, str | None]:
    """Stored ``vertOverflow``/``horzOverflow`` of ``a:bodyPr`` (None if absent)."""
    return {
        attr: None if body_properties is None else body_properties.get(attr)
        for attr in _TEXT_OVERFLOW_VALUES
    }


# CT_TextCharacterProperties child order (ECMA-376 Part 1, 21.1.2.3.9).
_RUN_PROPERTY_CHILD_ORDER = (
    "ln",
    "noFill",
    "solidFill",
    "gradFill",
    "blipFill",
    "pattFill",
    "grpFill",
    "effectLst",
    "effectDag",
    "highlight",
    "uLnTx",
    "uLn",
    "uFillTx",
    "uFill",
    "latin",
    "ea",
    "cs",
    "sym",
    "hlinkClick",
    "hlinkMouseOver",
    "rtl",
    "extLst",
)
# Boolean ``a:rPr`` attributes of CT_TextCharacterProperties.
_PORTION_BOOL_ATTRS = frozenset({"kumimoji", "normalizeH", "noProof", "dirty", "err", "smtClean"})
_PORTION_TYPEFACE_TAGS = ("ea", "cs", "sym")
_FONT_METADATA_FIELDS = frozenset(
    f"{slot}.{attr}"
    for slot in ("latin", "ea", "cs", "sym")
    for attr in ("panose", "pitchFamily", "charset")
)
_PITCH_FAMILIES = frozenset(family + pitch for family in range(0, 81, 16) for pitch in range(3))
_PORTION_FIELDS = frozenset(
    {"strike", "kern", "cap", "smtId", "bmk", "altLang"}
    | _PORTION_BOOL_ATTRS
    | set(_PORTION_TYPEFACE_TAGS)
    | {"ln", "uLn", "uFill", "rtl"}
    | _FONT_METADATA_FIELDS
)
#: ST_TextNonNegativePoint / ST_LineWidth upper bounds.
_MAX_KERNING = 400000
_MAX_LINE_WIDTH = 20116800
_MAX_UNSIGNED_INT = 4294967295


def _insert_run_property_child(run_properties: ET.Element, child: ET.Element) -> None:
    rank = _RUN_PROPERTY_CHILD_ORDER.index(_xml_local_name(child.tag))
    for index, sibling in enumerate(list(run_properties)):
        name = _xml_local_name(sibling.tag)
        if name in _RUN_PROPERTY_CHILD_ORDER and _RUN_PROPERTY_CHILD_ORDER.index(name) > rank:
            run_properties.insert(index, child)
            return
    run_properties.append(child)


def _remove_run_property_children(run_properties: ET.Element, *names: str) -> None:
    for child in list(run_properties):
        if _xml_local_name(child.tag) in names:
            run_properties.remove(child)


def _rgb_token(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a six-digit RGB string")
    clean = value.removeprefix("#").upper()
    if len(clean) != 6 or any(char not in "0123456789ABCDEF" for char in clean):
        raise ValueError(f"{label} must be a six-digit RGB string")
    return clean


def _solid_fill(color: str) -> ET.Element:
    fill = ET.Element(f"{{{A_NS}}}solidFill")
    ET.SubElement(fill, f"{{{A_NS}}}srgbClr", {"val": color})
    return fill


def _line_element(tag: str, value: Any, label: str) -> ET.Element:
    """``a:ln``/``a:uLn`` from ``{"width": EMU, "color": "RRGGBB" | None}``."""
    if not isinstance(value, dict) or set(value) - {"width", "color"}:
        raise TypeError(f"{label} must be a dict with 'width' and/or 'color'")
    line = ET.Element(f"{{{A_NS}}}{tag}")
    width = value.get("width")
    if width is not None:
        line.set("w", str(_integer_value(width, f"{label} width", minimum=0)))
        if int(width) > _MAX_LINE_WIDTH:
            raise ValueError(f"{label} width must be at most {_MAX_LINE_WIDTH} EMU")
    color = value.get("color")
    if color is not None:
        line.append(_solid_fill(_rgb_token(color, f"{label} color")))
    return line


def _set_portion_attribute(run_properties: ET.Element, name: str, value: Any) -> None:
    if value is None:
        run_properties.attrib.pop(name, None)
        return
    if name in _PORTION_BOOL_ATTRS:
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be bool or None")
        run_properties.set(name, "1" if value else "0")
    elif name == "strike":
        _set_font_strike(run_properties, value)
    elif name == "kern":
        kern = _integer_value(value, "kerning", minimum=0)
        if kern > _MAX_KERNING:
            raise ValueError(f"kerning must be at most {_MAX_KERNING}")
        run_properties.set("kern", str(kern))
    elif name == "cap":
        if value not in {"none", "small", "all"}:
            raise ValueError("capitalisation must be 'none', 'small' or 'all'")
        run_properties.set("cap", value)
    elif name == "smtId":
        smart_tag = _integer_value(value, "smart tag id", minimum=0)
        if smart_tag > _MAX_UNSIGNED_INT:
            raise ValueError("smart tag id must fit an unsigned 32-bit integer")
        run_properties.set("smtId", str(smart_tag))
    else:  # bmk, altLang
        if not isinstance(value, str) or (name == "altLang" and not value):
            raise TypeError(f"{name} must be a non-empty string or None")
        run_properties.set(name, value)


def _set_font_metadata(run_properties: ET.Element, name: str, value: Any) -> None:
    slot, attr = name.split(".")
    if value is not None:
        if attr == "panose":
            if not isinstance(value, str):
                raise TypeError("panose must be a 20-digit hexadecimal string or None")
            if len(value) != 20 or any(char not in "0123456789abcdefABCDEF" for char in value):
                raise ValueError("panose must be a 20-digit hexadecimal string")
        elif attr == "pitchFamily":
            value = _integer_value(value, "pitch_family")
            if value not in _PITCH_FAMILIES:
                raise ValueError("pitch_family must be an ST_PitchFamily value")
        else:
            value = _integer_value(value, "charset")
            if not -128 <= value <= 127:
                raise ValueError("charset must fit a signed 8-bit integer")
    child = find_ooxml(run_properties, f"{{{A_NS}}}{slot}")
    if value is None:
        if child is not None:
            child.attrib.pop(attr, None)
        return
    if child is None:
        child = ET.Element(f"{{{ooxml_namespace(run_properties, A_NS)}}}{slot}", {"typeface": ""})
        _insert_run_property_child(run_properties, child)
    child.set(attr, str(value))


def _set_portion_format(run_properties: ET.Element, fields: dict[str, Any]) -> None:
    """Write portion (run) format fields onto ``a:rPr``; ``None`` removes one.

    Keys are the DrawingML names: attributes ``strike`` (``ST_TextStrikeType``),
    ``kern`` (hundredths of a point), ``cap``, ``kumimoji``, ``normalizeH``,
    ``noProof``, ``dirty``, ``err``, ``smtClean``, ``smtId``, ``bmk`` and
    ``altLang``; typeface children ``ea``, ``cs`` and ``sym``; font metadata
    ``latin/ea/cs/sym.panose/pitchFamily/charset``; ``rtl`` as bool or None;
    ``ln`` (text outline) and ``uLn`` (underline line) as ``{"width", "color"}``
    dicts or, for ``uLn``, ``"text"``; and ``uFill`` as RGB or ``"text"``.
    """
    unknown = set(fields) - _PORTION_FIELDS
    if unknown:
        raise ValueError(f"unknown portion format fields: {sorted(unknown)}")
    for name, value in fields.items():
        if name in _FONT_METADATA_FIELDS:
            _set_font_metadata(run_properties, name, value)
        elif name == "rtl":
            if value is not None and not isinstance(value, bool):
                raise TypeError("rtl must be bool or None")
            _remove_run_property_children(run_properties, "rtl")
            if value is not None:
                _insert_run_property_child(
                    run_properties,
                    ET.Element(f"{{{A_NS}}}rtl", {"val": "1" if value else "0"}),
                )
        elif name in _PORTION_TYPEFACE_TAGS:
            if value is None:
                _remove_run_property_children(run_properties, name)
            else:
                if not isinstance(value, str) or not value:
                    raise TypeError(f"{name} typeface must be a non-empty string")
                child = run_properties.find(f"{{{A_NS}}}{name}")
                if child is None:
                    child = ET.Element(f"{{{A_NS}}}{name}")
                    _insert_run_property_child(run_properties, child)
                child.set("typeface", value)
        elif name == "ln":
            _remove_run_property_children(run_properties, "ln")
            if value is not None:
                _insert_run_property_child(
                    run_properties, _line_element("ln", value, "text outline")
                )
        elif name == "uLn":
            _remove_run_property_children(run_properties, "uLn", "uLnTx")
            if value == "text":
                _insert_run_property_child(run_properties, ET.Element(f"{{{A_NS}}}uLnTx"))
            elif value is not None:
                _insert_run_property_child(
                    run_properties, _line_element("uLn", value, "underline line")
                )
        elif name == "uFill":
            _remove_run_property_children(run_properties, "uFill", "uFillTx")
            if value == "text":
                _insert_run_property_child(run_properties, ET.Element(f"{{{A_NS}}}uFillTx"))
            elif value is not None:
                fill = ET.Element(f"{{{A_NS}}}uFill")
                fill.append(_solid_fill(_rgb_token(value, "underline fill")))
                _insert_run_property_child(run_properties, fill)
        else:
            _set_portion_attribute(run_properties, name, value)


def _read_line(line: ET.Element) -> dict[str, Any]:
    width = line.get("w")
    color = line.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    return {
        "width": None if width is None else int(width),
        "color": None if color is None else color.get("val"),
    }


def _read_portion_field(run_properties: ET.Element | None, name: str) -> Any:
    """Stored value of one ``_set_portion_format`` field (None if absent)."""
    if name not in _PORTION_FIELDS:
        raise ValueError(f"unknown portion format field: {name!r}")
    if run_properties is None:
        return None
    if name in _FONT_METADATA_FIELDS:
        slot, attr = name.split(".")
        child = find_ooxml(run_properties, f"{{{A_NS}}}{slot}")
        raw = None if child is None else child.get(attr)
        return raw if raw is None or attr == "panose" else int(raw)
    if name == "rtl":
        child = find_ooxml(run_properties, f"{{{A_NS}}}rtl")
        return None if child is None else child.get("val") in {"1", "true"}
    if name in _PORTION_TYPEFACE_TAGS:
        child = run_properties.find(f"{{{A_NS}}}{name}")
        return None if child is None else child.get("typeface")
    if name == "ln":
        line = run_properties.find(f"{{{A_NS}}}ln")
        return None if line is None else _read_line(line)
    if name == "uLn":
        if run_properties.find(f"{{{A_NS}}}uLnTx") is not None:
            return "text"
        line = run_properties.find(f"{{{A_NS}}}uLn")
        return None if line is None else _read_line(line)
    if name == "uFill":
        if run_properties.find(f"{{{A_NS}}}uFillTx") is not None:
            return "text"
        color = run_properties.find(f"{{{A_NS}}}uFill/{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
        return None if color is None else color.get("val")
    raw = run_properties.get(name)
    if raw is None:
        return None
    if name in _PORTION_BOOL_ATTRS:
        return raw in {"1", "true"}
    if name in {"kern", "smtId"}:
        return int(raw)
    return raw


def _add_paragraph_tab_stop(
    paragraph_properties: ET.Element,
    pos: int,
    align: str = "l",
) -> None:
    position = _integer_value(pos, "tab stop position", minimum=0)
    align = _TAB_ALIGNMENT_ALIASES.get(align, align)
    if align not in _TAB_ALIGNMENTS:
        raise ValueError(
            "tab stop alignment must be 'l'/'left', 'ctr'/'center', 'r'/'right' or 'dec'/'decimal'"
        )
    tab_lst = paragraph_properties.find(f"{{{A_NS}}}tabLst")
    if tab_lst is None:
        tab_lst = ET.Element(f"{{{A_NS}}}tabLst")
        from .shape_xml import _ppr_child_insert_index

        paragraph_properties.insert(
            _ppr_child_insert_index(paragraph_properties, "tabLst"), tab_lst
        )
    for tab in list(tab_lst):
        if tab.get("pos") == str(position):
            tab_lst.remove(tab)
    tab = ET.SubElement(tab_lst, f"{{{A_NS}}}tab")
    tab.set("pos", str(position))
    tab.set("algn", align)
    tab_lst[:] = sorted(tab_lst, key=lambda child: int(child.get("pos", "0")))


__all__ = [
    "_UNDERLINE_TOKENS",
    "_add_paragraph_tab_stop",
    "_apply_text_body_auto_size",
    "_clear_paragraph_bullet",
    "_clear_text_frame_auto_size_children",
    "_end_paragraph_run_properties_element",
    "_read_paragraph_bullet",
    "_read_portion_field",
    "_set_fit_font_properties",
    "_set_font_baseline",
    "_set_font_bool_attribute",
    "_set_font_caps",
    "_set_font_highlight",
    "_set_font_name",
    "_set_font_size",
    "_set_font_spacing",
    "_set_font_strike",
    "_set_font_underline",
    "_set_paragraph_auto_number",
    "_set_paragraph_bullet",
    "_set_paragraph_bullet_char",
    "_set_paragraph_bullet_color",
    "_set_paragraph_bullet_font",
    "_set_paragraph_no_bullet",
    "_set_portion_format",
    "_set_text_body_columns",
    "_set_text_body_overflow",
    "_set_text_body_vertical",
    "_text_body_overflow",
    "_text_character_properties_element",
    "_text_frame_auto_size_insert_index",
]

from .shape_xml import (
    _clear_paragraph_bullet,
    _read_paragraph_bullet,
    _set_paragraph_auto_number,
    _set_paragraph_bullet,
    _set_paragraph_bullet_char,
    _set_paragraph_bullet_color,
    _set_paragraph_bullet_font,
    _set_paragraph_no_bullet,
)
