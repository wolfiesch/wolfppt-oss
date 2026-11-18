"""Package edits for creating and editing a PresentationML handout-master part."""

from __future__ import annotations

import posixpath
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)

if TYPE_CHECKING:
    from .presentation_slides import HandoutMaster

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

HANDOUT_MASTER_CT = "application/vnd.openxmlformats-officedocument.presentationml.handoutMaster+xml"
REL_HANDOUT_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/handoutMaster"
)
REL_OFFICE_DOCUMENT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
HEADER_FOOTER_FLAGS = ("hdr", "ftr", "dt", "sldNum")


class HandoutMasterRefusal(ValueError):
    """Handout-master lifecycle input cannot be preserved safely."""


def remove_handout_master(master: HandoutMaster) -> None:
    """Remove the saved handout master, retaining its shared dependencies.

    Reacquire package handles afterwards. Reading ``presentation.handout_master``
    after removal stages a fresh default master, as for a deck without one.
    Shared inbound references, ambiguous registrations and pending edits are
    refused before any write.
    """
    from .presentation_slides import HandoutMaster

    if not isinstance(master, HandoutMaster):
        raise HandoutMasterRefusal("target must be a HandoutMaster")
    if getattr(master, "_deleted", False):
        raise HandoutMasterRefusal("handout master was deleted")
    presentation = master._presentation
    with presentation._mutation_lock:
        _require_handout_saved(presentation)
        presentation._rewrite_package(
            "removing a handout master",
            lambda package: _handout_removal_plan(package, master.partname.lstrip("/")),
        )
        master._deleted = True


def clone_handout_master(presentation: Any, source: HandoutMaster) -> HandoutMaster:
    """Clone a saved master and its relationship closure into a presentation.

    PresentationML permits one registered handout master. Replace the current
    master atomically, or install the clone when none exists. A foreign source
    imports its own theme/media/custom-data context. Source bytes and unrelated
    destination parts are preserved; old destination dependencies are retained.
    Save pending edits in both decks before calling, then save the result.
    """
    from .package_closure import AssemblyRefusal, copy_rooted_relationship_closure
    from .package_parts import open_package_source
    from .presentation import Presentation
    from .presentation_slides import HandoutMaster

    if not isinstance(presentation, Presentation) or not isinstance(source, HandoutMaster):
        raise HandoutMasterRefusal("clone needs a Presentation and a HandoutMaster")
    if getattr(source, "_deleted", False):
        raise HandoutMasterRefusal("source handout master was deleted")
    # Snapshot the source without holding two presentations' mutation locks.
    with source._presentation._mutation_lock:
        _require_handout_saved(source._presentation)
        with open_package_source(source._presentation._source_path) as package:
            _main, _root, _rels, source_part = _handout_registration(package)
            if source_part != source.partname.lstrip("/"):
                raise HandoutMasterRefusal("source master is not registered in its presentation")
            source_parts = {name: package.read(name) for name in package.namelist()}

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        replacements, removals, _ = _handout_removal_plan(package)
        parts = {name: package.read(name) for name in package.namelist() if name not in removals}
        parts.update(replacements)
        part = "ppt/handoutMasters/handoutMaster1.xml"
        number = 1
        while part in parts or _rels_part_for_package_part(part) in parts:
            number += 1
            part = f"ppt/handoutMasters/handoutMaster{number}.xml"
        try:
            copy_rooted_relationship_closure(parts, source_parts, {source_part: part})
        except (AssemblyRefusal, ET.ParseError, KeyError, ValueError) as exc:
            raise HandoutMasterRefusal(str(exc)) from exc
        parts.update(handout_master_replacements(parts, part))
        changed = {
            name: payload
            for name, payload in parts.items()
            if name not in package.namelist() or package.read(name) != payload
        }
        # A copied part may reuse a removed root name. Do not remove its replacement.
        return changed, removals - parts.keys(), None

    with presentation._mutation_lock:
        _require_handout_saved(presentation)
        presentation._rewrite_package("cloning a handout master", plan)
        return presentation.handout_master


def _require_handout_saved(presentation: Any) -> None:
    try:
        presentation._require_saved_package("editing handout-master lifecycle")
    except (ValueError, RuntimeError) as exc:
        raise HandoutMasterRefusal(str(exc)) from exc


