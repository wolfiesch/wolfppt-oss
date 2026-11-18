"""Saved-package ActiveX inspection and property-bag editing, without executing controls.

Use ``ActiveXControls(presentation, slide_index)`` to list, add and remove controls.
Edits rebase the saved facade atomically, like Presentation's slide utilities; save
queued shape edits first, then call ``Presentation.save`` to publish the result.
XML property bags support merge, removal and clear. Binary persistence stays opaque.
Read and edit saved preview geometry in EMUs; supported DrawingML/VML previews keep
their image bytes. Unsupported or shared mutation targets receive named refusals.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID
from xml.etree import ElementTree as ET

from .package_parts import open_package_source, rels_part_for_package_part, resolve_package_target
from .presentation_tags import xml_string

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
AX = "http://schemas.microsoft.com/office/2006/activeX"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
CONTROL_TYPE = R + "/control"
BINARY_TYPE = "http://schemas.microsoft.com/office/2006/relationships/activeXControlBinary"
CONTROL_CT = "application/vnd.ms-office.activeX+xml"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
V = "urn:schemas-microsoft-com:vml"
OFFICE = "urn:schemas-microsoft-com:office:office"
ET.register_namespace("ax", AX)


class ActiveXControlRefusal(ValueError):
    """Named atomic refusal for unsupported control persistence or package topology."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"ActiveXControlRefusal: {reason}")


class ActiveXControlKind(StrEnum):
    """Saved class identity only; classification never executes a control."""

    UNKNOWN = "unknown"
    CHECK_BOX = "check_box"
    COMBO_BOX = "combo_box"
    COMMAND_BUTTON = "command_button"
    IMAGE = "image"
    LABEL = "label"
    LIST_BOX = "list_box"
    OPTION_BUTTON = "option_button"
    SCROLL_BAR = "scroll_bar"
    SPIN_BUTTON = "spin_button"
    TEXT_BOX = "text_box"
    TOGGLE_BUTTON = "toggle_button"


_CLASS_KINDS = {
    UUID(guid): kind
    for guid, kind in (
        ("8bd21d40-ec42-11ce-9e0d-00aa006002f3", ActiveXControlKind.CHECK_BOX),
        ("8bd21d30-ec42-11ce-9e0d-00aa006002f3", ActiveXControlKind.COMBO_BOX),
        ("d7053240-ce69-11cd-a777-00dd01143c57", ActiveXControlKind.COMMAND_BUTTON),
        ("4c599241-6926-101b-9992-00000b65c6f9", ActiveXControlKind.IMAGE),
        ("978c9e23-d4b0-11ce-bf2d-00aa003f40d0", ActiveXControlKind.LABEL),
        ("8bd21d10-ec42-11ce-9e0d-00aa006002f3", ActiveXControlKind.LIST_BOX),
        ("8bd21d50-ec42-11ce-9e0d-00aa006002f3", ActiveXControlKind.OPTION_BUTTON),
        ("dfd181e0-5e2f-11ce-a449-00aa004a803d", ActiveXControlKind.SCROLL_BAR),
        ("79176fb0-b7f2-11ce-97ef-00aa006d2776", ActiveXControlKind.SPIN_BUTTON),
        ("8bd21d20-ec42-11ce-9e0d-00aa006002f3", ActiveXControlKind.TEXT_BOX),
        ("8bd21d60-ec42-11ce-9e0d-00aa006002f3", ActiveXControlKind.TOGGLE_BUTTON),
    )
}


@dataclass(frozen=True)
class ActiveXPreviewGeometry:
    """Axis-aligned saved preview position and size, in EMUs."""

    left: int
    top: int
    width: int
    height: int


@dataclass
class _Preview:
    part: str
    root: ET.Element
    shape: ET.Element
    geometry: ActiveXPreviewGeometry
    image_rid: str
    image_part: str
    vml_rid: str | None = None


class _XmlBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ActiveXControlRefusal("xml_declaration_unsupported")


