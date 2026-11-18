"""Dispatch native shape-add operations."""

from __future__ import annotations

import hashlib
import uuid
import zipfile
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import native
from .chart_adds import (
    _ensure_content_type_default,
    _ensure_content_type_override,
    _insert_shape_tree_child,
    _next_numbered_part,
    _presentation_part,
    _presentation_slide_parts,
    _relationships_by_id,
    _relationships_root,
    _relative_package_target,
    _slide_shape_tree,
)
from .group_shape_edits import (
    apply_existing_deeper_nested_group_child_grouping,
    apply_existing_group_child_grouping,
    apply_existing_nested_group_child_grouping,
    apply_existing_shape_grouping,
)
from .image_inputs import image_extension_from_blob, image_input_bytes
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .section_xml import read_sections_from_element
from .shape_adds_freeform import apply_freeform_shape_add
from .shape_adds_group_connectors import apply_group_connector_shape_add
from .shape_adds_group_media import apply_group_media_shape_add
from .shape_adds_media_chart import apply_media_or_chart_shape_add
from .shape_connector_adds import (
    coalesce_connected_connector_auto_shapes,  # noqa: F401 - presentation facade reexport
)
from .shape_xml import (
    _SLIDE_REL_TYPE,
    _next_relationship_id,
    register_zoom_namespaces,
    slide_creation_id,
    zoom_alternate_content,
)
from .xml_helpers import content_types_xml as _content_types_xml

ChartAddFn = Callable[..., None]
ShapeAdd = tuple[str, tuple[Any, ...]]
ShapeTextEdit = tuple[tuple[int, int], str]
TableCellTextEdit = tuple[tuple[int, int, int, int], str]
ShapeRef = int | tuple[int, int]
ShapeAdjustmentEdit = tuple[tuple[int, ShapeRef], list[tuple[str, int]]]


def coalesce_auto_shape_text(
    shape_adds: list[ShapeAdd],
    text_edits: list[ShapeTextEdit],
) -> tuple[list[ShapeAdd], list[ShapeTextEdit]]:
    text_by_shape = dict(text_edits)
    consumed: set[tuple[int, int]] = set()
    coalesced: list[ShapeAdd] = []
    for add_kind, args in shape_adds:
        if add_kind == "auto_shape":
            slide_index, shape_index, *_ = args
            key = (slide_index, shape_index)
            if key in text_by_shape:
                coalesced.append((add_kind, (*args, text_by_shape[key])))
                consumed.add(key)
                continue
        if add_kind == "freeform_shape":
            slide_index, shape_index, *_ = args
            key = (slide_index, shape_index)
            if key in text_by_shape:
                coalesced.append((add_kind, (*args, text_by_shape[key])))
                consumed.add(key)
                continue
        if add_kind == "text_box":
            slide_index, _x_emu, _y_emu, _cx_emu, _cy_emu, shape_index = args
            key = (slide_index, shape_index)
            if key in text_by_shape:
                coalesced.append((add_kind, (*args, text_by_shape[key])))
                consumed.add(key)
                continue
        coalesced.append((add_kind, args))
    remaining_text_edits = [(key, text) for key, text in text_edits if key not in consumed]
    return coalesced, remaining_text_edits


def coalesce_table_cell_text(
    shape_adds: list[ShapeAdd],
    table_cell_edits: list[TableCellTextEdit],
) -> tuple[list[ShapeAdd], list[TableCellTextEdit]]:
    edits_by_table: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    for (slide_index, table_index, row_index, col_index), text in table_cell_edits:
        edits_by_table.setdefault((slide_index, table_index), []).append(
            (row_index, col_index, text)
        )

    consumed: set[tuple[int, int]] = set()
    coalesced: list[ShapeAdd] = []
    for add_kind, args in shape_adds:
        if add_kind == "table":
            slide_index, table_index, *_ = args
            key = (slide_index, table_index)
            if key in edits_by_table:
                coalesced.append((add_kind, (*args, edits_by_table[key])))
                consumed.add(key)
                continue
        coalesced.append((add_kind, args))

    remaining_table_cell_edits = [
        (key, text) for key, text in table_cell_edits if (key[0], key[1]) not in consumed
    ]
    return coalesced, remaining_table_cell_edits


def coalesce_auto_shape_adjustments(
    shape_adds: list[ShapeAdd],
    adjustment_edits: list[ShapeAdjustmentEdit],
) -> tuple[list[ShapeAdd], list[ShapeAdjustmentEdit]]:
    adjustments_by_shape = dict(adjustment_edits)
    consumed: set[tuple[int, int]] = set()
    coalesced: list[ShapeAdd] = []
    for add_kind, args in shape_adds:
        if add_kind == "auto_shape":
            slide_index, shape_index, *_ = args
            key = (slide_index, shape_index)
            if key in adjustments_by_shape:
                coalesced.append((add_kind, (*args, adjustments_by_shape[key])))
                consumed.add(key)
                continue
        coalesced.append((add_kind, args))
    remaining_adjustment_edits = [
        (key, guides) for key, guides in adjustment_edits if key not in consumed
    ]
    return coalesced, remaining_adjustment_edits


