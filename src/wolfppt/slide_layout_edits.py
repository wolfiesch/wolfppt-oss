"""Layout lifecycle, saved master/layout custom data and slide master display.

``layout_master_custom_data(target)`` returns an immediate, saved-package string
mapping backed by the same OOXML tags as ``Slide.tags``. ``slide_master_display_manager``
reads and writes a slide's ``showMasterSp`` and ``showMasterPhAnim`` attributes.
Save queued edits first and save again to publish a package rewrite. Neither
facade changes ``Slide.hidden`` or promises playback of master animations.
"""

from __future__ import annotations

import posixpath
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .chart_workbook import serialize_xml_preserving_namespaces
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .presentation_tags import (
    LifecycleRefusal,
    OwnerRef,
    TagCollection,
    _records,
    _tag_part,
    apply_tag_edits,
    one,
    parse_xml,
    serialize_xml,
    xml_string,
)
from .shape_tree import (
    _first_transform,
    _matching_placeholder,
    _placeholder_key,
    _shape_identity,
    _transform_box,
    _tree_elements,
)
from .xml_helpers import find_ooxml, findall_ooxml, ooxml_namespace, ooxml_path

if TYPE_CHECKING:
    from .presentation import Presentation
    from .presentation_slides import Slide, SlideLayout, SlideMaster


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SLIDE_LAYOUT_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)


@dataclass(frozen=True)
class LayoutMasterRename:
    """Queue key staging a ``p:cSld/@name`` rewrite for a layout or master part.

    Renames share the slide-layout edit queue so they are written by
    :func:`apply_slide_layout_edits`, which runs after staged master/layout
    authoring has materialized pending parts.
    """

    partname: str


def queue_layout_master_rename(presentation: Presentation, partname: str, name: str) -> None:
    """Stage a rename of the slide layout or slide master stored at ``partname``."""
    changes = getattr(presentation, "_slide_layout_changes", None)
    if changes is None:
        changes = {}
        presentation._slide_layout_changes = changes
    changes[LayoutMasterRename(_normalize_package_partname(partname).lstrip("/"))] = name


def _stage_layout_master_rename(target: SlideLayout | SlideMaster, value: str | None) -> None:
    name = "" if value is None else str(value)
    if name == target.name:
        return
    if getattr(target, "_deleted", False):
        raise ValueError("cannot rename a removed slide layout")
    queue_layout_master_rename(target._presentation, target.partname, name)
    target._payload["name"] = name


def apply_slide_layout_removals(
    input_path: Path,
    output_path: Path,
    partnames: list[str],
) -> None:
    removals = {_normalize_package_partname(partname).lstrip("/") for partname in partnames}
    if not removals:
        _copy_package_with_replacements(input_path, output_path, {})
        return

    with zipfile.ZipFile(input_path) as package:
        replacements: dict[str, bytes] = {}
        removed_parts = set(removals)
        for partname in removals:
            removed_parts.add(_rels_part_for_package_part(partname))
            master_part, rel_id = _master_relationship_for_layout(package, partname)
            if master_part and rel_id:
                _remove_master_layout_reference(
                    package,
                    replacements,
                    master_part,
                    rel_id,
                    partname,
                )
        replacements["[Content_Types].xml"] = _content_types_without_layouts(
            package,
            removals,
        )

    _copy_package_with_replacements(
        input_path,
        output_path,
        replacements,
        removals=removed_parts,
    )


def apply_slide_layout_edits(
    input_path: Path | str,
    output_path: Path | str,
    edits: list[tuple[Any, str]],
) -> None:
    """Apply queued slide layout reassignments and layout/master renames.

    Preserves stable part identities, package structure, and all unrelated
    relationships, shapes, and media.
    """
    input_p = Path(input_path)
    output_p = Path(output_path)
    if not edits:
        _copy_package_with_replacements(input_p, output_p, {})
        return

    # Normalize edits: slide_part -> layout_part (last queued edit per slide wins)
    normalized_edits: dict[str, str] = {}
    renames: dict[str, str] = {}
    for target, value in edits:
        if isinstance(target, LayoutMasterRename):
            renames[target.partname] = value
            continue
        s_part = _normalize_package_partname(target).lstrip("/")
        l_part = _normalize_package_partname(value).lstrip("/")
        normalized_edits[s_part] = l_part

    with zipfile.ZipFile(input_p) as package:
        existing_names = set(package.namelist())
        replacements: dict[str, bytes] = {}

        for slide_part, layout_part in normalized_edits.items():
            if slide_part not in existing_names:
                raise ValueError(f"slide part {slide_part!r} not found in package")
            if layout_part not in existing_names:
                raise ValueError(f"layout part {layout_part!r} not found in package")

            # Validate placeholder geometry inheritance on package XML before applying
            slide_root = ET.fromstring(package.read(slide_part))
            layout_root = ET.fromstring(package.read(layout_part))
            master_part, _ = _master_relationship_for_layout(package, layout_part)
            master_root = (
                ET.fromstring(package.read(master_part))
                if master_part and master_part in existing_names
                else None
            )
            validate_slide_layout_roots_compatibility(
                slide_root,
                layout_root,
                master_root,
                layout_name=layout_part,
            )

            # Update relationship in slide's .rels part
            rels_part = _rels_part_for_package_part(slide_part)
            if rels_part not in existing_names and rels_part not in replacements:
                raise ValueError(f"slide relationships part {rels_part!r} not found")

            rels_data = replacements.get(rels_part) or package.read(rels_part)
            rels_root = ET.fromstring(rels_data)

            new_target = posixpath.relpath(layout_part, posixpath.dirname(slide_part) or ".")

            found_layout_rel = False
            for rel in findall_ooxml(rels_root, f"{{{PKG_REL_NS}}}Relationship"):
                rel_type = rel.attrib.get("Type", "")
                if rel_type == SLIDE_LAYOUT_REL_TYPE or rel_type.endswith("/slideLayout"):
                    rel.set("Target", new_target)
                    found_layout_rel = True
                    break

            if not found_layout_rel:
                # If no existing slideLayout relationship, add one
                existing_ids = {
                    r.attrib.get("Id", "")
                    for r in findall_ooxml(rels_root, f"{{{PKG_REL_NS}}}Relationship")
                }
                counter = 1
                while f"rId{counter}" in existing_ids:
                    counter += 1
                new_rel = ET.SubElement(rels_root, f"{{{PKG_REL_NS}}}Relationship")
                new_rel.set("Id", f"rId{counter}")
                new_rel.set("Type", f"{ooxml_namespace(slide_root, R_NS)}/slideLayout")
                new_rel.set("Target", new_target)

            ET.register_namespace("", PKG_REL_NS)
            replacements[rels_part] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

        for partname, name in renames.items():
            if partname not in existing_names:
                raise ValueError(f"layout or master part {partname!r} not found")
            root = ET.fromstring(package.read(partname))
            common_slide_data = find_ooxml(root, f"{{{P_NS}}}cSld")
            if common_slide_data is None:
                raise ValueError(f"part {partname!r} has no p:cSld element")
            if name:
                common_slide_data.set("name", name)
            else:
                common_slide_data.attrib.pop("name", None)
            replacements[partname] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    _copy_package_with_replacements(input_p, output_p, replacements)