def _xml(package: Any, part: str) -> ET.Element:
    try:
        payload = package.read(part)
        return ET.fromstring(payload, parser=ET.XMLParser(target=_XmlBuilder()))
    except (KeyError, ET.ParseError) as exc:
        raise ActiveXControlRefusal("control_xml_unavailable:" + part) from exc


def _bytes(root: ET.Element) -> bytes:
    # ElementTree's prefix map is process-global, so another module may have claimed the
    # default prefix; package parts must keep an unprefixed root for native readers.
    for namespace in (REL, CT):
        if root.tag.startswith(f"{{{namespace}}}"):
            ET.register_namespace("", namespace)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _rels(package: Any, part: str) -> ET.Element:
    name = rels_part_for_package_part(part)
    if name not in package.namelist():
        return ET.Element(f"{{{REL}}}Relationships")
    root = _xml(package, name)
    if root.tag != f"{{{REL}}}Relationships":
        raise ActiveXControlRefusal("invalid_relationships")
    return root


def _target(package: Any, part: str, rid: str | None, kind: str) -> str:
    matches = [node for node in _rels(package, part) if node.get("Id") == rid]
    if rid is None or len(matches) != 1:
        raise ActiveXControlRefusal("control_relationship_unavailable")
    rel = matches[0]
    if rel.get("Type") != kind or rel.get("TargetMode", "Internal") != "Internal":
        raise ActiveXControlRefusal("internal_control_relationship_required")
    target = resolve_package_target(part, rel.get("Target", ""))
    if target.startswith("../") or target not in package.namelist():
        raise ActiveXControlRefusal("control_part_unavailable")
    return target


def _string(value: str, label: str) -> str:
    try:
        xml_string(value, label)
    except (TypeError, ValueError) as exc:
        raise ActiveXControlRefusal("invalid_" + label) from exc
    if not value:
        raise ActiveXControlRefusal("empty_" + label)
    return value


def _properties(values: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise ActiveXControlRefusal("string_property_mapping_required")
    result = {}
    for name, value in values.items():
        _string(name, "property_name")
        try:
            xml_string(value, "property_value")
        except (TypeError, ValueError) as exc:
            raise ActiveXControlRefusal("invalid_property_value") from exc
        result[name] = value
    return result


@dataclass(frozen=True)
class _Control:
    rid: str
    name: str
    partname: str
    class_id: str
    persistence: str
    properties: dict[str, str]
    binary_partname: str | None
    xml: bytes


def _inspect(package: Any, slide: str) -> tuple[_Control, ...]:
    root = _xml(package, slide)
    found = []
    seen = set()
    for node in root.findall(f"{{{P}}}cSld/{{{P}}}controls/{{{P}}}control"):
        rid = node.get(f"{{{R}}}id")
        if rid in seen:
            raise ActiveXControlRefusal("duplicate_control_relationship")
        seen.add(rid)
        part = _target(package, slide, rid, CONTROL_TYPE)
        ocx = _xml(package, part)
        if ocx.tag != f"{{{AX}}}ocx":
            raise ActiveXControlRefusal("invalid_control_root")
        persistence = ocx.get(f"{{{AX}}}persistence", "")
        if persistence not in {
            "persistPropertyBag",
            "persistStorage",
            "persistStream",
            "persistStreamInit",
        }:
            raise ActiveXControlRefusal("unsupported_persistence:" + persistence)
        properties = {}
        for prop in ocx.findall(f"{{{AX}}}ocxPr"):
            name = prop.get(f"{{{AX}}}name")
            value = prop.get(f"{{{AX}}}value")
            if name is None or name in properties or value is None:
                raise ActiveXControlRefusal("invalid_control_property")
            properties[name] = value
        binary = None
        if persistence != "persistPropertyBag":
            binary = _target(package, part, ocx.get(f"{{{R}}}id"), BINARY_TYPE)
        found.append(
            _Control(
                rid,
                node.get("name", ""),
                part,
                ocx.get(f"{{{AX}}}classid", ""),
                persistence,
                properties,
                binary,
                package.read(part),
            )
        )
    return tuple(found)


def _incoming(package: Any, target: str) -> Iterator[tuple[str, str | None]]:
    for part in package.namelist():
        if not part.endswith(".rels"):
            continue
        parent, filename = (
            part.rsplit("/_rels/", 1) if "/_rels/" in part else ("", part.removeprefix("_rels/"))
        )
        source = posixpath.join(parent, filename.removesuffix(".rels"))
        for rel in _xml(package, part):
            if (
                rel.get("TargetMode", "Internal") == "Internal"
                and resolve_package_target(source, rel.get("Target", "")) == target
            ):
                yield part, rel.get("Id")


def _signed(package: Any) -> None:
    if any(name.startswith("_xmlsignatures/") for name in package.namelist()):
        raise ActiveXControlRefusal("signed_package_mutation_unsupported")


def _geometry(values: Iterable[int]) -> ActiveXPreviewGeometry:
    values = tuple(values)
    if len(values) != 4 or any(type(value) is not int for value in values):
        raise ActiveXControlRefusal("invalid_preview_geometry")
    if values[2] <= 0 or values[3] <= 0:
        raise ActiveXControlRefusal("invalid_preview_geometry")
    return ActiveXPreviewGeometry(*values)


def _vml_length(value: str) -> int:
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))(pt|in|cm|mm|px)?", value)
    if match is None:
        raise ActiveXControlRefusal("control_preview_mutation_unsupported")
    try:
        number = Decimal(match[1])
        if match[2] is None and number != 0:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        scale = {"pt": 12700, "in": 914400, "cm": 360000, "mm": 36000, "px": 9525}
        return round(number * scale.get(match[2], 1))
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ActiveXControlRefusal("control_preview_mutation_unsupported") from exc