def _handout_registration(package: Any) -> tuple[str, ET.Element, ET.Element, str | None]:
    from .presentation_tags import LifecycleRefusal, one, parse_xml, relationship_target

    try:
        main = relationship_target(
            package, "", parse_xml(package.read("_rels/.rels")), rel_type=REL_OFFICE_DOCUMENT
        )
        if main is None:
            raise HandoutMasterRefusal("package has no presentation registration")
        root = parse_xml(package.read(main))
        if root.tag != f"{{{P_NS}}}presentation":
            raise HandoutMasterRefusal("handout lifecycle requires Transitional PresentationML")
        rels = parse_xml(package.read(_rels_part_for_package_part(main)))
        part = relationship_target(package, main, rels, rel_type=REL_HANDOUT_MASTER)
        ids = one(root, f"{{{P_NS}}}handoutMasterIdLst")
        entries = [] if ids is None else list(ids)
        registrations = [rel for rel in rels if rel.get("Type") == REL_HANDOUT_MASTER]
        if part is None:
            if entries:
                raise HandoutMasterRefusal("handout master id has no relationship")
        elif (
            len(entries) != 1
            or entries[0].tag != f"{{{P_NS}}}handoutMasterId"
            or entries[0].get(f"{{{R_NS}}}id") != registrations[0].get("Id")
            or parse_xml(package.read(part)).tag != f"{{{P_NS}}}handoutMaster"
        ):
            raise HandoutMasterRefusal("missing or ambiguous handout master registration")
        return main, root, rels, part
    except HandoutMasterRefusal:
        raise
    except (LifecycleRefusal, ET.ParseError, KeyError, ValueError) as exc:
        raise HandoutMasterRefusal(str(exc)) from exc


def _handout_removal_plan(
    package: Any, expected: str | None = None
) -> tuple[dict[str, bytes], set[str], None]:
    from .package_parts import resolve_package_target
    from .presentation_tags import LifecycleRefusal, parse_xml, serialize_xml

    main, root, rels, part = _handout_registration(package)
    if expected is not None and expected != part:
        raise HandoutMasterRefusal("handout master is no longer registered")
    if part is None:
        return {}, set(), None
    rels_part = _rels_part_for_package_part(main)
    try:
        for name in package.namelist():
            if not name.endswith(".rels"):
                continue
            if name == "_rels/.rels":
                owner = ""
            elif "/_rels/" in name:
                directory, filename = name.rsplit("/_rels/", 1)
                owner = f"{directory}/{filename.removesuffix('.rels')}"
            else:
                raise HandoutMasterRefusal("unsupported relationship part name")
            if owner == part:
                continue
            for rel in parse_xml(package.read(name)):
                if rel.get("TargetMode", "Internal") == "External":
                    continue
                if resolve_package_target(owner, rel.get("Target", "")) != part:
                    continue
                if name != rels_part or rel.get("Type") != REL_HANDOUT_MASTER:
                    raise HandoutMasterRefusal("handout master has shared inbound references")
        ids = root.find(f"{{{P_NS}}}handoutMasterIdLst")
        if ids is not None:
            root.remove(ids)
        for rel in list(rels):
            if rel.get("Type") == REL_HANDOUT_MASTER:
                rels.remove(rel)
        types = parse_xml(package.read("[Content_Types].xml"))
        for entry in list(types):
            if entry.get("PartName", "").lstrip("/") == part:
                types.remove(entry)
        return (
            {
                main: serialize_xml(root),
                rels_part: serialize_xml(rels),
                "[Content_Types].xml": serialize_xml(types),
            },
            {part, _rels_part_for_package_part(part)},
            None,
        )
    except HandoutMasterRefusal:
        raise
    except (LifecycleRefusal, ET.ParseError, KeyError, ValueError) as exc:
        raise HandoutMasterRefusal(str(exc)) from exc


def apply_handout_master_add(
    input_path: Path,
    output_path: Path,
    handout_master_part: str,
) -> None:
    """Add one handout master without altering unrelated package parts."""
    with zipfile.ZipFile(input_path) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    replacements = handout_master_replacements(parts, handout_master_part)
    _copy_package_with_replacements(input_path, output_path, replacements)


