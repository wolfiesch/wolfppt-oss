"""Zoom frames through ``slide.shapes`` and byte-preserving package transactions.

Use ``add_slide_zoom(target, left, top, width, height, image_file)`` or
``add_section_zoom`` on a slide's shapes. Use ``add_summary_zoom(targets, left,
top, width, height, images)`` for an ordered row of section thumbnails. Read and
edit ``shape.zoom``; edit summary objects through ``shape.zoom.sections``.
Durations are milliseconds; None means destination timing. ``preview`` uses the
destination slide, ``cover`` uses the supplied custom image. Save and reopen as
with any other shape edit. Summary sections support add, remove and move.

``read_zoom_frame`` and ``apply_zoom_frame_edit`` also expose saved-package
inspection and atomic metadata transactions, independent of queued edits.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree as ET
from xml.parsers import expat

from .image_inputs import InMemoryImage, image_extension_from_blob, image_input_bytes
from .package_parts import copy_package_with_replacements
from .shape_xml import MC_NS, P166_NS, PSEZ_NS, PSLZ_NS
from .slide_zoom_targets import presentation_slide_parts

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PSUZ_NS = "http://schemas.microsoft.com/office/powerpoint/2016/summaryzoom"
_KINDS = {
    "slide": (PSLZ_NS, "sldZm", "sldZmObj", "sldId"),
    "section": (PSEZ_NS, "sectionZm", "sectionZmObj", "sectionId"),
    "summary": (PSUZ_NS, "summaryZm", "summaryZmObj", "sectionId"),
}
_TIME = re.compile(r"([0-9]+(?:\.[0-9]+)?)(h|min|s|ms|µs|ns)?\Z")
_TIME_FACTORS = {
    None: Decimal(1),
    "ms": Decimal(1),
    "s": Decimal(1000),
    "min": Decimal(60000),
    "h": Decimal(3600000),
    "µs": Decimal("0.001"),
    "ns": Decimal("0.000001"),
}
_START_TAG = re.compile(rb"""<(?:[^>"']|"[^"]*"|'[^']*')*>""")
_UNCHANGED = object()


class ZoomFrameRefusal(ValueError):
    """Unsupported or malformed zoom metadata; no output is written."""


@dataclass(frozen=True)
class ZoomObject:
    """One slide/section destination; summary frames contain ordered objects."""

    target: str
    title: str
    description: str
    image_type: str
    return_to_parent: bool
    transition_duration: Decimal | None
    show_background: bool


@dataclass(frozen=True)
class ZoomFrame:
    kind: str
    objects: tuple[ZoomObject, ...]
    layout: str | None

    @property
    def sections(self) -> tuple[str, ...]:
        """Section GUIDs in summary or section zoom document order."""
        return () if self.kind == "slide" else tuple(obj.target for obj in self.objects)


def _boolean(raw: str | None, name: str) -> bool:
    if raw is None:
        return True
    if raw in {"1", "true"}:
        return True
    if raw in {"0", "false"}:
        return False
    raise ZoomFrameRefusal(f"{name} is not an XML boolean: {raw!r}")


def _duration(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    match = _TIME.fullmatch(raw)
    if match is None:
        raise ZoomFrameRefusal(f"transition duration is not a time offset: {raw!r}")
    return Decimal(match[1]) * _TIME_FACTORS[match[2]]


def _parse(payload: bytes) -> tuple[ET.Element, dict[int, tuple[int, int]]]:
    # Byte offsets allow attribute-only edits without serializing unrelated XML,
    # dropping unused mc:Requires prefixes, or rewriting opaque extensions.
    starts: list[tuple[int, int]] = []
    parser = expat.ParserCreate()

    def refuse_doctype(*_args: Any) -> None:
        raise ZoomFrameRefusal("zoom metadata does not admit a DTD")

    def start(_name: str, _attributes: dict[str, str]) -> None:
        match = _START_TAG.match(payload, parser.CurrentByteIndex)
        if match is None:
            raise ZoomFrameRefusal("zoom metadata editing requires UTF-8 XML")
        starts.append(match.span())

    parser.StartDoctypeDeclHandler = refuse_doctype
    parser.StartElementHandler = start
    try:
        parser.Parse(payload, True)
        root = ET.fromstring(payload)
    except (expat.ExpatError, ET.ParseError) as error:
        raise ZoomFrameRefusal(f"malformed zoom slide XML: {error}") from error
    nodes = list(root.iter())
    if len(nodes) != len(starts):
        raise ZoomFrameRefusal("ambiguous zoom XML element offsets")
    return root, {id(node): span for node, span in zip(nodes, starts, strict=True)}


def _select(root: ET.Element, shape_id: int) -> tuple[str, ET.Element, list[ET.Element]]:
    candidates = []
    for alternate in root.iter(f"{{{MC_NS}}}AlternateContent"):
        choice = alternate.find(f"{{{MC_NS}}}Choice")
        if choice is None:
            continue
        frame = choice.find(f"{{{P_NS}}}graphicFrame")
        if frame is None:
            continue
        identity = frame.find(f"{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr")
        if identity is None or identity.get("id") != str(shape_id):
            continue
        for kind, (ns, container, object_tag, _target) in _KINDS.items():
            zoom = frame.find(f".//{{{ns}}}{container}")
            if zoom is not None:
                candidates.append((kind, zoom, zoom.findall(f"{{{ns}}}{object_tag}")))
    if len(candidates) != 1:
        raise ZoomFrameRefusal(f"shape id {shape_id} must identify exactly one saved zoom frame")
    return candidates[0]


def _properties(kind: str, node: ET.Element) -> ET.Element:
    ns = _KINDS[kind][0]
    properties = [child for child in node if child.tag in {f"{{{ns}}}zmPr", f"{{{P166_NS}}}zmPr"}]
    if len(properties) != 1:
        raise ZoomFrameRefusal("zoom object must have exactly one properties element")
    return properties[0]


def _read(kind: str, container: ET.Element, nodes: list[ET.Element]) -> ZoomFrame:
    if kind != "summary" and len(nodes) != 1:
        raise ZoomFrameRefusal(f"{kind} zoom must have exactly one destination")
    objects = []
    for node in nodes:
        target = node.get(_KINDS[kind][3])
        if not target:
            raise ZoomFrameRefusal("zoom destination is missing")
        properties = _properties(kind, node)
        image_type = properties.get("imageType", "preview")
        if image_type not in {"preview", "cover"}:
            raise ZoomFrameRefusal(f"unsupported zoom image type: {image_type!r}")
        objects.append(
            ZoomObject(
                target,
                node.get("title", ""),
                node.get("descr", ""),
                image_type,
                _boolean(properties.get("returnToParent"), "returnToParent"),
                _duration(properties.get("transitionDur")),
                _boolean(properties.get("showBg"), "showBg"),
            )
        )
    layout = None
    if kind == "summary":
        layouts = [
            child.tag
            for child in container
            if child.tag
            in {
                f"{{{PSUZ_NS}}}gridLayout",
                f"{{{PSUZ_NS}}}fixedLayout",
            }
        ]
        if len(layouts) != 1:
            raise ZoomFrameRefusal("summary zoom requires exactly one grid or fixed layout")
        layout = layouts[0].split("}")[-1].removesuffix("Layout")
    return ZoomFrame(kind, tuple(objects), layout)


def read_zoom_frame(shape: Any) -> ZoomFrame:
    """Inspect a saved Shape from the public shape tree, including grouped zooms.

    The result reflects saved bytes, not queued edits. Refuse non-zoom shapes.
    """
    if getattr(shape, "shape_id", None) is None:
        raise ZoomFrameRefusal("zoom inspection requires a saved shape id")
    root, _spans = _parse(shape.part.blob)
    return _read(*_select(root, shape.shape_id))


def _attribute(tag: bytes, name: str, value: str | None) -> bytes:
    # Match whole attributes so a lookalike inside another quoted value is opaque.
    pattern = re.compile(rb"""\s+([A-Za-z_][\w.:-]*)\s*=\s*(?:"[^"]*"|'[^']*')""")
    matches = [match for match in pattern.finditer(tag) if match[1] == name.encode()]
    if len(matches) > 1:
        raise ZoomFrameRefusal(f"duplicate zoom attribute {name}")
    replacement = b"" if value is None else f' {name}="{value}"'.encode()
    if matches:
        match = matches[0]
        return tag[: match.start()] + replacement + tag[match.end() :]
    if value is None:
        return tag
    end = -2 if tag.endswith(b"/>") else -1
    return tag[:end] + replacement + tag[end:]


def apply_zoom_frame_edit(
    input_path: str | Path,
    output_path: str | Path,
    *,
    slide_index: int,
    shape_id: int,
    object_index: int = 0,
    transition_duration: Any = _UNCHANGED,
    return_to_parent: Any = _UNCHANGED,
    image_type: Any = _UNCHANGED,
    show_background: Any = _UNCHANGED,
) -> None:
    """Atomically edit saved zoom metadata, retaining all other bytes.

    ``object_index`` selects a summary section in document order. Supply None
    for destination-derived timing, or finite nonnegative milliseconds. With one
    fallback picture per object, render ``preview`` from its destination and
    ``cover`` from its custom image. Composite summary caches remain preserved.
    """
    for name, value in (
        ("slide_index", slide_index),
        ("shape_id", shape_id),
        ("object_index", object_index),
    ):
        if type(value) is not int or value < 0:
            raise ZoomFrameRefusal(f"{name} must be a nonnegative integer")
    changes: dict[str, str | None] = {}
    for name, value in (("returnToParent", return_to_parent), ("showBg", show_background)):
        if value is not _UNCHANGED:
            if type(value) is not bool:
                raise ZoomFrameRefusal(f"{name} must be a bool")
            changes[name] = "1" if value else "0"
    if image_type is not _UNCHANGED:
        if not isinstance(image_type, str) or image_type not in {"preview", "cover"}:
            raise ZoomFrameRefusal("image_type must be preview or cover")
        changes["imageType"] = image_type
    if transition_duration is not _UNCHANGED:
        value = transition_duration
        if value is None:
            changes["transitionDur"] = None
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ZoomFrameRefusal(
                    "transition duration must be finite nonnegative milliseconds"
                )
            number = Decimal(str(value))
            if not number.is_finite() or number < 0:
                raise ZoomFrameRefusal(
                    "transition duration must be finite nonnegative milliseconds"
                )
            changes["transitionDur"] = format(number, "f")
    with zipfile.ZipFile(input_path) as package:
        presentation = ET.fromstring(package.read("ppt/presentation.xml"))
        parts = list(presentation_slide_parts(package, presentation).values())
        if slide_index >= len(parts):
            raise ZoomFrameRefusal("zoom slide index is out of range")
        part = parts[slide_index]
        payload = package.read(part)
        root, spans = _parse(payload)
        kind, container, nodes = _select(root, shape_id)
        _read(kind, container, nodes)
        if object_index >= len(nodes):
            raise ZoomFrameRefusal("zoom object index is out of range")
        properties = _properties(kind, nodes[object_index])
        start, end = spans[id(properties)]
        tag = payload[start:end]
        for name, value in changes.items():
            tag = _attribute(tag, name, value)
        updated = payload[:start] + tag + payload[end:]
        updated_root, _ = _parse(updated)
        _read(*_select(updated_root, shape_id))
    copy_package_with_replacements(Path(input_path), Path(output_path), {part: updated})


def _metadata_value(name: str, value: Any) -> Any:
    if name in {"return_to_parent", "show_background"}:
        if type(value) is not bool:
            raise ZoomFrameRefusal(f"{name} must be a bool")
    elif name == "image_type":
        if value not in ("preview", "cover"):
            raise ZoomFrameRefusal("image_type must be preview or cover")
    elif name == "transition_duration":
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ZoomFrameRefusal(
                    "transition duration must be finite nonnegative milliseconds"
                )
            value = Decimal(str(value))
            if not value.is_finite() or value < 0:
                raise ZoomFrameRefusal(
                    "transition duration must be finite nonnegative milliseconds"
                )
    elif name in {"title", "description"} and (
        not isinstance(value, str)
        or any(
            not (
                char in "\t\n\r"
                or 0x20 <= ord(char) <= 0xD7FF
                or 0xE000 <= ord(char) <= 0xFFFD
                or 0x10000 <= ord(char) <= 0x10FFFF
            )
            for char in value
        )
    ):
        raise ZoomFrameRefusal(f"{name} must be XML text")
    return value


def _image_source(image: Any) -> InMemoryImage:
    try:
        blob = image_input_bytes(image)
        image_extension_from_blob(blob)
        # Admit actual decoded pixels, not just a format signature.
        import io

        from PIL import Image

        with Image.open(io.BytesIO(blob)) as decoded:
            decoded.verify()
        return InMemoryImage(blob)
    except (OSError, ValueError, TypeError) as error:
        raise ZoomFrameRefusal(f"zoom image is unsupported: {error}") from error


def _target(shape: Any, kind: str, value: Any) -> str:
    presentation = shape._slide._presentation
    if kind == "slide":
        slides = list(presentation.slides)
        if type(value) is int:
            if not 0 <= value < len(slides):
                raise ZoomFrameRefusal("slide zoom target index is out of range")
            value = slides[value]
        if not any(slide is value for slide in slides):
            raise ZoomFrameRefusal("slide zoom target must belong to this presentation")
        return str(value.slide_id)
    identifier = getattr(value, "id", value)
    if not isinstance(identifier, str):
        raise ZoomFrameRefusal("section zoom target must be a section id or Section")
    section = next(
        (section for section in presentation.sections if section.id.upper() == identifier.upper()),
        None,
    )
    if section is None:
        raise ZoomFrameRefusal(f"section {identifier!r} does not exist")
    if hasattr(value, "_collection") and value._collection._presentation is not presentation:
        raise ZoomFrameRefusal("section zoom target must belong to this presentation")
    if not section.slides:
        raise ZoomFrameRefusal(f"section {identifier!r} has no slides to zoom to")
    return section.id


def _state(shape: Any) -> dict[str, Any]:
    queued = getattr(shape._slide._presentation, "_zoom_edits", {})
    if shape in queued:
        return queued[shape]
    root, _ = _parse(shape.part.blob)
    kind, container, nodes = _select(root, shape.shape_id)
    frame = _read(kind, container, nodes)
    identities = [_properties(kind, node).get("id") for node in nodes]
    if (
        not identities
        or any(not identifier for identifier in identities)
        or len(set(identities)) != len(identities)
    ):
        raise ZoomFrameRefusal("zoom destinations require unique persistent identities")
    return {
        "kind": kind,
        "new": False,
        "rebuild": False,
        "objects": [
            {
                "id": _properties(kind, node).get("id"),
                **vars(obj),
            }
            for node, obj in zip(nodes, frame.objects, strict=True)
        ],
        "layout": frame.layout,
    }


def _copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "objects": [dict(obj) for obj in state["objects"]]}


def _queue(shape: Any, state: dict[str, Any]) -> None:
    if shape._payload.get("_deleted"):
        raise ZoomFrameRefusal("cannot edit a deleted zoom frame")
    if not state["objects"] or len({obj["target"] for obj in state["objects"]}) != len(
        state["objects"]
    ):
        raise ZoomFrameRefusal("summary section destinations must be nonempty and unique")
    if state["kind"] == "summary" and shape.width < len(state["objects"]):
        raise ZoomFrameRefusal("summary width must provide positive extent for every section")
    shape._slide._presentation._queue_zoom_edit(shape, state)


class ZoomObjectEditor:
    """One persistent zoom destination, including one summary section."""

    def __init__(self, shape: Any, object_id: str) -> None:
        self._shape = shape
        self._object_id = object_id

    def _object(self, state: dict[str, Any]) -> dict[str, Any]:
        matches = [obj for obj in state["objects"] if obj["id"] == self._object_id]
        if len(matches) != 1:
            raise ZoomFrameRefusal("zoom destination was removed or has an ambiguous identity")
        return matches[0]

    def _get(self, name: str) -> Any:
        return self._object(_state(self._shape))[name]

    def _set(self, name: str, value: Any) -> None:
        state = _copy_state(_state(self._shape))
        obj = self._object(state)
        obj[name] = (
            _target(self._shape, state["kind"], value)
            if name == "target"
            else _metadata_value(name, value)
        )
        _queue(self._shape, state)

    @property
    def target(self) -> str:
        """Persistent slide id or section GUID. Assign a Slide/index or Section/GUID."""
        return self._get("target")

    @target.setter
    def target(self, value: Any) -> None:
        self._set("target", value)

    @property
    def transition_duration(self) -> Decimal | None:
        return self._get("transition_duration")

    @transition_duration.setter
    def transition_duration(self, value: Any) -> None:
        self._set("transition_duration", value)

    @property
    def image_type(self) -> str:
        return self._get("image_type")

    @image_type.setter
    def image_type(self, value: str) -> None:
        self._set("image_type", value)

    @property
    def return_to_parent(self) -> bool:
        return self._get("return_to_parent")

    @return_to_parent.setter
    def return_to_parent(self, value: bool) -> None:
        self._set("return_to_parent", value)

    @property
    def show_background(self) -> bool:
        return self._get("show_background")

    @show_background.setter
    def show_background(self, value: bool) -> None:
        self._set("show_background", value)

    @property
    def title(self) -> str:
        return self._get("title")

    @title.setter
    def title(self, value: str) -> None:
        self._set("title", value)

    @property
    def description(self) -> str:
        return self._get("description")

    @description.setter
    def description(self, value: str) -> None:
        self._set("description", value)

    def replace_image(self, image_file: Any) -> None:
        """Replace the custom image without overwriting a shared media part."""
        image = _image_source(image_file)
        state = _copy_state(_state(self._shape))
        self._object(state)["image"] = image
        _queue(self._shape, state)


class SummaryZoomSections(Sequence[ZoomObjectEditor]):
    """Ordered summary destinations. Held entries retain their identity after moves."""

    def __init__(self, shape: Any) -> None:
        self._shape = shape

    def __len__(self) -> int:
        return len(_state(self._shape)["objects"])

    def __getitem__(self, index: int | slice) -> Any:
        objects = _state(self._shape)["objects"]
        if isinstance(index, slice):
            return [ZoomObjectEditor(self._shape, obj["id"]) for obj in objects[index]]
        return ZoomObjectEditor(self._shape, objects[index]["id"])

    def __iter__(self) -> Iterator[ZoomObjectEditor]:
        return iter(self[:])

    def add(
        self, target: Any, image_file: Any, *, title: str = "", description: str = ""
    ) -> ZoomObjectEditor:
        state = _copy_state(_state(self._shape))
        obj = _new_object(self._shape, "summary", target, image_file)
        obj["title"] = _metadata_value("title", title)
        obj["description"] = _metadata_value("description", description)
        if any(existing["target"] == obj["target"] for existing in state["objects"]):
            raise ZoomFrameRefusal("summary section destinations must be unique")
        state["objects"].append(obj)
        state["rebuild"] = True
        _queue(self._shape, state)
        return ZoomObjectEditor(self._shape, obj["id"])

    def remove(self, section: ZoomObjectEditor) -> None:
        state = _copy_state(_state(self._shape))
        if section._shape is not self._shape:
            raise ZoomFrameRefusal("summary destination belongs to a different zoom")
        obj = section._object(state)
        if len(state["objects"]) == 1:
            raise ZoomFrameRefusal("summary zoom requires at least one section")
        state["objects"].remove(obj)
        state["rebuild"] = True
        _queue(self._shape, state)

    def move(self, section: ZoomObjectEditor, index: int) -> None:
        state = _copy_state(_state(self._shape))
        if type(index) is not int or not 0 <= index < len(state["objects"]):
            raise ZoomFrameRefusal("summary section position is out of range")
        if section._shape is not self._shape:
            raise ZoomFrameRefusal("summary destination belongs to a different zoom")
        obj = section._object(state)
        state["objects"].remove(obj)
        state["objects"].insert(index, obj)
        state["rebuild"] = True
        _queue(self._shape, state)


class ZoomEditor(ZoomObjectEditor):
    """Shape-tree zoom editor. For a summary, edit each entry in ``sections``."""

    def __init__(self, shape: Any) -> None:
        state = _state(shape)
        super().__init__(shape, state["objects"][0]["id"] if state["objects"] else "")

    def _object(self, state: dict[str, Any]) -> dict[str, Any]:
        if state["kind"] == "summary":
            raise ZoomFrameRefusal("edit summary zoom properties through its sections")
        return super()._object(state)

    @property
    def kind(self) -> str:
        return _state(self._shape)["kind"]

    @property
    def objects(self) -> tuple[ZoomObject, ...]:
        return tuple(
            ZoomObject(**{key: obj[key] for key in ZoomObject.__dataclass_fields__})
            for obj in _state(self._shape)["objects"]
        )

    @property
    def sections(self) -> SummaryZoomSections:
        if self.kind != "summary":
            raise ZoomFrameRefusal("only summary zoom frames have editable sections")
        return SummaryZoomSections(self._shape)


def _new_object(shape: Any, kind: str, target: Any, image: Any, **options: Any) -> dict[str, Any]:
    return {
        "id": "{" + str(uuid4()).upper() + "}",
        "target": _target(shape, kind, target),
        "image": _image_source(image),
        **{
            name: _metadata_value(name, value)
            for name, value in {
                "title": "",
                "description": "",
                "image_type": "preview",
                "return_to_parent": True,
                "transition_duration": None,
                "show_background": True,
                **options,
            }.items()
        },
    }


def add_zoom_shape(
    collection: Any,
    kind: str,
    targets: Sequence[Any],
    images: Sequence[Any],
    left: Any,
    top: Any,
    width: Any,
    height: Any,
    **options: Any,
) -> Any:
    """Shared implementation for the public shape collection methods."""
    from .shape_core_facade import Shape
    from .shape_inspection import _next_shape_id

    dimensions = (left, top, width, height)
    for name, value in zip(("left", "top", "width", "height"), dimensions, strict=True):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < (1 if name in {"width", "height"} else 0)
        ):
            constraint = "positive" if name in {"width", "height"} else "nonnegative"
            raise ZoomFrameRefusal(f"zoom {name} must be a {constraint} integer")
    if not targets or len(targets) != len(images):
        raise ZoomFrameRefusal("each zoom destination requires exactly one image")
    shape_id = _next_shape_id(collection._shapes)
    shape = Shape(
        collection._slide,
        len(collection),
        {
            "id": str(shape_id),
            "_pending_shape": True,
            "name": f"{kind.title()} Zoom {shape_id - 1}",
            "kind": "group" if kind == "summary" else "picture",
            "text": "",
            "paragraphs": [],
            "transform": dict(zip(("x", "y", "cx", "cy"), dimensions, strict=True)),
        },
    )
    objects = [
        _new_object(shape, kind, target, image, **options)
        for target, image in zip(targets, images, strict=True)
    ]
    if len({obj["target"] for obj in objects}) != len(objects):
        raise ZoomFrameRefusal("summary section destinations must be unique")
    _queue(
        shape,
        {
            "kind": kind,
            "new": True,
            "rebuild": True,
            "layout": "fixed" if kind == "summary" else None,
            "objects": objects,
        },
    )
    collection._shapes.append(shape)
    return shape


def validate_queued_zoom_edits(presentation: Any) -> None:
    """Refuse stale/deleted destinations before save creates any output or staging."""
    for shape, state in getattr(presentation, "_zoom_edits", {}).items():
        if shape._payload.get("_deleted") or not any(
            slide is shape._slide for slide in presentation.slides
        ):
            raise ZoomFrameRefusal("zoom owner no longer belongs to this presentation")
        if not state["objects"]:
            raise ZoomFrameRefusal("summary zoom requires at least one section")
        for obj in state["objects"]:
            if state["kind"] == "slide":
                if not any(str(slide.slide_id) == obj["target"] for slide in presentation.slides):
                    raise ZoomFrameRefusal("slide zoom destination was deleted")
            else:
                _target(shape, state["kind"], obj["target"])
        if not state["new"] and state["rebuild"]:
            if getattr(shape, "_group_shapes", None) is not None:
                raise ZoomFrameRefusal(
                    "summary layout editing requires unexpanded fallback children; reopen the deck"
                )
            root, _ = _parse(shape.part.blob)
            kind, container, nodes = _select(root, shape.shape_id)
            # Unknown extensions may carry semantic state. Never silently drop them
            # when regenerating section layout and fallbacks.
            if any(node.tag.rsplit("}", 1)[-1] == "extLst" for node in container.iter()):
                raise ZoomFrameRefusal(
                    "summary layout editing cannot preserve opaque zoom extensions"
                )


def _full_span(payload: bytes, root: ET.Element, node: ET.Element) -> tuple[int, int]:
    ordinal = list(root.iter()).index(node)
    parser = expat.ParserCreate()
    starts: list[int] = []
    ends: dict[int, int] = {}
    stack: list[int] = []

    def start(_name: str, _attrs: Any) -> None:
        stack.append(len(starts))
        starts.append(parser.CurrentByteIndex)

    def end(_name: str) -> None:
        index = stack.pop()
        offset = parser.CurrentByteIndex
        ends[index] = (
            payload.index(b">", offset) + 1 if payload[offset : offset + 2] == b"</" else offset
        )

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(payload, True)
    return starts[ordinal], ends[ordinal]


def _alternate(root: ET.Element, shape_id: int) -> ET.Element:
    for alternate in root.iter(f"{{{MC_NS}}}AlternateContent"):
        identity = alternate.find(
            f"{{{MC_NS}}}Choice/{{{P_NS}}}graphicFrame/{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr"
        )
        if identity is not None and identity.get("id") == str(shape_id):
            return alternate
    raise ZoomFrameRefusal("saved zoom frame is unavailable")


def apply_queued_zoom_edits(presentation: Any, input_path: Path, output_path: Path) -> None:
    """Apply staged zoom state before section reconciliation, retaining unrelated XML."""
    from .chart_adds import (
        _content_types_xml,
        _ensure_content_type_default,
        _next_numbered_part,
        _relationships_root,
    )
    from .package_parts import rels_part_for_package_part
    from .shape_adds import _IMAGE_REL_TYPE, _ZOOM_IMAGE_CONTENT_TYPES, _append_relationship
    from .shape_xml import (
        _SLIDE_REL_TYPE,
        A_NS,
        PKG_REL_NS,
        R_NS,
        register_zoom_namespaces,
        slide_creation_id,
    )

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        names = set(package.namelist())
        pres_root = ET.fromstring(package.read("ppt/presentation.xml"))
        parts = presentation_slide_parts(package, pres_root)
        staged = getattr(presentation, "_staged_slide_materializations", {})
        live_parts = {
            str(slide.slide_id): staged.get(
                slide._payload.get("_creation_token"), str(slide.partname).lstrip("/")
            )
            for slide in presentation.slides
        }
        content_types = ET.fromstring(package.read("[Content_Types].xml"))
        content_types_changed = False
        for shape, state in getattr(presentation, "_zoom_edits", {}).items():
            host = live_parts[str(shape._slide.slide_id)]
            payload = replacements.get(host, package.read(host))
            root, spans = _parse(payload)
            rels_part = rels_part_for_package_part(host)
            rels = (
                ET.fromstring(replacements[rels_part])
                if rels_part in replacements
                else _relationships_root(package, rels_part)
            )
            rels_changed = False
            kind = state["kind"]
            if state["new"]:
                used = [
                    int(item.get("id"))
                    for item in root.iter(f"{{{P_NS}}}cNvPr")
                    if (item.get("id") or "").isdigit()
                ]
                if shape._slide.partname:
                    source_root, _ = _parse(shape.part.blob)
                    used.extend(
                        int(item.get("id"))
                        for item in source_root.iter(f"{{{P_NS}}}cNvPr")
                        if (item.get("id") or "").isdigit()
                    )
                shape_id = max(used, default=0) + 1
                old_alternate = None
            else:
                shape_id = shape.shape_id
                old_alternate = _alternate(root, shape_id)
            objects = [dict(obj) for obj in state["objects"]]
            old_nodes = (
                {}
                if old_alternate is None
                else {
                    _properties(kind, node).get("id"): node for node in _select(root, shape_id)[2]
                }
            )
            links = (
                []
                if old_alternate is None
                else list(old_alternate.findall(f"{{{MC_NS}}}Fallback//{{{A_NS}}}hlinkClick"))
            )
            bindings = []
            for index, obj in enumerate(objects):
                if kind == "slide":
                    target_part = live_parts.get(obj["target"]) or parts.get(int(obj["target"]))
                    obj["target"] = str(
                        next(
                            identifier for identifier, part in parts.items() if part == target_part
                        )
                    )
                    creation = slide_creation_id(ET.fromstring(package.read(target_part)))
                else:
                    section = next(
                        section for section in presentation.sections if section.id == obj["target"]
                    )
                    target_part = live_parts[str(section.slides[0].slide_id)]
                    creation = None
                old_node = old_nodes.get(obj["id"])
                image_rid = None
                if "image" in obj:
                    blob = obj["image"].blob
                    extension = image_extension_from_blob(blob)
                    media_part = _next_numbered_part(names, "ppt/media/image", f".{extension}")
                    names.add(media_part)
                    replacements[media_part] = blob
                    image_rid = _append_relationship(
                        rels, _IMAGE_REL_TYPE, "../media/" + media_part.rsplit("/", 1)[1]
                    )
                    _ensure_content_type_default(
                        content_types, extension, _ZOOM_IMAGE_CONTENT_TYPES[extension]
                    )
                    content_types_changed = True
                    rels_changed = True
                elif old_node is not None:
                    blip = _properties(kind, old_node).find(f".//{{{A_NS}}}blip")
                    image_rid = None if blip is None else blip.get(f"{{{R_NS}}}embed")
                if not image_rid:
                    raise ZoomFrameRefusal("zoom destination has no embedded custom image")
                if state["rebuild"]:
                    link_rid = _append_relationship(
                        rels, _SLIDE_REL_TYPE, target_part.rsplit("/", 1)[1]
                    )
                    rels_changed = True
                elif len(links) == len(objects):
                    link_rid = links[index].get(f"{{{R_NS}}}id")
                    relationship = next(
                        (entry for entry in rels if entry.get("Id") == link_rid), None
                    )
                    if relationship is None:
                        raise ZoomFrameRefusal("zoom fallback relationship is missing")
                    import posixpath

                    target = posixpath.relpath(target_part, posixpath.dirname(host))
                    previous, separator, fragment = relationship.get("Target", "").partition("#")
                    if previous != target:
                        relationship.set("Target", target + ("#" + fragment if separator else ""))
                        rels_changed = True
                else:
                    link_rid = None
                    if old_node is not None and old_node.get(_KINDS[kind][3]) != obj["target"]:
                        raise ZoomFrameRefusal("cannot retarget an ambiguous summary fallback")
                bindings.append((image_rid, link_rid, creation))
            if state["rebuild"]:
                alternate = _build_alternate(
                    shape, shape_id, {**state, "objects": objects}, bindings, root
                )
                register_zoom_namespaces()
                ET.register_namespace("psuz", PSUZ_NS)
                updated = ET.tostring(alternate, encoding="utf-8")
                if old_alternate is None:
                    tree = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
                    if tree is None:
                        raise ZoomFrameRefusal("zoom host has no shape tree")
                    children = [
                        node
                        for node in tree
                        if node.tag.rsplit("}", 1)[-1]
                        in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp", "AlternateContent"}
                    ]
                    position = list(shape._slide.shapes).index(shape)
                    if position < len(children):
                        start, _end = _full_span(payload, root, children[position])
                    else:
                        _start, end = _full_span(payload, root, tree)
                        start = payload.rfind(b"</", _start, end)
                    payload = payload[:start] + updated + payload[start:]
                else:
                    start, end = _full_span(payload, root, old_alternate)
                    payload = payload[:start] + updated + payload[end:]
            else:
                patches = []
                for obj, (image_rid, _link, creation) in zip(objects, bindings, strict=True):
                    node = old_nodes[obj["id"]]
                    properties = _properties(kind, node)
                    attrs = _object_attributes(obj)
                    attrs[_KINDS[kind][3]] = obj["target"]
                    if kind == "slide":
                        attrs["cId"] = creation
                    for element, changes in (
                        (
                            node,
                            {
                                key: value
                                for key, value in attrs.items()
                                if key in {_KINDS[kind][3], "cId", "title", "descr"}
                            },
                        ),
                        (properties, _property_attributes(obj)),
                    ):
                        start, end = spans[id(element)]
                        tag = payload[start:end]
                        from xml.sax.saxutils import escape

                        for name, value in changes.items():
                            tag = _attribute(
                                tag, name, None if value is None else escape(value, {'"': "&quot;"})
                            )
                        patches.append((start, end, tag))
                    if "image" in obj:
                        image_blips = list(properties.iter(f"{{{A_NS}}}blip"))
                        if len(links) == len(objects):
                            pictures = list(
                                old_alternate.findall(f"{{{MC_NS}}}Fallback//{{{P_NS}}}pic")
                            )
                            image_blips.extend(pictures[objects.index(obj)].iter(f"{{{A_NS}}}blip"))
                        for blip in image_blips:
                            start, end = spans[id(blip)]
                            tag = payload[start:end]
                            match = re.search(rb"""([\w.-]+):embed\s*=""", tag)
                            if match is None:
                                raise ZoomFrameRefusal(
                                    "zoom custom image requires an embedded relationship"
                                )
                            patches.append(
                                (
                                    start,
                                    end,
                                    _attribute(tag, match[1].decode() + ":embed", image_rid),
                                )
                            )
                for start, end, replacement in sorted(patches, reverse=True):
                    payload = payload[:start] + replacement + payload[end:]
            _parse(payload)
            replacements[host] = payload
            if rels_changed:
                ET.register_namespace("", PKG_REL_NS)
                replacements[rels_part] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)
        if content_types_changed:
            replacements["[Content_Types].xml"] = _content_types_xml(content_types)
    copy_package_with_replacements(input_path, output_path, replacements)