def validate_slide_layout_assignment(slide: Slide, target_layout: SlideLayout) -> None:
    """Validate that target_layout can be assigned to slide.

    Refuses foreign, deleted, or removed layouts, deleted slides, and any
    reassignment that would silently omit visible placeholder content due to
    unresolvable layout/master geometry.
    """
    from .presentation_slides import SlideLayout

    if not isinstance(target_layout, SlideLayout):
        raise TypeError(f"expected SlideLayout, got {type(target_layout).__name__}")
    if getattr(slide, "_deleted", False):
        raise ValueError("cannot assign layout to a deleted slide")
    if getattr(slide, "_stale", False) or (
        isinstance(getattr(slide, "_payload", None), dict) and slide._payload.get("_stale")
    ):
        raise ValueError("cannot assign layout to a stale slide")
    if (
        isinstance(getattr(slide, "_payload", None), dict)
        and slide._payload.get("_pending_creation")
    ) or not slide.partname:
        raise ValueError(
            "cannot assign layout to an unsaved new slide; save and reopen the "
            "presentation before reassigning layout"
        )

    presentation = getattr(slide, "_presentation", None)
    if presentation is None:
        raise ValueError("slide is detached from presentation")
    if slide not in presentation.slides:
        raise ValueError("slide is not in presentation slides collection")

    if getattr(target_layout, "_presentation", None) is not presentation:
        raise ValueError("slide layout belongs to a different presentation")
    if getattr(target_layout, "_deleted", False) or target_layout not in presentation.slide_layouts:
        raise ValueError("slide layout has been removed or is not in presentation")
    if getattr(target_layout, "_stale", False) or (
        isinstance(getattr(target_layout, "_payload", None), dict)
        and target_layout._payload.get("_stale")
    ):
        raise ValueError("cannot assign a stale slide layout")

    # If already assigned to the same layout partname, no-op / valid
    current_layout = getattr(slide, "slide_layout", None)
    if current_layout is not None and current_layout.partname == target_layout.partname:
        return

    # Extract XML trees for validation
    slide_root = slide.element._element
    layout_root = target_layout.element._element
    slide_master = target_layout.slide_master
    master_root = slide_master.element._element if slide_master is not None else None

    # Check for in-memory visible shapes on slide facade
    facade_content_map: dict[tuple[str, str] | str, bool] = {}
    if getattr(slide, "_shapes", None) is not None:
        for s in slide.shapes:
            if getattr(s, "is_placeholder", False):
                has_content = (
                    bool(s.text and s.text.strip())
                    or getattr(s, "has_table", False)
                    or getattr(s, "has_chart", False)
                )
                elem = getattr(s, "element", None)
                raw_elem = getattr(elem, "_element", None) if elem is not None else None
                if raw_elem is not None:
                    ph_key = _placeholder_key(raw_elem)
                    if ph_key is not None:
                        facade_content_map[ph_key] = has_content
                if getattr(s, "name", None):
                    facade_content_map[s.name] = has_content

    validate_slide_layout_roots_compatibility(
        slide_root,
        layout_root,
        master_root,
        layout_name=target_layout.name or target_layout.partname,
        facade_content=facade_content_map,
    )


def validate_slide_layout_roots_compatibility(
    slide_root: ET.Element,
    layout_root: ET.Element,
    master_root: ET.Element | None,
    layout_name: str = "",
    facade_content: dict[tuple[str, str] | str, bool] | None = None,
) -> None:
    """Refuse any reassignment that would silently omit visible placeholder content.

    Reuses current placeholder matching and inheritance semantics from render_scene.
    """
    for element in _tree_elements(slide_root):
        name, hidden = _shape_identity(element, "shape")
        if hidden:
            continue

        key = _placeholder_key(element)
        if key is None:
            continue

        # Check if the slide's shape has its own explicit valid transform
        own_sp_pr = find_ooxml(element, f"{{{P_NS}}}spPr")
        own_transform = _first_transform([own_sp_pr])
        if own_transform is not None and _transform_box(own_transform) is not None:
            # Explicit slide geometry exists; the renderer will use it directly.
            continue

        # Check if target layout or master provides a valid transform for key
        chain: list[ET.Element] = []
        match_layout = _matching_placeholder(layout_root, key)
        if match_layout is not None:
            chain.append(match_layout)
        if master_root is not None:
            match_master = _matching_placeholder(master_root, key)
            if match_master is not None:
                chain.append(match_master)

        target_sources = [find_ooxml(c, f"{{{P_NS}}}spPr") for c in chain]
        target_transform = _first_transform(target_sources)
        target_box = None if target_transform is None else _transform_box(target_transform)

        if target_box is not None:
            # Resolvable geometry found in target layout or master!
            continue

        # Geometry cannot be resolved in target layout/master.
        # Check if the shape on the slide has visible placeholder content.
        has_content = _shape_has_visible_placeholder_content(element)
        if facade_content is not None:
            # Prefer exact OOXML placeholder key over non-unique shape name
            if key in facade_content:
                has_content = facade_content[key]
            elif name in facade_content:
                has_content = facade_content[name]

        if has_content:
            label = layout_name or "target layout"
            raise ValueError(
                f"cannot reassign slide layout to {label!r}: visible placeholder "
                f"{name!r} ({key[0]}:{key[1]}) has content but neither the target "
                "layout nor its slide master provides resolvable geometry"
            )


