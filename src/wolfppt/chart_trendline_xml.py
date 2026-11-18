"""OOXML chart series trendline XML parsing, validation, and serialization."""

from __future__ import annotations

import math
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class TrendlineRefusal(ValueError):
    """Base exception for chart trendline authoring refusals."""


class TrendlineUnsupportedFamilyError(TrendlineRefusal):
    """Raised when trendlines are requested on an unsupported chart family."""


class Trendline3DPolicyError(TrendlineRefusal):
    """Raised when trendlines are requested on a 3-D chart family (policy refusal)."""


class TrendlineUnsupportedError(TrendlineRefusal):
    """Raised when attempting to modify or remove an unsupported foreign trendline."""


class TrendlineStaleHandleError(TrendlineRefusal):
    """Raised when operating on a stale or already removed trendline handle."""


SUPPORTED_TRENDLINE_TYPES = frozenset(
    {
        "linear",
        "exp",
        "log",
        "power",
        "poly",
        "movingAvg",
    }
)

SUPPORTED_PLOT_FAMILIES = frozenset(
    {
        "barChart",
        "lineChart",
        "areaChart",
        "scatterChart",
        "bubbleChart",
    }
)

# Complete schema child orders per ISO/IEC 29500-1 DrawingML Chart specifications.
# Note that in all supported series types, trendline elements sit immediately after
# dLbls and immediately before errBars.
_BAR_SERIES_ORDER = (
    "idx",
    "order",
    "tx",
    "spPr",
    "invertIfNegative",
    "pictureOptions",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "cat",
    "val",
    "shape",
    "extLst",
)

_LINE_SERIES_ORDER = (
    "idx",
    "order",
    "tx",
    "spPr",
    "marker",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "cat",
    "val",
    "smooth",
    "extLst",
)

_AREA_SERIES_ORDER = (
    "idx",
    "order",
    "tx",
    "spPr",
    "pictureOptions",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "cat",
    "val",
    "extLst",
)

_SCATTER_SERIES_ORDER = (
    "idx",
    "order",
    "tx",
    "spPr",
    "marker",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "xVal",
    "yVal",
    "smooth",
    "extLst",
)

_BUBBLE_SERIES_ORDER = (
    "idx",
    "order",
    "tx",
    "spPr",
    "invertIfNegative",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "xVal",
    "yVal",
    "bubbleSize",
    "bubble3D",
    "extLst",
)

_DEFAULT_SERIES_ORDER = (
    "idx",
    "order",
    "tx",
    "spPr",
    "invertIfNegative",
    "pictureOptions",
    "marker",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "cat",
    "xVal",
    "val",
    "yVal",
    "bubbleSize",
    "bubble3D",
    "smooth",
    "shape",
    "extLst",
)

_SERIES_CHILD_ORDERS: dict[str, tuple[str, ...]] = {
    "barChart": _BAR_SERIES_ORDER,
    "lineChart": _LINE_SERIES_ORDER,
    "areaChart": _AREA_SERIES_ORDER,
    "scatterChart": _SCATTER_SERIES_ORDER,
    "bubbleChart": _BUBBLE_SERIES_ORDER,
}

_TRENDLINE_CHILD_ORDER = (
    "name",
    "spPr",
    "trendlineType",
    "order",
    "period",
    "forward",
    "backward",
    "intercept",
    "dispRSqr",
    "dispEq",
    "trendlineLbl",
    "extLst",
)


@dataclass(frozen=True)
class TrendlineEntry:
    """Represents a single trendline entry, either authored or preserved from source."""

    type: str
    order: int | None = None
    period: int | None = None
    forward: float | None = None
    backward: float | None = None
    intercept: float | None = None
    display_equation: bool = False
    display_r_squared: bool = False
    is_supported: bool = True
    raw_xml: str | None = None
    handle_id: int = 0
    label_xml: str | None = None


@dataclass(frozen=True)
class TrendlineSpec:
    """Cumulative trendline specification for one series."""

    entries: tuple[TrendlineEntry, ...] = ()


def is_3d_plot(plot_family: str) -> bool:
    """Return True if plot family denotes a 3-D chart."""
    lower = plot_family.lower()
    return "3d" in lower or lower.endswith("3dchart")


