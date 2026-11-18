"""Per-shape facade objects for slides and masters."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, NamedTuple
from xml.etree import ElementTree as ET

from .facade_values import (
    coerce_emu as _coerce_emu,
)
from .facade_values import (
    coerce_rotation_degrees as _coerce_rotation_degrees,
)
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    open_package_source,
)
from .package_parts import (
    package_xml_element as _package_xml_element,
)
from .shape_edit_refs import shape_edit_ref as _shape_edit_ref
from .shape_format_facade import FillFormat, LineFormat, ShadowFormat
from .shape_inspection import (
    ConnectorRerouteError,
    MediaFormat,
    PictureImage,
    _auto_shape_preset_geometry,
    _picture_crop_value,
    _picture_image,
    _replace_picture_image,
    _set_picture_crop_value,
    _set_shape_transform_value,
    _shape_auto_shape_preset_geometry,
    _shape_auto_shape_type_value,
    _shape_is_text_box,
    _shape_line_xml_element,
    _shape_media_format,
    _shape_media_type,
    _shape_poster_frame,
    _shape_type_value,
)
from .shape_locks import check_shape_locks
from .shape_master_facade import MasterShape
from .shape_payloads import (
    _paragraph_runs_and_line_breaks,
    _shape_paragraph_runs,
    _shape_transform_value,
)
from .shape_xml import (
    _find_shape_transform_xml_element,
    _shape_xml_element,
    parse_ooxml_bool,
)
from .xml_helpers import find_ooxml as _find_ooxml

if TYPE_CHECKING:
    from .chart_facade import Chart
    from .presentation_slides import Slide
    from .shape_3d_format import ThreeDFormat
    from .shape_action_facade import ActionSetting, AdjustmentCollection, PlaceholderFormat
    from .shape_freeform import CustomGeometry
    from .shape_glow_edits import GlowSpec
    from .shape_group_collection_facade import GroupShapeCollection
    from .shape_locks import ShapeLocks
    from .shape_ole_facade import OleFormat
    from .shape_shadow_edits import SoftEdgeSpec
    from .table_facade import Table
    from .text_facade import TextFrame
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
DGM_NS = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"

__all__ = [
    "ConnectorConnection",
    "ConnectorRerouteError",
    "MasterShape",
    "Shape",
    "SmartArt",
    "SmartArtNode",
]


class ConnectorConnection(NamedTuple):
    """One connector endpoint attachment, ``a:stCxn`` or ``a:endCxn`` (CT_Connection).

    ``shape_id`` is the connected shape's ``cNvPr/@id``; ``cxn_pt_idx`` is the
    connection-site index on that shape's geometry.
    """

    shape_id: int
    cxn_pt_idx: int


def _connector_connection(shape: Shape, endpoint: str) -> ConnectorConnection | None:
    """Read one endpoint attachment, honouring queued connect/disconnect edits."""
    if shape._payload.get("kind") != "connector":
        raise AttributeError(f"'Shape' object has no attribute '{endpoint}_connection'")
    queued = shape._payload.get(f"{endpoint}_connection")
    if queued is None:
        edits = shape._slide._presentation._connector_connection_edits.get(
            (shape._slide._index, _shape_edit_ref(shape)), {}
        )
        if endpoint in edits:
            queued = edits[endpoint]
            if queued is None:
                return None
    if queued is not None:
        return ConnectorConnection(int(queued["shape_id"]), int(queued["cxn_pt_idx"]))
    if shape._payload.get("_pending_shape") or shape._payload.get("_pending_group_child"):
        return None
    root = _package_xml_element(shape._slide._presentation.path, shape._slide.partname)
    element = _shape_xml_element(root._element, shape._payload)
    tag = "stCxn" if endpoint == "begin" else "endCxn"
    connection = _find_ooxml(element, f"./{{{P_NS}}}nvCxnSpPr/{{{P_NS}}}cNvCxnSpPr/{{{A_NS}}}{tag}")
    if connection is None:
        return None
    values = []
    for attr in ("id", "idx"):
        # @id is ST_DrawingElementId and @idx xsd:unsignedInt; both are required.
        raw = connection.get(attr)
        if raw is None or not (raw.isascii() and raw.isdigit()) or int(raw) > 0xFFFFFFFF:
            raise ValueError(f"a:{tag}/@{attr} must be an unsigned 32-bit integer, got {raw!r}")
        values.append(int(raw))
    return ConnectorConnection(*values)


def _shape_flip(shape: Shape, axis: str) -> bool:
    long_key = f"flip_{'horizontal' if axis == 'h' else 'vertical'}"
    if long_key in shape._payload:
        return bool(shape._payload[long_key])
    short_key = "flip_h" if axis == "h" else "flip_v"
    if short_key in shape._payload:
        return bool(shape._payload[short_key])
    try:
        root = _package_xml_element(
            shape._slide._presentation.path,
            shape._slide.partname,
        )
        shape_element = _shape_xml_element(root._element, shape._payload)
        transform = _find_shape_transform_xml_element(shape_element)
        if transform is None:
            return False
        attr = "flipH" if axis == "h" else "flipV"
        raw = transform.attrib.get(attr)
        if raw is None:
            return False
        return parse_ooxml_bool(raw)
    except (
        AttributeError,
        FileNotFoundError,
        KeyError,
        ET.ParseError,
    ):
        return False


class _SmartArtTextFrame:
    """Minimal editable text-frame facade for a SmartArt node."""

    def __init__(self, node: SmartArtNode) -> None:
        self._node = node

    @property
    def text(self) -> str:
        return self._node.text

    @text.setter
    def text(self, value: str) -> None:
        self._node.text = value

    def clear(self) -> None:
        self.text = ""


_KEEP_SMARTART_PARENT = object()


class SmartArtNode:
    """One editable node in a SmartArt diagram data model."""

    def __init__(self, smartart: SmartArt, node_id: str) -> None:
        self._smartart = smartart
        self._node_id = node_id

    @property
    def id(self) -> str:
        return self._node_id

    @property
    def parent(self) -> SmartArtNode | None:
        """Parent node, or None for a root (the document point is not a node)."""
        parent_id = self._smartart._node(self.id)["parent"]
        if parent_id is None:
            return None
        self._smartart._node(parent_id)
        return SmartArtNode(self._smartart, parent_id)

    @property
    def level(self) -> int:
        """Zero-based depth; malformed cyclic ancestry raises ValueError."""
        level = 0
        seen = {self.id}
        parent = self.parent
        while parent is not None:
            if parent.id in seen:
                raise ValueError("SmartArt hierarchy contains a cycle")
            seen.add(parent.id)
            level += 1
            parent = parent.parent
        return level

    @property
    def text(self) -> str:
        return str(self._smartart._node(self._node_id)["text"])

    @text.setter
    def text(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("SmartArt node text must be a string")
        node = self._smartart._node(self._node_id)
        if node["text"] != value:
            node["text"] = value
            self._smartart._commit()

    @property
    def text_frame(self) -> _SmartArtTextFrame:
        return _SmartArtTextFrame(self)

    def remove(self) -> None:
        """Remove this node, its descendants and their diagram connections."""
        self._smartart.remove_node(self)


class SmartArt(Sequence[SmartArtNode]):
    """Editable SmartArt nodes and related definition XML.

    Read or replace ``layout_xml``, ``quick_style_xml`` and ``colors_xml`` as
    UTF-8 XML bytes. Replacements must retain the part's OOXML namespace profile
    and expected root (layoutDef, styleDef, colorsDef); relationships stay bound
    to the same part. ``drawing_xml`` is a read-only cached dsp:drawing, or None
    when absent. Invalid XML raises ValueError before an edit is queued.
    """

    def __init__(self, shape: Shape) -> None:
        self._shape = shape
        raw_nodes = shape._payload.get("smartart_nodes")
        if not isinstance(raw_nodes, list):
            raw_nodes = _smartart_nodes_from_package(shape)
            shape._payload["smartart_nodes"] = raw_nodes
        self._nodes = raw_nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterator[SmartArtNode]:
        return (SmartArtNode(self, str(node["id"])) for node in self._nodes)

    def __getitem__(self, index: int | slice) -> SmartArtNode | list[SmartArtNode]:
        if isinstance(index, slice):
            return [SmartArtNode(self, str(node["id"])) for node in self._nodes[index]]
        return SmartArtNode(self, str(self._nodes[index]["id"]))

    @property
    def nodes(self) -> SmartArt:
        return self

    @property
    def all_nodes(self) -> SmartArt:
        return self

    @property
    def layout(self) -> str | None:
        """Selected fallback layout name; None when the definition has no title.

        Assign a supported standard name to switch layout without changing the
        data model. For cached diagrams, bound definitions or unsupported names,
        catch ``wolfppt.smartart_styles.SmartArtLayoutRefusal``; no edit is queued.
        """
        from .smartart_styles import _layout_name

        return _layout_name(self)

    @layout.setter
    def layout(self, value: str) -> None:
        from .smartart_styles import _switch_layout

        _switch_layout(self, value)

    @property
    def layout_xml(self) -> bytes:
        return self._definition_xml("layout")

    @layout_xml.setter
    def layout_xml(self, value: bytes) -> None:
        self._set_definition_xml("layout", value)

    @property
    def quick_style_xml(self) -> bytes:
        return self._definition_xml("quickStyle")

    @quick_style_xml.setter
    def quick_style_xml(self, value: bytes) -> None:
        self._set_definition_xml("quickStyle", value)

    @property
    def colors_xml(self) -> bytes:
        return self._definition_xml("colors")

    @colors_xml.setter
    def colors_xml(self, value: bytes) -> None:
        self._set_definition_xml("colors", value)

    @property
    def drawing_xml(self) -> bytes | None:
        from .shape_adds import _smartart_partname, _smartart_xml

        slide = self._shape._slide
        if any(
            kind == "smartart" and (args[0], args[2]) == (slide._index, self._shape.shape_id)
            for kind, args in slide._presentation._shape_adds
        ):
            return None
        with open_package_source(slide._presentation.path) as package:
            try:
                part = _smartart_partname(package, slide.partname, self._shape.shape_id, "drawing")
            except ValueError as exc:
                if str(exc) == "SmartArt drawing relationship is missing":
                    return None
                raise
            blob = package.read(part)
        _smartart_xml(blob, "drawing")
        return blob

    def _definition_xml(self, kind: str) -> bytes:
        from .shape_adds import (
            _smartart_colors_xml,
            _smartart_layout_xml,
            _smartart_partname,
            _smartart_quick_style_xml,
            _smartart_xml,
        )

        slide = self._shape._slide
        for operation, args in reversed(slide._presentation._shape_adds):
            if operation == "smartart_part_update" and args[:3] == (
                slide._index,
                self._shape.shape_id,
                kind,
            ):
                return args[3]
            if operation == "smartart" and (args[0], args[2]) == (
                slide._index,
                self._shape.shape_id,
            ):
                if kind == "layout":
                    return _smartart_layout_xml(args[3], args[8])
                if kind == "quickStyle":
                    return _smartart_quick_style_xml(args[8])
                return _smartart_colors_xml(args[8])
        with open_package_source(slide._presentation.path) as package:
            part = _smartart_partname(package, slide.partname, self._shape.shape_id, kind)
            blob = package.read(part)
        _smartart_xml(blob, kind)
        return blob

    def _set_definition_xml(self, kind: str, value: bytes) -> None:
        from .shape_adds import _smartart_xml

        replacement = _smartart_xml(value, kind)
        current = self._definition_xml(kind)
        if replacement.tag != _smartart_xml(current, kind).tag:
            raise ValueError("SmartArt definition replacement must retain its namespace profile")
        if value != current:
            self._shape._slide._presentation._queue_smartart_part_update(
                self._shape._slide._index, self._shape.shape_id, kind, value
            )

    def move_node(
        self,
        node: SmartArtNode,
        index: int,
        *,
        parent: SmartArtNode | None | object = _KEEP_SMARTART_PARENT,
    ) -> None:
        """Move a node to a final zero-based index in the flat node sequence.

        Omit parent to retain ancestry; pass None to make a root. Descendants
        retain their parent links and their relative sequence positions.
        Invalid handles, indices and cycles are refused before any mutation.
        """
        if not isinstance(node, SmartArtNode):
            raise TypeError("SmartArt movement requires a SmartArtNode")
        if node._smartart._shape is not self._shape:
            raise ValueError("SmartArt node belongs to another diagram")
        current = self._node(node.id)
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("SmartArt node index must be an integer")
        if not 0 <= index < len(self._nodes):
            raise IndexError("SmartArt node index is out of range")
        parent_id = current["parent"]
        if parent is not _KEEP_SMARTART_PARENT:
            if parent is not None:
                if not isinstance(parent, SmartArtNode):
                    raise TypeError("SmartArt parent must be a SmartArtNode or None")
                if parent._smartart._shape is not self._shape:
                    raise ValueError("SmartArt parent node belongs to another diagram")
                self._node(parent.id)
            parent_id = None if parent is None else parent.id
        ancestor = parent_id
        seen = {node.id}
        while ancestor is not None:
            if ancestor in seen:
                raise ValueError("SmartArt movement would create a hierarchy cycle")
            seen.add(ancestor)
            ancestor = self._node(ancestor)["parent"]
        if self._nodes.index(current) == index and parent_id == current["parent"]:
            return
        nodes = [dict(item) for item in self._nodes if item["id"] != node.id]
        nodes.insert(index, {**current, "parent": parent_id})
        slide = self._shape._slide
        presentation = slide._presentation
        shape_id = self._shape.shape_id
        if any(
            kind == "smartart" and (args[0], args[2]) == (slide._index, shape_id)
            for kind, args in presentation._shape_adds
        ):
            presentation._queue_smartart_update(slide._index, shape_id, nodes)
        else:
            presentation._shape_adds.append(
                ("smartart_move", (slide._index, shape_id, node.id, parent_id, nodes))
            )
        self._nodes[:] = nodes

    def remove_node(self, node: SmartArtNode) -> None:
        """Remove a node and descendants; refuse foreign, stale and final nodes."""
        if not isinstance(node, SmartArtNode):
            raise TypeError("SmartArt removal requires a SmartArtNode")
        if node._smartart._shape is not self._shape:
            raise ValueError("SmartArt node belongs to another diagram")
        self._node(node.id)
        removed = {node.id}
        while True:
            descendants = {str(item["id"]) for item in self._nodes if item["parent"] in removed}
            if descendants <= removed:
                break
            removed.update(descendants)
        remaining = [item for item in self._nodes if item["id"] not in removed]
        if not remaining:
            raise ValueError("SmartArt requires at least one node")
        self._shape._slide._presentation._queue_smartart_remove(
            self._shape._slide._index, self._shape.shape_id, tuple(sorted(removed)), remaining
        )
        self._nodes[:] = remaining
        self._shape._payload.setdefault("smartart_removed_ids", set()).update(removed)

    def add_node(self, text: str = "", parent: SmartArtNode | None = None) -> SmartArtNode:
        if not isinstance(text, str):
            raise TypeError("SmartArt node text must be a string")
        if parent is not None and parent._smartart._shape is not self._shape:
            raise ValueError("SmartArt parent node belongs to another diagram")
        parent_id = None if parent is None else parent.id
        if parent_id is not None and parent_id not in {node["id"] for node in self._nodes}:
            raise ValueError("SmartArt parent node is not in this diagram")
        used_ids = {str(node["id"]) for node in self._nodes}
        used_ids.update(self._shape._payload.get("smartart_removed_ids", ()))
        partname = _smartart_data_partname(self._shape)
        if partname is not None:
            from .shape_adds import _smartart_xml

            root = _smartart_xml(
                PackagePart(self._shape._slide._presentation, partname).blob, "data"
            )
            used_ids.update(item.get("modelId") for item in root.iter() if item.get("modelId"))
        numeric_ids = [int(node_id) for node_id in used_ids if node_id.isdecimal()]
        node_id = str(max(numeric_ids, default=1) + 1)
        while node_id in used_ids:
            node_id = str(int(node_id) + 1)
        self._nodes.append({"id": node_id, "text": text, "parent": parent_id})
        self._commit()
        return SmartArtNode(self, node_id)

    def _node(self, node_id: str) -> dict[str, str | None]:
        for node in self._nodes:
            if node["id"] == node_id:
                return node
        raise ValueError(f"SmartArt node {node_id!r} is unavailable")

    def _commit(self) -> None:
        nodes = self._nodes
        shape_id = self._shape.shape_id
        if not isinstance(shape_id, int):
            raise ValueError("SmartArt shape has no numeric identity")  # noqa: TRY004 - unavailable identity is a shape-state error
        self._shape._slide._presentation._queue_smartart_update(
            self._shape._slide._index,
            shape_id,
            nodes,
        )


def _smartart_nodes_from_package(shape: Shape) -> list[dict[str, str | None]]:
    partname = _smartart_data_partname(shape)
    if partname is None:
        return []
    from .shape_adds import _smartart_xml
    from .smartart_model import ordered_nodes

    root = _smartart_xml(PackagePart(shape._slide._presentation, partname).blob, "data")
    dgm_namespace = root.tag.removesuffix("dataModel")
    a_namespace = (
        "http://purl.oclc.org/ooxml/drawingml/main"
        if root.tag.startswith("{http://purl.oclc.org/")
        else A_NS
    )
    nodes: list[dict[str, str | None]] = []
    for point in root.findall(f".//{dgm_namespace}pt"):
        node_id = point.get("modelId")
        if not node_id or point.get("type", "node") in {
            "doc",
            "pres",
            "parTrans",
            "sibTrans",
        }:
            continue
        nodes.append(
            {
                "id": node_id,
                "text": "".join(
                    text.text or "" for text in point.findall(f".//{{{a_namespace}}}t")
                ),
                "parent": None,
            }
        )
    by_id = {str(node["id"]): node for node in nodes}
    ordered, parents = ordered_nodes(list(by_id), root.findall(f".//{dgm_namespace}cxn"))
    for child_id, parent_id in parents.items():
        by_id[child_id]["parent"] = parent_id
    return [by_id[node_id] for node_id in ordered]


def _smartart_data_partname(shape: Shape) -> str | None:
    """Resolve diagram data using either exact OOXML namespace profile."""
    from .shape_adds import _smartart_partname

    try:
        with open_package_source(shape._slide._presentation.path) as package:
            return _smartart_partname(package, shape._slide.partname, shape.shape_id, "data")
    except (AttributeError, FileNotFoundError, KeyError, OSError, ET.ParseError, ValueError):
        return None


class Shape:
    def __init__(
        self,
        slide: Slide,
        index: int,
        payload: dict[str, Any],
        table_index: int = 0,
        run_start_index: int = 0,
        *,
        _native: bool = False,
    ) -> None:
        self._slide = slide
        self._index = index
        self._payload = dict(payload)
        self._table_index = table_index
        self._run_start_index = run_start_index
        # Native summaries already contain canonical text, paragraphs, and string runs.
        paragraph_runs = self._payload.get("paragraph_runs") if _native else None
        if paragraph_runs is None:
            paragraph_runs = _shape_paragraph_runs(self)
        elif not paragraph_runs and self.has_text_frame:
            paragraph_runs = [[]]
        self._existing_paragraph_count = len(paragraph_runs)
        self._existing_run_counts = [len(runs) for runs in paragraph_runs]

    @property
    def shape_id(self) -> int | str | None:
        raw = self._payload.get("id")
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return raw

    @property
    def zoom(self) -> Any:
        """Read or edit a zoom frame; refuse non-zoom shapes with ZoomFrameRefusal."""
        from .zoom_frames import ZoomEditor

        return ZoomEditor(self)

    def save_image(
        self,
        destination: Any,
        *,
        fonts: Any = (),
        dpi: int = 96,
        supersample: int = 2,
        format: Any = "png",
        quality: Any = None,
        bounds: str | None = None,
        time: float = 0.0,
    ) -> Any:
        """Write this shape as a transparent PNG or a white-backed JPEG (commercial
        edition; see :func:`wolfppt.render_raster.save_shape_image`).

        ``format`` takes an :class:`~wolfppt.shape_picture_inspection.ImageFormat`
        or its name; JPEG takes ``quality`` from 1 to 100. SVG and PDF are slide
        outputs of ``render-native`` and raise ImageFormatRefusal here. Every
        refusal precedes the write. Omitted ``bounds`` preserves the legacy
        frame/outset crop; ``slide`` keeps full-slide transparent dimensions,
        ``geometry`` crops to the transformed authored frame without effects,
        and ``appearance`` crops to nonzero alpha including visible effects.
        All crops clip at the slide edges. ``time`` selects embedded animated
        image frames in seconds, not slide animation timing. Returns PNG crop
        bytes and geometry even when the destination encodes as JPEG.
        """
        import io

        from .editions import commercial_module
        from .shape_picture_inspection import (
            ImageFormat,
            ImageFormatRefusal,
            check_image_destination,
            encode_image,
            image_format,
            jpeg_quality,
            write_image_output,
        )

        target = image_format(format)
        if target not in (ImageFormat.PNG, ImageFormat.JPEG):
            raise ImageFormatRefusal(
                f"a shape image encodes as png or jpeg, not {target.value}; "
                "render-native publishes SVG and PDF slides"
            )
        if quality is not None and target is not ImageFormat.JPEG:
            raise ImageFormatRefusal("quality applies only to JPEG output")
        jpeg_quality(quality)
        check_image_destination(destination)
        render_raster = commercial_module("render_raster", "Saving a shape image")
        rendered = io.BytesIO()
        crop = render_raster.save_shape_image(
            self,
            rendered,
            fonts=fonts,
            dpi=dpi,
            supersample=supersample,
            bounds=bounds,
            time=time,
        )
        payload = crop.png
        if target is ImageFormat.JPEG:
            payload = encode_image(payload, target, quality=quality, dpi=(dpi, dpi))
        write_image_output(destination, payload)
        return crop

    def get_effective(self) -> Any:
        """Return this shape's effective fill, outline, and text formatting.

        Each value is resolved the way the built-in renderer draws it and
        records the inheritance level that supplied it (commercial edition;
        see :func:`wolfppt.effective_format_readback.shape_effective`).
        """
        from .editions import commercial_module

        readback = commercial_module("effective_format_readback", "Reading effective formatting")
        return readback.shape_effective(self)

    @property
    def shape_type(self) -> Any:
        return _shape_type_value(self)

    @property
    def auto_shape_type(self) -> Any:
        return _shape_auto_shape_type_value(self)

    @auto_shape_type.setter
    def auto_shape_type(self, value: Any) -> None:
        """Change this auto shape's preset (``a:prstGeom/@prst``) on save.

        Adjust guides the new preset declares keep their values; the others are dropped.
        Refuses, before queueing anything, an unknown preset (``NotImplementedError``) and
        a target that is not a saved auto shape: picture, group, connector, freeform
        (``a:custGeom``), text box, graphic frame, or a pending unsaved shape
        (``ValueError``).
        """
        preset = _auto_shape_preset_geometry(value)
        if self._payload.get("kind") != "shape" or _shape_is_text_box(self):
            raise ValueError("shape is not an auto shape")
        current = _shape_auto_shape_preset_geometry(self)
        partname = getattr(self._slide, "partname", None)
        if (
            self.shape_id is None
            or not partname
            or self._slide._payload.get("_pending_creation")
            or self._payload.get("_pending_shape")
            or self._payload.get("_pending_group_child")
        ):
            raise ValueError("cannot change the preset of an unsaved pending shape; save it first")
        if preset == current:
            return
        check_shape_locks(self, "preset change", "no_change_shape_type")
        self._slide._presentation._queue_shape_preset(partname, self.shape_id, preset)
        self._payload["preset_geometry"] = preset
        self._payload.pop("adjustment_guides", None)

    @property
    def adjustments(self) -> AdjustmentCollection:
        if self._payload.get("kind") not in {"shape", "freeform"}:
            raise AttributeError("'Shape' object has no attribute 'adjustments'")
        from .shape_action_facade import AdjustmentCollection

        return AdjustmentCollection(self)

    @property
    def custom_geometry(self) -> CustomGeometry | None:
        """This shape's ``a:custGeom`` as a :class:`~wolfppt.shape_freeform.CustomGeometry`.

        Paths and segments, adjust values (``a:avLst``), guides (``a:gdLst``), adjust
        handles, connection sites and the text rectangle, read from Strict or transitional
        DrawingML; ``None`` when the shape has no custom geometry.
        """
        from .shape_freeform import read_custom_geometry

        return read_custom_geometry(self)

    @custom_geometry.setter
    def custom_geometry(self, value: CustomGeometry) -> None:
        """Write ``value`` back to this shape's ``a:custGeom``.

        Only changed sections are re-serialized, in the source profile; all other slide
        bytes are kept. Refuses, before writing anything, an invalid model (``TypeError``
        or ``CustomGeometryError``), a shape without custom geometry or a pending shape
        (``CustomGeometryError``), and a presentation with other pending edits
        (``ValueError``).
        """
        from .shape_freeform import write_custom_geometry

        write_custom_geometry(self, value)

    @property
    def ln(self) -> XmlElementProxy | None:
        if self._payload.get("kind") not in {
            "connector",
            "shape",
            "picture",
            "freeform",
        }:
            raise AttributeError("'Shape' object has no attribute 'ln'")
        line = _shape_line_xml_element(self)
        return None if line is None else XmlElementProxy(line)

    def get_or_add_ln(self) -> XmlElementProxy:
        if self._payload.get("kind") not in {
            "connector",
            "shape",
            "picture",
            "freeform",
        }:
            raise AttributeError("'Shape' object has no attribute 'get_or_add_ln'")
        line = _shape_line_xml_element(self)
        if line is None:
            line = ET.Element(f"{{{A_NS}}}ln")
        self._payload["has_line_element"] = True
        self._slide._presentation._queue_shape_line_element(
            self._slide._index,
            _shape_edit_ref(self),
        )
        return XmlElementProxy(line)

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._slide._presentation.path,
            self._slide.partname,
        )
        return XmlElementProxy(_shape_xml_element(root._element, self._payload))

    @property
    def _element(self) -> XmlElementProxy:
        return self.element

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"value must be a string, got {type(value)!r}")
        if value == self.name:
            return
        self._payload["name"] = value
        self._slide._presentation._queue_shape_name(
            self._slide._index,
            _shape_edit_ref(self),
            value,
        )

    @property
    def left(self) -> int:
        return _shape_transform_value(self, "x")

    @left.setter
    def left(self, value: int) -> None:
        _set_shape_transform_value(self, "x", _coerce_emu(value, "left"))

    @property
    def top(self) -> int:
        return _shape_transform_value(self, "y")

    @top.setter
    def top(self, value: int) -> None:
        _set_shape_transform_value(self, "y", _coerce_emu(value, "top"))

    @property
    def width(self) -> int:
        return _shape_transform_value(self, "cx")

    @width.setter
    def width(self, value: int) -> None:
        self._set_extent("cx", "width", value)

    @property
    def height(self) -> int:
        return _shape_transform_value(self, "cy")

    @height.setter
    def height(self, value: int) -> None:
        self._set_extent("cy", "height", value)

    def _set_extent(self, key: str, name: str, value: int) -> None:
        extent = _coerce_emu(value, name)
        # a:ext cx/cy is ST_PositiveCoordinate; a placeholder override must not write a
        # negative extent into the package.
        if self.is_placeholder and extent < 0:
            raise ValueError(f"{name} must not be negative, got {extent}")
        _set_shape_transform_value(self, key, extent)

    @property
    def begin_x(self) -> int:
        from .shape_connector_facade import connector_endpoint_value

        return connector_endpoint_value(self, "begin", "x")

    @begin_x.setter
    def begin_x(self, value: int) -> None:
        from .shape_connector_facade import set_connector_endpoint_value

        set_connector_endpoint_value(self, "begin", "x", value)

    @property
    def begin_y(self) -> int:
        from .shape_connector_facade import connector_endpoint_value

        return connector_endpoint_value(self, "begin", "y")

    @begin_y.setter
    def begin_y(self, value: int) -> None:
        from .shape_connector_facade import set_connector_endpoint_value

        set_connector_endpoint_value(self, "begin", "y", value)

    @property
    def end_x(self) -> int:
        from .shape_connector_facade import connector_endpoint_value

        return connector_endpoint_value(self, "end", "x")

    @end_x.setter
    def end_x(self, value: int) -> None:
        from .shape_connector_facade import set_connector_endpoint_value

        set_connector_endpoint_value(self, "end", "x", value)

    @property
    def end_y(self) -> int:
        from .shape_connector_facade import connector_endpoint_value

        return connector_endpoint_value(self, "end", "y")

    @end_y.setter
    def end_y(self, value: int) -> None:
        from .shape_connector_facade import set_connector_endpoint_value

        set_connector_endpoint_value(self, "end", "y", value)

    def begin_connect(self, shape: Any, cxn_pt_idx: int) -> None:
        from .shape_connector_facade import connect_connector_endpoint

        connect_connector_endpoint(self, "begin", shape, cxn_pt_idx)

    def end_connect(self, shape: Any, cxn_pt_idx: int) -> None:
        from .shape_connector_facade import connect_connector_endpoint

        connect_connector_endpoint(self, "end", shape, cxn_pt_idx)

    def begin_disconnect(self) -> None:
        from .shape_connector_facade import disconnect_connector_endpoint

        disconnect_connector_endpoint(self, "begin")

    def end_disconnect(self) -> None:
        from .shape_connector_facade import disconnect_connector_endpoint

        disconnect_connector_endpoint(self, "end")

    @property
    def begin_connection(self) -> ConnectorConnection | None:
        """Connected shape id and site index of the begin point (``a:stCxn``), or None."""
        return _connector_connection(self, "begin")

    @property
    def end_connection(self) -> ConnectorConnection | None:
        """Connected shape id and site index of the end point (``a:endCxn``), or None."""
        return _connector_connection(self, "end")

    @property
    def rotation(self) -> float:
        raw = self._payload.get("rotation")
        if not isinstance(raw, (int, float)):
            from .text_facade import _shape_rotation

            raw = _shape_rotation(self)
            self._payload["rotation"] = raw
        return float(raw)

    @rotation.setter
    def rotation(self, value: float) -> None:
        rotation = _coerce_rotation_degrees(value)
        if rotation == self.rotation:
            return
        check_shape_locks(self, "rotation", "no_rotate")
        self._payload["rotation"] = rotation
        self._slide._presentation._queue_shape_rotation(
            self._slide._index,
            _shape_edit_ref(self),
            rotation,
        )

    @property
    def flip_horizontal(self) -> bool:
        raw = self._payload.get("flip_horizontal")
        if raw is None:
            raw = _shape_flip(self, "h")
            self._payload["flip_horizontal"] = raw
            self._payload["flip_h"] = raw
        return bool(raw)

    @flip_horizontal.setter
    def flip_horizontal(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError(f"flip_horizontal must be a bool, got {type(value).__name__}")
        if value == self.flip_horizontal:
            return
        self._payload["flip_horizontal"] = value
        self._payload["flip_h"] = value
        self._slide._presentation._queue_shape_flip(
            self._slide._index,
            _shape_edit_ref(self),
            "h",
            value,
        )

    @property
    def flip_vertical(self) -> bool:
        raw = self._payload.get("flip_vertical")
        if raw is None:
            raw = _shape_flip(self, "v")
            self._payload["flip_vertical"] = raw
            self._payload["flip_v"] = raw
        return bool(raw)

    @flip_vertical.setter
    def flip_vertical(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError(f"flip_vertical must be a bool, got {type(value).__name__}")
        if value == self.flip_vertical:
            return
        self._payload["flip_vertical"] = value
        self._payload["flip_v"] = value
        self._slide._presentation._queue_shape_flip(
            self._slide._index,
            _shape_edit_ref(self),
            "v",
            value,
        )

    @property
    def fill(self) -> FillFormat:
        return FillFormat(self)

    @property
    def line(self) -> LineFormat:
        return LineFormat(self)

    @property
    def shadow(self) -> ShadowFormat:
        return ShadowFormat(self)

    @property
    def three_d(self) -> ThreeDFormat:
        """Read and edit this shape's ``a:scene3d`` and ``a:sp3d`` (3-D format).

        Camera, light rig, backdrop, bevels, extrusion, contour, material and depth;
        see :mod:`wolfppt.shape_3d_format`. Available on shapes, connectors and
        pictures; any other kind raises ``AttributeError``. Reads cover Transitional
        and Strict decks; edits refuse Strict shapes with ``ThreeDFormatRefusal``.
        """
        if self._payload.get("kind") not in {"connector", "shape", "picture", "freeform"}:
            raise AttributeError("'Shape' object has no attribute 'three_d'")
        from .shape_3d_format import ThreeDFormat

        return ThreeDFormat(self)

    @property
    def locks(self) -> ShapeLocks:
        from .shape_locks import ShapeLocks

        return ShapeLocks(self)

    @property
    def glow(self) -> GlowSpec | None:
        from .shape_glow_edits import get_shape_glow

        return get_shape_glow(self)

    @glow.setter
    def glow(self, value: Any) -> None:
        if value is None:
            self.clear_glow()
        else:
            self.set_glow(value)

    def set_glow(
        self,
        spec: GlowSpec | Mapping[str, Any],
    ) -> None:
        from .shape_glow_edits import (
            _assert_shape_editable,
            validate_glow_spec,
        )

        _assert_shape_editable(self)
        validated = validate_glow_spec(spec)
        if validated is None:
            self.clear_glow()
            return

        current = self.glow
        if current == validated:
            return

        self._payload["glow"] = validated
        prs = self._slide._presentation
        ref = _shape_edit_ref(self)
        slide_idx = self._slide._index
        prs._queue_shape_glow(slide_idx, ref, validated.to_dict())

    def clear_glow(self) -> None:
        from .shape_glow_edits import _assert_shape_editable

        _assert_shape_editable(self)
        current = self.glow
        if current is None:
            return

        self._payload["glow"] = "__cleared__"
        prs = self._slide._presentation
        ref = _shape_edit_ref(self)
        slide_idx = self._slide._index
        prs._queue_shape_glow(slide_idx, ref, None)

    @property
    def soft_edge(self) -> SoftEdgeSpec | None:
        return self.shadow.soft_edge

    @soft_edge.setter
    def soft_edge(self, value: Any) -> None:
        if value is None:
            self.clear_soft_edge()
        else:
            self.set_soft_edge(value)

    def set_soft_edge(
        self,
        radius: int | SoftEdgeSpec | Mapping[str, Any],
    ) -> None:
        """Set ``a:softEdge``; ``radius`` is an EMU length or a soft-edge spec."""
        from .shape_shadow_edits import (
            SoftEdgeSpec,
            _assert_shape_editable,
            _supports_shape_shadow,
            _validate_advanced_effect,
        )

        _assert_shape_editable(self)
        if not _supports_shape_shadow(self):
            raise ValueError(f"soft edge is not supported on {self._payload.get('kind')!r} shapes")
        if isinstance(radius, int) and not isinstance(radius, bool):
            spec: SoftEdgeSpec | Mapping[str, Any] = {"radius": radius}
        elif isinstance(radius, SoftEdgeSpec | Mapping):
            spec = radius
        else:
            raise TypeError(
                "soft edge must be an EMU int, SoftEdgeSpec, Mapping, or None; "
                f"got {type(radius).__name__}"
            )
        validated = _validate_advanced_effect("soft_edge", spec)
        assert validated is not None
        if self.soft_edge == validated:
            return
        self.shadow.soft_edge = validated

    def clear_soft_edge(self) -> None:
        # Queuing a clear for an absent effect would author an empty
        # a:effectLst, which suppresses theme effects inherited via effectRef.
        if self.soft_edge is None:
            return
        self.shadow.soft_edge = None

    @property
    def click_action(self) -> ActionSetting:
        from .shape_action_facade import ActionSetting

        return ActionSetting(self)

    @property
    def has_text_frame(self) -> bool:
        return self._payload.get("kind") in {"shape", "freeform"}

    @property
    def has_picture(self) -> bool:
        return bool(self._payload.get("has_picture")) or self._payload.get("kind") == "picture"

    @property
    def signature_line(self) -> Any:
        """Signature-line metadata on this picture, or None for an unsigned picture."""
        from .signature_lines import SignatureLines

        if not self.has_picture:
            raise AttributeError("signature_line requires a picture")
        return SignatureLines(self._slide).for_picture(self)

    @property
    def image(self) -> PictureImage:
        return _picture_image(self)

    def replace_image(self, image_file: Any) -> PictureImage:
        return _replace_picture_image(self, image_file)

    @property
    def media_format(self) -> MediaFormat:
        return _shape_media_format(self)

    @property
    def media_type(self) -> Any:
        return _shape_media_type(self)

    @property
    def poster_frame(self) -> PictureImage:
        return _shape_poster_frame(self)

    @property
    def crop_left(self) -> float:
        return _picture_crop_value(self, "l")

    @crop_left.setter
    def crop_left(self, value: Any) -> None:
        _set_picture_crop_value(self, "l", value)

    @property
    def crop_right(self) -> float:
        return _picture_crop_value(self, "r")

    @crop_right.setter
    def crop_right(self, value: Any) -> None:
        _set_picture_crop_value(self, "r", value)

    @property
    def crop_top(self) -> float:
        return _picture_crop_value(self, "t")

    @crop_top.setter
    def crop_top(self, value: Any) -> None:
        _set_picture_crop_value(self, "t", value)

    @property
    def crop_bottom(self) -> float:
        return _picture_crop_value(self, "b")

    @crop_bottom.setter
    def crop_bottom(self, value: Any) -> None:
        _set_picture_crop_value(self, "b", value)

    @property
    def image_transforms(self) -> Any:
        """Live ordered DrawingML image effects; raw OOXML attribute units."""
        from .shape_picture_recolor_edits import ImageTransformCollection

        return ImageTransformCollection(self)

    @property
    def picture_transparency(self) -> float:
        from .shape_picture_recolor_edits import get_picture_component

        return get_picture_component(self, "transparency")

    @picture_transparency.setter
    def picture_transparency(self, value: Any) -> None:
        from .shape_picture_recolor_edits import set_picture_component

        set_picture_component(self, "transparency", value)

    @property
    def picture_brightness(self) -> float:
        from .shape_picture_recolor_edits import get_picture_component

        return get_picture_component(self, "brightness")

    @picture_brightness.setter
    def picture_brightness(self, value: Any) -> None:
        from .shape_picture_recolor_edits import set_picture_component

        set_picture_component(self, "brightness", value)

    @property
    def picture_contrast(self) -> float:
        from .shape_picture_recolor_edits import get_picture_component

        return get_picture_component(self, "contrast")

    @picture_contrast.setter
    def picture_contrast(self, value: Any) -> None:
        from .shape_picture_recolor_edits import set_picture_component

        set_picture_component(self, "contrast", value)

    @property
    def has_table(self) -> bool:
        return bool(self._payload.get("tables"))

    @property
    def has_chart(self) -> bool:
        return bool(self._payload.get("has_chart"))

    @property
    def has_smartart(self) -> bool:
        if bool(self._payload.get("has_smartart")):
            return True
        return _smartart_data_partname(self) is not None

    @property
    def smartart(self) -> SmartArt:
        if not self.has_smartart:
            raise AttributeError("shape does not have SmartArt")
        return SmartArt(self)

    @property
    def is_placeholder(self) -> bool:
        return bool(self._payload.get("is_placeholder"))

    @property
    def placeholder_format(self) -> PlaceholderFormat:
        if not self.is_placeholder:
            raise ValueError("shape is not a placeholder")
        from .shape_action_facade import PlaceholderFormat

        return PlaceholderFormat(self)

    def insert_picture(self, image_file: Any) -> Shape:
        """Fill this unfilled slide placeholder with an image cropped to fit.

        ``image_file`` may be a path, a binary file-like object, or bytes.
        Returns the placeholder picture that replaces this shape.
        """
        from .shape_placeholder_collections import insert_placeholder_picture

        return insert_placeholder_picture(self, image_file)

    def insert_table(self, rows: int, cols: int) -> Shape:
        """Fill this unfilled slide placeholder with an empty table.

        Returns the placeholder graphic frame that replaces this shape; its
        ``table`` property exposes the new table.
        """
        from .shape_placeholder_collections import insert_placeholder_table

        return insert_placeholder_table(self, rows, cols)

    @property
    def table(self) -> Table:
        tables = self._payload.get("tables") or []
        if not tables:
            raise AttributeError("shape does not have a table")
        from .table_facade import Table

        return Table(self._slide, self._table_index, tables[0])

    @property
    def chart(self) -> Chart:
        if not self.has_chart:
            raise AttributeError("shape does not have a chart")
        from .chart_facade import Chart

        return Chart(self)

    @property
    def chart_part(self) -> PackagePart:
        if not self.has_chart:
            raise ValueError("this graphic frame does not contain a chart")
        from .shape_ole_facade import _shape_related_partname

        partname = _shape_related_partname(self, "/chart")
        if partname is None:
            partname = _shape_related_partname(self, "/chartEx")
        if partname is None:
            raise ValueError("this graphic frame does not contain a chart")
        return PackagePart(self._slide._presentation, partname, None)

    @property
    def ole_format(self) -> OleFormat:
        if self._payload.get("kind") != "ole_object":
            raise ValueError("not an OLE-object shape")
        from .shape_ole_facade import OleFormat

        return OleFormat(self)

    @property
    def shapes(self) -> GroupShapeCollection:
        if self._payload.get("kind") != "group":
            raise AttributeError("'Shape' object has no attribute 'shapes'")
        shapes = getattr(self, "_group_shapes", None)
        if shapes is None:
            from .shape_group_collection_facade import GroupShapeCollection

            shapes = GroupShapeCollection(self)
            self._group_shapes = shapes
        return shapes

    @property
    def text(self) -> str:
        return str(self._payload.get("text") or "")

    @text.setter
    def text(self, value: str) -> None:
        if not self.has_text_frame:
            raise AttributeError("shape does not have a text frame")
        text = str(value)
        check_shape_locks(self, "text edit", "no_text_edit")
        paragraphs = text.split("\n") if text else [""]
        # A vertical tab is a soft line break (a:br), as in python-pptx; it
        # separates runs and never reaches a:t as a raw control character.
        parsed = [_paragraph_runs_and_line_breaks(paragraph) for paragraph in paragraphs]
        self._payload["text"] = text
        self._payload["paragraphs"] = paragraphs
        self._payload["paragraph_runs"] = [runs for runs, _ in parsed]
        self._payload["paragraph_line_breaks"] = [line_breaks for _, line_breaks in parsed]
        from .shape_group_text_queue import queue_pending_group_child_text

        if queue_pending_group_child_text(self, text):
            return
        presentation = self._slide._presentation
        presentation._queue_shape_text_for_shape(self, text)
        if "\v" in text:
            from .text_facade_queue import (
                _is_group_child_text_shape,
                _is_part_scoped_text_shape,
                _queue_pending_shape_text,
            )

            if _is_part_scoped_text_shape(self) or _is_group_child_text_shape(self):
                return

            _queue_pending_shape_text(self)

    @property
    def text_frame(self) -> TextFrame:
        if not self.has_text_frame:
            raise AttributeError("shape does not have a text frame")
        from .text_facade import TextFrame

        return TextFrame(self)

    def bring_to_front(self) -> None:
        from .shape_z_order_edits import bring_to_front

        bring_to_front(self)

    def send_to_back(self) -> None:
        from .shape_z_order_edits import send_to_back

        send_to_back(self)

    def bring_forward(self) -> None:
        from .shape_z_order_edits import bring_forward

        bring_forward(self)

    def send_backward(self) -> None:
        from .shape_z_order_edits import send_backward

        send_backward(self)