def _shape_has_visible_placeholder_content(shape: ET.Element) -> bool:
    """Check if an OOXML shape element contains visible placeholder content."""
    # Text content in txBody
    for t in findall_ooxml(shape, f".//{{{A_NS}}}t"):
        if t.text and t.text.strip():
            return True

    # Picture content
    if find_ooxml(shape, f".//{{{A_NS}}}blip") is not None:
        return True

    # Graphic frame content (table, chart, diagram)
    if (
        find_ooxml(shape, f".//{{{A_NS}}}graphic") is not None
        or find_ooxml(shape, f".//{{{A_NS}}}tbl") is not None
    ):
        return True

    # Check for explicit shape fill in spPr (not noFill)
    sp_pr = find_ooxml(shape, f"{{{P_NS}}}spPr")
    if sp_pr is not None:
        for tag in ("solidFill", "gradFill", "blipFill", "pattFill"):
            if find_ooxml(sp_pr, f"{{{A_NS}}}{tag}") is not None:
                return True

    return False


def _master_relationship_for_layout(
    package: zipfile.ZipFile,
    layout_part: str,
) -> tuple[str | None, str | None]:
    """Return (master_part, rel_id_in_master_pointing_to_layout).

    Resolves authoritative slide master via layout's relationships, then finds
    the matching relationship in that master pointing to layout_part and returns
    its relationship ID.
    """
    master_part: str | None = None
    layout_rels = _rels_part_for_package_part(layout_part)
    if layout_rels in package.namelist():
        try:
            root = ET.fromstring(package.read(layout_rels))
            for relationship in findall_ooxml(root, f"{{{PKG_REL_NS}}}Relationship"):
                target_mode = relationship.attrib.get("TargetMode")
                if target_mode == "External":
                    continue
                rel_type = relationship.attrib.get("Type", "")
                if rel_type.endswith("/slideMaster"):
                    target = relationship.attrib.get("Target")
                    if target:
                        cand = _resolve_package_target(layout_part, target)
                        if cand in package.namelist():
                            master_part = cand
                            break
        except (KeyError, ET.ParseError):
            pass

    # If master_part was resolved, find the relationship in THAT master pointing to layout_part
    if master_part is not None:
        master_rels = _rels_part_for_package_part(master_part)
        if master_rels in package.namelist():
            try:
                root = ET.fromstring(package.read(master_rels))
                for relationship in findall_ooxml(root, f"{{{PKG_REL_NS}}}Relationship"):
                    target_mode = relationship.attrib.get("TargetMode")
                    if target_mode == "External":
                        continue
                    target = relationship.attrib.get("Target")
                    rel_id = relationship.attrib.get("Id")
                    if not target or not rel_id:
                        continue
                    if _resolve_package_target(master_part, target) == layout_part:
                        return master_part, rel_id
            except (KeyError, ET.ParseError):
                pass
        return None, None

    # Fallback only when layout rels part is absent: scan internal master rels
    for name in package.namelist():
        if not (name.startswith("ppt/slideMasters/_rels/") and name.endswith(".rels")):
            continue
        master_cand = f"ppt/slideMasters/{Path(name).name.removesuffix('.rels')}"
        try:
            root = ET.fromstring(package.read(name))
        except (KeyError, ET.ParseError):
            continue
        for relationship in findall_ooxml(root, f"{{{PKG_REL_NS}}}Relationship"):
            target_mode = relationship.attrib.get("TargetMode")
            if target_mode == "External":
                continue
            target = relationship.attrib.get("Target")
            rel_id = relationship.attrib.get("Id")
            if not target or not rel_id:
                continue
            if _resolve_package_target(master_cand, target) == layout_part:
                return master_cand, rel_id
    return None, None


def _remove_master_layout_reference(
    package: zipfile.ZipFile,
    replacements: dict[str, bytes],
    master_part: str,
    rel_id: str,
    layout_part: str,
) -> None:
    rels_part = _rels_part_for_package_part(master_part)
    rels_root = ET.fromstring(replacements.get(rels_part, package.read(rels_part)))
    for relationship in list(rels_root):
        target = relationship.attrib.get("Target")
        if relationship.attrib.get("Id") == rel_id or (
            target and _resolve_package_target(master_part, target) == layout_part
        ):
            rels_root.remove(relationship)
    ET.register_namespace("", PKG_REL_NS)
    replacements[rels_part] = ET.tostring(rels_root, encoding="utf-8")

    master_root = ET.fromstring(replacements.get(master_part, package.read(master_part)))
    layout_ids = find_ooxml(master_root, f"{{{P_NS}}}sldLayoutIdLst")
    if layout_ids is not None:
        for layout_id in list(layout_ids):
            if layout_id.attrib.get(ooxml_path(layout_id, f"{{{R_NS}}}id")) == rel_id:
                layout_ids.remove(layout_id)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
    replacements[master_part] = ET.tostring(master_root, encoding="utf-8")


def _content_types_without_layouts(
    package: zipfile.ZipFile,
    removals: set[str],
) -> bytes:
    root = ET.fromstring(package.read("[Content_Types].xml"))
    partnames = {f"/{partname}" for partname in removals}
    for override in list(findall_ooxml(root, f"{{{CONTENT_TYPES_NS}}}Override")):
        if override.attrib.get("PartName") in partnames:
            root.remove(override)
    ET.register_namespace("", CONTENT_TYPES_NS)
    return ET.tostring(root, encoding="utf-8")


_SINGLETON_PLACEHOLDERS = {
    "title": frozenset({"title", "ctrTitle"}),
    "dt": frozenset({"dt"}),
    "ftr": frozenset({"ftr"}),
    "sldNum": frozenset({"sldNum"}),
}
_FOOTER_IDX = {"dt": 10, "ftr": 11, "sldNum": 12}