def handout_master_replacements(
    parts: dict[str, bytes], handout_master_part: str
) -> dict[str, bytes]:
    """Parts to write so ``handout_master_part`` exists and is wired in.

    Idempotent: an existing part is only (re)registered, never regenerated.
    A new part gets PowerPoint's header, date, footer and page-number
    placeholders sized to the notes page. Like before, it relates no theme
    part (the relationship is optional for handout masters).
    """
    handout_master_part = handout_master_part.lstrip("/")
    if not handout_master_part.startswith("ppt/handoutMasters/"):
        raise ValueError("handout master part must be in ppt/handoutMasters")
    presentation_part = _presentation_part(parts)
    content_types = ET.fromstring(parts["[Content_Types].xml"])
    _ensure_content_type(content_types, f"/{handout_master_part}", HANDOUT_MASTER_CT)
    presentation_rels_part = _rels_part_for_package_part(presentation_part)
    presentation_rels = ET.fromstring(parts[presentation_rels_part])
    relationship_id = _ensure_relationship(
        presentation_rels,
        REL_HANDOUT_MASTER,
        _relative_target(presentation_part, handout_master_part),
    )
    presentation = ET.fromstring(parts[presentation_part])
    _ensure_handout_master_id(presentation, relationship_id)
    replacements: dict[str, bytes] = {}
    if handout_master_part not in parts:
        replacements[handout_master_part] = _handout_master_xml(
            _notes_size(presentation), handout_master_part
        )
    replacements["[Content_Types].xml"] = _xml_bytes(content_types)
    replacements[presentation_rels_part] = _xml_bytes(presentation_rels)
    replacements[presentation_part] = _xml_bytes(presentation)
    return replacements


class HandoutHeaderFooterManager:
    """Header, footer, date and page-number placeholders of the handout master.

    Visibility is the handout master's ``p:hf`` flags; texts go to the
    matching placeholders. Showing page numbers also guarantees the page
    number placeholder carries PowerPoint's page-number field. Everything is
    written on the next save, creating the handout master when needed.
    """

    def __init__(self, handout_master: HandoutMaster) -> None:
        self._master = handout_master

    @property
    def header_visible(self) -> bool:
        return self._flags()["hdr"]

    @property
    def footer_visible(self) -> bool:
        return self._flags()["ftr"]

    @property
    def date_time_visible(self) -> bool:
        return self._flags()["dt"]

    @property
    def page_number_visible(self) -> bool:
        return self._flags()["sldNum"]

    def set_header_visibility(self, visible: bool) -> None:
        self._set_flag("hdr", visible)

    def set_footer_visibility(self, visible: bool) -> None:
        self._set_flag("ftr", visible)

    def set_date_time_visibility(self, visible: bool) -> None:
        self._set_flag("dt", visible)

    def set_page_number_visibility(self, visible: bool) -> None:
        self._set_flag("sldNum", visible)
        if visible:
            self._request()["page_number_field"] = True

    def set_header_text(self, text: str) -> None:
        self._placeholder("hdr").text = text

    def set_footer_text(self, text: str) -> None:
        self._placeholder("ftr").text = text

    def set_date_time_text(self, text: str) -> None:
        self._placeholder("dt").text = text

    def set_header_and_footer_text(
        self,
        *,
        header: str | None = None,
        footer: str | None = None,
        date_time: str | None = None,
    ) -> None:
        """Set any of the texts and show the placeholders that received one."""
        for flag, text in (("hdr", header), ("ftr", footer), ("dt", date_time)):
            if text is not None:
                self._placeholder(flag).text = text
                self._set_flag(flag, True)

    @property
    def header_text(self) -> str:
        return str(self._placeholder("hdr").text)

    @property
    def footer_text(self) -> str:
        return str(self._placeholder("ftr").text)

    @property
    def date_time_text(self) -> str:
        return str(self._placeholder("dt").text)

    def _placeholder(self, kind: str) -> Any:
        for placeholder in self._master.placeholders:
            if placeholder._payload.get("placeholder_type") == kind:
                return placeholder
        raise ValueError(f"the handout master has no {kind} placeholder")

    def _pending(self) -> dict[str, Any] | None:
        presentation = self._master._presentation
        part = self._master.partname.lstrip("/")
        return next(
            (
                request
                for request in getattr(presentation, "_slide_master_authoring_requests", [])
                if request.get("kind") == "handout_header_footer" and request.get("part") == part
            ),
            None,
        )

    def _request(self) -> dict[str, Any]:
        request = self._pending()
        if request is None:
            request = {
                "kind": "handout_header_footer",
                "part": self._master.partname.lstrip("/"),
                "flags": self._saved_flags(),
                "page_number_field": False,
            }
            self._master._presentation._slide_master_authoring_requests.append(request)
        return request

    def _flags(self) -> dict[str, bool]:
        request = self._pending()
        return dict(request["flags"]) if request is not None else self._saved_flags()

    def _saved_flags(self) -> dict[str, bool]:
        presentation = self._master._presentation
        part = self._master.partname.lstrip("/")
        try:
            with zipfile.ZipFile(presentation.path) as package:
                root = ET.fromstring(package.read(part))
        except KeyError:
            # A handout master staged in this session starts with every
            # placeholder shown.
            return dict.fromkeys(HEADER_FOOTER_FLAGS, True)
        header_footer = root.find(f"{{{P_NS}}}hf")
        return {
            flag: header_footer is not None and header_footer.get(flag, "1") in {"1", "true"}
            for flag in HEADER_FOOTER_FLAGS
        }

    def _set_flag(self, flag: str, visible: bool) -> None:
        if not isinstance(visible, bool):
            raise TypeError("visibility must be a bool")
        self._request()["flags"][flag] = visible