def _vml_style(shape: ET.Element) -> dict[str, str]:
    style = {}
    for declaration in shape.get("style", "").split(";"):
        if not declaration.strip():
            continue
        key, separator, value = declaration.partition(":")
        key = key.strip().casefold()
        if not separator or key in style:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        style[key] = value.strip().casefold()
    if (
        set(style)
        - {"position", "left", "top", "margin-left", "margin-top", "width", "height", "z-index"}
        or style.get("position", "absolute") != "absolute"
    ):
        raise ActiveXControlRefusal("control_preview_mutation_unsupported")
    return style


def _preview_image(package: Any, part: str, rid: str | None) -> str:
    try:
        target = _target(package, part, rid, R + "/image")
    except ActiveXControlRefusal as exc:
        raise ActiveXControlRefusal("control_preview_mutation_unsupported:" + exc.reason) from exc
    if posixpath.splitext(target)[1].casefold() not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
    }:
        raise ActiveXControlRefusal("control_preview_mutation_unsupported")
    return target


def _previews(package: Any, slide: str, root: ET.Element, node: ET.Element) -> list[_Preview]:
    result = []
    if any(child.tag != f"{{{P}}}pic" for child in node):
        raise ActiveXControlRefusal("control_preview_mutation_unsupported")
    pictures = node.findall(f"{{{P}}}pic")
    if len(pictures) > 1:
        raise ActiveXControlRefusal("ambiguous_control_preview")
    if pictures:
        picture = pictures[0]
        transform = picture.find(f"{{{P}}}spPr/{{{A}}}xfrm")
        blip = picture.find(f"{{{P}}}blipFill/{{{A}}}blip")
        if transform is None or blip is None or blip.get(f"{{{R}}}link") is not None:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        if any(value not in {"0", "false"} for value in transform.attrib.values()):
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        offset, extent = transform.find(f"{{{A}}}off"), transform.find(f"{{{A}}}ext")
        if offset is None or extent is None:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        try:
            geometry = _geometry(
                int(value)
                for value in (offset.get("x"), offset.get("y"), extent.get("cx"), extent.get("cy"))
            )
        except (TypeError, ValueError) as exc:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported") from exc
        rid = blip.get(f"{{{R}}}embed")
        image_part = _preview_image(package, slide, rid)
        result.append(_Preview(slide, root, picture, geometry, rid, image_part))
    spid = node.get("spid")
    matches = []
    if spid:
        identifiers = {spid, "_x0000_s" + spid}
        for rel in _rels(package, slide):
            if rel.get("Type") != R + "/vmlDrawing":
                continue
            part = _target(package, slide, rel.get("Id"), R + "/vmlDrawing")
            vroot = _xml(package, part)
            for shape in vroot.iter():
                if shape.tag in {f"{{{V}}}shape", f"{{{V}}}rect"} and (
                    shape.get("id") in identifiers or shape.get(f"{{{OFFICE}}}spid") in identifiers
                ):
                    if shape not in list(vroot):
                        raise ActiveXControlRefusal("control_preview_mutation_unsupported")
                    matches.append((part, vroot, shape, rel.get("Id")))
    if len(matches) > 1:
        raise ActiveXControlRefusal("ambiguous_control_preview")
    for part, vroot, shape, vml_rid in matches:
        images = shape.findall(f"{{{V}}}imagedata")
        if len(images) != 1:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        image = images[0]
        if set(image.attrib) - {
            f"{{{OFFICE}}}relid",
            f"{{{OFFICE}}}title",
            f"{{{R}}}id",
            "title",
            "cropleft",
            "croptop",
            "cropright",
            "cropbottom",
        } or any(
            image.get(key, "0") not in {"0", "0f", "0%"}
            for key in ("cropleft", "croptop", "cropright", "cropbottom")
        ):
            raise ActiveXControlRefusal("control_preview_mutation_unsupported")
        style = _vml_style(shape)
        try:
            geometry = _geometry(
                (
                    _vml_length(style.get("left", "0"))
                    + _vml_length(style.get("margin-left", "0")),
                    _vml_length(style.get("top", "0")) + _vml_length(style.get("margin-top", "0")),
                    _vml_length(style.get("width", "0")),
                    _vml_length(style.get("height", "0")),
                )
            )
        except ActiveXControlRefusal as exc:
            raise ActiveXControlRefusal("control_preview_mutation_unsupported") from exc
        rid = image.get(f"{{{OFFICE}}}relid") or image.get(f"{{{R}}}id")
        result.append(
            _Preview(part, vroot, shape, geometry, rid, _preview_image(package, part, rid), vml_rid)
        )
    if result and any(preview.geometry != result[0].geometry for preview in result[1:]):
        raise ActiveXControlRefusal("inconsistent_control_preview_geometry")
    return result