class LayoutPlaceholderManager:
    """Adds placeholders to one slide layout.

    Positions and sizes are in EMU. Each call returns the new layout
    placeholder shape, which slides added from the layout afterwards inherit;
    the placeholder is written on the next save. A layout holds at most one
    title, date, footer and slide-number placeholder.
    """

    def __init__(self, layout: SlideLayout) -> None:
        if not layout.partname:
            raise ValueError("the slide layout has no package part")
        self._layout = layout

    def add_title_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("title", (x, y, width, height))

    def add_vertical_title_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("title", (x, y, width, height), vertical=True)

    def add_text_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("body", (x, y, width, height))

    def add_vertical_text_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("body", (x, y, width, height), vertical=True)

    def add_content_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("obj", (x, y, width, height))

    def add_vertical_content_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("obj", (x, y, width, height), vertical=True)

    def add_chart_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("chart", (x, y, width, height))

    def add_table_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("tbl", (x, y, width, height))

    def add_picture_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("pic", (x, y, width, height))

    def add_media_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("media", (x, y, width, height))

    def add_smart_art_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("dgm", (x, y, width, height))

    def add_date_time_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("dt", (x, y, width, height))

    def add_footer_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("ftr", (x, y, width, height))

    def add_slide_number_placeholder(self, x: int, y: int, width: int, height: int) -> Any:
        return self._add("sldNum", (x, y, width, height))

    def _add(self, kind: str, box: tuple[int, int, int, int], *, vertical: bool = False) -> Any:
        from .shape_facade import MasterShape
        from .slide_master_facade import (
            LATENT_PLACEHOLDER_TYPES,
            _placeholder_spec_payload,
            _requests,
            placeholder_spec,
        )
        from .slide_payloads import load_slide_layout_placeholder_payloads

        layout = self._layout
        if layout._deleted:
            raise ValueError("cannot add placeholders to a removed slide layout")
        presentation = layout._presentation
        part = layout.partname.lstrip("/")
        request = next(
            (
                entry
                for entry in _requests(presentation)
                if entry.get("kind") == "layout_placeholders" and entry.get("part") == part
            ),
            None,
        )
        pending = [] if request is None else list(request["shapes"])
        ids, indexes, kinds = _layout_placeholder_inventory(layout.element._element)
        ids.update(int(spec["id"]) for spec in pending)
        indexes.update(int(spec["idx"]) for spec in pending if spec["idx"] is not None)
        kinds.update(str(spec["type"]) for spec in pending)
        for singleton, rivals in _SINGLETON_PLACEHOLDERS.items():
            if kind == singleton and kinds & rivals:
                raise ValueError(f"the layout already has a {kind} placeholder")
        idx: int | None = None
        if kind != "title":
            idx = _FOOTER_IDX.get(kind, 1)
            while idx in indexes:
                idx += 1
        spec = placeholder_spec(
            kind,
            max(ids, default=1) + 1,
            idx,
            box,
            vertical=vertical,
            size="quarter" if kind in {"ftr", "sldNum"} else None,
        )
        if request is None:
            request = {"kind": "layout_placeholders", "part": part, "shapes": []}
            _requests(presentation).append(request)
        request["shapes"].append(spec)

        payload = _placeholder_spec_payload(spec)
        shapes = layout.shapes
        shape = MasterShape(layout, len(shapes), payload)
        shapes._shapes.append(shape)
        layout.placeholders._placeholders.append(shape)
        if kind not in LATENT_PLACEHOLDER_TYPES:
            staged = layout._payload.get("_placeholder_payloads")
            if staged is None:
                staged = load_slide_layout_placeholder_payloads(presentation.path, part)
                layout._payload["_placeholder_payloads"] = staged
            staged.append({**payload, "paragraph_line_breaks": [[]]})
        return shape


def layout_placeholder_manager(layout: SlideLayout) -> LayoutPlaceholderManager:
    """The placeholder manager of ``layout``."""
    return LayoutPlaceholderManager(layout)


class MasterLayoutRefusal(ValueError):
    """An unsupported master/layout edit, refused before the package is changed."""


class _LayoutMasterOwnerRef(OwnerRef):
    """Part-bound adapter; layout/master owners are not slide owners."""

    def validate(self) -> None:
        presentation = self.presentation
        _require_master_layout_saved(presentation)
        owner = self.part_owner
        if getattr(owner, "_presentation", None) is not presentation:
            raise MasterLayoutRefusal("custom data owner belongs to another presentation")
        if getattr(owner, "_deleted", False) or getattr(owner, "_stale", False):
            raise MasterLayoutRefusal("custom data owner is deleted or stale")
        payload = getattr(owner, "_payload", {})
        if payload.get("_pending_creation") or payload.get("_stale"):
            raise MasterLayoutRefusal("custom data owner must be saved and current")
        from .presentation_slides import SlideLayout

        collection = (
            presentation.slide_layouts
            if isinstance(owner, SlideLayout)
            else presentation.slide_masters
        )
        part = self.source_part()
        if not part or part not in {entry.partname.lstrip("/") for entry in collection}:
            raise MasterLayoutRefusal("custom data owner is detached from the presentation")


def layout_master_custom_data(target: Any) -> TagCollection:
    """Return saved layout/master custom data using the existing OOXML tags format.

    Keys are exact case-sensitive strings. Assignment, ``update``, deletion and
    ``clear`` commit atomically and immediately; call ``Presentation.save`` to
    publish the result. Shared tag parts use existing copy-on-write semantics.
    Pending edits, deleted/detached owners, ambiguous metadata and unsafe XML
    refuse with ``MasterLayoutRefusal`` before writing. A missing key still
    raises ``KeyError``, as on every other ``TagCollection``.
    """
    from .presentation_slides import SlideLayout, SlideMaster

    if not isinstance(target, (SlideLayout, SlideMaster)):
        raise MasterLayoutRefusal("custom data target must be a SlideLayout or SlideMaster")
    return _LayoutMasterTagCollection(target)