def register_chart_namespaces() -> None:
    """Register classic DrawingML chart namespaces for stable prefix serialization."""
    ET.register_namespace("c", C_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("r", R_NS)


def chart_number_text(value: float) -> str:
    """Format floating point numbers without trailing .0 when integral."""
    if value.is_integer():
        return str(int(value))
    return str(value)


def validate_trendline_parameters(
    type: str,
    *,
    order: int | None = None,
    period: int | None = None,
    forward: float | None = None,
    backward: float | None = None,
    intercept: float | None = None,
    display_equation: bool = False,
    display_r_squared: bool = False,
) -> None:
    """Validate trendline authoring parameters against schema constraints and numeric ranges."""
    if not isinstance(type, str):
        raise TypeError(f"trendline type must be a string, got {type.__class__.__name__}")
    if type not in SUPPORTED_TRENDLINE_TYPES:
        raise ValueError(
            f"unsupported trendline type {type!r}; "
            f"expected one of {sorted(SUPPORTED_TRENDLINE_TYPES)}"
        )

    if isinstance(display_equation, bool):
        pass
    else:
        raise TypeError(
            f"display_equation must be a bool, got {display_equation.__class__.__name__}"
        )

    if isinstance(display_r_squared, bool):
        pass
    else:
        raise TypeError(
            f"display_r_squared must be a bool, got {display_r_squared.__class__.__name__}"
        )

    # Validate poly order
    if type == "poly":
        if order is None:
            raise ValueError("poly trendline requires order between 2 and 6")
        if isinstance(order, bool) or not isinstance(order, int):
            raise TypeError(
                f"poly trendline order must be an integer, got {order.__class__.__name__}"
            )
        if order < 2 or order > 6:
            raise ValueError(f"poly trendline order must be in range 2 to 6 inclusive, got {order}")
    else:
        if order is not None:
            raise ValueError(
                f"order cannot be set for trendline type {type!r}; only valid for 'poly'"
            )

    # Validate movingAvg period
    if type == "movingAvg":
        if period is None:
            raise ValueError("movingAvg trendline requires period between 2 and 255")
        if isinstance(period, bool) or not isinstance(period, int):
            raise TypeError(
                f"movingAvg trendline period must be an integer, got {period.__class__.__name__}"
            )
        if period < 2 or period > 255:
            raise ValueError(
                f"movingAvg trendline period must be in range 2 to 255 inclusive, got {period}"
            )
    else:
        if period is not None:
            raise ValueError(
                f"period cannot be set for trendline type {type!r}; only valid for 'movingAvg'"
            )

    # Validate forward forecast
    if forward is not None:
        if isinstance(forward, bool) or not isinstance(forward, (int, float)):
            raise TypeError(f"forward must be a real number, got {forward.__class__.__name__}")
        val_f = float(forward)
        if not math.isfinite(val_f) or val_f < 0.0:
            raise ValueError(f"forward must be a finite non-negative number, got {forward}")

    # Validate backward forecast
    if backward is not None:
        if isinstance(backward, bool) or not isinstance(backward, (int, float)):
            raise TypeError(f"backward must be a real number, got {backward.__class__.__name__}")
        val_b = float(backward)
        if not math.isfinite(val_b) or val_b < 0.0:
            raise ValueError(f"backward must be a finite non-negative number, got {backward}")

    # Validate intercept
    if intercept is not None:
        if isinstance(intercept, bool) or not isinstance(intercept, (int, float)):
            raise TypeError(f"intercept must be a real number, got {intercept.__class__.__name__}")
        val_i = float(intercept)
        if not math.isfinite(val_i):
            raise ValueError(f"intercept must be a finite number, got {intercept}")


def parse_trendline_element(
    trendline_elem: ET.Element,
    handle_id: int = 0,
) -> TrendlineEntry:
    """Parse an existing c:trendline XML element into a TrendlineEntry."""
    raw_xml = ET.tostring(trendline_elem, encoding="unicode")

    # CT_Trendline has no schema attributes; unknown attributes denote foreign markup
    has_unknown_attrs = bool(trendline_elem.attrib)

    # Check for unsupported or unknown child elements
    supported_tags = {
        "trendlineType",
        "order",
        "period",
        "forward",
        "backward",
        "intercept",
        "dispRSqr",
        "dispEq",
        "trendlineLbl",
    }
    children = list(trendline_elem)
    child_tags = {_xml_local_name(c.tag) for c in children}
    has_unsupported_children = (
        bool(child_tags - supported_tags)
        or len(trendline_elem.findall(f"{{{C_NS}}}trendlineLbl")) > 1
    )

    type_elem = trendline_elem.find(f"{{{C_NS}}}trendlineType")
    trendline_type = type_elem.attrib.get("val") if type_elem is not None else None

    if (
        has_unknown_attrs
        or has_unsupported_children
        or trendline_type not in SUPPORTED_TRENDLINE_TYPES
    ):
        return TrendlineEntry(
            type=trendline_type or "unknown",
            is_supported=False,
            raw_xml=raw_xml,
            handle_id=handle_id,
        )

    order: int | None = None
    order_elem = trendline_elem.find(f"{{{C_NS}}}order")
    if order_elem is not None and "val" in order_elem.attrib:
        try:
            order = int(order_elem.attrib["val"])
        except (ValueError, TypeError):
            return TrendlineEntry(
                type=trendline_type,
                is_supported=False,
                raw_xml=raw_xml,
                handle_id=handle_id,
            )

    period: int | None = None
    period_elem = trendline_elem.find(f"{{{C_NS}}}period")
    if period_elem is not None and "val" in period_elem.attrib:
        try:
            period = int(period_elem.attrib["val"])
        except (ValueError, TypeError):
            return TrendlineEntry(
                type=trendline_type,
                is_supported=False,
                raw_xml=raw_xml,
                handle_id=handle_id,
            )

    forward: float | None = None
    forward_elem = trendline_elem.find(f"{{{C_NS}}}forward")
    if forward_elem is not None and "val" in forward_elem.attrib:
        try:
            forward = float(forward_elem.attrib["val"])
        except (ValueError, TypeError):
            return TrendlineEntry(
                type=trendline_type,
                is_supported=False,
                raw_xml=raw_xml,
                handle_id=handle_id,
            )

    backward: float | None = None
    backward_elem = trendline_elem.find(f"{{{C_NS}}}backward")
    if backward_elem is not None and "val" in backward_elem.attrib:
        try:
            backward = float(backward_elem.attrib["val"])
        except (ValueError, TypeError):
            return TrendlineEntry(
                type=trendline_type,
                is_supported=False,
                raw_xml=raw_xml,
                handle_id=handle_id,
            )

    intercept: float | None = None
    intercept_elem = trendline_elem.find(f"{{{C_NS}}}intercept")
    if intercept_elem is not None and "val" in intercept_elem.attrib:
        try:
            intercept = float(intercept_elem.attrib["val"])
        except (ValueError, TypeError):
            return TrendlineEntry(
                type=trendline_type,
                is_supported=False,
                raw_xml=raw_xml,
                handle_id=handle_id,
            )

    disp_eq = False
    disp_eq_elem = trendline_elem.find(f"{{{C_NS}}}dispEq")
    if disp_eq_elem is not None:
        val = disp_eq_elem.attrib.get("val", "1")
        disp_eq = val in ("1", "true", "True")

    disp_rsq = False
    disp_rsq_elem = trendline_elem.find(f"{{{C_NS}}}dispRSqr")
    if disp_rsq_elem is not None:
        val = disp_rsq_elem.attrib.get("val", "1")
        disp_rsq = val in ("1", "true", "True")

    # Enforce semantic pairing
    if trendline_type == "poly" and (order is None or order < 2 or order > 6):
        return TrendlineEntry(
            type=trendline_type,
            is_supported=False,
            raw_xml=raw_xml,
            handle_id=handle_id,
        )
    if trendline_type == "movingAvg" and (period is None or period < 2 or period > 255):
        return TrendlineEntry(
            type=trendline_type,
            is_supported=False,
            raw_xml=raw_xml,
            handle_id=handle_id,
        )

    label = trendline_elem.find(f"{{{C_NS}}}trendlineLbl")
    return TrendlineEntry(
        type=trendline_type,
        order=order,
        period=period,
        forward=forward,
        backward=backward,
        intercept=intercept,
        display_equation=disp_eq,
        display_r_squared=disp_rsq,
        is_supported=True,
        raw_xml=raw_xml,
        handle_id=handle_id,
        label_xml=ET.tostring(label, encoding="unicode") if label is not None else None,
    )


def build_trendline_element(entry: TrendlineEntry) -> ET.Element:
    """Construct a schema-valid c:trendline XML element from a TrendlineEntry."""
    elem = ET.Element(f"{{{C_NS}}}trendline")

    type_elem = ET.SubElement(elem, f"{{{C_NS}}}trendlineType")
    type_elem.set("val", entry.type)

    if entry.type == "poly" and entry.order is not None:
        order_elem = ET.SubElement(elem, f"{{{C_NS}}}order")
        order_elem.set("val", str(entry.order))

    if entry.type == "movingAvg" and entry.period is not None:
        period_elem = ET.SubElement(elem, f"{{{C_NS}}}period")
        period_elem.set("val", str(entry.period))

    if entry.forward is not None:
        fwd_elem = ET.SubElement(elem, f"{{{C_NS}}}forward")
        fwd_elem.set("val", chart_number_text(entry.forward))

    if entry.backward is not None:
        bwd_elem = ET.SubElement(elem, f"{{{C_NS}}}backward")
        bwd_elem.set("val", chart_number_text(entry.backward))

    if entry.intercept is not None:
        icpt_elem = ET.SubElement(elem, f"{{{C_NS}}}intercept")
        icpt_elem.set("val", chart_number_text(entry.intercept))

    if entry.display_r_squared:
        rsq_elem = ET.SubElement(elem, f"{{{C_NS}}}dispRSqr")
        rsq_elem.set("val", "1")

    if entry.display_equation:
        eq_elem = ET.SubElement(elem, f"{{{C_NS}}}dispEq")
        eq_elem.set("val", "1")

    if entry.label_xml is not None:
        elem.append(ET.fromstring(entry.label_xml))

    return elem


def trendline_insert_index(series_element: ET.Element, plot_family: str) -> int:
    """Calculate the schema-valid child insert index for c:trendline within c:ser.

    When existing trendlines are present, appends after the last trendline.
    Otherwise places trendline after dLbls and before errBars / data sources.
    """
    existing_indices = [
        i
        for i, child in enumerate(list(series_element))
        if _xml_local_name(child.tag) == "trendline"
    ]
    if existing_indices:
        return existing_indices[-1] + 1

    order = _SERIES_CHILD_ORDERS.get(plot_family, _DEFAULT_SERIES_ORDER)
    target = order.index("trendline") if "trendline" in order else len(order)
    for index, child in enumerate(list(series_element)):
        name = _xml_local_name(child.tag)
        if name in order and order.index(name) > target:
            return index
    return len(series_element)


def resolve_series_and_plot(
    chart_root: ET.Element,
    series_index: int,
) -> tuple[ET.Element, ET.Element]:
    """Resolve the series element and its owning plot element for a series index.

    Supports combination charts spanning multiple plot groups in c:plotArea.
    """
    plot_area = chart_root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        raise IndexError("chart plotArea element is unavailable")

    plots = [child for child in list(plot_area) if _xml_local_name(child.tag).endswith("Chart")]

    # First pass: match explicit c:idx val
    for plot in plots:
        for ser in plot.findall(f"{{{C_NS}}}ser"):
            idx_elem = ser.find(f"{{{C_NS}}}idx")
            if idx_elem is not None:
                val_str = idx_elem.attrib.get("val")
                if val_str is not None:
                    try:
                        if int(val_str) == series_index:
                            return ser, plot
                    except ValueError:
                        pass

    # Second pass: document order across all plot groups
    global_index = 0
    for plot in plots:
        for ser in plot.findall(f"{{{C_NS}}}ser"):
            if global_index == series_index:
                return ser, plot
            global_index += 1

    raise IndexError(f"chart series index {series_index} out of range")


def validate_series_plot_family(plot_element: ET.Element) -> str:
    """Validate plot family against supported 2D families and 3D policy."""
    plot_family = _xml_local_name(plot_element.tag)
    if is_3d_plot(plot_family):
        raise Trendline3DPolicyError(
            f"trendlines are not supported on 3-D chart family {plot_family!r}"
        )
    if plot_family not in SUPPORTED_PLOT_FAMILIES:
        raise TrendlineUnsupportedFamilyError(
            f"trendlines are not supported on chart family {plot_family!r}; "
            f"supported families: {sorted(SUPPORTED_PLOT_FAMILIES)}"
        )
    return plot_family


def set_chart_series_trendlines(
    chart_root: ET.Element,
    series_index: int,
    spec: TrendlineSpec,
) -> None:
    """Mutate chart XML root to apply the cumulative TrendlineSpec for a series."""
    series_element, plot_element = resolve_series_and_plot(chart_root, series_index)
    plot_family = validate_series_plot_family(plot_element)

    existing_trendlines = [
        child for child in list(series_element) if _xml_local_name(child.tag) == "trendline"
    ]
    for elem in existing_trendlines:
        series_element.remove(elem)

    for entry in spec.entries:
        if entry.raw_xml:
            trendline_elem = ET.fromstring(entry.raw_xml)
        else:
            trendline_elem = build_trendline_element(entry)
        insert_idx = trendline_insert_index(series_element, plot_family)
        series_element.insert(insert_idx, trendline_elem)


def coerce_trendline_spec(spec: Any) -> TrendlineSpec:
    """Coerce input into a TrendlineSpec."""
    if isinstance(spec, TrendlineSpec):
        return spec
    if spec is None:
        return TrendlineSpec(entries=())
    if isinstance(spec, (list, tuple)):
        entries: list[TrendlineEntry] = []
        for item in spec:
            if isinstance(item, TrendlineEntry):
                entries.append(item)
            elif isinstance(item, dict):
                entries.append(TrendlineEntry(**item))
            else:
                raise TypeError(f"expected TrendlineEntry or dict, got {type(item).__name__}")
        return TrendlineSpec(entries=tuple(entries))
    if isinstance(spec, dict):
        raw_entries = spec.get("entries", ())
        entries = []
        for item in raw_entries:
            if isinstance(item, TrendlineEntry):
                entries.append(item)
            elif isinstance(item, dict):
                entries.append(TrendlineEntry(**item))
            else:
                raise TypeError(f"expected TrendlineEntry or dict, got {type(item).__name__}")
        return TrendlineSpec(entries=tuple(entries))
    raise TypeError(f"expected TrendlineSpec, dict, or list, got {type(spec).__name__}")


def normalize_trendline_edits(
    edits: Any,
) -> list[tuple[str, int, TrendlineSpec]]:
    """Normalize edits into a uniform list of (chart_part, series_index, spec)."""
    if isinstance(edits, dict):
        result: list[tuple[str, int, TrendlineSpec]] = []
        for key, value in edits.items():
            if isinstance(key, tuple) and len(key) == 2:
                result.append((str(key[0]), int(key[1]), coerce_trendline_spec(value)))
            else:
                raise ValueError(f"invalid edit key {key!r}, expected (chart_part, series_index)")
        return result

    result = []
    for item in edits:
        if isinstance(item, tuple) and len(item) == 3:
            result.append((str(item[0]), int(item[1]), coerce_trendline_spec(item[2])))
        elif isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], tuple):
            result.append((str(item[0][0]), int(item[0][1]), coerce_trendline_spec(item[1])))
        else:
            raise ValueError(
                f"invalid edit item {item!r}, expected (chart_part, series_index, spec)"
            )
    return result