def handout_header_footer_manager(
    handout_master: HandoutMaster,
) -> HandoutHeaderFooterManager:
    """The header/footer manager of ``presentation.handout_master``."""
    return HandoutHeaderFooterManager(handout_master)


def set_handout_placeholder_text_style(
    handout_master: HandoutMaster,
    kind: str,
    *,
    font_size: float | None = None,
    font_name: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    color: str | None = None,
) -> None:
    """Edit a handout placeholder's own text style in a saved package.

    Handout masters have no global text-style element. This writes legal
    ``a:lstStyle/a:lvl1pPr/a:defRPr`` defaults and matching existing paragraph
    and run overrides, without using slide-indexed text queues. ``kind`` is
    header/footer/date_time/slide_number, or its OOXML placeholder name.
    Save pending edits first; save the presentation afterwards to publish it.
    """
    import math
    import re

    from .header_footer_facade import (
        HeaderFooterRefusal,
        _Document,
        _safe_placeholder,
        _shape_span,
        _text_body,
    )
    from .presentation_save_state import _element_spans
    from .presentation_tags import xml_string
    from .slide_master_facade import (
        _FILLS,
        _RPR_ORDER,
        _insert_ordered,
        _set_fill,
        xml_fragment,
    )

    manager, placeholder_kind = _handout_style_target(handout_master, kind)
    if all(value is None for value in (font_size, font_name, bold, italic, color)):
        raise HeaderFooterRefusal("handout text style needs at least one setting")
    if font_size is not None and (
        isinstance(font_size, bool)
        or not isinstance(font_size, (int, float))
        or not math.isfinite(font_size)
        or not 1 <= font_size <= 4000
    ):
        raise HeaderFooterRefusal("font_size must be finite points in the supported range")
    if font_name is not None:
        try:
            xml_string(font_name, "font_name")
        except (TypeError, ValueError) as exc:
            raise HeaderFooterRefusal(str(exc)) from exc
        if not font_name.strip():
            raise HeaderFooterRefusal("font_name must not be empty")
    for label, value in (("bold", bold), ("italic", italic)):
        if value is not None and not isinstance(value, bool):
            raise HeaderFooterRefusal(f"{label} must be a bool or None")
    if color is not None:
        if not isinstance(color, str) or re.fullmatch(r"#?[0-9a-fA-F]{6}", color) is None:
            raise HeaderFooterRefusal("color must be an RGB hex string")
        color = color.lstrip("#").upper()

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        document = _Document(package)
        document.root(manager._part, "handoutMaster")
        match = document.template(manager._part, placeholder_kind)
        if match is None:
            raise HeaderFooterRefusal("handout text style placeholder is missing")
        shape = match[0]
        _safe_placeholder(shape)
        payload = document.payloads[manager._part]
        span = _shape_span(_element_spans(payload), shape)
        body = _text_body(shape)
        style = body.find(f"{{{A_NS}}}lstStyle")
        if style is None:
            style = ET.Element(f"{{{A_NS}}}lstStyle")
            body.insert(1, style)
        level = style.find(f"{{{A_NS}}}lvl1pPr")
        if level is None:
            level = ET.Element(f"{{{A_NS}}}lvl1pPr")
            style.insert(1 if style.find(f"{{{A_NS}}}defPPr") is not None else 0, level)
        defaults = level.find(f"{{{A_NS}}}defRPr")
        if defaults is None:
            defaults = ET.SubElement(level, f"{{{A_NS}}}defRPr")
        properties = [
            element
            for element in body.iter()
            if element.tag
            in {
                f"{{{A_NS}}}defRPr",
                f"{{{A_NS}}}rPr",
                f"{{{A_NS}}}endParaRPr",
            }
        ]
        for paragraph in body.findall(f"{{{A_NS}}}p"):
            for run in paragraph:
                if run.tag not in {f"{{{A_NS}}}r", f"{{{A_NS}}}fld"}:
                    continue
                if run.find(f"{{{A_NS}}}rPr") is None:
                    run_properties = ET.Element(f"{{{A_NS}}}rPr")
                    run.insert(0, run_properties)
                    properties.append(run_properties)
        for properties_element in properties:
            if font_size is not None:
                properties_element.set("sz", str(round(font_size * 100)))
            for attribute, value in (("b", bold), ("i", italic)):
                if value is not None:
                    properties_element.set(attribute, "1" if value else "0")
            if font_name is not None:
                _insert_ordered(properties_element, "latin", _RPR_ORDER).set("typeface", font_name)
            if color is not None:
                _set_fill(properties_element, "srgbClr", color, _RPR_ORDER, _FILLS)
        replacement = xml_fragment(shape, payload)
        rewritten = payload[: span["start"]] + replacement + payload[span["end"] :]
        return {manager._part: rewritten}, set(), None

    presentation = handout_master._presentation
    with presentation._mutation_lock:
        manager._require_saved()
        presentation._rewrite_package("changing handout placeholder text style", plan)