class _LayoutMasterTagCollection(TagCollection):
    def __init__(self, target: Any) -> None:
        self._ref = _LayoutMasterOwnerRef(target._presentation, target, target, None)
        self._edits: dict[str, str | None] = {}
        self._values = self._read_values()

    def _read_values(self) -> dict[str, str]:
        from .package_parts import open_package_source

        presentation = self._ref.presentation
        with presentation._mutation_lock:
            self._ref.validate()
            try:
                with open_package_source(presentation._source_path) as package:
                    part = self._ref.source_part()
                    root = parse_xml(package.read(part), read_only=True)
                    _require_custom_data_root(root, self._ref.part_owner)
                    _, tags = _tag_part(package, part, root, None, {}, read_only=True)
                    return _records(tags)
            except (LifecycleRefusal, ET.ParseError, KeyError, TypeError, ValueError) as exc:
                raise MasterLayoutRefusal(str(exc)) from exc

    def __getitem__(self, key: str) -> str:
        return self._read_values()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._read_values())

    def __len__(self) -> int:
        return len(self._read_values())

    def __setitem__(self, key: str, value: str) -> None:
        self.update({key: value})

    def __delitem__(self, key: str) -> None:
        presentation = self._ref.presentation
        with presentation._mutation_lock:
            values = self._read_values()
            if key not in values:
                raise KeyError(key)
            self._commit({key: None})

    def update(self, other: Any = (), **kwargs: str) -> None:
        try:
            incoming = dict(other, **kwargs)
            for key, value in incoming.items():
                xml_string(key, "tag name")
                xml_string(value, "tag value")
        except (TypeError, ValueError) as exc:
            raise MasterLayoutRefusal(str(exc)) from exc
        self._commit(incoming)

    def clear(self) -> None:
        presentation = self._ref.presentation
        with presentation._mutation_lock:
            self._commit(dict.fromkeys(self._read_values()))

    def _commit(self, edits: dict[str, str | None]) -> None:
        from .presentation_fields import _signature

        presentation = self._ref.presentation
        with presentation._mutation_lock:
            self._ref.validate()

            def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
                try:
                    part = self._ref.source_part()
                    source = package.read(part)
                    root = parse_xml(source)
                    _require_custom_data_root(root, self._ref.part_owner)
                    roots = {part: root}
                    _, tags = _tag_part(package, part, root, None, roots)
                    current = _records(tags)
                    changed = tuple(
                        (key, value)
                        for key, value in edits.items()
                        if (key in current if value is None else current.get(key) != value)
                    )
                    if not changed:
                        return {}, set(), None
                    apply_tag_edits(package, roots, (self._ref, changed), {}, None)
                    replacements = {}
                    for name, staged in roots.items():
                        if name in package.namelist() and _signature(staged) == _signature(
                            parse_xml(package.read(name))
                        ):
                            continue
                        replacements[name] = (
                            _splice_custom_data_link(source, staged)
                            if name == part
                            else serialize_xml(staged)
                        )
                        if name == part and _signature(parse_xml(replacements[name])) != _signature(
                            staged
                        ):
                            raise MasterLayoutRefusal(
                                "custom data link cannot be preserved in this XML encoding"
                            )
                    return replacements, set(), None
                except (LifecycleRefusal, ET.ParseError, KeyError, TypeError, ValueError) as exc:
                    raise MasterLayoutRefusal(str(exc)) from exc

            presentation._rewrite_package("editing layout/master custom data", plan)


def _require_custom_data_root(root: ET.Element, owner: Any) -> None:
    from .presentation_slides import SlideLayout

    local = "sldLayout" if isinstance(owner, SlideLayout) else "sldMaster"
    if root.tag != ooxml_path(root, f"{{{P_NS}}}{local}"):
        raise MasterLayoutRefusal("custom data owner has an unexpected package root")


def _splice_custom_data_link(source: bytes, root: ET.Element) -> bytes:
    """Change only the tags link; preserve opaque customer data and shape bytes."""
    from copy import deepcopy

    from .presentation_save_state import _element_spans, _tag_end

    common = one(root, f"{{{P_NS}}}cSld")
    container = one(common, f"{{{P_NS}}}custDataLst")
    link = one(container, f"{{{P_NS}}}tags")
    fragment_node = deepcopy(link)
    fragment_node.tail = None
    fragment = serialize_xml(fragment_node).split(b"?>", 1)[1].lstrip(b"\r\n")
    nodes = _element_spans(source)
    p_ns = ooxml_namespace(root, P_NS)
    common_index = next(
        index
        for index, node in enumerate(nodes)
        if node["parent"] == 0 and node["tag"] == f"{{{p_ns}}}cSld"
    )
    container_index = next(
        (
            index
            for index, node in enumerate(nodes)
            if node["parent"] == common_index and node["tag"] == f"{{{p_ns}}}custDataLst"
        ),
        None,
    )
    if container_index is None:
        wrapper = ET.Element(f"{{{p_ns}}}custDataLst")
        wrapper.append(fragment_node)
        fragment = serialize_xml(wrapper).split(b"?>", 1)[1].lstrip(b"\r\n")
        parent_index = common_index
    else:
        parent_index = container_index
        existing = next(
            (
                node
                for node in nodes
                if node["parent"] == parent_index and node["tag"] == f"{{{p_ns}}}tags"
            ),
            None,
        )
        if existing is not None:
            return source[: existing["start"]] + fragment + source[existing["end"] :]
    parent = nodes[parent_index]
    opening_end = _tag_end(source, parent["start"])
    if source[opening_end - 2 : opening_end] == b"/>":
        opening = source[parent["start"] : opening_end]
        name = opening.split(None, 1)[0][1:].rstrip(b"/>")
        replacement = opening[:-2] + b">" + fragment + b"</" + name + b">"
        return source[: parent["start"]] + replacement + source[opening_end:]
    anchor = next(
        (
            node["start"]
            for node in nodes
            if node["parent"] == parent_index
            and node["tag"] in {f"{{{p_ns}}}controls", f"{{{p_ns}}}extLst"}
        ),
        source.rindex(b"</", parent["start"], parent["end"]),
    )
    return source[:anchor] + fragment + source[anchor:]