def _exclusive_preview(package: Any, slide: str, node: ET.Element, preview: _Preview) -> None:
    if preview.vml_rid is None:
        return
    if any(
        reference != (rels_part_for_package_part(slide), preview.vml_rid)
        for reference in _incoming(package, preview.part)
    ):
        raise ActiveXControlRefusal("shared_control_preview_edit_unsupported")
    spid = node.get("spid", "").removeprefix("_x0000_s")
    root = _xml(package, slide)
    for sibling in root.findall(f"{{{P}}}cSld/{{{P}}}controls/{{{P}}}control"):
        if sibling.get(f"{{{R}}}id") != node.get(f"{{{R}}}id") and (
            sibling.get("spid", "").removeprefix("_x0000_s") == spid
        ):
            raise ActiveXControlRefusal("shared_control_preview_edit_unsupported")


def _set_geometry(preview: _Preview, geometry: ActiveXPreviewGeometry) -> None:
    if preview.vml_rid is None:
        transform = preview.shape.find(f"{{{P}}}spPr/{{{A}}}xfrm")
        offset, extent = transform.find(f"{{{A}}}off"), transform.find(f"{{{A}}}ext")
        offset.set("x", str(geometry.left))
        offset.set("y", str(geometry.top))
        extent.set("cx", str(geometry.width))
        extent.set("cy", str(geometry.height))
    else:
        style = _vml_style(preview.shape)
        style.update(
            {
                "left": "0",
                "top": "0",
                "margin-left": f"{Decimal(geometry.left) / 12700}pt",
                "margin-top": f"{Decimal(geometry.top) / 12700}pt",
                "width": f"{Decimal(geometry.width) / 12700}pt",
                "height": f"{Decimal(geometry.height) / 12700}pt",
            }
        )
        preview.shape.set("style", ";".join(f"{key}:{value}" for key, value in style.items()))