def read_handout_placeholder_text_style(handout_master: HandoutMaster, kind: str) -> dict[str, Any]:
    """Read saved direct text formatting of a handout placeholder.

    Returns font_size (points), font_name, bold, italic and explicit RGB color.
    An absent direct property is ``None``; theme-resolved fonts/colors are not
    invented. Existing first-run overrides take precedence over list defaults.
    """
    from .header_footer_facade import HeaderFooterRefusal, _Document
    from .package_parts import open_package_source

    manager, placeholder_kind = _handout_style_target(handout_master, kind)
    with handout_master._presentation._mutation_lock:
        manager._require_saved()
        with open_package_source(handout_master._presentation._source_path) as package:
            document = _Document(package)
            match = document.template(manager._part, placeholder_kind)
            if match is None:
                raise HeaderFooterRefusal("handout text style placeholder is missing")
            body = match[0].find(f"{{{P_NS}}}txBody")
            result: dict[str, Any] = dict.fromkeys(
                ("font_size", "font_name", "bold", "italic", "color")
            )
            if body is None:
                return result
            properties = [
                body.find(f"{{{A_NS}}}lstStyle/{{{A_NS}}}defPPr/{{{A_NS}}}defRPr"),
                body.find(f"{{{A_NS}}}lstStyle/{{{A_NS}}}lvl1pPr/{{{A_NS}}}defRPr"),
            ]
            paragraph = body.find(f"{{{A_NS}}}p")
            if paragraph is not None:
                properties.append(paragraph.find(f"{{{A_NS}}}pPr/{{{A_NS}}}defRPr"))
                run = next(
                    (
                        child
                        for child in paragraph
                        if child.tag in {f"{{{A_NS}}}r", f"{{{A_NS}}}fld"}
                    ),
                    None,
                )
                properties.append(
                    paragraph.find(f"{{{A_NS}}}endParaRPr")
                    if run is None
                    else run.find(f"{{{A_NS}}}rPr")
                )
            for element in properties:
                if element is None:
                    continue
                try:
                    if element.get("sz") is not None:
                        result["font_size"] = int(element.get("sz", "0")) / 100
                except ValueError as exc:
                    raise HeaderFooterRefusal("invalid handout text font size") from exc
                for key, attribute in (("bold", "b"), ("italic", "i")):
                    raw = element.get(attribute)
                    if raw is not None:
                        if raw not in {"0", "1", "false", "true"}:
                            raise HeaderFooterRefusal("invalid handout text style boolean")
                        result[key] = raw in {"1", "true"}
                latin = element.find(f"{{{A_NS}}}latin")
                if latin is not None:
                    result["font_name"] = latin.get("typeface")
                fill = element.find(f"{{{A_NS}}}solidFill")
                if fill is not None:
                    rgb = fill.find(f"{{{A_NS}}}srgbClr")
                    result["color"] = None if rgb is None else rgb.get("val")
            return result