def slide_master_display_manager(slide: Slide) -> SlideMasterDisplayManager:
    """Control a saved slide's master shapes and master placeholder animations."""
    return SlideMasterDisplayManager(slide)


class SlideMasterDisplayManager:
    """Immediate atomic controls for ``showMasterSp`` and ``showMasterPhAnim``.

    Both default to true when absent. These controls do not hide slide-owned
    placeholders or change ``Slide.hidden``. The animation flag is persisted;
    this API does not claim animation playback. Save queued edits first, then
    save the presentation again to publish. Managers resolve their saved part
    afresh after a rewrite; removed, stale, or unsaved targets are refused.
    """

    def __init__(self, slide: Slide) -> None:
        from .presentation_slides import Slide

        if not isinstance(slide, Slide):
            raise MasterLayoutRefusal("master display target must be a Slide")
        self._slide = slide
        self._presentation = slide._presentation
        self._part = slide.partname.lstrip("/")
        with self._presentation._mutation_lock:
            self._validate()
            self._read()

    def _validate(self) -> None:
        _require_master_layout_saved(self._presentation)
        payload = getattr(self._slide, "_payload", {})
        if getattr(self._slide, "_deleted", False) or getattr(self._slide, "_stale", False):
            raise MasterLayoutRefusal("master display target is deleted or stale")
        if payload.get("_pending_creation") or payload.get("_stale"):
            raise MasterLayoutRefusal("master display target must be saved and current")
        if not self._part or self._part not in {
            slide.partname.lstrip("/") for slide in self._presentation.slides
        }:
            raise MasterLayoutRefusal("master display target is detached from the presentation")

    def _flags(self, source: bytes) -> dict[str, bool]:
        try:
            root = parse_xml(source)
            if root.tag != ooxml_path(root, f"{{{P_NS}}}sld"):
                raise MasterLayoutRefusal("master display target is not a slide part")
            flags = {}
            for name in ("showMasterSp", "showMasterPhAnim"):
                raw = root.get(name, "true")
                if raw not in {"0", "1", "false", "true"}:
                    raise MasterLayoutRefusal(f"invalid slide {name} flag")
                flags[name] = raw in {"1", "true"}
            return flags
        except (LifecycleRefusal, ET.ParseError) as exc:
            raise MasterLayoutRefusal(str(exc)) from exc

    def _read(self) -> dict[str, bool]:
        from .package_parts import open_package_source

        with self._presentation._mutation_lock:
            self._validate()
            try:
                with open_package_source(self._presentation._source_path) as package:
                    return self._flags(package.read(self._part))
            except KeyError as exc:
                raise MasterLayoutRefusal("master display slide part is missing") from exc

    @property
    def show_master_shapes(self) -> bool:
        return self._read()["showMasterSp"]

    @show_master_shapes.setter
    def show_master_shapes(self, value: bool) -> None:
        self.update(show_master_shapes=value)

    @property
    def show_master_placeholder_animations(self) -> bool:
        return self._read()["showMasterPhAnim"]

    @show_master_placeholder_animations.setter
    def show_master_placeholder_animations(self, value: bool) -> None:
        self.update(show_master_placeholder_animations=value)

    def update(
        self,
        *,
        show_master_shapes: bool | None = None,
        show_master_placeholder_animations: bool | None = None,
    ) -> None:
        """Atomically set either or both flags, preserving every other XML byte."""
        changes = {}
        for name, value in (
            ("showMasterSp", show_master_shapes),
            ("showMasterPhAnim", show_master_placeholder_animations),
        ):
            if value is not None:
                if not isinstance(value, bool):
                    raise MasterLayoutRefusal(f"{name} must be a bool or None")
                changes[name] = value
        if not changes:
            raise MasterLayoutRefusal("master display update needs at least one setting")
        with self._presentation._mutation_lock:
            self._validate()

            def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
                try:
                    source = package.read(self._part)
                    self._flags(source)
                    payload = _edit_slide_root_flags(source, changes)
                    persisted = self._flags(payload)
                    if any(persisted[name] != value for name, value in changes.items()):
                        raise MasterLayoutRefusal(
                            "slide master display flags could not be preserved"
                        )
                    return ({self._part: payload} if payload != source else {}), set(), None
                except (KeyError, ValueError) as exc:
                    raise MasterLayoutRefusal(str(exc)) from exc

            self._presentation._rewrite_package("editing slide master display", plan)


def _edit_slide_root_flags(source: bytes, changes: dict[str, bool]) -> bytes:
    from .package_conformance import _ATTRIBUTE, _insert_attribute
    from .presentation_save_state import _element_spans, _tag_end

    root = _element_spans(source)[0]
    start = root["start"]
    end = _tag_end(source, start)
    opening = source[start:end]
    replacements = []
    present = set()
    for match in _ATTRIBUTE.finditer(opening):
        name = match.group(2).decode("utf-8")
        if name in changes:
            present.add(name)
            replacements.append(
                (
                    match.start(5),
                    match.end(5),
                    b"1" if changes[name] else b"0",
                )
            )
    for begin, finish, replacement in reversed(replacements):
        opening = opening[:begin] + replacement + opening[finish:]
    for name, value in changes.items():
        if name not in present:
            opening = _insert_attribute(opening, f' {name}="{int(value)}"'.encode())
    return source[:start] + opening + source[end:]


def set_layout_type(layout: SlideLayout, kind: str) -> None:
    """Edit a saved layout's declared type without replacing its authored shapes.

    Use ``add_layout_of_type`` to synthesize a new placeholder arrangement.
    Save pending edits first; package-rewriting operations invalidate old handles.
    """
    from .presentation_slides import SlideLayout
    from .slide_master_facade import layout_type_value

    if not isinstance(layout, SlideLayout):
        raise MasterLayoutRefusal("target must be a SlideLayout")
    try:
        value = layout_type_value(kind)
    except (TypeError, ValueError) as exc:
        raise MasterLayoutRefusal(str(exc)) from exc
    presentation = layout._presentation
    part = layout.partname.lstrip("/")
    with presentation._mutation_lock:
        _require_master_layout_saved(presentation)
        if layout._deleted or part not in {entry.partname for entry in presentation.slide_layouts}:
            raise MasterLayoutRefusal("layout is detached from the presentation")

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            source = package.read(part)
            root = _master_layout_xml(source)
            if root.tag != ooxml_path(root, f"{{{P_NS}}}sldLayout"):
                raise MasterLayoutRefusal("target part is not a slide layout")
            root.set("type", value)
            return {part: serialize_xml_preserving_namespaces(root, source)}, set(), None

        presentation._rewrite_package("setting layout type", plan)