class ActiveXControl:
    """Live control handle; payload access never instantiates the control class."""

    def __init__(self, collection: ActiveXControls, rid: str) -> None:
        self._collection = collection
        self._rid = rid

    def _read(self) -> _Control:
        return self._collection._read(self._rid)

    @property
    def name(self) -> str:
        return self._read().name

    @property
    def class_id(self) -> str:
        return self._read().class_id

    @property
    def kind(self) -> ActiveXControlKind:
        """Classify the saved GUID; valid unrecognized classes stay UNKNOWN."""
        try:
            guid = UUID(self.class_id.strip("{}"))
        except (AttributeError, ValueError) as exc:
            raise ActiveXControlRefusal("invalid_control_class_id") from exc
        return _CLASS_KINDS.get(guid, ActiveXControlKind.UNKNOWN)

    @property
    def preview_geometry(self) -> ActiveXPreviewGeometry | None:
        with self._collection._presentation._mutation_lock:
            self._collection._require_saved()
            with open_package_source(self._collection._presentation._source_path) as package:
                _, root, node = self._collection._locate(package, self._rid)
                previews = _previews(package, self._collection._slide, root, node)
                return previews[0].geometry if previews else None

    def _preview_value(self, field: str) -> int:
        geometry = self.preview_geometry
        if geometry is None:
            raise ActiveXControlRefusal("control_preview_unavailable")
        return getattr(geometry, field)

    @property
    def left(self) -> int:
        return self._preview_value("left")

    @left.setter
    def left(self, value: int) -> None:
        self.edit(left=value)

    @property
    def top(self) -> int:
        return self._preview_value("top")

    @top.setter
    def top(self, value: int) -> None:
        self.edit(top=value)

    @property
    def width(self) -> int:
        return self._preview_value("width")

    @width.setter
    def width(self, value: int) -> None:
        self.edit(width=value)

    @property
    def height(self) -> int:
        return self._preview_value("height")

    @height.setter
    def height(self, value: int) -> None:
        self.edit(height=value)

    @property
    def partname(self) -> str:
        return self._read().partname

    @property
    def persistence(self) -> str:
        return self._read().persistence

    @property
    def properties(self) -> dict[str, str]:
        return dict(self._read().properties)

    @property
    def xml(self) -> bytes:
        return self._read().xml

    @property
    def binary_blob(self) -> bytes | None:
        with self._collection._presentation._mutation_lock:
            control = self._read()
            if control.binary_partname is None:
                return None
            with open_package_source(self._collection._presentation._source_path) as package:
                return package.read(control.binary_partname)

    def edit(
        self,
        *,
        name: str | None = None,
        properties: Mapping[str, str] | None = None,
        left: int | None = None,
        top: int | None = None,
        width: int | None = None,
        height: int | None = None,
        remove_properties: Iterable[str] = (),
        clear_properties: bool = False,
    ) -> None:
        """Atomically rename, edit preview EMUs, or clear/remove/merge XML properties.

        Property operations apply clear, removal, then merge. Missing removal names
        and simultaneous removal/update of the same name are refused. Geometry
        edits synchronize inline and VML previews without touching image or binary
        payloads. No preview geometry is invented for nonvisual controls.
        """
        new_name = None if name is None else _string(name, "control_name")
        updates = {} if properties is None else _properties(properties)
        if type(clear_properties) is not bool or isinstance(remove_properties, (str, bytes)):
            raise ActiveXControlRefusal("invalid_property_removal")
        try:
            removals = tuple(_string(key, "property_name") for key in remove_properties)
        except TypeError as exc:
            raise ActiveXControlRefusal("invalid_property_removal") from exc
        if len(set(removals)) != len(removals) or set(removals) & updates.keys():
            raise ActiveXControlRefusal("conflicting_property_edit")
        geometry_updates = (left, top, width, height)
        for index, value in enumerate(geometry_updates):
            if value is not None and (type(value) is not int or (index >= 2 and value <= 0)):
                raise ActiveXControlRefusal("invalid_preview_geometry")

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            control, slide_root, node = self._collection._locate(package, self._rid)
            _signed(package)
            previews = _previews(package, self._collection._slide, slide_root, node)
            replacements = {}
            if new_name is not None:
                if any(
                    c.name == new_name and c.rid != self._rid
                    for c in _inspect(package, self._collection._slide)
                ):
                    raise ActiveXControlRefusal("duplicate_control_name")
                node.set("name", new_name)
                replacements[self._collection._slide] = _bytes(slide_root)
            if any(value is not None for value in geometry_updates):
                if not previews:
                    raise ActiveXControlRefusal("control_preview_unavailable")
                old = previews[0].geometry
                geometry = _geometry(
                    previous if value is None else value
                    for value, previous in zip(
                        geometry_updates, (old.left, old.top, old.width, old.height), strict=True
                    )
                )
                for preview in previews:
                    _exclusive_preview(package, self._collection._slide, node, preview)
                    _set_geometry(preview, geometry)
                    replacements[preview.part] = _bytes(preview.root)
            if updates or removals or clear_properties:
                if control.persistence != "persistPropertyBag":
                    raise ActiveXControlRefusal("binary_property_edit_unsupported")
                own_reference = (rels_part_for_package_part(self._collection._slide), self._rid)
                if any(
                    reference != own_reference for reference in _incoming(package, control.partname)
                ):
                    raise ActiveXControlRefusal("shared_control_property_edit_unsupported")
                ocx = _xml(package, control.partname)
                for prop in ocx:
                    if prop.tag != f"{{{AX}}}ocxPr" or len(prop):
                        raise ActiveXControlRefusal("complex_property_edit_unsupported")
                existing = {prop.get(f"{{{AX}}}name"): prop for prop in ocx}
                if any(key not in existing for key in removals):
                    raise ActiveXControlRefusal("control_property_unavailable")
                for key, prop in list(existing.items()):
                    if clear_properties or key in removals:
                        ocx.remove(prop)
                        del existing[key]
                for key, value in updates.items():
                    prop = existing.get(key)
                    if prop is None:
                        prop = ET.SubElement(ocx, f"{{{AX}}}ocxPr", {f"{{{AX}}}name": key})
                    prop.set(f"{{{AX}}}value", value)
                replacements[control.partname] = _bytes(ocx)
            return replacements, set(), None

        self._collection._mutate(plan)

    def remove_property(self, name: str) -> None:
        """Remove one existing scalar XML property."""
        self.edit(remove_properties=(name,))

    def clear_properties(self) -> None:
        """Clear scalar XML properties while preserving class and package dependencies."""
        self.edit(clear_properties=True)

    def remove(self) -> None:
        self._collection.remove(self)