def _handout_style_target(handout_master: HandoutMaster, kind: str) -> tuple[Any, str]:
    from .header_footer_facade import HeaderFooterRefusal, header_footer_manager
    from .presentation_slides import HandoutMaster as HandoutMasterType

    if not isinstance(handout_master, HandoutMasterType):
        raise HeaderFooterRefusal("handout text styles require a HandoutMaster")
    aliases = {
        "header": "hdr",
        "footer": "ftr",
        "date_time": "dt",
        "slide_number": "sldNum",
        "page_number": "sldNum",
        **dict.fromkeys(HEADER_FOOTER_FLAGS),
    }
    if not isinstance(kind, str) or kind not in aliases:
        raise HeaderFooterRefusal("unsupported handout text style placeholder kind")
    return header_footer_manager(handout_master), aliases[kind] or kind


def apply_handout_header_footer_request(parts: dict[str, bytes], request: dict[str, Any]) -> None:
    """Write staged ``p:hf`` flags (and the page-number field) into the parts."""
    from .presentation_save_state import _element_spans
    from .slide_master_facade import splice_root_child, xml_fragment

    part = str(request["part"]).lstrip("/")
    if part not in parts:
        parts.update(handout_master_replacements(parts, part))
    flags = request["flags"]
    header_footer = ET.Element(
        f"{{{P_NS}}}hf",
        {flag: "1" if flags[flag] else "0" for flag in HEADER_FOOTER_FLAGS},
    )
    payload = splice_root_child(
        parts[part], "hf", xml_fragment(header_footer, parts[part]), ("extLst",)
    )
    if request.get("page_number_field"):
        nodes = _element_spans(payload)
        root = ET.fromstring(payload)
        shapes = [
            shape
            for shape in root.iter(f"{{{P_NS}}}sp")
            if (ph := shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}nvPr/{{{P_NS}}}ph")) is not None
            and ph.get("type") == "sldNum"
        ]
        spans = [
            node
            for index, node in enumerate(nodes)
            if node["tag"] == f"{{{P_NS}}}sp" and _span_has_page_number(nodes, index)
        ]
        if shapes and len(shapes) == len(spans):
            shape, span = shapes[0], spans[0]
            if _ensure_page_number_field(shape, part):
                replacement = xml_fragment(shape, payload)
                payload = payload[: span["start"]] + replacement + payload[span["end"] :]
    parts[part] = payload


def _span_has_page_number(nodes: list[dict[str, Any]], shape_index: int) -> bool:
    shape = nodes[shape_index]
    for node in nodes[shape_index + 1 :]:
        if node["start"] >= shape["end"]:
            return False
        if node["tag"] == f"{{{P_NS}}}ph" and node["attrib"].get("type") == "sldNum":
            return True
    return False


def _ensure_page_number_field(shape: ET.Element, part: str) -> bool:
    """Give the page-number placeholder a ``slidenum`` field; True when changed."""
    if any(field.get("type") == "slidenum" for field in shape.iter(f"{{{A_NS}}}fld")):
        return False
    body = shape.find(f"{{{P_NS}}}txBody")
    if body is None:
        body = ET.SubElement(shape, f"{{{P_NS}}}txBody")
        ET.SubElement(body, f"{{{A_NS}}}bodyPr")
        ET.SubElement(body, f"{{{A_NS}}}lstStyle")
    for paragraph in body.findall(f"{{{A_NS}}}p"):
        body.remove(paragraph)
    paragraph = ET.SubElement(body, f"{{{A_NS}}}p")
    paragraph.append(_page_number_field(part))
    ET.SubElement(paragraph, f"{{{A_NS}}}endParaRPr", {"lang": "en-US"})
    return True