def remove_slide_master(master: Any) -> None:
    """Remove an unused saved master and its child layouts atomically.

    Shared themes, images and other dependencies remain byte-identical.
    Refuse removal of the last master, in-use layouts, foreign or shared layout
    graphs, deleted/stale targets, malformed registrations and pending edits.
    Reacquire handles after this operation.
    """
    from .presentation_slides import SlideMaster
    from .slide_metadata import presentation_partname

    if not isinstance(master, SlideMaster):
        raise MasterLayoutRefusal("target must be a SlideMaster")
    presentation = master._presentation
    master_part = master.partname.lstrip("/")
    with presentation._mutation_lock:
        _require_master_layout_saved(presentation)
        if getattr(master, "_deleted", False) or getattr(master, "_stale", False):
            raise MasterLayoutRefusal("master is deleted or stale")
        payload = getattr(master, "_payload", {})
        if payload.get("_pending_creation") or payload.get("_stale"):
            raise MasterLayoutRefusal("master must be saved and current")
        masters = {entry.partname.lstrip("/") for entry in presentation.slide_masters}
        if master_part not in masters:
            raise MasterLayoutRefusal("master is detached from the presentation")
        if len(masters) <= 1:
            raise MasterLayoutRefusal("cannot remove the last slide master")
        layouts = {entry.partname.lstrip("/") for entry in master.slide_layouts}
        if any(slide.slide_layout.partname.lstrip("/") in layouts for slide in presentation.slides):
            raise MasterLayoutRefusal("cannot remove a master with layouts in use")
        presentation_part = presentation_partname(presentation.path)

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            names = set(package.namelist())
            removed = {master_part, *layouts}
            if not removed <= names:
                raise MasterLayoutRefusal("master or child layout part is missing")
            master_root = _master_layout_xml(package.read(master_part))
            if master_root.tag != ooxml_path(master_root, f"{{{P_NS}}}sldMaster"):
                raise MasterLayoutRefusal("master target has an unexpected package root")
            for layout_part in layouts:
                layout_root = _master_layout_xml(package.read(layout_part))
                if layout_root.tag != ooxml_path(layout_root, f"{{{P_NS}}}sldLayout"):
                    raise MasterLayoutRefusal("child layout has an unexpected package root")
                owner, _ = _master_relationship_for_layout(package, layout_part)
                if owner != master_part:
                    raise MasterLayoutRefusal("master owns a foreign or unresolved layout")
            # Any remaining internal reference would become dangling. Only the
            # presentation's own registration is removed along with this closure.
            presentation_rels_part = _rels_part_for_package_part(presentation_part)
            for name in names:
                if name == "_rels/.rels":
                    owner = ""
                elif name.endswith(".rels") and "/_rels/" in name:
                    directory, filename = name.rsplit("/_rels/", 1)
                    owner = f"{directory}/{filename.removesuffix('.rels')}"
                else:
                    continue
                if owner in removed:
                    continue
                for relationship in _master_layout_xml(package.read(name)):
                    if relationship.get("TargetMode") == "External":
                        continue
                    target = relationship.get("Target", "")
                    if _resolve_package_target(owner, target) not in removed:
                        continue
                    if (
                        name == presentation_rels_part
                        and _resolve_package_target(owner, target) == master_part
                        and relationship.get("Type", "").endswith("/slideMaster")
                    ):
                        continue
                    raise MasterLayoutRefusal(f"removed part is referenced by {owner}")
            source = package.read(presentation_part)
            rels_source = package.read(presentation_rels_part)
            root = _master_layout_xml(source)
            rels = _master_layout_xml(rels_source)
            if root.tag != ooxml_path(root, f"{{{P_NS}}}presentation"):
                raise MasterLayoutRefusal("master registration owner is not a presentation")
            ids = {
                relationship.get("Id")
                for relationship in rels
                if relationship.get("TargetMode") != "External"
                and _resolve_package_target(presentation_part, relationship.get("Target", ""))
                == master_part
            }
            if not ids:
                raise MasterLayoutRefusal("master has no presentation registration")
            if len(ids) != 1 or not next(iter(ids)):
                raise MasterLayoutRefusal("master has an ambiguous presentation registration")
            master_ids = find_ooxml(root, f"{{{P_NS}}}sldMasterIdLst")
            if master_ids is None:
                raise MasterLayoutRefusal("presentation has no master id list")
            registered = [
                entry for entry in master_ids if entry.get(ooxml_path(root, f"{{{R_NS}}}id")) in ids
            ]
            if len(registered) != 1:
                raise MasterLayoutRefusal("master has missing or ambiguous master id registration")
            for entry in list(master_ids):
                if entry.get(ooxml_path(root, f"{{{R_NS}}}id")) in ids:
                    master_ids.remove(entry)
            for entry in list(rels):
                if entry.get("Id") in ids:
                    rels.remove(entry)
            replacements = {
                presentation_part: serialize_xml_preserving_namespaces(root, source),
                presentation_rels_part: serialize_xml_preserving_namespaces(rels, rels_source),
                "[Content_Types].xml": _content_types_without_layouts(package, removed),
            }
            removed.update(_rels_part_for_package_part(part) for part in tuple(removed))
            return replacements, removed, None

        try:
            presentation._rewrite_package("removing a slide master", plan)
        except MasterLayoutRefusal:
            raise
        except (LifecycleRefusal, ET.ParseError, KeyError, TypeError, ValueError) as exc:
            raise MasterLayoutRefusal(str(exc)) from exc