def apply_chart_trendline_edits(
    input_path: str | Path,
    output_path: str | Path,
    edits: Any,
) -> None:
    """Apply queued chart series trendline edits to a presentation package.

    Consumes a collection of (chart_part, series_index, spec) triples or a mapping.
    Preserves unknown attributes/children on existing trendlines and preserves all
    unrelated package parts byte-for-byte.
    """
    in_p = Path(input_path)
    out_p = Path(output_path)

    normalized = normalize_trendline_edits(edits)
    if not normalized:
        if in_p.resolve() != out_p.resolve():
            import shutil

            out_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(in_p, out_p)
        return

    edits_by_part: dict[str, dict[int, TrendlineSpec]] = {}
    for chart_part, series_index, spec in normalized:
        norm_part = chart_part.lstrip("/")
        edits_by_part.setdefault(norm_part, {})[series_index] = spec

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(in_p) as package:
        for part_name, series_specs in edits_by_part.items():
            try:
                xml_bytes = package.read(part_name)
            except KeyError as exc:
                raise KeyError(f"chart part {part_name!r} not found in package") from exc

            root = ET.fromstring(xml_bytes)
            for s_idx, spec in series_specs.items():
                set_chart_series_trendlines(root, s_idx, spec)

            register_chart_namespaces()
            replacements[part_name] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    if in_p.resolve() == out_p.resolve():
        import os

        tmp_fd, tmp_file = tempfile.mkstemp(
            dir=out_p.parent,
            prefix="trendline_edit_",
            suffix=".pptx",
        )
        os.close(tmp_fd)
        tmp_path = Path(tmp_file)
        try:
            _copy_package_with_replacements(in_p, tmp_path, replacements)
            tmp_path.replace(out_p)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    else:
        _copy_package_with_replacements(in_p, out_p, replacements)