def _object_attributes(obj: dict[str, Any]) -> dict[str, str]:
    return {"title": obj["title"], "descr": obj["description"]}


def _property_attributes(obj: dict[str, Any]) -> dict[str, str | None]:
    return {
        "imageType": obj["image_type"],
        "returnToParent": "1" if obj["return_to_parent"] else "0",
        "showBg": "1" if obj["show_background"] else "0",
        "transitionDur": None
        if obj["transition_duration"] is None
        else format(obj["transition_duration"], "f"),
    }


def _build_alternate(
    shape: Any, shape_id: int, state: dict[str, Any], bindings: list, root: ET.Element
) -> ET.Element:
    from .shape_xml import A_NS, zoom_alternate_content

    offset = (shape.left, shape.top)
    extent = (shape.width, shape.height)
    kind = state["kind"]
    pieces = []
    objects = state["objects"]
    for index, (obj, (image_rid, link_rid, creation)) in enumerate(
        zip(objects, bindings, strict=True)
    ):
        cell_width = extent[0] // len(objects) if kind == "summary" else extent[0]
        piece = zoom_alternate_content(
            "section" if kind == "summary" else kind,
            shape_id=shape_id,
            name=shape.name,
            offset=(index * cell_width, 0) if kind == "summary" else offset,
            extent=(cell_width, extent[1]),
            target=obj["target"],
            zoom_id=obj["id"],
            image_relationship_id=image_rid,
            link_relationship_id=link_rid,
            return_to_parent=obj["return_to_parent"],
            image_type=obj["image_type"],
            creation_id=creation,
        )
        object_kind = "section" if kind == "summary" else kind
        namespace, _container, object_tag, _attribute_name = _KINDS[object_kind]
        node = piece.find(f".//{{{namespace}}}{object_tag}")
        node.attrib.update(_object_attributes(obj))
        properties = _properties("section" if kind == "summary" else kind, node)
        for name, value in _property_attributes(obj).items():
            if value is not None:
                properties.set(name, value)
        if kind == "summary":
            transform = properties.find(f"{{{P166_NS}}}spPr/{{{A_NS}}}xfrm/{{{A_NS}}}off")
            transform.set("x", str(index * cell_width))
        pieces.append(piece)
    if kind != "summary":
        return pieces[0]
    summary_nodes = [deepcopy(piece.find(f".//{{{PSEZ_NS}}}sectionZmObj")) for piece in pieces]
    first = pieces[0]
    choice = first.find(f"{{{MC_NS}}}Choice")
    choice.set("Requires", "psuz")
    frame = choice.find(f"{{{P_NS}}}graphicFrame")
    xfrm = frame.find(f"{{{P_NS}}}xfrm")
    xfrm.find(f"{{{A_NS}}}off").attrib.update({"x": str(offset[0]), "y": str(offset[1])})
    xfrm.find(f"{{{A_NS}}}ext").attrib.update({"cx": str(extent[0]), "cy": str(extent[1])})
    data = frame.find(f"{{{A_NS}}}graphic/{{{A_NS}}}graphicData")
    data.clear()
    data.set("uri", PSUZ_NS)
    container = ET.SubElement(data, f"{{{PSUZ_NS}}}summaryZm")
    fallback = first.find(f"{{{MC_NS}}}Fallback")
    fallback.clear()
    group = ET.SubElement(fallback, f"{{{P_NS}}}grpSp")
    nv = ET.SubElement(group, f"{{{P_NS}}}nvGrpSpPr")
    ET.SubElement(nv, f"{{{P_NS}}}cNvPr", {"id": str(shape_id), "name": shape.name})
    ET.SubElement(nv, f"{{{P_NS}}}cNvGrpSpPr")
    ET.SubElement(nv, f"{{{P_NS}}}nvPr")
    props = ET.SubElement(group, f"{{{P_NS}}}grpSpPr")
    transform = ET.SubElement(props, f"{{{A_NS}}}xfrm")
    for tag, attrs in (
        ("off", {"x": offset[0], "y": offset[1]}),
        ("ext", {"cx": extent[0], "cy": extent[1]}),
        ("chOff", {"x": 0, "y": 0}),
        ("chExt", {"cx": extent[0], "cy": extent[1]}),
    ):
        ET.SubElement(
            transform, f"{{{A_NS}}}{tag}", {name: str(value) for name, value in attrs.items()}
        )
    next_id = max(
        (
            int(node.get("id"))
            for node in root.iter(f"{{{P_NS}}}cNvPr")
            if (node.get("id") or "").isdigit()
        ),
        default=shape_id,
    )
    next_id = max(next_id, shape_id) + 1
    for index, node in enumerate(summary_nodes):
        for element in node.iter():
            if element.tag.startswith(f"{{{PSEZ_NS}}}"):
                local = element.tag.split("}")[1]
                element.tag = f"{{{PSUZ_NS}}}{'summaryZmObj' if local == 'sectionZmObj' else local}"
        container.append(node)
        # first's original fallback was cleared above; construct its thumbnail anew.
        image_rid, link_rid, _creation = bindings[index]
        thumbnail = zoom_alternate_content(
            "section",
            shape_id=next_id + index,
            name=objects[index]["title"] or f"Summary Section {index + 1}",
            offset=(index * (extent[0] // len(objects)), 0),
            extent=(extent[0] // len(objects), extent[1]),
            target=objects[index]["target"],
            zoom_id=objects[index]["id"],
            image_relationship_id=image_rid,
            link_relationship_id=link_rid,
            return_to_parent=objects[index]["return_to_parent"],
            image_type=objects[index]["image_type"],
        )
        group.append(thumbnail.find(f"{{{MC_NS}}}Fallback/{{{P_NS}}}pic"))
    ET.SubElement(container, f"{{{PSUZ_NS}}}fixedLayout")
    return first


__all__ = [
    "ZoomFrame",
    "ZoomFrameRefusal",
    "ZoomObject",
    "apply_zoom_frame_edit",
    "read_zoom_frame",
]