def _master_layout_xml(source: bytes) -> ET.Element:
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        return ET.fromstring(source, parser=parser)
    except ET.ParseError as exc:
        raise MasterLayoutRefusal("master/layout package XML is malformed") from exc


def _require_master_layout_saved(presentation: Any) -> None:
    try:
        presentation._require_saved_package("editing masters and layouts")
    except (ValueError, RuntimeError) as exc:
        raise MasterLayoutRefusal(str(exc)) from exc


def _layout_placeholder_inventory(
    root: ET.Element,
) -> tuple[set[int], set[int], set[str]]:
    ids: set[int] = set()
    indexes: set[int] = set()
    kinds: set[str] = set()
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local == "cNvPr" and element.get("id", "").isdigit():
            ids.add(int(element.get("id", "0")))
        elif local == "ph":
            kinds.add(element.get("type", "obj"))
            raw = element.get("idx")
            if raw is not None and raw.isdigit():
                indexes.add(int(raw))
    return ids, indexes, kinds


def apply_layout_placeholder_request(parts: dict[str, bytes], request: dict[str, Any]) -> None:
    """Append the staged placeholders to a layout's shape tree, byte-preserving."""
    from .presentation_save_state import _element_spans
    from .slide_master_facade import placeholder_element, xml_fragment

    part = str(request["part"]).lstrip("/")
    if part not in parts:
        raise ValueError(f"slide layout part {part!r} does not exist")
    payload = parts[part]
    fragment = b"".join(
        xml_fragment(placeholder_element(spec, part), payload) for spec in request["shapes"]
    )
    nodes = _element_spans(payload)
    tree_index = next(
        (
            index
            for index, node in enumerate(nodes)
            if node["tag"] == f"{{{P_NS}}}spTree"
            and node["parent"] is not None
            and nodes[node["parent"]]["tag"] == f"{{{P_NS}}}cSld"
            and nodes[node["parent"]]["parent"] == 0
        ),
        None,
    )
    if tree_index is None:
        raise ValueError(f"slide layout {part!r} has no shape tree")
    tree = nodes[tree_index]
    extension = next(
        (
            node
            for node in nodes
            if node["parent"] == tree_index and node["tag"] == f"{{{P_NS}}}extLst"
        ),
        None,
    )
    if extension is not None:
        anchor = extension["start"]
    else:
        anchor = payload.rindex(b"</", tree["start"], tree["end"])
    parts[part] = payload[:anchor] + fragment + payload[anchor:]


def layout_region(region: str, width: int, height: int) -> tuple[int, int, int, int]:
    """EMU box of a named layout region, proportional to PowerPoint's Office theme."""
    margin = round(width * 0.06875)
    gap = round(width * 0.015625)
    inner = width - 2 * margin
    half = (inner - gap) // 2
    title_y, title_h = round(height * 0.0532), round(height * 0.1933)
    body_y, body_h = round(height * 0.2662), round(height * 0.6345)
    half_h = (body_h - gap) // 2
    header_h = round(body_h * 0.18)
    right_x = margin + half + gap
    lower_y = body_y + half_h + gap
    footer_y, footer_h = round(height * 0.9268), round(height * 0.0532)
    side_w = round(width * 0.225)
    vertical_title_w = round(width * 0.2)
    vertical_title_x = width - margin - vertical_title_w
    vertical_body_w = inner - vertical_title_w - gap
    vertical_h = body_y + body_h - title_y
    vertical_half = (vertical_h - gap) // 2
    caption_w = round(width * 0.3)
    caption_main_x = margin + caption_w + 2 * gap
    boxes = {
        "title": (margin, title_y, inner, title_h),
        "center_title": (
            round(width * 0.125),
            round(height * 0.1636),
            round(width * 0.75),
            round(height * 0.348),
        ),
        "subtitle": (
            round(width * 0.125),
            round(height * 0.525),
            round(width * 0.75),
            round(height * 0.2413),
        ),
        "full": (margin, body_y, inner, body_h),
        "whole": (margin, title_y, inner, body_y + body_h - title_y),
        "left": (margin, body_y, half, body_h),
        "right": (right_x, body_y, half, body_h),
        "top": (margin, body_y, inner, half_h),
        "bottom": (margin, lower_y, inner, half_h),
        "left_top": (margin, body_y, half, half_h),
        "right_top": (right_x, body_y, half, half_h),
        "left_bottom": (margin, lower_y, half, half_h),
        "right_bottom": (right_x, lower_y, half, half_h),
        "left_header": (margin, body_y, half, header_h),
        "right_header": (right_x, body_y, half, header_h),
        "left_under_header": (
            margin,
            body_y + header_h + gap,
            half,
            body_h - header_h - gap,
        ),
        "right_under_header": (
            right_x,
            body_y + header_h + gap,
            half,
            body_h - header_h - gap,
        ),
        "vertical_title": (vertical_title_x, title_y, vertical_title_w, vertical_h),
        "vertical_body": (margin, title_y, vertical_body_w, vertical_h),
        "vertical_body_top": (margin, title_y, vertical_body_w, vertical_half),
        "vertical_body_bottom": (
            margin,
            title_y + vertical_half + gap,
            vertical_body_w,
            vertical_half,
        ),
        "section_title": (
            margin,
            round(height * 0.25),
            inner,
            round(height * 0.4167),
        ),
        "section_body": (margin, round(height * 0.671), inner, round(height * 0.22)),
        "caption_title": (
            margin,
            round(height * 0.0667),
            caption_w,
            round(height * 0.2333),
        ),
        "caption_main": (
            caption_main_x,
            round(height * 0.1333),
            width - margin - caption_main_x,
            round(height * 0.73),
        ),
        "caption_text": (
            margin,
            round(height * 0.3),
            caption_w,
            round(height * 0.5633),
        ),
        "date": (margin, footer_y, side_w, footer_h),
        "footer": (
            round(width * 0.33125),
            footer_y,
            round(width * 0.3375),
            footer_h,
        ),
        "slide_number": (width - margin - side_w, footer_y, side_w, footer_h),
    }
    if region not in boxes:
        raise ValueError(f"unknown layout region {region!r}")
    return boxes[region]
