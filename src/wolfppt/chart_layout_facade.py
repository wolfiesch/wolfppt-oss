"""Public chart-element layout delegates and lossless queued layout XML.

Coordinates use chart-frame fractions. Factor x/y offset measured automatic
placement; edge x/y are absolute. Factor w/h are extents; edge w/h identify the
right/bottom edge. Axis layouts move the axis line, ticks and labels as a group,
not the plot marks/gridlines. Axis titles have independent layouts. Since axes
have no standard layout child, their geometry uses a namespaced chart extension.
Actual rectangles are measured chart-local EMU, available after render_layout;
changing chart XML, queued properties or frame geometry invalidates readback.
"""

from __future__ import annotations

import hashlib
from typing import Any
from xml.etree import ElementTree as ET

from .chart_facade_helpers import chart_payload, shape_chart_root
from .chart_gap_xml import MANUAL_LAYOUT_ORDER, normalize_manual_layout, set_child
from .chart_xml_utils import C_NS

LAYOUT_NS = "https://wolfppt.dev/chart/element-layout"
AXIS_LAYOUT_URI = "{F0D95A20-0131-4A2C-BEEF-5B0E05110101}"
_C = f"{{{C_NS}}}"


def normalize_element_layout(value: Any) -> dict[str, Any]:
    values = normalize_manual_layout(value)
    for name, fraction in values.items():
        if not name.endswith("Mode") and not -1.0 <= fraction <= 1.0:
            raise ValueError(f"{name} must be between -1 and 1")
        if name in {"w", "h"} and values.get(name + "Mode", "factor") == "factor" and fraction <= 0:
            raise ValueError(f"{name} must be positive in factor mode")
    for extent, origin in (("w", "x"), ("h", "y")):
        if (
            extent in values
            and origin in values
            and values.get(extent + "Mode") == "edge"
            and values.get(origin + "Mode") == "edge"
            and values[extent] <= values[origin]
        ):
            raise ValueError(f"{extent} edge must follow {origin} edge")
    return values


def _manual_element(element: ET.Element, axis: bool) -> ET.Element | None:
    if axis:
        layouts = element.findall(
            f"{_C}extLst/{_C}ext[@uri='{AXIS_LAYOUT_URI}']/{{{LAYOUT_NS}}}layout"
        )
    else:
        layouts = element.findall(_C + "layout")
    if len(layouts) > 1:
        raise ValueError("manual element layout repeats the layout container")
    if not layouts:
        return None
    manuals = layouts[0].findall(_C + "manualLayout")
    if len(manuals) > 1:
        raise ValueError("manual element layout repeats manualLayout")
    return manuals[0] if manuals else None


def read_element_layout(element: ET.Element, *, axis: bool = False) -> dict[str, Any]:
    manual = _manual_element(element, axis)
    if manual is None:
        return {}
    values: dict[str, Any] = {}
    seen: set[str] = set()
    for child in manual:
        name = child.tag.removeprefix(_C)
        if name in seen:
            raise ValueError(f"manual element layout repeats {name!r}")
        seen.add(name)
        if name == "layoutTarget":
            if child.get("val") != "outer":
                raise ValueError("manual element layout supports only outer target")
            continue
        if name == "extLst":
            continue
        if name not in MANUAL_LAYOUT_ORDER[1:-1]:
            raise ValueError(f"manual element layout has unsupported child {name!r}")
        raw = child.get("val")
        if raw is None:
            raise ValueError(f"manual element layout {name} has no value")
        try:
            values[name] = raw if name.endswith("Mode") else float(raw)
        except ValueError as exc:
            raise ValueError(f"manual element layout {name} is not numeric") from exc
    return normalize_element_layout(values)


def write_element_layout(
    element: ET.Element, values: dict[str, Any], *, axis: bool = False
) -> None:
    """Write already-validated values, preserving unrelated extension children."""
    if axis:
        extensions = element.find(_C + "extLst")
        extension = (
            None if extensions is None else extensions.find(f"{_C}ext[@uri='{AXIS_LAYOUT_URI}']")
        )
        layout = None if extension is None else extension.find(f"{{{LAYOUT_NS}}}layout")
        if not values:
            if extension is not None and layout is not None:
                extension.remove(layout)
                if not len(extension):
                    extensions.remove(extension)
                if not len(extensions):
                    element.remove(extensions)
            return
        if extensions is None:
            extensions = ET.SubElement(element, _C + "extLst")
        if extension is None:
            extension = ET.SubElement(extensions, _C + "ext", {"uri": AXIS_LAYOUT_URI})
        if layout is None:
            layout = ET.SubElement(extension, f"{{{LAYOUT_NS}}}layout")
    else:
        layout = element.find(_C + "layout")
        if layout is None:
            if not values:
                return
            layout = ET.Element(_C + "layout")
            predecessors = {"tx", "idx", "delete", "legendPos", "legendEntry"}
            index = next(
                (
                    i
                    for i, child in enumerate(element)
                    if child.tag.removeprefix(_C) not in predecessors
                ),
                len(element),
            )
            element.insert(index, layout)
    manual = layout.find(_C + "manualLayout")
    if manual is None:
        if not values:
            return
        manual = ET.Element(_C + "manualLayout")
        layout.insert(0, manual)
    for child in list(manual):
        if child.tag.removeprefix(_C) in MANUAL_LAYOUT_ORDER[:-1]:
            manual.remove(child)
    for name in MANUAL_LAYOUT_ORDER[1:-1]:
        if name in values:
            set_child(manual, name, values[name], MANUAL_LAYOUT_ORDER)
    if not len(manual) and not manual.attrib:
        layout.remove(manual)


