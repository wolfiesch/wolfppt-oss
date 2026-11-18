"""Scoped, atomic header/footer editing of saved PresentationML decks.

Import ``header_footer_manager`` from this module. Save queued presentation edits
before using it, then save the presentation again to publish its rewritten
package. Text setters show their placeholder; visibility setters can remove and
restore slide/notes placeholders. ``propagate=True`` follows package
relationships, never unrelated masters or layouts. Slides and slide layouts never
receive an ``hdr`` placeholder: header text, and positive header visibility that
would materialize one, are refused (also when propagated from a slide master)
before any package write. Header text on a slide master, notes slide, notes
master or handout master, and hiding a header anywhere, remain supported.
Strict OOXML is explicitly unsupported. Dates are caller-supplied fixed text; no
clock or locale is consulted. Slide numbers retain a ``slidenum`` field unless
explicit fixed text is requested.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET

from .package_parts import A_NS, P_NS, open_package_source
from .presentation_fields import (
    _max_shape_id,
    _placeholder_copy,
    _placeholders,
    _set_paragraph_text,
    _shape_tree,
)
from .presentation_save_state import (
    _drop_deleted_shape_timing,
    _element_spans,
    _tag_end,
)
from .presentation_tags import (
    LifecycleRefusal,
    one,
    parse_xml,
    relationship_target,
    relationships,
    xml_string,
)
from .slide_master_facade import splice_root_child, xml_fragment

__all__ = ["HeaderFooterManager", "HeaderFooterRefusal", "header_footer_manager"]

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_KINDS = {"header": "hdr", "footer": "ftr", "date_time": "dt", "slide_number": "sldNum"}
_ROOTS = {
    "Slide": "sld",
    "SlideLayout": "sldLayout",
    "SlideMaster": "sldMaster",
    "NotesSlide": "notes",
    "NotesMaster": "notesMaster",
    "HandoutMaster": "handoutMaster",
}
_MASTERS = {"sldMaster", "sldLayout", "notesMaster", "handoutMaster"}
# Slides and layouts never receive an ``hdr`` placeholder; it is master/page-master only.
_HEADERLESS = {"sld", "sldLayout"}


class HeaderFooterRefusal(ValueError):
    """The requested scoped edit cannot be preserved or represented safely."""


def header_footer_manager(target: Any) -> HeaderFooterManager:
    """Return a manager for a saved Slide/Layout/Master or notes/handout target."""
    return HeaderFooterManager(target)


class HeaderFooterManager:
    """Visibility and fixed text of a single saved package owner.

    ``update`` is atomic even when propagating. Individual setters are immediate
    saved-package operations, not queued shape edits. Existing manager objects
    remain usable after a rewrite because they resolve their part afresh.
    """

    def __init__(self, target: Any) -> None:
        from .presentation_slides import (
            HandoutMaster,
            NotesMaster,
            NotesSlide,
            Slide,
            SlideLayout,
            SlideMaster,
        )

        classes = (Slide, SlideLayout, SlideMaster, NotesSlide, NotesMaster, HandoutMaster)
        target_type = next((cls for cls in classes if isinstance(target, cls)), None)
        if target_type is None:
            raise HeaderFooterRefusal("unsupported header/footer target")
        self._presentation = target._presentation
        self._part = target.partname.lstrip("/")
        self._root_kind = _ROOTS[target_type.__name__]
        if getattr(target, "_deleted", False):
            raise HeaderFooterRefusal("deleted header/footer target")
        with self._presentation._mutation_lock:
            self._require_saved()
            with open_package_source(self._presentation._source_path) as package:
                _Document(package).root(self._part, self._root_kind)

    def _require_saved(self) -> None:
        try:
            self._presentation._require_saved_package("changing scoped headers and footers")
        except (ValueError, RuntimeError) as exc:
            raise HeaderFooterRefusal(str(exc)) from exc

    def _read(self, kind: str, *, text: bool = False) -> bool | str:
        with self._presentation._mutation_lock:
            self._require_saved()
            with open_package_source(self._presentation._source_path) as package:
                document = _Document(package)
                root = document.root(self._part, self._root_kind)
                if text:
                    template = document.template(self._part, kind)
                    if template is None:
                        return ""
                    return _shape_text(template[0])
                present = _placeholders(_shape_tree(root), kind)
                if self._root_kind not in _MASTERS:
                    return bool(present)
                return document.visible(self._part, kind)

    @property
    def header_visible(self) -> bool:
        return bool(self._read("hdr"))

    @property
    def footer_visible(self) -> bool:
        return bool(self._read("ftr"))

    @property
    def date_time_visible(self) -> bool:
        return bool(self._read("dt"))

    @property
    def slide_number_visible(self) -> bool:
        return bool(self._read("sldNum"))

    @property
    def page_number_visible(self) -> bool:
        return self.slide_number_visible

    @property
    def header_text(self) -> str:
        return str(self._read("hdr", text=True))

    @property
    def footer_text(self) -> str:
        return str(self._read("ftr", text=True))

    @property
    def date_time_text(self) -> str:
        return str(self._read("dt", text=True))

    @property
    def slide_number_text(self) -> str:
        return str(self._read("sldNum", text=True))

    @property
    def page_number_text(self) -> str:
        return self.slide_number_text

    def update(
        self,
        *,
        header_visible: bool | None = None,
        footer_visible: bool | None = None,
        date_time_visible: bool | None = None,
        slide_number_visible: bool | None = None,
        header_text: str | None = None,
        footer_text: str | None = None,
        date_time_text: str | None = None,
        slide_number_text: str | None = None,
        propagate: bool = False,
    ) -> None:
        """Apply settings to this owner and optionally associated children.

        Text alone shows that placeholder. Text and explicit hiding of the same
        placeholder is refused. Propagation is valid only for slide masters,
        layouts and notes masters; notes slides are not implicitly created.
        Header text and header visibility that would materialize an ``hdr``
        placeholder on a slide or layout (directly or through propagation from a
        master) are refused; master-only, notes and handout headers and header
        hiding are supported. Missing slide templates, unsafe placeholder
        extensions and unsupported package profiles are refused before any
        package bytes are written.
        """
        if not isinstance(propagate, bool):
            raise HeaderFooterRefusal("propagate must be a bool")
        if propagate and self._root_kind not in {"sldMaster", "sldLayout", "notesMaster"}:
            raise HeaderFooterRefusal("this header/footer target has no propagation children")
        visibility = (header_visible, footer_visible, date_time_visible, slide_number_visible)
        values = (header_text, footer_text, date_time_text, slide_number_text)
        toggles: dict[str, bool] = {}
        texts: dict[str, str] = {}
        for (name, kind), visible, value in zip(_KINDS.items(), visibility, values, strict=True):
            if visible is None and value is None:
                continue
            if visible is not None and not isinstance(visible, bool):
                raise HeaderFooterRefusal(f"{name}_visible must be a bool or None")
            if value is not None:
                try:
                    texts[kind] = xml_string(value, f"{name}_text")
                except (TypeError, ValueError) as exc:
                    raise HeaderFooterRefusal(str(exc)) from exc
                if visible is False:
                    raise HeaderFooterRefusal(f"cannot set {name} text while hiding it")
                toggles[kind] = True
            if visible is not None:
                toggles[kind] = visible
        if not toggles:
            raise HeaderFooterRefusal("header/footer update needs at least one setting")
        with self._presentation._mutation_lock:
            self._require_saved()
            slide_parts = [slide.partname.lstrip("/") for slide in self._presentation.slides]
            layout_parts = [
                layout.partname.lstrip("/") for layout in self._presentation.slide_layouts
            ]

            def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
                try:
                    document = _Document(package)
                    document.root(self._part, self._root_kind)
                    targets = [self._part]
                    if propagate:
                        targets.extend(document.children(self._part, slide_parts, layout_parts))
                    for part in targets:
                        document.edit(part, toggles, texts, slide_parts)
                    return document.replacements, set(), None
                except HeaderFooterRefusal:
                    raise
                except (LifecycleRefusal, ET.ParseError, KeyError, TypeError, ValueError) as exc:
                    raise HeaderFooterRefusal(str(exc)) from exc

            self._presentation._rewrite_package("changing scoped headers and footers", plan)

    def set_header_visibility(self, visible: bool, *, propagate: bool = False) -> None:
        self.update(header_visible=visible, propagate=propagate)

    def set_footer_visibility(self, visible: bool, *, propagate: bool = False) -> None:
        self.update(footer_visible=visible, propagate=propagate)

    def set_date_time_visibility(self, visible: bool, *, propagate: bool = False) -> None:
        self.update(date_time_visible=visible, propagate=propagate)

    def set_slide_number_visibility(self, visible: bool, *, propagate: bool = False) -> None:
        self.update(slide_number_visible=visible, propagate=propagate)

    def set_page_number_visibility(self, visible: bool, *, propagate: bool = False) -> None:
        self.set_slide_number_visibility(visible, propagate=propagate)

    def set_header_text(self, text: str, *, propagate: bool = False) -> None:
        self.update(header_text=text, propagate=propagate)

    def set_footer_text(self, text: str, *, propagate: bool = False) -> None:
        self.update(footer_text=text, propagate=propagate)

    def set_date_time_text(self, text: str, *, propagate: bool = False) -> None:
        self.update(date_time_text=text, propagate=propagate)

    def set_slide_number_text(self, text: str, *, propagate: bool = False) -> None:
        self.update(slide_number_text=text, propagate=propagate)

    def set_page_number_text(self, text: str, *, propagate: bool = False) -> None:
        self.set_slide_number_text(text, propagate=propagate)

    def set_header_and_footer_text(
        self,
        *,
        header: str | None = None,
        footer: str | None = None,
        date_time: str | None = None,
        propagate: bool = False,
    ) -> None:
        self.update(
            header_text=header, footer_text=footer, date_time_text=date_time, propagate=propagate
        )


class _Document:
    def __init__(self, package: Any) -> None:
        self.package = package
        self.roots: dict[str, ET.Element] = {}
        self.payloads: dict[str, bytes] = {}
        self.replacements: dict[str, bytes] = {}
        self.relationship_roots: dict[str, ET.Element] = {}

    def root(self, part: str, expected: str | None = None) -> ET.Element:
        if part not in self.roots:
            if part not in self.package.namelist():
                raise HeaderFooterRefusal("header/footer target is not saved in this package")
            payload = self.package.read(part)
            # Validate namespace rebinding before serializing any changed fragment.
            try:
                checked = parse_xml(payload)
            except (LifecycleRefusal, ET.ParseError) as exc:
                raise HeaderFooterRefusal(str(exc)) from exc
            if not isinstance(checked.tag, str) or not checked.tag.startswith("{" + P_NS + "}"):
                raise HeaderFooterRefusal(
                    "unsupported header/footer OOXML profile; Transitional required"
                )
            root = ET.fromstring(
                payload,
                parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True)),
            )
            if root.tag.rsplit("}", 1)[-1] not in set(_ROOTS.values()) | {"presentation"}:
                raise HeaderFooterRefusal("unsupported header/footer package root")
            if root.tag != f"{{{P_NS}}}presentation":
                try:
                    _shape_tree(root)
                except LifecycleRefusal as exc:
                    raise HeaderFooterRefusal(str(exc)) from exc
            self.roots[part] = root
            self.payloads[part] = payload
        root = self.roots[part]
        if expected is not None and root.tag != f"{{{P_NS}}}{expected}":
            raise HeaderFooterRefusal("header/footer target has an unexpected package root")
        return root

    def related(self, part: str, kind: str) -> str | None:
        self.root(part)
        try:
            target = relationship_target(
                self.package,
                part,
                relationships(self.package, part, self.relationship_roots),
                rel_type=f"{R_NS}/{kind}",
            )
        except LifecycleRefusal as exc:
            raise HeaderFooterRefusal(str(exc)) from exc
        if target is not None:
            expected = {
                "slideLayout": "sldLayout",
                "slideMaster": "sldMaster",
                "notesSlide": "notes",
                "notesMaster": "notesMaster",
                "slide": "sld",
            }[kind]
            self.root(target, expected)
        return target

    def parent(self, part: str) -> str | None:
        kind = self.root(part).tag.rsplit("}", 1)[-1]
        relation = {"sld": "slideLayout", "sldLayout": "slideMaster", "notes": "notesMaster"}.get(
            kind
        )
        return None if relation is None else self.related(part, relation)

    def template(self, part: str, kind: str) -> tuple[ET.Element, str] | None:
        matches = _placeholders(_shape_tree(self.root(part)), kind)
        if len(matches) > 1:
            raise HeaderFooterRefusal("ambiguous header/footer placeholder")
        if matches:
            if matches[0][0] is not _shape_tree(self.root(part)):
                raise HeaderFooterRefusal("grouped header/footer placeholders are unsupported")
            return matches[0][1], part
        parent = self.parent(part)
        return None if parent is None else self.template(parent, kind)

    def visible(self, part: str, kind: str) -> bool:
        root = self.root(part)
        flags = one(root, f"{{{P_NS}}}hf")
        if flags is not None:
            raw = flags.get(kind, "true")
            if raw not in {"0", "1", "false", "true"}:
                raise HeaderFooterRefusal("invalid header/footer visibility flag")
            if raw in {"0", "false"}:
                return False
        parent = self.parent(part)
        if flags is None and parent is not None and not self.visible(parent, kind):
            return False
        return self.template(part, kind) is not None

    def children(self, part: str, slides: list[str], layouts: list[str]) -> list[str]:
        kind = self.root(part).tag.rsplit("}", 1)[-1]
        if kind == "notesMaster":
            notes = [self.related(slide, "notesSlide") for slide in slides]
            return list(
                dict.fromkeys(
                    note for note in notes if note is not None and self.parent(note) == part
                )
            )
        selected_layouts = (
            [layout for layout in layouts if self.parent(layout) == part]
            if kind == "sldMaster"
            else [part]
        )
        selected_slides = [slide for slide in slides if self.parent(slide) in selected_layouts]
        return (selected_layouts if kind == "sldMaster" else []) + selected_slides

    def page_size(self, *, notes: bool = True) -> tuple[int, int]:
        presentation = relationship_target(
            self.package,
            "",
            relationships(self.package, "", self.relationship_roots),
            rel_type=f"{R_NS}/officeDocument",
        )
        if presentation is None:
            raise HeaderFooterRefusal("package has no presentation relationship")
        root = self.root(presentation, "presentation")
        local = "notesSz" if notes else "sldSz"
        size = one(root, f"{{{P_NS}}}{local}")
        if size is None:
            raise HeaderFooterRefusal(f"presentation has no {local} page size")
        width, height = int(size.get("cx", "0")), int(size.get("cy", "0"))
        if width <= 0 or height <= 0:
            raise HeaderFooterRefusal(f"invalid {local} page size")
        return width, height

    def number(self, part: str, slides: list[str]) -> int:
        owner = part if part in slides else self.related(part, "slide")
        if owner not in slides:
            raise HeaderFooterRefusal("slide-number placeholder has no associated slide")
        presentation = relationship_target(
            self.package,
            "",
            relationships(self.package, "", self.relationship_roots),
            rel_type=f"{R_NS}/officeDocument",
        )
        if presentation is None:
            raise HeaderFooterRefusal("package has no presentation relationship")
        first = int(self.root(presentation, "presentation").get("firstSlideNum", "1"))
        if first < 1:
            raise HeaderFooterRefusal("unsupported first slide number")
        return first + slides.index(owner)

    def new_placeholder(self, part: str, kind: str, shape_id: int) -> ET.Element:
        root = self.root(part)
        indexes = [int(ph.get("idx", "0")) for ph in root.iter(f"{{{P_NS}}}ph")]
        idx = max(indexes, default=0) + 1
        root_kind = root.tag.rsplit("}", 1)[-1]
        if root_kind in {"notes", "notesMaster", "handoutMaster"}:
            from .notes_slide_edits import notes_header_footer_placeholder

            return notes_header_footer_placeholder(kind, shape_id, idx, self.page_size(), part)
        if kind == "hdr":
            from .notes_slide_edits import notes_header_footer_placeholder

            return notes_header_footer_placeholder(
                kind, shape_id, idx, self.page_size(notes=False), part
            )
        from .slide_master_facade import _typed_layout_specs, placeholder_element

        spec = next(
            spec
            for spec in _typed_layout_specs("blank", self.page_size(notes=False))
            if spec["type"] == kind
        )
        spec["id"] = shape_id
        spec["idx"] = idx
        return placeholder_element(spec, part)

    def edit(
        self, part: str, toggles: dict[str, bool], texts: dict[str, str], slides: list[str]
    ) -> None:
        root = self.root(part)
        root_kind = root.tag.rsplit("}", 1)[-1]
        master = root_kind in _MASTERS
        tree = _shape_tree(root)
        payload = self.payloads[part]
        nodes = _element_spans(payload)
        changes: list[tuple[int, int, bytes]] = []
        added: list[ET.Element] = []
        removed: set[str] = set()
        next_id = _max_shape_id(root)
        for kind, visible in toggles.items():
            matches = _placeholders(tree, kind)
            if len(matches) > 1 or any(parent is not tree for parent, _shape in matches):
                raise HeaderFooterRefusal("ambiguous or grouped header/footer placeholder")
            if not visible:
                if not master:
                    for parent, shape in matches:
                        span = _shape_span(nodes, shape)
                        identity = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
                        if identity is not None:
                            removed.add(identity.get("id", ""))
                        changes.append((span["start"], span["end"], b""))
                        parent.remove(shape)
                continue
            if kind == "hdr" and root_kind in _HEADERLESS and (kind in texts or not matches):
                raise HeaderFooterRefusal(
                    "slide and layout header placeholders are unsupported; "
                    "header text is limited to slide masters, notes and handout masters"
                )
            fresh = not matches
            source = part
            if fresh:
                template = self.template(part, kind)
                if template is None:
                    if root_kind == "sld":
                        raise HeaderFooterRefusal(f"no {kind} placeholder template for this target")
                    next_id += 1
                    shape = self.new_placeholder(part, kind, next_id)
                else:
                    template_shape, source = template
                    _safe_placeholder(template_shape)
                    next_id += 1
                    # Geometry must remain visible in native rendering; copy an
                    # inherited layout's resolved master geometry when necessary.
                    shape = _placeholder_copy(template_shape, False, next_id, kind, 1)
                    for index, field in enumerate(shape.iter(f"{{{A_NS}}}fld")):
                        field_id = uuid5(NAMESPACE_URL, f"wolfppt:{part}#{next_id}:field:{index}")
                        field.set("id", "{" + str(field_id).upper() + "}")
                    if _geometry(shape) is None:
                        ancestor = self.parent(source)
                        fallback = None if ancestor is None else self.template(ancestor, kind)
                        if fallback is not None and _geometry(fallback[0]) is not None:
                            properties = shape.find(f"{{{P_NS}}}spPr")
                            inherited = fallback[0].find(f"{{{P_NS}}}spPr")
                            if properties is not None and inherited is not None:
                                shape.remove(properties)
                                shape.insert(1, deepcopy(inherited))
                    if _geometry(shape) is None:
                        if root_kind in {"notes", "notesMaster", "handoutMaster"}:
                            default = self.new_placeholder(part, kind, next_id)
                            properties = shape.find(f"{{{P_NS}}}spPr")
                            if properties is not None:
                                shape.remove(properties)
                            inherited = default.find(f"{{{P_NS}}}spPr")
                            assert inherited is not None
                            shape.insert(1, deepcopy(inherited))
                        else:
                            raise HeaderFooterRefusal(
                                "header/footer template has no explicit or inherited geometry"
                            )
                tree.append(shape)
                added.append(shape)
            else:
                shape = matches[0][1]
                _safe_placeholder(shape)
            changed = fresh
            if root_kind in {"notesMaster", "handoutMaster"} and _geometry(shape) is None:
                identity = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
                if identity is None or not identity.get("id", "").isdigit():
                    raise HeaderFooterRefusal("page placeholder has no valid shape identity")
                default = self.new_placeholder(part, kind, int(identity.get("id", "0")))
                properties = shape.find(f"{{{P_NS}}}spPr")
                if properties is not None:
                    shape.remove(properties)
                inherited = default.find(f"{{{P_NS}}}spPr")
                assert inherited is not None
                shape.insert(1, deepcopy(inherited))
                changed = True
            if kind in texts:
                body = _text_body(shape)
                _set_paragraph_text(body, texts[kind])
                changed = True
            elif kind == "sldNum":
                number = None if master else self.number(part, slides)
                changed = _number_field(shape, number, part) or changed
            elif fresh and part != source:
                # Empty layout prompts should not erase configured master text.
                if not _shape_text(shape):
                    ancestor = self.parent(source)
                    fallback = None if ancestor is None else self.template(ancestor, kind)
                    if fallback is not None and _shape_text(fallback[0]):
                        _set_paragraph_text(_text_body(shape), _shape_text(fallback[0]))
            if changed and not fresh:
                span = _shape_span(nodes, shape)
                changes.append((span["start"], span["end"], xml_fragment(shape, payload)))
        if added:
            tree_node = next(node for node in nodes if node["tag"] == f"{{{P_NS}}}spTree")
            if (
                payload[
                    _tag_end(payload, tree_node["start"]) - 2 : _tag_end(
                        payload, tree_node["start"]
                    )
                ]
                == b"/>"
            ):
                raise HeaderFooterRefusal("self-closing shape trees are unsupported")
            extension = next(
                (
                    node
                    for node in nodes
                    if node["parent"] == nodes.index(tree_node)
                    and node["tag"] == f"{{{P_NS}}}extLst"
                ),
                None,
            )
            anchor = (
                extension["start"]
                if extension is not None
                else payload.rindex(b"</", tree_node["start"], tree_node["end"])
            )
            changes.append(
                (anchor, anchor, b"".join(xml_fragment(shape, payload) for shape in added))
            )
        for start, end, replacement in sorted(changes, key=lambda item: item[0], reverse=True):
            payload = payload[:start] + replacement + payload[end:]
        if removed:
            payload = _drop_deleted_shape_timing(payload, removed) or payload
        if master:
            flags = one(root, f"{{{P_NS}}}hf")
            if flags is None:
                flags = ET.Element(f"{{{P_NS}}}hf")
                root.append(flags)
            for kind, visible in toggles.items():
                flags.set(kind, "1" if visible else "0")
            payload = splice_root_child(
                payload, "hf", xml_fragment(flags, payload), ("txStyles", "notesStyle", "extLst")
            )
        if payload != self.payloads[part]:
            self.replacements[part] = payload
            self.payloads[part] = payload


def _shape_text(shape: ET.Element) -> str:
    body = shape.find(f"{{{P_NS}}}txBody")
    if body is None:
        return ""
    return "\n".join(
        "".join(node.text or "" for node in paragraph.iter(f"{{{A_NS}}}t"))
        for paragraph in body.findall(f"{{{A_NS}}}p")
    )


def _safe_placeholder(shape: ET.Element) -> None:
    for element in shape.iter():
        if not isinstance(element.tag, str):
            continue
        if element.tag.rsplit("}", 1)[-1] == "extLst" or not element.tag.startswith(
            (f"{{{P_NS}}}", f"{{{A_NS}}}")
        ):
            raise HeaderFooterRefusal("extended header/footer placeholder is unsupported")
        if any(name.startswith("{") for name in element.attrib):
            raise HeaderFooterRefusal(
                "relationship-bearing or extended header/footer placeholder is unsupported"
            )


def _geometry(shape: ET.Element) -> ET.Element | None:
    return shape.find(f"{{{P_NS}}}spPr/{{{A_NS}}}xfrm")


def _text_body(shape: ET.Element) -> ET.Element:
    body = shape.find(f"{{{P_NS}}}txBody")
    if body is None:
        body = ET.SubElement(shape, f"{{{P_NS}}}txBody")
        ET.SubElement(body, f"{{{A_NS}}}bodyPr")
        ET.SubElement(body, f"{{{A_NS}}}lstStyle")
    return body


def _number_field(shape: ET.Element, number: int | None, part: str) -> bool:
    fields = list(shape.iter(f"{{{A_NS}}}fld"))
    if any(field.get("type") != "slidenum" for field in fields):
        raise HeaderFooterRefusal("unsupported field in slide-number placeholder")
    if len(fields) > 1:
        raise HeaderFooterRefusal("ambiguous slide-number field")
    changed = False
    if not fields:
        body = _text_body(shape)
        _set_paragraph_text(body, "")
        paragraph = body.find(f"{{{A_NS}}}p")
        assert paragraph is not None
        identity = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
        shape_id = "" if identity is None else identity.get("id", "")
        field_id = uuid5(NAMESPACE_URL, f"wolfppt:{part}#{shape_id}:slidenum")
        field = ET.Element(
            f"{{{A_NS}}}fld", {"id": "{" + str(field_id).upper() + "}", "type": "slidenum"}
        )
        ET.SubElement(field, f"{{{A_NS}}}rPr", {"lang": "en-US"})
        paragraph.insert(0, field)
        changed = True
    else:
        field = fields[0]
    text = field.find(f"{{{A_NS}}}t")
    if text is None:
        text = ET.SubElement(field, f"{{{A_NS}}}t")
        changed = True
    value = str(number) if number is not None else "\u2039#\u203a"
    if text.text != value:
        text.text = value
        changed = True
    return changed


def _shape_span(nodes: list[dict[str, Any]], shape: ET.Element) -> dict[str, Any]:
    identity = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
    if identity is None or not identity.get("id", "").isdigit():
        raise HeaderFooterRefusal("header/footer placeholder has no valid shape identity")
    shape_id = identity.get("id")
    matches = []
    for index, node in enumerate(nodes):
        if node["tag"] != f"{{{P_NS}}}sp":
            continue
        for child in nodes[index + 1 :]:
            if child["start"] >= node["end"]:
                break
            if child["tag"] == f"{{{P_NS}}}cNvPr" and child["attrib"].get("id") == shape_id:
                matches.append(node)
                break
    if len(matches) != 1:
        raise HeaderFooterRefusal("ambiguous header/footer shape identity")
    return matches[0]