class ActiveXControls:
    """Slide-scoped collection over a saved Presentation. Indexes follow slide XML order."""

    def __init__(self, presentation: Any, slide_index: int) -> None:
        self._presentation = presentation
        with presentation._mutation_lock:
            self._require_saved()
            self._slide = presentation.slides[slide_index].partname.lstrip("/")
            retired = getattr(presentation, "_activex_retired_relationships", None)
            if retired is None:
                retired = {}
                presentation._activex_retired_relationships = retired
            self._retired = retired

    def _require_saved(self) -> None:
        try:
            self._presentation._require_saved_package("editing ActiveX controls")
        except ValueError as exc:
            raise ActiveXControlRefusal("save_pending_edits_first") from exc

    def _read(self, rid: str) -> _Control:
        with self._presentation._mutation_lock:
            self._require_saved()
            with open_package_source(self._presentation._source_path) as package:
                for control in _inspect(package, self._slide):
                    if control.rid == rid:
                        return control
        raise ActiveXControlRefusal("control_handle_unavailable")

    def __iter__(self) -> Iterator[ActiveXControl]:
        with self._presentation._mutation_lock:
            self._require_saved()
            with open_package_source(self._presentation._source_path) as package:
                rids = [c.rid for c in _inspect(package, self._slide)]
        return iter(ActiveXControl(self, rid) for rid in rids)

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __getitem__(self, index: int) -> ActiveXControl:
        return tuple(self)[index]

    def _locate(self, package: Any, rid: str) -> tuple[_Control, ET.Element, ET.Element]:
        control = next((c for c in _inspect(package, self._slide) if c.rid == rid), None)
        if control is None:
            raise ActiveXControlRefusal("control_handle_unavailable")
        root = _xml(package, self._slide)
        node = next(
            n
            for n in root.findall(f"{{{P}}}cSld/{{{P}}}controls/{{{P}}}control")
            if n.get(f"{{{R}}}id") == rid
        )
        return control, root, node

    def _mutate(self, plan: Any) -> Any:
        with self._presentation._mutation_lock:
            self._require_saved()
            return self._presentation._rewrite_package("editing ActiveX controls", plan)

    def add(
        self,
        name: str,
        class_id: str,
        *,
        properties: Mapping[str, str],
        persistence: str = "persistPropertyBag",
    ) -> ActiveXControl:
        """Add a nonvisual XML-persisted control. No class code is loaded or executed."""
        if persistence != "persistPropertyBag":
            raise ActiveXControlRefusal("binary_control_authoring_unsupported")
        name = _string(name, "control_name")
        try:
            class_id = "{" + str(UUID(class_id.strip("{}"))).upper() + "}"
        except (AttributeError, ValueError) as exc:
            raise ActiveXControlRefusal("invalid_control_class_id") from exc
        values = _properties(properties)

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], str]:
            if any(c.name == name for c in _inspect(package, self._slide)):
                raise ActiveXControlRefusal("duplicate_control_name")
            root = _xml(package, self._slide)
            _signed(package)
            cslide = root.find(f"{{{P}}}cSld")
            if cslide is None:
                raise ActiveXControlRefusal("slide_content_unavailable")
            controls = cslide.find(f"{{{P}}}controls")
            if controls is None:
                controls = ET.Element(f"{{{P}}}controls")
                # cSld order: spTree, custDataLst, controls, extLst.
                position = next(
                    (i for i, child in enumerate(cslide) if child.tag == f"{{{P}}}extLst"),
                    len(cslide),
                )
                cslide.insert(position, controls)
            rels = _rels(package, self._slide)
            used = {rel.get("Id") for rel in rels} | self._retired.get(self._slide, set())
            number = 1
            while f"rId{number}" in used:
                number += 1
            rid = f"rId{number}"
            number = 1
            names = set(package.namelist())
            while f"ppt/activeX/activeX{number}.xml" in names:
                number += 1
            part = f"ppt/activeX/activeX{number}.xml"
            ET.SubElement(controls, f"{{{P}}}control", {"name": name, f"{{{R}}}id": rid})
            ET.SubElement(
                rels,
                f"{{{REL}}}Relationship",
                {
                    "Id": rid,
                    "Type": CONTROL_TYPE,
                    "Target": posixpath.relpath(part, posixpath.dirname(self._slide)),
                },
            )
            ocx = ET.Element(
                f"{{{AX}}}ocx",
                {f"{{{AX}}}classid": class_id, f"{{{AX}}}persistence": "persistPropertyBag"},
            )
            for key, value in values.items():
                ET.SubElement(
                    ocx, f"{{{AX}}}ocxPr", {f"{{{AX}}}name": key, f"{{{AX}}}value": value}
                )
            types = _xml(package, "[Content_Types].xml")
            ET.SubElement(
                types, f"{{{CT}}}Override", {"PartName": "/" + part, "ContentType": CONTROL_CT}
            )
            return (
                {
                    self._slide: _bytes(root),
                    rels_part_for_package_part(self._slide): _bytes(rels),
                    part: _bytes(ocx),
                    "[Content_Types].xml": _bytes(types),
                },
                set(),
                rid,
            )

        return ActiveXControl(self, self._mutate(plan))

    def remove(self, control: ActiveXControl) -> None:
        """Remove an unshared control and only its exclusively owned preview resources."""
        if not isinstance(control, ActiveXControl) or control._collection is not self:
            raise ActiveXControlRefusal("foreign_control_handle")

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            item, root, node = self._locate(package, control._rid)
            _signed(package)
            previews = _previews(package, self._slide, root, node)
            for preview in previews:
                _exclusive_preview(package, self._slide, node, preview)
            owned = {item.partname, rels_part_for_package_part(item.partname)}
            if item.binary_partname:
                owned.add(item.binary_partname)
            for rel in _rels(package, item.partname):
                if (
                    rel.get("Type") != BINARY_TYPE
                    or rel.get("TargetMode", "Internal") != "Internal"
                    or resolve_package_target(item.partname, rel.get("Target", ""))
                    != item.binary_partname
                ):
                    raise ActiveXControlRefusal("control_dependency_removal_unsupported")
            slide_rels = rels_part_for_package_part(self._slide)
            # Refuse shared references rather than deleting another owner's data.
            for part in package.namelist():
                if not part.endswith(".rels") or part in owned:
                    continue
                parent, filename = (
                    part.rsplit("/_rels/", 1)
                    if "/_rels/" in part
                    else ("", part.removeprefix("_rels/"))
                )
                source = posixpath.join(parent, filename.removesuffix(".rels"))
                for rel in _xml(package, part):
                    if rel.get("TargetMode", "Internal") != "Internal":
                        continue
                    target = resolve_package_target(source, rel.get("Target", ""))
                    if target in owned and not (part == slide_rels and rel.get("Id") == item.rid):
                        raise ActiveXControlRefusal("shared_control_part_removal_unsupported")
            controls = root.find(f"{{{P}}}cSld/{{{P}}}controls")
            controls.remove(node)
            if not len(controls):
                root.find(f"{{{P}}}cSld").remove(controls)
            rels = _rels(package, self._slide)
            rels.remove(next(rel for rel in rels if rel.get("Id") == item.rid))
            replacements = {}
            removed_references = set()
            reference_attributes = {
                f"{{{R}}}id",
                f"{{{R}}}embed",
                f"{{{R}}}link",
                f"{{{OFFICE}}}relid",
            }
            for preview in previews:
                if preview.vml_rid is None:
                    owner_root, owner_rels = root, rels
                else:
                    owner_root = preview.root
                    owner_root.remove(preview.shape)
                    owner_rels = _rels(package, preview.part)
                    if len(owner_root):
                        replacements[preview.part] = _bytes(owner_root)
                    else:
                        owned.update({preview.part, rels_part_for_package_part(preview.part)})
                        rels.remove(next(rel for rel in rels if rel.get("Id") == preview.vml_rid))
                # A fallback can share its image relationship with an ordinary shape.
                if not any(
                    element.get(attribute) == preview.image_rid
                    for element in owner_root.iter()
                    for attribute in reference_attributes
                ):
                    owner_rels.remove(
                        next(rel for rel in owner_rels if rel.get("Id") == preview.image_rid)
                    )
                    owner_rels_part = rels_part_for_package_part(preview.part)
                    removed_references.add((owner_rels_part, preview.image_rid))
                    if preview.vml_rid is not None and preview.part not in owned:
                        replacements[owner_rels_part] = _bytes(owner_rels)
            for image_part in {preview.image_part for preview in previews}:
                # Keep images with their own dependency graph rather than guessing ownership.
                if rels_part_for_package_part(image_part) in package.namelist():
                    continue
                if all(
                    part in owned or (part, rid) in removed_references
                    for part, rid in _incoming(package, image_part)
                ):
                    owned.add(image_part)
            types = _xml(package, "[Content_Types].xml")
            for override in list(types):
                if override.get("PartName", "").lstrip("/") in owned:
                    types.remove(override)
            return (
                replacements
                | {
                    self._slide: _bytes(root),
                    slide_rels: _bytes(rels),
                    "[Content_Types].xml": _bytes(types),
                },
                owned,
                None,
            )

        with self._presentation._mutation_lock:
            self._mutate(plan)
            self._retired.setdefault(self._slide, set()).add(control._rid)
