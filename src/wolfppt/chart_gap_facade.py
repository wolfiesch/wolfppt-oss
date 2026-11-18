"""Live chart split/layout and embedded-picture facade delegates.

Source: ECMA-376 Part 1 §21.2 (DrawingML Charts), dml-chart.xsd types
CT_OfPieChart, CT_CustSplit, CT_ManualLayout, CT_DPt and CT_PictureOptions;
ordered schema transcriptions and their source URLs are in chart_gap_xml.
Public position/value/custom and stack-and-scale tokens normalize respectively
to OOXML pos/val/cust and stackScale. Only bar/area series admit pictureOptions;
other series support stretch, while data points admit all three picture modes.
Image decoding follows the existing image_inputs/Pillow byte-preserving pattern.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from typing import Any
from xml.etree import ElementTree as ET

from .chart_facade_helpers import shape_chart_part, shape_chart_root
from .chart_gap_xml import (
    C_NS,
    SPLIT_TYPES,
    finite_number,
    integer_in_range,
    local_name,
    normalize_manual_layout,
    normalize_plot_property,
    picture_fill_descriptor,
    picture_target,
    plot_area_layout,
    plot_element,
    series_and_plot,
    set_picture_fill_xml,
    set_plot_area_layout,
    set_plot_option,
    validate_picture_options,
)
from .image_inputs import image_extension_from_blob, image_input_bytes
from .package_parts import rels_part_for_package_part, resolve_package_target

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
}


def _group_path(chart: Any) -> list[int]:
    payload = chart._shape._payload
    path = [int(payload["_group_index"])]
    for name in ("_nested_group_child_index", "_deeper_group_child_index"):
        if name in payload:
            path.append(int(payload[name]))
    path.append(int(payload["_group_child_index"]))
    return path


def _queue_identity(chart: Any) -> tuple[Any, int, int, str | None]:
    shape = chart._shape
    presentation = shape._slide._presentation
    part = shape._payload.get("_chart_part")
    if not part and shape._payload.get("relationship_ids"):
        part = shape_chart_part(shape)
    part = str(part) if part else None
    index = shape._index
    if shape._payload.get("_group_child"):
        identity = (
            part if part is not None else (shape._slide._index, *_group_path(chart))
        )
        # Group-child indices overlap both top-level and other group children.
        # A private negative key remains in the canonical queue and is resolved
        # by its part or ancestry hint, never by flat slide shape traversal.
        indices = getattr(presentation, "_chart_gap_group_queue_indices", None)
        if indices is None:
            indices = {}
            presentation._chart_gap_group_queue_indices = indices
        if identity not in indices:
            occupied = [
                key[1]
                for edits in (
                    presentation._chart_plot_property_edits,
                    presentation._chart_legend_edits,
                )
                for key in edits
                if isinstance(key[1], int)
            ]
            indices[identity] = min([0, *occupied, *indices.values()]) - 1
        index = indices[identity]
    return presentation, shape._slide._index, index, part


def _pending(chart: Any, attr: str) -> dict[str, Any]:
    presentation, slide_index, shape_index, _ = _queue_identity(chart)
    state = presentation._chart_plot_property_edits.get(
        (slide_index, shape_index), {}
    ).get(attr)
    return dict(state) if isinstance(state, dict) else {}


def _queue(chart: Any, attr: str, value: dict[str, Any]) -> None:
    presentation, slide_index, shape_index, part = _queue_identity(chart)
    presentation._queue_chart_plot_property(slide_index, shape_index, attr, value)
    if part is not None:
        presentation._queue_chart_plot_property(
            slide_index, shape_index, "_chart_part", part
        )
    if chart._shape._payload.get("_group_child"):
        presentation._queue_chart_plot_property(
            slide_index, shape_index, "_chart_group_path", _group_path(chart)
        )
    chart._shape._payload.pop("_chart_actual_layout", None)


def queue_legend_entries(chart: Any, entries: list[bytes]) -> None:
    """Queue entry overrides with the same saved/pending group identity rules."""
    presentation, slide_index, shape_index, part = _queue_identity(chart)
    state: dict[str, Any] = {"has_legend": True, "entries": list(entries)}
    if part is not None:
        state["_chart_part"] = part
    if chart._shape._payload.get("_group_child"):
        state["_chart_group_path"] = _group_path(chart)
    presentation._queue_chart_legend(slide_index, shape_index, state)
    chart._shape._payload.pop("_chart_actual_layout", None)


def is_of_pie_plot(plot: Any) -> bool:
    return (
        local_name(plot_element(shape_chart_root(plot._chart._shape), plot._index))
        == "ofPieChart"
    )


def get_plot_property(plot: Any, name: str) -> Any:
    element = plot_element(shape_chart_root(plot._chart._shape), plot._index)
    if name != "gap_width" and local_name(element) != "ofPieChart":
        raise AttributeError(f"{name} is only available on of-pie plots")
    names = {
        "split_type": ("splitType", "auto"),
        "split_value": ("splitPos", "0"),
        "second_plot_size": ("secondPieSize", "75"),
        "gap_width": ("gapWidth", "150"),
    }
    if name == "split_custom_points":
        return sorted(
            {
                int(point.get("val", "0"))
                for point in element.findall(
                    f"{{{C_NS}}}custSplit/{{{C_NS}}}secondPiePt"
                )
            }
        )
    if name not in names:
        raise ValueError(f"unsupported chart plot property: {name!r}")
    xml_name, default = names[name]
    child = element.find(f"{{{C_NS}}}{xml_name}")
    value = default if child is None else child.get("val", default)
    if name == "split_type":
        return {token: public for public, token in SPLIT_TYPES.items()}.get(
            value, value
        )
    return float(value) if name == "split_value" else int(value)


def set_plot_property(plot: Any, name: str, value: Any) -> None:
    normalized = normalize_plot_property(name, value)
    element = plot_element(shape_chart_root(plot._chart._shape), plot._index)
    set_plot_option(element, name, normalized)
    options = _pending(plot._chart, "plot_options")
    index = str(plot._index)
    scoped = dict(options.get(index) or {})
    scoped[name] = normalized
    options[index] = scoped
    _queue(plot._chart, "plot_options", options)


def _point_count(series: ET.Element) -> int:
    for name in ("val", "yVal", "xVal", "cat"):
        data = series.find(f"{{{C_NS}}}{name}")
        if data is None:
            continue
        count = data.find(f".//{{{C_NS}}}ptCount")
        if count is not None:
            return int(count.get("val", "0"))
        points = data.findall(f".//{{{C_NS}}}pt")
        if points:
            return max(int(point.get("idx", "0")) for point in points) + 1
    return 0


class PieSplitCustomPoints:
    """Mutable zero-based membership of the secondary pie/bar plot.

    Adding a member does not implicitly change split_type: choose 'custom' to
    activate these members. Removing a missing member raises KeyError.
    """

    def __init__(self, plot: Any) -> None:
        self._plot = plot
        if not is_of_pie_plot(plot):
            raise AttributeError(
                "split_custom_points is only available on of-pie plots"
            )

    def __iter__(self) -> Iterator[int]:
        return iter(get_plot_property(self._plot, "split_custom_points"))

    def __len__(self) -> int:
        return len(get_plot_property(self._plot, "split_custom_points"))

    def __contains__(self, index: Any) -> bool:
        return index in get_plot_property(self._plot, "split_custom_points")

    def add(self, index: int) -> None:
        index = integer_in_range(index, "point index", 0, 4294967295)
        element = plot_element(
            shape_chart_root(self._plot._chart._shape), self._plot._index
        )
        series = element.find(f"{{{C_NS}}}ser")
        if series is None or index >= _point_count(series):
            raise IndexError("custom split point index out of range")
        points = get_plot_property(self._plot, "split_custom_points")
        if index not in points:
            set_plot_property(self._plot, "split_custom_points", [*points, index])

    def remove(self, index: int) -> None:
        index = integer_in_range(index, "point index", 0, 4294967295)
        points = get_plot_property(self._plot, "split_custom_points")
        if index not in points:
            raise KeyError(index)
        points.remove(index)
        set_plot_property(self._plot, "split_custom_points", points)


class ChartPlotArea:
    def __init__(self, chart: Any) -> None:
        self._chart = chart

    @property
    def layout_target(self) -> str:
        return plot_area_layout(shape_chart_root(self._chart._shape))["layout_target"]

    @layout_target.setter
    def layout_target(self, value: str) -> None:
        if not isinstance(value, str) or value not in {"inner", "outer"}:
            raise ValueError("layout_target must be 'inner' or 'outer'")
        state = plot_area_layout(shape_chart_root(self._chart._shape))
        state["layout_target"] = value
        self._set_layout(state)

    @property
    def manual_layout(self) -> dict[str, Any]:
        """Return explicit x/y/w/h fractions and factor/edge mode tokens.

        Assign a dictionary to replace the manual coordinates/modes. None or
        an empty dictionary removes them without discarding the layout target.
        """
        return plot_area_layout(shape_chart_root(self._chart._shape))["manual_layout"]

    @manual_layout.setter
    def manual_layout(self, value: dict[str, Any] | None) -> None:
        normalized = normalize_manual_layout(value)
        state = plot_area_layout(shape_chart_root(self._chart._shape))
        state["manual_layout"] = normalized
        self._set_layout(state)

    @property
    def actual_layout(self) -> dict[str, int | float] | None:
        state = self._chart._shape._payload.get("_chart_actual_layout")
        if not isinstance(state, dict):
            return None
        return {name: state[name] for name in ("x", "y", "width", "height")}

    def _set_layout(self, state: dict[str, Any]) -> None:
        set_plot_area_layout(shape_chart_root(self._chart._shape), state)
        _queue(self._chart, "plot_area_layout", state)


def _image_spec(image: Any) -> dict[str, Any]:
    from PIL import Image, UnidentifiedImageError

    blob = image if isinstance(image, bytes) else image_input_bytes(image)
    extension = image_extension_from_blob(blob)
    try:
        with Image.open(io.BytesIO(blob)) as decoded:
            if decoded.format not in {"PNG", "JPEG", "GIF", "BMP", "TIFF"}:
                raise ValueError(
                    f"unsupported chart picture format: {decoded.format!r}"
                )
            width, height = decoded.size
            decoded.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("chart picture image cannot be decoded") from exc
    return {
        "blob": blob,
        "extension": extension,
        "content_type": _IMAGE_CONTENT_TYPES[extension],
        "width": width,
        "height": height,
    }


def _picture_indices(
    series: Any, point_index: int | None
) -> tuple[ET.Element, ET.Element, int | None]:
    root = shape_chart_root(series._chart._shape)
    element, plot = series_and_plot(root, series.index)
    if point_index is not None:
        point_index = integer_in_range(point_index, "point_index", 0, 4294967295)
        if point_index >= _point_count(element):
            raise IndexError("chart picture point index out of range")
    return root, plot, point_index


def set_picture_fill(
    series: Any,
    image: Any,
    picture_type: str = "stretch",
    stack_unit: float = 1.0,
    point_index: int | None = None,
) -> None:
    root, plot, point_index = _picture_indices(series, point_index)
    validate_picture_options(plot, picture_type, point_index)
    stack_unit = finite_number(stack_unit, "stack_unit")
    if stack_unit <= 0:
        raise ValueError("stack_unit must be greater than zero")
    if (
        point_index is None
        and local_name(plot)
        not in {"barChart", "bar3DChart", "areaChart", "area3DChart"}
        and stack_unit != 1.0
    ):
        raise ValueError(
            "stack_unit is only available for bar/area series or individual points"
        )
    # Stack units have no meaning outside the scaled-stack picture format.
    if picture_type != "stack-and-scale":
        stack_unit = 1.0
    spec = {
        **_image_spec(image),
        "series_index": series.index,
        "point_index": point_index,
        "picture_type": picture_type,
        "stack_unit": stack_unit,
    }
    # No fabricated relationship: save materializes the real image part/rId.
    set_picture_fill_xml(root, spec, None)
    fills = _pending(series._chart, "picture_fills")
    key = f"{series.index}:{'series' if point_index is None else point_index}"
    fills[key] = spec
    _queue(series._chart, "picture_fills", fills)


def picture_fill(series: Any, point_index: int | None = None) -> dict[str, Any] | None:
    root, _, point_index = _picture_indices(series, point_index)
    target, _ = picture_target(root, series.index, point_index)
    descriptor = picture_fill_descriptor(target)
    if descriptor is None:
        return None
    key = f"{series.index}:{'series' if point_index is None else point_index}"
    pending = _pending(series._chart, "picture_fills").get(key)
    if pending is not None:
        return {**pending, "relationship_id": None}
    from .chart_edits import _chart_part_for_edit

    shape = series._chart._shape
    presentation, slide_index, shape_index, part = _queue_identity(series._chart)
    edit: dict[str, Any] = {}
    if part is not None:
        edit["_chart_part"] = part
    if shape._payload.get("_group_child"):
        edit["_chart_group_path"] = _group_path(series._chart)
    with zipfile.ZipFile(presentation.path) as package:
        chart_part, _ = _chart_part_for_edit(
            presentation.path, package, None, {}, slide_index, shape_index, edit
        )
        rel_id = descriptor["relationship_id"]
        if rel_id is None:
            # Save clears the canonical queue but held facade roots remain
            # live. Resolve the relationship allocated by that completed save.
            saved_root = ET.fromstring(package.read(chart_part))
            saved_target, _ = picture_target(saved_root, series.index, point_index)
            descriptor = picture_fill_descriptor(saved_target)
            if descriptor is None or descriptor["relationship_id"] is None:
                raise ValueError(
                    "chart picture fill has no embedded image relationship"
                )
            rel_id = descriptor["relationship_id"]
        descriptor.update({"series_index": series.index, "point_index": point_index})
        rels = ET.fromstring(package.read(rels_part_for_package_part(chart_part)))
        relation = next(
            (
                rel
                for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
                if rel.get("Id") == rel_id
            ),
            None,
        )
        if relation is None or not relation.get("Type", "").endswith("/image"):
            raise ValueError("chart picture fill image relationship is unavailable")
        if relation.get("TargetMode") == "External":
            raise ValueError("external chart picture images are not supported")
        media_part = resolve_package_target(chart_part, relation.get("Target", ""))
        descriptor.update(_image_spec(package.read(media_part)))
        descriptor["part"] = media_part
    return descriptor