def _page_number_field(part: str) -> ET.Element:
    guid = uuid.uuid5(uuid.NAMESPACE_URL, f"wolfppt:{part}#slidenum")
    field = ET.Element(f"{{{A_NS}}}fld", {"id": "{" + str(guid).upper() + "}", "type": "slidenum"})
    ET.SubElement(field, f"{{{A_NS}}}rPr", {"lang": "en-US"})
    ET.SubElement(field, f"{{{A_NS}}}t").text = "\u2039#\u203a"
    return field


def _presentation_part(parts: dict[str, bytes]) -> str:
    root = ET.fromstring(parts["_rels/.rels"])
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type") == REL_OFFICE_DOCUMENT:
            return posixpath.normpath(rel.attrib.get("Target", "").lstrip("/"))
    raise ValueError("package has no presentation part")


def _notes_size(presentation: ET.Element) -> tuple[int, int]:
    size = presentation.find(f"{{{P_NS}}}notesSz")
    if size is None:
        return (6858000, 9144000)
    return (int(size.get("cx", "6858000")), int(size.get("cy", "9144000")))


def _ensure_content_type(root: ET.Element, partname: str, content_type: str) -> None:
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == partname:
            override.set("ContentType", content_type)
            return
    ET.SubElement(
        root,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": partname, "ContentType": content_type},
    )


def _ensure_relationship(root: ET.Element, rel_type: str, target: str) -> str:
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type") == rel_type and rel.attrib.get("Target") == target:
            return str(rel.attrib["Id"])
    relationship_id = _next_relationship_id(root)
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": relationship_id, "Type": rel_type, "Target": target},
    )
    return relationship_id


def _ensure_handout_master_id(root: ET.Element, relationship_id: str) -> None:
    master_list = root.find(f"{{{P_NS}}}handoutMasterIdLst")
    if master_list is None:
        master_list = ET.Element(f"{{{P_NS}}}handoutMasterIdLst")
        root.insert(_handout_master_list_insert_index(root), master_list)
    for master_id in master_list.findall(f"{{{P_NS}}}handoutMasterId"):
        if master_id.attrib.get(f"{{{R_NS}}}id") == relationship_id:
            return
    ET.SubElement(
        master_list,
        f"{{{P_NS}}}handoutMasterId",
        {f"{{{R_NS}}}id": relationship_id},
    )


def _handout_master_list_insert_index(root: ET.Element) -> int:
    following = {"sldIdLst", "sldSz", "notesSz", "defaultTextStyle", "extLst"}
    for index, child in enumerate(root):
        if _local_name(child.tag) in following:
            return index
    return len(root)


def _next_relationship_id(root: ET.Element) -> str:
    highest = 0
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        raw = rel.attrib.get("Id", "")
        if raw.startswith("rId") and raw[3:].isdigit():
            highest = max(highest, int(raw[3:]))
    return f"rId{highest + 1}"


def _relative_target(source_part: str, target_part: str) -> str:
    source_dir = source_part.rsplit("/", 1)[0]
    target = target_part.removeprefix(source_dir + "/")
    return target if source_dir == "ppt" else f"../{target}"


_HANDOUT_PLACEHOLDERS = (
    # (shape id, name, type, idx, right column, bottom row)
    (2, "Header Placeholder 1", "hdr", 0, False, False),
    (3, "Date Placeholder 2", "dt", 1, True, False),
    (4, "Footer Placeholder 3", "ftr", 2, False, True),
    (5, "Slide Number Placeholder 4", "sldNum", 3, True, True),
)