def apply_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
    apply_chart_add: ChartAddFn,
    *,
    transition_duration: Any = None,
    show_background: Any = None,
) -> None:
    if add_kind not in {"slide_zoom", "section_zoom"} and (
        transition_duration is not None or show_background is not None
    ):
        raise TypeError("transition_duration and show_background apply only to zoom shape adds")
    if apply_media_or_chart_shape_add(add_kind, args, current, step, apply_chart_add):
        return
    if apply_group_connector_shape_add(add_kind, args, current, step):
        return
    if apply_group_media_shape_add(add_kind, args, current, step):
        return
    if apply_freeform_shape_add(add_kind, args, current, step):
        return
    if add_kind in {"placeholder_picture", "placeholder_table"}:
        from .shape_placeholder_collections import apply_placeholder_insert

        apply_placeholder_insert(add_kind, args, current, step)
        return
    if add_kind == "smartart":
        _apply_smartart_add(current, step, args)
        return
    if add_kind == "smartart_update":
        _apply_smartart_update(current, step, args)
        return
    if add_kind == "smartart_part_update":
        _apply_smartart_part_update(current, step, args)
        return
    if add_kind == "smartart_remove":
        _apply_smartart_remove(current, step, args)
        return
    if add_kind == "smartart_move":
        _apply_smartart_move(current, step, args)
        return
    if add_kind in {"slide_zoom", "section_zoom"}:
        _apply_zoom_add(
            current,
            step,
            add_kind,
            args,
            transition_duration=transition_duration,
            show_background=show_background,
        )
        return
    if add_kind == "text_box":
        slide_index, x_emu, y_emu, cx_emu, cy_emu, *_shape_index_and_text = args
        text = _shape_index_and_text[1:] if len(_shape_index_and_text) > 1 else ()
        if text:
            native.add_text_box_with_text(
                current,
                step,
                slide_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                text[0],
            )
        else:
            native.add_text_box(
                current,
                step,
                slide_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        return
    if add_kind == "group_text_box":
        (
            slide_index,
            group_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_group_text_box_with_text(
            current,
            step,
            slide_index,
            group_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_text_box":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_text_box_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_text_box_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_text_box_in_new_group_with_text(
            current,
            step,
            slide_index,
            group_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "deeper_nested_group_text_box":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_deeper_nested_group_text_box_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "group_auto_shape":
        (
            slide_index,
            group_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
            *_shape_id_tail,
        ) = args
        native.add_group_auto_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_auto_shape":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_auto_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "deeper_nested_group_auto_shape":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_deeper_nested_group_auto_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_auto_shape_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_auto_shape_in_new_group_with_text(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "group_shape":
        (slide_index,) = args
        native.add_group_shape(current, step, slide_index)
        return
    if add_kind == "group_existing_shapes":
        slide_index, shape_indices = args
        apply_existing_shape_grouping(current, step, slide_index, tuple(shape_indices))
        return
    if add_kind == "group_existing_child_shapes":
        slide_index, group_index, child_indices = args
        apply_existing_group_child_grouping(
            current,
            step,
            slide_index,
            group_index,
            tuple(child_indices),
        )
        return
    if add_kind == "group_existing_nested_child_shapes":
        slide_index, group_index, nested_group_child_index, child_indices = args
        apply_existing_nested_group_child_grouping(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            tuple(child_indices),
        )
        return
    if add_kind == "group_existing_deeper_nested_child_shapes":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            child_indices,
        ) = args
        apply_existing_deeper_nested_group_child_grouping(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            tuple(child_indices),
        )
        return
    if add_kind == "nested_group_shape":
        slide_index, group_index, _child_index = args
        native.add_nested_group_shape(current, step, slide_index, group_index)
        return
    if add_kind == "group_shape_to_nested_group":
        slide_index, group_index, nested_group_child_index, _child_index = args
        native.add_group_shape_to_nested_group(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
        )
        return
    if add_kind == "group_shape_to_deeper_nested_group":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
        ) = args
        native.add_group_shape_to_deeper_nested_group(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
        return
    if add_kind == "placeholder_shape":
        (
            slide_index,
            _shape_index,
            placeholder_type,
            placeholder_orient,
            placeholder_size,
            placeholder_idx,
        ) = args
        native.add_placeholder_shape(
            current,
            step,
            slide_index,
            placeholder_type,
            placeholder_orient,
            placeholder_size,
            placeholder_idx,
        )
        return
    if add_kind == "placeholder_shapes":
        slide_index, placeholders = args
        native.add_placeholder_shapes(
            current,
            step,
            slide_index,
            placeholders,
        )
        return
    if add_kind == "layout_placeholders":
        slide_index, layout_index = args
        native.add_layout_placeholders(
            current,
            step,
            slide_index,
            layout_index,
        )
        return
    if add_kind == "auto_shape":
        (
            slide_index,
            _shape_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            *extras,
        ) = args
        text = next((extra for extra in extras if isinstance(extra, str)), None)
        adjustment_guides = next(
            (extra for extra in extras if isinstance(extra, list)),
            [],
        )
        if adjustment_guides:
            native.add_auto_shape_with_options(
                current,
                step,
                slide_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                text,
                adjustment_guides,
            )
        elif text is not None:
            native.add_auto_shape_with_text(
                current,
                step,
                slide_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                text,
            )
        else:
            native.add_auto_shape(
                current,
                step,
                slide_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        return
    if add_kind == "connector":
        (
            slide_index,
            _shape_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ) = args
        native.add_connector(
            current,
            step,
            slide_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        return
    if add_kind == "connected_connector":
        (
            slide_index,
            _shape_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            begin_connection,
            end_connection,
        ) = args
        native.add_connected_connector(
            current,
            step,
            slide_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            begin_connection,
            end_connection,
        )
        return
    if add_kind == "connected_connector_with_auto_shapes":
        (
            slide_index,
            _begin_shape_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            _end_shape_index,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            _connector_shape_index,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        ) = args
        native.add_connected_connector_with_auto_shapes(
            current,
            step,
            slide_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        )
        return
    raise ValueError(f"unknown shape add kind: {add_kind}")


DGM_NS = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_SMARTART_LAYOUTS = frozenset(
    {
        "process",
        "basicprocess",
        "continuingprocess",
        "hierarchy",
        "organizationchart",
        "orgchart",
        "cycle",
        "radialcycle",
        "basiccycle",
        "pyramid",
        "basicpyramid",
    }
)
_SMARTART_PARTS = (
    (
        "data",
        "diagramData",
        "application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml",
    ),
    (
        "layout",
        "diagramLayout",
        "application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml",
    ),
    (
        "quickStyle",
        "diagramQuickStyle",
        "application/vnd.openxmlformats-officedocument.drawingml.diagramStyle+xml",
    ),
    (
        "colors",
        "diagramColors",
        "application/vnd.openxmlformats-officedocument.drawingml.diagramColors+xml",
    ),
)


def _apply_smartart_add(current: Path, step: Path, args: tuple[Any, ...]) -> None:
    (
        slide_index,
        _shape_index,
        shape_id,
        layout_type,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        raw_nodes,
    ) = args
    layout = _smartart_layout(layout_type)
    nodes = _smartart_nodes(raw_nodes)
    with zipfile.ZipFile(current) as package:
        names = set(package.namelist())
        slides = _presentation_slide_parts(package)
        if not isinstance(slide_index, int) or not 0 <= slide_index < len(slides):
            raise IndexError("SmartArt slide index is out of range")
        slide_part = slides[slide_index]
        slide_root = ET.fromstring(package.read(slide_part))
        slide_rels_part = _rels_part_for_package_part(slide_part)
        slide_rels = _relationships_root(package, slide_rels_part)
        content_types = ET.fromstring(package.read("[Content_Types].xml"))
        part_names: dict[str, str] = {}
        relationship_ids: dict[str, str] = {}
        replacements: dict[str, bytes] = {}
        for prefix, relationship_suffix, content_type in _SMARTART_PARTS:
            part = _next_numbered_part(names, f"ppt/diagrams/{prefix}", ".xml")
            names.add(part)
            relationship_id = _next_relationship_id(slide_rels)
            part_names[prefix] = part
            relationship_ids[prefix] = relationship_id
            slide_rels.append(
                ET.Element(
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": relationship_id,
                        "Type": (
                            "http://schemas.openxmlformats.org/officeDocument/"
                            f"2006/relationships/{relationship_suffix}"
                        ),
                        "Target": _relative_package_target(slide_part, part),
                    },
                )
            )
            _ensure_content_type_override(content_types, part, content_type)
        frame = _smartart_graphic_frame(
            _required_int(shape_id, "shape_id"),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            relationship_ids,
        )
        _insert_shape_tree_child(_slide_shape_tree(slide_root), frame)
        replacements[part_names["data"]] = _smartart_data_xml(nodes)
        replacements[part_names["layout"]] = _smartart_layout_xml(layout, nodes)
        replacements[part_names["quickStyle"]] = _smartart_quick_style_xml(nodes)
        replacements[part_names["colors"]] = _smartart_colors_xml(nodes)
        replacements[slide_part] = ET.tostring(slide_root, encoding="utf-8", xml_declaration=True)
        replacements[slide_rels_part] = ET.tostring(
            slide_rels, encoding="utf-8", xml_declaration=True
        )
        replacements["[Content_Types].xml"] = _content_types_xml(content_types)
    _copy_package_with_replacements(current, step, replacements)


def _apply_smartart_update(current: Path, step: Path, args: tuple[Any, ...]) -> None:
    """Apply text and node additions to the existing authored data model."""
    from .chart_workbook import serialize_xml_preserving_namespaces

    slide_index, shape_id, raw_nodes = args
    nodes = _smartart_nodes(raw_nodes)
    with zipfile.ZipFile(current) as package:
        slide_part = _presentation_slide_parts(package)[slide_index]
        data_part = _smartart_partname(package, slide_part, shape_id, "data")
        original = package.read(data_part)
        root = _smartart_xml(original, "data")
    namespace = root.tag.removesuffix("dataModel")
    a_namespace = (
        "{http://purl.oclc.org/ooxml/drawingml/main}"
        if namespace == f"{{{_STRICT_DGM_NS}}}"
        else f"{{{A_NS}}}"
    )
    points = root.find(f"{namespace}ptLst")
    connections = root.find(f"{namespace}cxnLst")
    if points is None or connections is None:
        raise ValueError("SmartArt diagramData has no point or connection list")
    by_id = {point.get("modelId"): point for point in points}
    used_ids = {item.get("modelId") for item in root.iter()}
    used_ids.update(node["id"] for node in nodes)
    document_id = next((p.get("modelId") for p in points if p.get("type") == "doc"), None)
    connection_id = 1
    for node in nodes:
        point = by_id.get(node["id"])
        if point is None:
            point = ET.SubElement(points, f"{namespace}pt", {"modelId": node["id"], "type": "node"})
            ET.SubElement(point, f"{namespace}prSet")
            ET.SubElement(point, f"{namespace}spPr")
            parent = node["parent"] if node["parent"] is not None else document_id
            if parent is not None:
                while str(connection_id) in used_ids:
                    connection_id += 1
                used_ids.add(str(connection_id))
                siblings = [
                    int(c.get("srcOrd", "0"))
                    for c in connections
                    if c.get("type", "parOf") == "parOf" and c.get("srcId") == parent
                ]
                ET.SubElement(
                    connections,
                    f"{namespace}cxn",
                    {
                        "modelId": str(connection_id),
                        "type": "parOf",
                        "srcId": parent,
                        "destId": node["id"],
                        "srcOrd": str(max(siblings, default=-1) + 1),
                        "destOrd": "0",
                    },
                )
        text_body = point.find(f"{namespace}t")
        texts = [] if text_body is None else text_body.findall(f".//{a_namespace}t")
        if text_body is not None and "".join(t.text or "" for t in texts) == node["text"]:
            continue
        if text_body is None:
            text_body = ET.SubElement(point, f"{namespace}t")
            ET.SubElement(text_body, f"{a_namespace}bodyPr")
            ET.SubElement(text_body, f"{a_namespace}lstStyle")
        if not texts:
            paragraph = text_body.find(f"{a_namespace}p")
            if paragraph is None:
                paragraph = ET.SubElement(text_body, f"{a_namespace}p")
            run = ET.SubElement(paragraph, f"{a_namespace}r")
            texts = [ET.SubElement(run, f"{a_namespace}t")]
        # Keep authored paragraph/run properties, including the first run's style.
        texts[0].text = node["text"]
        for text in texts[1:]:
            text.text = ""
    _copy_package_with_replacements(
        current, step, {data_part: serialize_xml_preserving_namespaces(root, original)}
    )


_SMARTART_DEFINITION_PARTS = {
    "data": ("dm", "diagramData", "dataModel"),
    "layout": ("lo", "diagramLayout", "layoutDef"),
    "quickStyle": ("qs", "diagramQuickStyle", "styleDef"),
    "colors": ("cs", "diagramColors", "colorsDef"),
}
_STRICT_DGM_NS = "http://purl.oclc.org/ooxml/drawingml/diagram"
_DSP_NS = "http://schemas.microsoft.com/office/drawing/2008/diagram"


def _smartart_find(root: ET.Element, path: str) -> ET.Element | None:
    """Query only the two OOXML namespace profiles, preserving source tags."""
    found = root.find(path)
    if found is not None:
        return found
    for old, new in (
        (P_NS, "http://purl.oclc.org/ooxml/presentationml/main"),
        (A_NS, "http://purl.oclc.org/ooxml/drawingml/main"),
        (DGM_NS, _STRICT_DGM_NS),
    ):
        path = path.replace(f"{{{old}}}", f"{{{new}}}")
    return root.find(path)


def _smartart_partname(package: Any, slide_part: str, shape_id: int, kind: str) -> str:
    frame = _smartart_frame_by_id(ET.fromstring(package.read(slide_part)), shape_id)
    rel_ids = _smartart_find(frame, f".//{{{DGM_NS}}}relIds")
    if rel_ids is None:
        raise ValueError("shape does not contain SmartArt relationship identifiers")
    source_part = slide_part
    if kind == "drawing":
        data_part = _smartart_partname(package, slide_part, shape_id, "data")
        data = _smartart_xml(package.read(data_part), "data")
        extension = data.find(f".//{{{_DSP_NS}}}dataModelExt")
        relationship_id = None if extension is None else extension.get("relId")
        suffix = "/diagramDrawing"
        data_rels = _relationships_root(package, _rels_part_for_package_part(data_part))
        if any(item.get("Id") == relationship_id for item in data_rels):
            source_part = data_part
    else:
        attr, rel_type, _root = _SMARTART_DEFINITION_PARTS[kind]
        relationship_id = rel_ids.get(f"{{{R_NS}}}{attr}") or rel_ids.get(
            f"{{http://purl.oclc.org/ooxml/officeDocument/relationships}}{attr}"
        )
        suffix = f"/{rel_type}"
    if not relationship_id:
        raise ValueError(f"SmartArt {kind} relationship is missing")
    relationships = _relationships_root(package, _rels_part_for_package_part(source_part))
    relationship = next((item for item in relationships if item.get("Id") == relationship_id), None)
    if (
        relationship is None
        or not relationship.get("Type", "").endswith(suffix)
        or relationship.get("TargetMode") == "External"
    ):
        raise ValueError(f"SmartArt {kind} relationship is unavailable")
    part = _resolve_package_target(source_part, relationship.get("Target", ""))
    if part not in package.namelist():
        raise ValueError(f"SmartArt {kind} part is missing")
    return part


def _smartart_xml(blob: bytes, kind: str) -> ET.Element:
    if not isinstance(blob, bytes):
        raise TypeError(f"SmartArt {kind} XML must be bytes")
    try:
        root = ET.fromstring(
            blob, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        )
    except ET.ParseError as exc:
        name = "diagramData" if kind == "data" else kind
        raise ValueError(f"malformed SmartArt {name} XML") from exc
    name = "drawing" if kind == "drawing" else _SMARTART_DEFINITION_PARTS[kind][2]
    namespaces = (_DSP_NS,) if kind == "drawing" else (DGM_NS, _STRICT_DGM_NS)
    if root.tag not in {f"{{{namespace}}}{name}" for namespace in namespaces}:
        raise ValueError(f"SmartArt {kind} XML must have a {name} root")
    return root


def _apply_smartart_part_update(current: Path, step: Path, args: tuple[Any, ...]) -> None:
    slide_index, shape_id, kind, blob = args
    replacement = _smartart_xml(blob, kind)
    with zipfile.ZipFile(current) as package:
        slide_part = _presentation_slide_parts(package)[slide_index]
        part = _smartart_partname(package, slide_part, shape_id, kind)
        original = _smartart_xml(package.read(part), kind)
        if replacement.tag != original.tag:
            raise ValueError("SmartArt definition replacement must retain its namespace profile")
    _copy_package_with_replacements(current, step, {part: blob})


def _apply_smartart_remove(current: Path, step: Path, args: tuple[Any, ...]) -> None:
    slide_index, shape_id, removed_ids = args
    from .chart_workbook import serialize_xml_preserving_namespaces

    removed = set(removed_ids)
    with zipfile.ZipFile(current) as package:
        slide_part = _presentation_slide_parts(package)[slide_index]
        part = _smartart_partname(package, slide_part, shape_id, "data")
        original = package.read(part)
        root = _smartart_xml(original, "data")
    namespace = root.tag.removesuffix("dataModel")
    points = root.find(f"{namespace}ptLst")
    connections = root.find(f"{namespace}cxnLst")
    if points is None or connections is None:
        raise ValueError("SmartArt diagramData has no point or connection list")
    # Transition points identify their owning connection with @cxnId. Connections
    # also refer to transitions and presentation points directly.
    while True:
        old_size = len(removed)
        for connection in connections:
            if connection.get("srcId") in removed or connection.get("destId") in removed:
                removed.update(
                    value
                    for key in ("modelId", "parTransId", "sibTransId")
                    if (value := connection.get(key))
                )
                if connection.get("type") == "presOf" and connection.get("destId"):
                    removed.add(connection.get("destId"))
        for point in points:
            if point.get("cxnId") in removed and point.get("modelId"):
                removed.add(point.get("modelId"))
        if len(removed) == old_size:
            break
    for point in list(points):
        if point.get("modelId") in removed:
            points.remove(point)
    for connection in list(connections):
        if connection.get("modelId") in removed:
            connections.remove(connection)
    _copy_package_with_replacements(
        current, step, {part: serialize_xml_preserving_namespaces(root, original)}
    )


def _apply_smartart_move(current: Path, step: Path, args: tuple[Any, ...]) -> None:
    """Change node order and parent links without rebuilding authored points."""
    from .chart_workbook import serialize_xml_preserving_namespaces

    slide_index, shape_id, node_id, parent_id, nodes = args
    with zipfile.ZipFile(current) as package:
        slide_part = _presentation_slide_parts(package)[slide_index]
        part = _smartart_partname(package, slide_part, shape_id, "data")
        original = package.read(part)
        root = _smartart_xml(original, "data")
    namespace = root.tag.removesuffix("dataModel")
    points = root.find(f"{namespace}ptLst")
    connections = root.find(f"{namespace}cxnLst")
    if points is None or connections is None:
        raise ValueError("SmartArt diagramData has no point or connection list")
    by_id = {point.get("modelId"): point for point in points}
    ordered = iter(by_id[node["id"]] for node in nodes)
    node_ids = {node["id"] for node in nodes}
    points[:] = [next(ordered) if p.get("modelId") in node_ids else p for p in points]
    document_id = next((p.get("modelId") for p in points if p.get("type") == "doc"), None)
    source_id = parent_id if parent_id is not None else document_id
    incoming = [
        c for c in connections if c.get("type", "parOf") == "parOf" and c.get("destId") == node_id
    ]
    if source_id is None:
        for connection in incoming:
            connections.remove(connection)
    elif incoming:
        for connection in incoming:
            connection.set("srcId", source_id)
    else:
        used_ids = {p.get("modelId") for p in points} | {c.get("modelId") for c in connections}
        connection_id = 1
        while str(connection_id) in used_ids:
            connection_id += 1
        connections.append(
            ET.Element(
                f"{namespace}cxn",
                {
                    "modelId": str(connection_id),
                    "type": "parOf",
                    "srcId": source_id,
                    "destId": node_id,
                    "srcOrd": "0",
                    "destOrd": "0",
                },
            )
        )
    sibling_indices: dict[str | None, int] = {}
    order = {}
    for node in nodes:
        parent = node["parent"] if node["parent"] is not None else document_id
        order[node["id"]] = sibling_indices.get(parent, 0)
        sibling_indices[parent] = order[node["id"]] + 1
    for connection in connections:
        if connection.get("type", "parOf") == "parOf" and connection.get("destId") in order:
            connection.set("srcOrd", str(order[connection.get("destId")]))
    _copy_package_with_replacements(
        current, step, {part: serialize_xml_preserving_namespaces(root, original)}
    )


def _smartart_layout(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("layout_type must be a string")
    normalized = value.replace("_", "").replace("-", "").replace(" ", "").casefold()
    if normalized not in _SMARTART_LAYOUTS:
        supported = ", ".join(sorted(_SMARTART_LAYOUTS))
        raise ValueError(f"unsupported SmartArt layout {value!r}; supported: {supported}")
    return normalized


def _smartart_nodes(value: Any) -> list[dict[str, str | None]]:
    if not isinstance(value, list) or not value:
        raise ValueError("SmartArt requires at least one node")
    nodes: list[dict[str, str | None]] = []
    node_ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise TypeError(f"SmartArt node {index} must be a mapping")
        node_id = raw.get("id")
        text = raw.get("text", "")
        parent = raw.get("parent")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"SmartArt node {index} has no id")
        if not _is_model_id(node_id):
            raise ValueError(f"SmartArt node id {node_id!r} is not an OOXML model id")
        if node_id in node_ids:
            raise ValueError(f"SmartArt node id {node_id!r} is duplicated")
        if not isinstance(text, str):
            raise TypeError(f"SmartArt node {node_id!r} text must be a string")
        if parent is not None and not isinstance(parent, str):
            raise TypeError(f"SmartArt node {node_id!r} parent must be a string or None")
        node_ids.add(node_id)
        nodes.append({"id": node_id, "text": text, "parent": parent})
    for node in nodes:
        parent = node["parent"]
        if parent is not None and parent not in node_ids:
            raise ValueError(f"SmartArt node {node['id']!r} has an unknown parent")
        if parent == node["id"]:
            raise ValueError(f"SmartArt node {node['id']!r} cannot parent itself")
    return nodes


def _is_model_id(value: str) -> bool:
    if value.isdecimal():
        return True
    try:
        uuid.UUID(value.strip("{}"))
    except ValueError:
        return False
    return True


def _required_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _smartart_frame_by_id(root: ET.Element, shape_id: int) -> ET.Element:
    for frame in root.iter():
        if frame.tag not in {
            f"{{{P_NS}}}graphicFrame",
            "{http://purl.oclc.org/ooxml/presentationml/main}graphicFrame",
        }:
            continue
        identity = _smartart_find(frame, f"{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr")
        if identity is not None and identity.get("id") == str(shape_id):
            return frame
    raise ValueError(f"SmartArt shape {shape_id} is unavailable")


def _smartart_graphic_frame(
    shape_id: int,
    x_emu: Any,
    y_emu: Any,
    cx_emu: Any,
    cy_emu: Any,
    relationship_ids: dict[str, str],
) -> ET.Element:
    frame = ET.Element(f"{{{P_NS}}}graphicFrame")
    non_visual = ET.SubElement(frame, f"{{{P_NS}}}nvGraphicFramePr")
    ET.SubElement(
        non_visual,
        f"{{{P_NS}}}cNvPr",
        {"id": str(shape_id), "name": f"SmartArt {shape_id - 1}"},
    )
    ET.SubElement(non_visual, f"{{{P_NS}}}cNvGraphicFramePr")
    ET.SubElement(non_visual, f"{{{P_NS}}}nvPr")
    transform = ET.SubElement(frame, f"{{{P_NS}}}xfrm")
    ET.SubElement(
        transform,
        f"{{{A_NS}}}off",
        {
            "x": str(_nonnegative_int(x_emu, "left")),
            "y": str(_nonnegative_int(y_emu, "top")),
        },
    )
    ET.SubElement(
        transform,
        f"{{{A_NS}}}ext",
        {
            "cx": str(_required_int(cx_emu, "width")),
            "cy": str(_required_int(cy_emu, "height")),
        },
    )
    graphic = ET.SubElement(frame, f"{{{A_NS}}}graphic")
    data = ET.SubElement(
        graphic,
        f"{{{A_NS}}}graphicData",
        {"uri": "http://schemas.openxmlformats.org/drawingml/2006/diagram"},
    )
    rel_ids = ET.SubElement(data, f"{{{DGM_NS}}}relIds")
    for source, target in (
        ("dm", "data"),
        ("lo", "layout"),
        ("qs", "quickStyle"),
        ("cs", "colors"),
    ):
        rel_ids.set(f"{{{R_NS}}}{source}", relationship_ids[target])
    return frame


def _smartart_data_xml(nodes: list[dict[str, str | None]]) -> bytes:
    root = ET.Element(f"{{{DGM_NS}}}dataModel")
    points = ET.SubElement(root, f"{{{DGM_NS}}}ptLst")
    ET.SubElement(points, f"{{{DGM_NS}}}pt", {"modelId": "1", "type": "doc"})
    for node in nodes:
        point = ET.SubElement(
            points, f"{{{DGM_NS}}}pt", {"modelId": str(node["id"]), "type": "node"}
        )
        ET.SubElement(point, f"{{{DGM_NS}}}prSet")
        ET.SubElement(point, f"{{{DGM_NS}}}spPr")
        text_body = ET.SubElement(point, f"{{{DGM_NS}}}t")
        ET.SubElement(text_body, f"{{{A_NS}}}bodyPr")
        ET.SubElement(text_body, f"{{{A_NS}}}lstStyle")
        paragraph = ET.SubElement(text_body, f"{{{A_NS}}}p")
        run = ET.SubElement(paragraph, f"{{{A_NS}}}r")
        ET.SubElement(run, f"{{{A_NS}}}t").text = str(node["text"])
    connections = ET.SubElement(root, f"{{{DGM_NS}}}cxnLst")
    sibling_indices: dict[str, int] = {}
    for index, node in enumerate(nodes, start=1):
        parent = node["parent"]
        if parent is None:
            continue
        sibling_index = sibling_indices.get(parent, 0)
        sibling_indices[parent] = sibling_index + 1
        ET.SubElement(
            connections,
            f"{{{DGM_NS}}}cxn",
            {
                "modelId": str(100000 + index),
                "srcId": parent,
                "destId": str(node["id"]),
                "srcOrd": str(sibling_index),
                "destOrd": "0",
                "type": "parOf",
            },
        )
    ET.SubElement(root, f"{{{DGM_NS}}}bg")
    ET.SubElement(root, f"{{{DGM_NS}}}whole")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _smartart_layout_xml(layout: str, nodes: list[dict[str, str | None]]) -> bytes:
    root = ET.Element(
        f"{{{DGM_NS}}}layoutDef",
        {"uniqueId": _smartart_unique_id(layout, nodes), "minVer": "12.0"},
    )
    ET.SubElement(root, f"{{{DGM_NS}}}title", {"val": layout})
    ET.SubElement(root, f"{{{DGM_NS}}}desc", {"val": f"WolfPPT {layout} diagram"})
    categories = ET.SubElement(root, f"{{{DGM_NS}}}catLst")
    ET.SubElement(categories, f"{{{DGM_NS}}}cat", {"type": layout, "pri": "1"})
    layout_node = ET.SubElement(root, f"{{{DGM_NS}}}layoutNode", {"name": "diagram"})
    ET.SubElement(layout_node, f"{{{DGM_NS}}}alg", {"type": "lin"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _smartart_quick_style_xml(nodes: list[dict[str, str | None]]) -> bytes:
    root = ET.Element(
        f"{{{DGM_NS}}}styleDef",
        {"uniqueId": _smartart_unique_id("style", nodes), "minVer": "12.0"},
    )
    ET.SubElement(root, f"{{{DGM_NS}}}title", {"val": "WolfPPT SmartArt"})
    ET.SubElement(root, f"{{{DGM_NS}}}desc", {"val": "Editable SmartArt fallback style"})
    style_label = ET.SubElement(root, f"{{{DGM_NS}}}styleLbl", {"name": "node0"})
    style = ET.SubElement(style_label, f"{{{DGM_NS}}}style")
    for tag, index, color in (
        ("lnRef", "0", "accent1"),
        ("fillRef", "0", "accent1"),
        ("effectRef", "0", "accent1"),
        ("fontRef", "minor", "lt1"),
    ):
        reference = ET.SubElement(style, f"{{{A_NS}}}{tag}", {"idx": index})
        ET.SubElement(reference, f"{{{A_NS}}}schemeClr", {"val": color})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _smartart_colors_xml(nodes: list[dict[str, str | None]]) -> bytes:
    root = ET.Element(
        f"{{{DGM_NS}}}colorsDef",
        {"uniqueId": _smartart_unique_id("colors", nodes), "minVer": "12.0"},
    )
    ET.SubElement(root, f"{{{DGM_NS}}}title", {"val": "WolfPPT SmartArt"})
    ET.SubElement(root, f"{{{DGM_NS}}}desc", {"val": "Editable SmartArt fallback colours"})
    style_label = ET.SubElement(root, f"{{{DGM_NS}}}styleLbl", {"name": "node0"})
    for tag, color in (
        ("fillClrLst", "accent1"),
        ("linClrLst", "accent1"),
        ("effectClrLst", "accent1"),
        ("txLinClrLst", "lt1"),
        ("txFillClrLst", "lt1"),
        ("txEffectClrLst", "lt1"),
    ):
        colors = ET.SubElement(style_label, f"{{{DGM_NS}}}{tag}")
        ET.SubElement(colors, f"{{{A_NS}}}schemeClr", {"val": color})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _smartart_unique_id(
    label: str,
    nodes: list[dict[str, str | None]],
) -> str:
    digest = hashlib.sha1(
        f"{label}:{','.join(str(node['id']) for node in nodes)}".encode()
    ).hexdigest()
    return f"{{{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}}}"


_IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_ZOOM_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
}


def _zoom_transition_duration(value: Any) -> str | None:
    """Return the ``zmPr/@transitionDur`` text for finite nonnegative milliseconds."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError("transition_duration must be finite nonnegative milliseconds")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError("transition_duration must be finite nonnegative milliseconds")
    return format(number, "f")


def _apply_zoom_add(
    current: Path,
    step: Path,
    add_kind: str,
    args: tuple[Any, ...],
    *,
    transition_duration: Any = None,
    show_background: Any = None,
) -> None:
    """Add a slide zoom or section zoom shape.

    ``args`` is ``(slide_index, shape_index, shape_id, target, left, top, width,
    height, image, return_to_parent, image_type)``. ``target`` is the 0-based
    index of the zoomed slide for ``slide_zoom`` and the section GUID for
    ``section_zoom``. ``image`` is the zoom thumbnail (path or file-like), shared
    by the zoom choice and the hyperlinked picture fallback.
    """
    (
        slide_index,
        _shape_index,
        shape_id,
        target,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        image,
        return_to_parent,
        image_type,
    ) = args
    kind = "slide" if add_kind == "slide_zoom" else "section"
    shape_id = _required_int(shape_id, "shape_id")
    offset = (_nonnegative_int(x_emu, "left"), _nonnegative_int(y_emu, "top"))
    extent = (_required_int(cx_emu, "width"), _required_int(cy_emu, "height"))
    if not isinstance(return_to_parent, bool):
        raise TypeError("return_to_parent must be a bool")
    if show_background is not None and not isinstance(show_background, bool):
        raise TypeError("show_background must be a bool")
    duration = _zoom_transition_duration(transition_duration)
    image_blob = image_input_bytes(image)
    extension = image_extension_from_blob(image_blob)
    with zipfile.ZipFile(current) as package:
        names = set(package.namelist())
        presentation_part = _presentation_part(package)
        presentation_root = ET.fromstring(package.read(presentation_part))
        slide_entries = _presentation_slide_entries(package, presentation_part, presentation_root)
        if (
            isinstance(slide_index, bool)
            or not isinstance(slide_index, int)
            or not 0 <= slide_index < len(slide_entries)
        ):
            raise IndexError("zoom slide index is out of range")
        if kind == "slide":
            zoom_target, target_part = _slide_zoom_target(slide_entries, target)
            creation_id = slide_creation_id(ET.fromstring(package.read(target_part)))
        else:
            zoom_target, target_part = _section_zoom_target(
                presentation_root, slide_entries, target
            )
            creation_id = None
        slide_part = slide_entries[slide_index][1]
        slide_root = ET.fromstring(package.read(slide_part))
        used_ids = {item.get("id") for item in slide_root.iter(f"{{{P_NS}}}cNvPr")}
        if str(shape_id) in used_ids:
            raise ValueError(f"shape id {shape_id} is already used on the slide")
        slide_rels_part = _rels_part_for_package_part(slide_part)
        slide_rels = _relationships_root(package, slide_rels_part)
        media_part = _next_numbered_part(names, "ppt/media/image", f".{extension}")
        image_relationship_id = _append_relationship(
            slide_rels,
            _IMAGE_REL_TYPE,
            _relative_package_target(slide_part, media_part),
        )
        link_relationship_id = _append_relationship(
            slide_rels,
            _SLIDE_REL_TYPE,
            _relative_package_target(slide_part, target_part),
        )
        content_types = ET.fromstring(package.read("[Content_Types].xml"))
        _ensure_content_type_default(content_types, extension, _ZOOM_IMAGE_CONTENT_TYPES[extension])
        digest = (
            hashlib.sha1(f"{kind}-zoom:{slide_part}:{shape_id}:{zoom_target}".encode())
            .hexdigest()
            .upper()
        )
        zoom = zoom_alternate_content(
            kind,
            shape_id=shape_id,
            name=f"{kind.title()} Zoom {shape_id - 1}",
            offset=offset,
            extent=extent,
            target=zoom_target,
            zoom_id=(
                f"{{{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}}}"
            ),
            image_relationship_id=image_relationship_id,
            link_relationship_id=link_relationship_id,
            return_to_parent=return_to_parent,
            image_type=image_type,
            creation_id=creation_id,
            transition_duration=duration,
            show_background=show_background,
        )
        _insert_shape_tree_child(_slide_shape_tree(slide_root), zoom)
        register_zoom_namespaces()
        replacements = {
            media_part: image_blob,
            slide_part: ET.tostring(slide_root, encoding="utf-8", xml_declaration=True),
            slide_rels_part: ET.tostring(slide_rels, encoding="utf-8", xml_declaration=True),
            "[Content_Types].xml": _content_types_xml(content_types),
        }
    _copy_package_with_replacements(current, step, replacements)


def _presentation_slide_entries(
    package: zipfile.ZipFile, presentation_part: str, presentation_root: ET.Element
) -> list[tuple[str, str]]:
    """Return ``(sldId, slide part)`` pairs in presentation order."""
    relationships = _relationships_by_id(
        _relationships_root(package, _rels_part_for_package_part(presentation_part))
    )
    entries: list[tuple[str, str]] = []
    for slide_id in presentation_root.findall(f"{{{P_NS}}}sldIdLst/{{{P_NS}}}sldId"):
        relationship = relationships.get(slide_id.get(f"{{{R_NS}}}id") or "")
        if relationship is None or not relationship.get("Type", "").endswith("/slide"):
            continue
        entries.append(
            (
                slide_id.get("id", ""),
                _resolve_package_target(presentation_part, relationship.get("Target", "")),
            )
        )
    return entries


def _slide_zoom_target(slide_entries: list[tuple[str, str]], target: Any) -> tuple[str, str]:
    if isinstance(target, bool) or not isinstance(target, int):
        raise TypeError("slide zoom target must be a slide index")
    if not 0 <= target < len(slide_entries):
        raise IndexError("slide zoom target index is out of range")
    return slide_entries[target]


def _section_zoom_target(
    presentation_root: ET.Element,
    slide_entries: list[tuple[str, str]],
    target: Any,
) -> tuple[str, str]:
    if not isinstance(target, str):
        raise TypeError("section zoom target must be a section id")
    wanted = target.strip().upper()
    section = next(
        (
            record
            for record in read_sections_from_element(presentation_root)
            if record.id.strip().upper() == wanted
        ),
        None,
    )
    if section is None:
        raise ValueError(f"section {target!r} does not exist")
    if not section.slide_ids:
        raise ValueError(f"section {target!r} has no slides to zoom to")
    parts = dict(slide_entries)
    first_slide = parts.get(str(section.slide_ids[0]))
    if first_slide is None:
        raise ValueError(f"section {target!r} starts with an unknown slide")
    return section.id, first_slide


def _append_relationship(rels_root: ET.Element, rel_type: str, target: str) -> str:
    relationship_id = _next_relationship_id(rels_root)
    rels_root.append(
        ET.Element(
            f"{{{PKG_REL_NS}}}Relationship",
            {"Id": relationship_id, "Type": rel_type, "Target": target},
        )
    )
    return relationship_id