def layout_queue_identity(chart: Any) -> tuple[Any, int, int, str | None]:
    """Resolve a live, safely addressable chart before any layout mutation."""
    from .chart_gap_facade import _queue_identity

    shape = chart._shape
    if shape._payload.get("_deleted") or shape._payload.get("_stale"):
        raise ValueError("cannot edit layout of a deleted or stale chart")
    slide = shape._slide
    if getattr(slide, "_deleted", False) or slide not in slide._presentation._slides:
        raise ValueError("cannot edit layout on a deleted slide")
    identity = _queue_identity(chart)
    if shape._payload.get("_group_child") and identity[3] is None:
        raise ValueError("save the grouped chart before editing element layout")
    if identity[3] is None:
        from .chart_facade import _staged_chart_source

        _staged_chart_source(shape)
    return identity


def queue_layout_xml(chart: Any) -> None:
    """Reuse the canonical chart-part snapshot queue; never replace a workbook."""
    presentation, slide_index, shape_index, part = layout_queue_identity(chart)
    key = (slide_index, shape_index)
    edit = dict(presentation._chart_data_edits.get(key) or {})
    if not edit and not part:
        from .chart_facade import _staged_chart_source

        edit = dict(_staged_chart_source(chart._shape))
    edit["_chart_xml"] = ET.tostring(
        shape_chart_root(chart._shape), encoding="utf-8", xml_declaration=True
    )
    if part:
        edit["_chart_part"] = part
    presentation._queue_chart_data_replace(slide_index, shape_index, edit)
    chart._shape._payload.pop("_chart_actual_layout", None)


def layout_signature(chart: Any) -> str:
    shape = chart._shape
    digest = hashlib.sha256(ET.tostring(shape_chart_root(shape)))
    digest.update(repr(chart_payload(shape)).encode())
    digest.update(repr((int(shape.width), int(shape.height))).encode())
    presentation = shape._slide._presentation
    key = (shape._slide._index, shape._index)
    for name in (
        "_chart_title_edits",
        "_chart_legend_edits",
        "_chart_font_edits",
        "_chart_data_label_edits",
        "_chart_axis_title_edits",
        "_chart_axis_property_edits",
        "_chart_plot_property_edits",
        "_chart_data_edits",
    ):
        digest.update(repr(getattr(presentation, name, {}).get(key)).encode())
    return digest.hexdigest()


def actual_element_layout(chart: Any, key: str, point: str | None = None) -> dict[str, int] | None:
    state = chart._shape._payload.get("_chart_actual_layout")
    if not isinstance(state, dict):
        return None
    if chart._shape._payload.get("_chart_actual_layout_signature") != layout_signature(chart):
        chart._shape._payload.pop("_chart_actual_layout", None)
        return None
    rectangle = state.get("elements", {}).get(key)
    if point is not None and isinstance(rectangle, dict):
        rectangle = rectangle.get(point)
    return dict(rectangle) if isinstance(rectangle, dict) else None


def set_facade_layout(owner: Any, value: Any) -> None:
    values = normalize_element_layout(value)
    element = owner._layout_element(False)
    if values == read_element_layout(element, axis=owner._layout_is_axis):
        return
    # Queue identity and liveness must be valid before mutating the XML.
    layout_queue_identity(owner._layout_chart)
    element = owner._layout_element(True)
    write_element_layout(element, values, axis=owner._layout_is_axis)
    queue_layout_xml(owner._layout_chart)


class ElementLayout:
    """Shared manual/actual layout contract of title, legend and axis facades."""

    _layout_is_axis = False

    @property
    def manual_layout(self) -> dict[str, Any]:
        return read_element_layout(self._layout_element(False), axis=self._layout_is_axis)

    @manual_layout.setter
    def manual_layout(self, value: dict[str, Any] | None) -> None:
        set_facade_layout(self, value)

    @property
    def actual_layout(self) -> dict[str, int] | None:
        return actual_element_layout(self._layout_chart, self._layout_key)


def axis_layout_elements(root: ET.Element) -> dict[str, ET.Element]:
    """Select the same primary/secondary axis order used by public facades."""
    from .chart_xml import chart_axis_element

    chart = root.find(_C + "chart")
    if chart is None:
        return {}
    result = {}
    for token, name in (
        ("cat", "category_axis"),
        ("val", "value_axis"),
        ("val2", "secondary_value_axis"),
    ):
        axis = chart_axis_element(chart, token)
        if axis is not None:
            result[name] = axis
    return result


def render_layout_package(chart: Any) -> Any:
    """Resolve embedded picture parts from this chart's saved source only.

    Plain in-memory layout retains its cache-only behavior. The bounded package
    reader never follows external image/workbook relationships or writes parts.
    """
    from pathlib import Path

    from .editions import commercial_module

    root = shape_chart_root(chart._shape)
    if root.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blipFill") is None:
        return None
    source = chart._shape._slide._presentation.path
    if source is None or not Path(source).is_file():
        return None
    package_reader = commercial_module("render_package", "Rendering chart layout")
    return package_reader.read_package(Path(source))