def _handout_master_xml(notes_size: tuple[int, int], part: str) -> bytes:
    """PowerPoint's default handout master laid out on the notes page."""
    width, height = notes_size
    box_w, box_h = round(width * 0.4333), round(height * 0.0502)
    root = ET.Element(f"{{{P_NS}}}handoutMaster")
    tree = ET.SubElement(ET.SubElement(root, f"{{{P_NS}}}cSld"), f"{{{P_NS}}}spTree")
    group = ET.SubElement(tree, f"{{{P_NS}}}nvGrpSpPr")
    ET.SubElement(group, f"{{{P_NS}}}cNvPr", {"id": "1", "name": ""})
    ET.SubElement(group, f"{{{P_NS}}}cNvGrpSpPr")
    ET.SubElement(group, f"{{{P_NS}}}nvPr")
    transform = ET.SubElement(ET.SubElement(tree, f"{{{P_NS}}}grpSpPr"), f"{{{A_NS}}}xfrm")
    for local, attrs in (
        ("off", {"x": "0", "y": "0"}),
        ("ext", {"cx": "0", "cy": "0"}),
        ("chOff", {"x": "0", "y": "0"}),
        ("chExt", {"cx": "0", "cy": "0"}),
    ):
        ET.SubElement(transform, f"{{{A_NS}}}{local}", attrs)
    for shape_id, name, kind, idx, right, bottom in _HANDOUT_PLACEHOLDERS:
        shape = ET.SubElement(tree, f"{{{P_NS}}}sp")
        non_visual = ET.SubElement(shape, f"{{{P_NS}}}nvSpPr")
        ET.SubElement(non_visual, f"{{{P_NS}}}cNvPr", {"id": str(shape_id), "name": name})
        ET.SubElement(
            ET.SubElement(non_visual, f"{{{P_NS}}}cNvSpPr"),
            f"{{{A_NS}}}spLocks",
            {"noGrp": "1"},
        )
        ET.SubElement(
            ET.SubElement(non_visual, f"{{{P_NS}}}nvPr"),
            f"{{{P_NS}}}ph",
            {"type": kind, "sz": "quarter", "idx": str(idx)},
        )
        properties = ET.SubElement(shape, f"{{{P_NS}}}spPr")
        frame = ET.SubElement(properties, f"{{{A_NS}}}xfrm")
        ET.SubElement(
            frame,
            f"{{{A_NS}}}off",
            {
                "x": str(width - box_w if right else 0),
                "y": str(height - box_h if bottom else 0),
            },
        )
        ET.SubElement(frame, f"{{{A_NS}}}ext", {"cx": str(box_w), "cy": str(box_h)})
        ET.SubElement(
            ET.SubElement(properties, f"{{{A_NS}}}prstGeom", {"prst": "rect"}),
            f"{{{A_NS}}}avLst",
        )
        body = ET.SubElement(shape, f"{{{P_NS}}}txBody")
        ET.SubElement(
            body,
            f"{{{A_NS}}}bodyPr",
            {"vert": "horz", "rtlCol": "0", "anchor": "b" if bottom else "t"},
        )
        level = ET.SubElement(
            ET.SubElement(body, f"{{{A_NS}}}lstStyle"),
            f"{{{A_NS}}}lvl1pPr",
            {"algn": "r"} if right else {},
        )
        ET.SubElement(level, f"{{{A_NS}}}defRPr", {"sz": "1200"})
        paragraph = ET.SubElement(body, f"{{{A_NS}}}p")
        if kind == "sldNum":
            paragraph.append(_page_number_field(part))
        ET.SubElement(paragraph, f"{{{A_NS}}}endParaRPr", {"lang": "en-US"})
    ET.SubElement(
        root,
        f"{{{P_NS}}}clrMap",
        {
            "bg1": "lt1",
            "tx1": "dk1",
            "bg2": "lt2",
            "tx2": "dk2",
            "accent1": "accent1",
            "accent2": "accent2",
            "accent3": "accent3",
            "accent4": "accent4",
            "accent5": "accent5",
            "accent6": "accent6",
            "hlink": "hlink",
            "folHlink": "folHlink",
        },
    )
    ET.SubElement(root, f"{{{P_NS}}}hf", dict.fromkeys(HEADER_FOOTER_FLAGS, "1"))
    _xml_namespaces()
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _xml_namespaces() -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)


def _xml_bytes(root: ET.Element) -> bytes:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
    namespace = _namespace_uri(root.tag)
    if namespace == P_NS:
        # Native readers match ``p:`` element names, so PresentationML parts
        # keep their conventional prefix instead of a default namespace.
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    ET.register_namespace("", namespace)
    try:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    finally:
        # Registering a default namespace can unbind a standard prefix
        # process-wide; restore it so later PresentationML writers keep
        # emitting ``p:`` elements that native readers match.
        ET.register_namespace("p", P_NS)


def _namespace_uri(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
