"""OOXML chart series error bars XML parsing, validation, and serialization."""

from __future__ import annotations

import math
import os
import tempfile
import zipfile
from collections.abc import Sequence
from contextlib import suppress
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


class ErrorBarsRefusal(ValueError):
    """Base exception for chart error bars authoring refusals."""


class ErrorBarsUnsupportedFamilyError(ErrorBarsRefusal):
    """Raised when error bars are requested on an unsupported chart family."""


class ErrorBars3DPolicyError(ErrorBarsRefusal):
    """Raised when error bars are requested on a 3-D chart family (policy refusal)."""


class ErrorBarsUnsupportedError(ErrorBarsRefusal):
    """Raised when attempting to modify or remove an unsupported foreign error bar."""


class ErrorBarsStaleHandleError(ErrorBarsRefusal):
    """Raised when operating on a stale or already removed error bar handle."""


class ErrorBarsDuplicateAxisError(ErrorBarsRefusal):
    """Raised when attempting to add a duplicate error bar on an already occupied axis."""


SUPPORTED_PLOT_FAMILIES = frozenset(
    {
        "barChart",
        "lineChart",
        "areaChart",
        "scatterChart",
        "bubbleChart",
    }
)

SUPPORTED_VALUE_TYPES = frozenset(
    {
        "fixedValue",
        "fixedVal",
        "percentage",
        "stdDev",
        "stdErr",
        "custom",
        "cust",
    }
)

SUPPORTED_DIRECTIONS = frozenset(
    {
        "both",
        "plus",
        "positive",
        "minus",
        "negative",
    }
)

# Complete schema child orders per ISO/IEC 29500-1 DrawingML Chart specifications.
# Note that in all supported series types, errBars sit immediately after
# trendline (or dLbls if no trendline) and immediately before data sources (cat, val, xVal, yVal).
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

_ERR_BARS_CHILD_ORDER = (
    "errDir",
    "errBarType",
    "errValType",
    "noEndCap",
    "plus",
    "minus",
    "val",
    "spPr",
    "extLst",
)


@dataclass(frozen=True)
class ErrorBarEntry:
    """Represents a single chart error bar entry, either authored or preserved from source."""

    axis: str = "y"  # "x" | "y"
    direction: str = "both"  # "both" | "plus" | "minus"
    value_type: str = "fixedValue"  # "fixedValue" | "percentage" | "stdDev" | "stdErr" | "custom"
    value: float | None = None
    end_caps: bool = True
    plus_values: tuple[float, ...] | None = None
    minus_values: tuple[float, ...] | None = None
    line_color: str | None = None
    is_supported: bool = True
    raw_xml: str | None = None
    handle_id: int = 0
    plus_reference: str | None = None
    minus_reference: str | None = None
    # Retain imported source subtrees, including sparse caches and format codes.
    plus_source_xml: str | None = None
    minus_source_xml: str | None = None


@dataclass(frozen=True)
class ErrorBarsSpec:
    """Cumulative error bars specification for one series."""

    entries: tuple[ErrorBarEntry, ...] = ()


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
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def normalize_color_hex(color: Any) -> str:
    """Normalize a color representation into a 6-character uppercase hex RGB string."""
    if hasattr(color, "rgb"):
        color = color.rgb
    s = str(color).strip().lstrip("#")
    if len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s):
        return s.upper()
    raise ValueError(f"invalid RGB hex color {color!r}, expected 6-character hex string")


def normalize_direction(direction: str) -> str:
    """Normalize error bar direction to OOXML canonical 'both', 'plus', or 'minus'."""
    if not isinstance(direction, str):
        raise TypeError(f"direction must be a string, got {type(direction).__name__}")
    lower = direction.strip().lower()
    if lower in ("both",):
        return "both"
    if lower in ("plus", "positive"):
        return "plus"
    if lower in ("minus", "negative"):
        return "minus"
    raise ValueError(
        f"unsupported error bar direction {direction!r}; "
        f"expected one of {sorted(SUPPORTED_DIRECTIONS)}"
    )


def normalize_value_type(value_type: str) -> str:
    """Normalize to fixedValue, percentage, stdDev, stdErr, or custom."""
    if not isinstance(value_type, str):
        raise TypeError(f"value_type must be a string, got {type(value_type).__name__}")
    lower = value_type.strip().lower()
    if lower in ("fixedvalue", "fixedval"):
        return "fixedValue"
    if lower in ("percentage", "percent"):
        return "percentage"
    if lower in ("stddev", "standarddeviation"):
        return "stdDev"
    if lower in ("stderr", "standarderror"):
        return "stdErr"
    if lower in ("custom", "cust"):
        return "custom"
    raise ValueError(
        f"unsupported error bar value type {value_type!r}; "
        f"expected one of {sorted(SUPPORTED_VALUE_TYPES)}"
    )


def _normalize_to_ooxml_val_type(value_type: str) -> str:
    """Convert canonical value type to OOXML ST_ErrValType attribute value."""
    norm = normalize_value_type(value_type)
    if norm == "fixedValue":
        return "fixedVal"
    if norm == "custom":
        return "cust"
    return norm


def is_horizontal_bar_chart(plot_elem: ET.Element) -> bool:
    """Return True if plot element represents a horizontal bar chart."""
    bar_dir = plot_elem.find(f"{{{C_NS}}}barDir")
    if bar_dir is not None:
        return bar_dir.attrib.get("val") == "bar"
    return False


def supported_axes_for_plot(plot_elem: ET.Element) -> frozenset[str]:
    """Return set of valid error bar axes for a given plot element."""
    plot_family = _xml_local_name(plot_elem.tag)
    if plot_family in ("scatterChart", "bubbleChart"):
        return frozenset({"x", "y"})
    if plot_family == "barChart":
        if is_horizontal_bar_chart(plot_elem):
            return frozenset({"x"})
        return frozenset({"y"})
    if plot_family in ("lineChart", "areaChart"):
        return frozenset({"y"})
    return frozenset()


def determine_series_point_count(series_elem: ET.Element, axis: str = "y") -> int | None:
    """Extract declared or actual point count from the series element for the given axis."""
    axis_lower = axis.lower()
    targets = ["xVal", "val", "cat"] if axis_lower == "x" else ["yVal", "val", "cat"]

    for tag_name in targets:
        holder = series_elem.find(f"{{{C_NS}}}{tag_name}")
        if holder is None:
            continue
        # Check numRef / numCache
        cache = holder.find(f"{{{C_NS}}}numRef/{{{C_NS}}}numCache")
        if cache is None:
            cache = holder.find(f"{{{C_NS}}}strRef/{{{C_NS}}}strCache")
        if cache is None:
            cache = holder.find(f"{{{C_NS}}}numLit")
        if cache is None:
            cache = holder.find(f"{{{C_NS}}}strLit")
        if cache is not None:
            pt_count_elem = cache.find(f"{{{C_NS}}}ptCount")
            if pt_count_elem is not None:
                val_attr = pt_count_elem.attrib.get("val")
                if val_attr is not None:
                    try:
                        return int(val_attr)
                    except ValueError:
                        pass
            pts = cache.findall(f"{{{C_NS}}}pt")
            if pts:
                return len(pts)

    return None


def validate_error_bar_parameters(
    value_type: str,
    *,
    direction: str = "both",
    value: float | None = None,
    axis: str = "y",
    end_caps: bool = True,
    plus: Sequence[float] | None = None,
    minus: Sequence[float] | None = None,
    line_color: str | None = None,
    series_point_count: int | None = None,
    plot_family: str | None = None,
    plot_elem: ET.Element | None = None,
    existing_axes: set[str] | None = None,
    plus_reference: str | None = None,
    minus_reference: str | None = None,
) -> None:
    """Validate error bar authoring parameters against schema constraints and numeric ranges."""
    norm_val_type = normalize_value_type(value_type)
    norm_direction = normalize_direction(direction)

    if not isinstance(axis, str):
        raise TypeError(f"axis must be a string, got {type(axis).__name__}")
    axis_lower = axis.strip().lower()
    if axis_lower not in ("x", "y"):
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

    if plot_elem is not None:
        allowed = supported_axes_for_plot(plot_elem)
        p_name = _xml_local_name(plot_elem.tag)
        if axis_lower not in allowed:
            raise ErrorBarsRefusal(
                f"chart family {p_name!r} does not support error bars on axis {axis!r}; "
                f"supported axes: {sorted(allowed)}"
            )
    elif plot_family is not None:
        if plot_family in ("lineChart", "areaChart") and axis_lower != "y":
            raise ErrorBarsRefusal(
                f"chart family {plot_family!r} only supports 'y' axis error bars, got {axis!r}"
            )

    if existing_axes is not None and axis_lower in existing_axes:
        raise ErrorBarsDuplicateAxisError(f"series already has error bars on axis {axis_lower!r}")

    if isinstance(end_caps, bool):
        pass
    else:
        raise TypeError(f"end_caps must be a bool, got {type(end_caps).__name__}")

    if line_color is not None:
        normalize_color_hex(line_color)

    for name, reference in (
        ("plus", plus_reference),
        ("minus", minus_reference),
    ):
        if reference is not None:
            if not isinstance(reference, str) or not reference.strip():
                raise ErrorBarsRefusal(f"{name} reference must be a non-empty formula string")
            if any(
                not (
                    char in "\t\n\r"
                    or 0x20 <= ord(char) <= 0xD7FF
                    or 0xE000 <= ord(char) <= 0xFFFD
                    or 0x10000 <= ord(char) <= 0x10FFFF
                )
                for char in reference
            ):
                raise ErrorBarsRefusal(f"{name} reference contains invalid XML text")
            if norm_val_type != "custom":
                raise ErrorBarsRefusal("reference sources are supported only for custom error bars")

    if norm_val_type in ("fixedValue", "percentage", "stdDev"):
        if value is None:
            raise ValueError(f"{norm_val_type} error bar requires a numeric value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"error bar value must be a number, got {type(value).__name__}")
        fval = float(value)
        if not math.isfinite(fval):
            raise ValueError(f"error bar value must be finite, got {value}")
        if fval < 0:
            raise ValueError(f"error bar value must be non-negative, got {value}")
        if plus is not None or minus is not None:
            raise ValueError(
                f"plus and minus arrays cannot be specified for {norm_val_type} error bars"
            )

    elif norm_val_type == "stdErr":
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"error bar value must be a number, got {type(value).__name__}")
            fval = float(value)
            if not math.isfinite(fval) or fval < 0:
                raise ValueError(
                    f"error bar value must be a finite non-negative number, got {value}"
                )
        if plus is not None or minus is not None:
            raise ValueError("plus and minus arrays cannot be specified for stdErr error bars")

    elif norm_val_type == "custom":
        if value is not None:
            raise ValueError("custom error bars use plus/minus arrays, not scalar value")
        if plus is None and minus is None and plus_reference is None and minus_reference is None:
            raise ValueError("custom error bars require plus and/or minus numeric arrays")

        def _validate_num_array(arr: Sequence[float], name: str) -> None:
            if isinstance(arr, (str, bytes, bool)) or not isinstance(arr, Sequence):
                raise TypeError(
                    f"{name} values must be a sequence of numbers, got {type(arr).__name__}"
                )
            if len(arr) == 0:
                raise ValueError(f"{name} values array cannot be empty")
            for idx, item in enumerate(arr):
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    raise TypeError(
                        f"{name} value at index {idx} must be a number, got {type(item).__name__}"
                    )
                f_item = float(item)
                if not math.isfinite(f_item):
                    raise ValueError(f"{name} value at index {idx} must be finite, got {item}")
                if f_item < 0:
                    raise ValueError(
                        f"{name} value at index {idx} must be non-negative, got {item}"
                    )
            if series_point_count is not None and len(arr) != series_point_count:
                raise ValueError(
                    f"custom error bar {name} array length ({len(arr)}) "
                    f"does not match series point count ({series_point_count})"
                )

        for name, arr, reference in (
            ("plus", plus, plus_reference),
            ("minus", minus, minus_reference),
        ):
            if norm_direction in ("both", name) or reference is not None:
                if arr is not None:
                    try:
                        _validate_num_array(arr, name)
                    except (TypeError, ValueError) as exc:
                        if reference is not None:
                            raise ErrorBarsRefusal(str(exc)) from exc
                        raise
                elif norm_direction == name and reference is None:
                    raise ValueError(f"{name}-direction custom error bar requires {name} array")


def _parse_num_data(data_elem: ET.Element | None) -> tuple[float, ...] | None:
    """Parse numeric values from c:numLit or c:numRef inside c:plus or c:minus."""
    if data_elem is None:
        return None
    cache = data_elem.find(f"{{{C_NS}}}numLit")
    if cache is None:
        cache = data_elem.find(f"{{{C_NS}}}numRef/{{{C_NS}}}numCache")
    if cache is None:
        return None

    pt_elems = cache.findall(f"{{{C_NS}}}pt")
    indexed_vals: dict[int, float] = {}
    for pt in pt_elems:
        idx_str = pt.attrib.get("idx")
        v_elem = pt.find(f"{{{C_NS}}}v")
        if idx_str is not None and v_elem is not None and v_elem.text:
            with suppress(ValueError):
                indexed_vals[int(idx_str)] = float(v_elem.text.strip())

    if not indexed_vals:
        return None

    max_idx = max(indexed_vals.keys())
    result: list[float] = []
    for i in range(max_idx + 1):
        result.append(indexed_vals.get(i, 0.0))
    return tuple(result)


def _parse_reference(data_elem: ET.Element | None) -> str | None:
    if data_elem is None:
        return None
    children = list(data_elem)
    if len(children) != 1 or children[0].tag not in (
        f"{{{C_NS}}}numRef",
        f"{{{C_NS}}}numLit",
    ):
        raise ErrorBarsRefusal("custom error source requires exactly one numeric source")
    refs = data_elem.findall(f"{{{C_NS}}}numRef")
    if not refs:
        return None
    formulas = refs[0].findall(f"{{{C_NS}}}f")
    if len(formulas) != 1 or not formulas[0].text or not formulas[0].text.strip():
        raise ErrorBarsRefusal("custom numeric reference requires one non-empty c:f")
    return formulas[0].text


def parse_error_bar_element(
    elem: ET.Element,
    handle_id: int = 0,
) -> ErrorBarEntry:
    """Parse an existing c:errBars XML element into an ErrorBarEntry."""
    raw_xml = ET.tostring(elem, encoding="utf-8").decode("utf-8")

    err_bar_type_elem = elem.find(f"{{{C_NS}}}errBarType")
    if err_bar_type_elem is None:
        raise ErrorBarsRefusal("malformed errBars element: missing required c:errBarType")
    raw_dir = err_bar_type_elem.attrib.get("val")
    if not raw_dir or raw_dir not in ("both", "plus", "minus"):
        raise ErrorBarsRefusal(f"malformed errBars element: invalid c:errBarType val {raw_dir!r}")
    direction = raw_dir

    err_val_type_elem = elem.find(f"{{{C_NS}}}errValType")
    if err_val_type_elem is None:
        raise ErrorBarsRefusal("malformed errBars element: missing required c:errValType")
    raw_val_type = err_val_type_elem.attrib.get("val")
    if not raw_val_type or raw_val_type not in (
        "cust",
        "fixedVal",
        "percentage",
        "stdDev",
        "stdErr",
    ):
        raise ErrorBarsRefusal(
            f"malformed errBars element: invalid c:errValType val {raw_val_type!r}"
        )

    if raw_val_type == "fixedVal":
        value_type = "fixedValue"
    elif raw_val_type == "cust":
        value_type = "custom"
    else:
        value_type = raw_val_type

    err_dir_elem = elem.find(f"{{{C_NS}}}errDir")
    axis = "y"
    if err_dir_elem is not None:
        axis = err_dir_elem.attrib.get("val", "y").lower()
        if axis not in ("x", "y"):
            raise ErrorBarsRefusal(f"malformed errBars element: invalid c:errDir val {axis!r}")

    no_end_cap_elem = elem.find(f"{{{C_NS}}}noEndCap")
    end_caps = True
    if no_end_cap_elem is not None:
        val_attr = no_end_cap_elem.attrib.get("val", "1")
        end_caps = val_attr in ("0", "false", "False")

    val_elem = elem.find(f"{{{C_NS}}}val")
    value: float | None = None
    if val_elem is not None and "val" in val_elem.attrib:
        try:
            value = float(val_elem.attrib["val"])
        except ValueError as exc:
            raise ErrorBarsRefusal(
                f"malformed errBars element: invalid numeric c:val {val_elem.attrib['val']!r}"
            ) from exc

    plus_values: tuple[float, ...] | None = None
    minus_values: tuple[float, ...] | None = None
    plus_reference: str | None = None
    minus_reference: str | None = None
    plus_source_xml: str | None = None
    minus_source_xml: str | None = None
    if raw_val_type == "cust":
        plus_elem = elem.find(f"{{{C_NS}}}plus")
        minus_elem = elem.find(f"{{{C_NS}}}minus")
        plus_reference = _parse_reference(plus_elem)
        minus_reference = _parse_reference(minus_elem)
        plus_values = _parse_num_data(plus_elem)
        minus_values = _parse_num_data(minus_elem)
        if plus_elem is not None:
            plus_source_xml = ET.tostring(plus_elem, encoding="unicode")
        if minus_elem is not None:
            minus_source_xml = ET.tostring(minus_elem, encoding="unicode")
        if plus_elem is None and direction in ("both", "plus"):
            plus_values = minus_values
            plus_reference = minus_reference
        if minus_elem is None and direction in ("both", "minus"):
            minus_values = plus_values
            minus_reference = plus_reference

    line_color: str | None = None
    sp_pr = elem.find(f"{{{C_NS}}}spPr")
    if sp_pr is not None:
        clr_elem = sp_pr.find(f".//{{{A_NS}}}srgbClr")
        if clr_elem is not None:
            val = clr_elem.attrib.get("val")
            if val and len(val) == 6:
                line_color = val.upper()

    # Check for foreign/unknown child elements
    is_supported = True
    known_children = set(_ERR_BARS_CHILD_ORDER)
    for child in list(elem):
        tag_name = _xml_local_name(child.tag)
        if tag_name not in known_children:
            is_supported = False
            break

    return ErrorBarEntry(
        axis=axis,
        direction=direction,
        value_type=value_type,
        value=value,
        end_caps=end_caps,
        plus_values=plus_values,
        minus_values=minus_values,
        line_color=line_color,
        is_supported=is_supported,
        raw_xml=raw_xml,
        handle_id=handle_id,
        plus_reference=plus_reference,
        minus_reference=minus_reference,
        plus_source_xml=plus_source_xml,
        minus_source_xml=minus_source_xml,
    )


def _build_num_lit_element(parent: ET.Element, values: Sequence[float]) -> ET.Element:
    """Construct schema-valid c:numLit element with cached numeric literal values."""
    num_lit = ET.SubElement(parent, f"{{{C_NS}}}numLit")
    fmt = ET.SubElement(num_lit, f"{{{C_NS}}}formatCode")
    fmt.text = "General"
    pt_count = ET.SubElement(num_lit, f"{{{C_NS}}}ptCount")
    pt_count.set("val", str(len(values)))
    for idx, val in enumerate(values):
        pt = ET.SubElement(num_lit, f"{{{C_NS}}}pt")
        pt.set("idx", str(idx))
        v = ET.SubElement(pt, f"{{{C_NS}}}v")
        v.text = chart_number_text(float(val))
    return num_lit


def _build_num_source(
    parent: ET.Element,
    name: str,
    values: Sequence[float] | None,
    reference: str | None,
    source_xml: str | None,
) -> None:
    if source_xml is not None:
        source = ET.fromstring(source_xml)
        source.tag = f"{{{C_NS}}}{name}"
        parent.append(source)
    elif reference is not None:
        source = ET.SubElement(parent, f"{{{C_NS}}}{name}")
        ref = ET.SubElement(source, f"{{{C_NS}}}numRef")
        ET.SubElement(ref, f"{{{C_NS}}}f").text = reference
        if values is not None:
            cache = _build_num_lit_element(ref, values)
            cache.tag = f"{{{C_NS}}}numCache"
    elif values is not None:
        source = ET.SubElement(parent, f"{{{C_NS}}}{name}")
        _build_num_lit_element(source, values)


def build_error_bar_element(entry: ErrorBarEntry) -> ET.Element:
    """Construct a schema-valid c:errBars XML element from an ErrorBarEntry."""
    elem = ET.Element(f"{{{C_NS}}}errBars")

    # 1. c:errDir (CT_ErrDir)
    err_dir = ET.SubElement(elem, f"{{{C_NS}}}errDir")
    err_dir.set("val", entry.axis.lower())

    # 2. c:errBarType (CT_ErrBarType)
    err_bar_type = ET.SubElement(elem, f"{{{C_NS}}}errBarType")
    err_bar_type.set("val", normalize_direction(entry.direction))

    # 3. c:errValType (CT_ErrValType)
    err_val_type = ET.SubElement(elem, f"{{{C_NS}}}errValType")
    ooxml_val_type = _normalize_to_ooxml_val_type(entry.value_type)
    err_val_type.set("val", ooxml_val_type)

    # 4. c:noEndCap (CT_Boolean)
    no_end_cap = ET.SubElement(elem, f"{{{C_NS}}}noEndCap")
    no_end_cap.set("val", "0" if entry.end_caps else "1")

    # 5. c:plus and 6. c:minus (CT_NumDataSource) for custom
    if ooxml_val_type == "cust":
        direction = normalize_direction(entry.direction)
        plus_source = (entry.plus_values, entry.plus_reference, entry.plus_source_xml)
        minus_source = (entry.minus_values, entry.minus_reference, entry.minus_source_xml)
        if plus_source == (None, None, None):
            plus_source = minus_source
        if minus_source == (None, None, None):
            minus_source = plus_source
        if direction in ("both", "plus") or entry.plus_reference is not None:
            _build_num_source(elem, "plus", *plus_source)
        if direction in ("both", "minus") or entry.minus_reference is not None:
            _build_num_source(elem, "minus", *minus_source)

    # 7. c:val (CT_Double) for fixedVal, percentage, stdDev
    if ooxml_val_type != "cust" and entry.value is not None:
        val_elem = ET.SubElement(elem, f"{{{C_NS}}}val")
        val_elem.set("val", chart_number_text(entry.value))

    # 8. c:spPr (a:CT_ShapeProperties)
    if entry.line_color is not None:
        sp_pr = ET.SubElement(elem, f"{{{C_NS}}}spPr")
        ln = ET.SubElement(sp_pr, f"{{{A_NS}}}ln")
        solid_fill = ET.SubElement(ln, f"{{{A_NS}}}solidFill")
        srgb_clr = ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr")
        srgb_clr.set("val", normalize_color_hex(entry.line_color))

    return elem


def error_bars_insert_index(series_element: ET.Element, plot_family: str) -> int:
    """Calculate schema-valid child insert index for c:errBars within c:ser.

    When existing errBars are present, appends after the last errBars.
    Otherwise places errBars after trendline (or dLbls) and before data sources.
    """
    children = list(series_element)
    existing_indices = [
        i for i, child in enumerate(children) if _xml_local_name(child.tag) == "errBars"
    ]
    if existing_indices:
        return existing_indices[-1] + 1

    trendline_indices = [
        i for i, child in enumerate(children) if _xml_local_name(child.tag) == "trendline"
    ]
    if trendline_indices:
        return trendline_indices[-1] + 1

    order = _SERIES_CHILD_ORDERS.get(plot_family, _DEFAULT_SERIES_ORDER)
    target = order.index("errBars") if "errBars" in order else len(order)
    for index, child in enumerate(children):
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
        raise ErrorBars3DPolicyError(
            f"error bars are not supported on 3-D chart family {plot_family!r}"
        )
    if plot_family not in SUPPORTED_PLOT_FAMILIES:
        raise ErrorBarsUnsupportedFamilyError(
            f"error bars are not supported on chart family {plot_family!r}; "
            f"supported families: {sorted(SUPPORTED_PLOT_FAMILIES)}"
        )
    return plot_family


def set_chart_series_error_bars(
    chart_root: ET.Element,
    series_index: int,
    spec: ErrorBarsSpec,
) -> None:
    """Mutate chart XML root to apply the cumulative ErrorBarsSpec for a series."""
    series_element, plot_element = resolve_series_and_plot(chart_root, series_index)
    plot_family = validate_series_plot_family(plot_element)

    existing_err_bars = [
        child for child in list(series_element) if _xml_local_name(child.tag) == "errBars"
    ]
    for elem in existing_err_bars:
        series_element.remove(elem)

    for entry in spec.entries:
        if entry.raw_xml:
            err_bars_elem = ET.fromstring(entry.raw_xml)
        else:
            err_bars_elem = build_error_bar_element(entry)
        insert_idx = error_bars_insert_index(series_element, plot_family)
        series_element.insert(insert_idx, err_bars_elem)


def coerce_error_bars_spec(spec: Any) -> ErrorBarsSpec:
    """Coerce input into an ErrorBarsSpec."""
    if isinstance(spec, ErrorBarsSpec):
        return spec
    if spec is None:
        return ErrorBarsSpec(entries=())
    if isinstance(spec, (list, tuple)):
        entries: list[ErrorBarEntry] = []
        for item in spec:
            if isinstance(item, ErrorBarEntry):
                entries.append(item)
            elif isinstance(item, dict):
                entries.append(ErrorBarEntry(**item))
            else:
                raise TypeError(f"expected ErrorBarEntry or dict, got {type(item).__name__}")
        return ErrorBarsSpec(entries=tuple(entries))
    if isinstance(spec, dict):
        raw_entries = spec.get("entries", ())
        entries = []
        for item in raw_entries:
            if isinstance(item, ErrorBarEntry):
                entries.append(item)
            elif isinstance(item, dict):
                entries.append(ErrorBarEntry(**item))
            else:
                raise TypeError(f"expected ErrorBarEntry or dict, got {type(item).__name__}")
        return ErrorBarsSpec(entries=tuple(entries))
    raise TypeError(f"expected ErrorBarsSpec, dict, or list, got {type(spec).__name__}")


def normalize_error_bar_edits(
    edits: Any,
) -> list[tuple[str, int, ErrorBarsSpec]]:
    """Normalize edits into (chart_part, series_index, spec) triples."""
    if isinstance(edits, dict):
        result: list[tuple[str, int, ErrorBarsSpec]] = []
        for key, value in edits.items():
            if isinstance(key, tuple) and len(key) == 2:
                result.append((str(key[0]), int(key[1]), coerce_error_bars_spec(value)))
            else:
                raise ValueError(f"invalid edit key {key!r}, expected (chart_part, series_index)")
        return result

    result = []
    for item in edits:
        if isinstance(item, tuple) and len(item) == 3:
            result.append((str(item[0]), int(item[1]), coerce_error_bars_spec(item[2])))
        elif isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], tuple):
            result.append((str(item[0][0]), int(item[0][1]), coerce_error_bars_spec(item[1])))
        else:
            raise ValueError(
                f"invalid edit item {item!r}, expected (chart_part, series_index, spec)"
            )
    return result


def apply_chart_error_bar_edits(
    input_path: str | Path,
    output_path: str | Path,
    edits: Any,
) -> None:
    """Apply queued chart series error bar edits to a presentation package.

    Consumes a collection of (chart_part, series_index, spec) triples or a mapping.
    Preserves unknown attributes/children on existing error bars and preserves all
    unrelated package parts byte-for-byte.
    """
    in_p = Path(input_path)
    out_p = Path(output_path)

    normalized = normalize_error_bar_edits(edits)
    if not normalized:
        if in_p.resolve() != out_p.resolve():
            import shutil

            out_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(in_p, out_p)
        return

    edits_by_part: dict[str, dict[int, ErrorBarsSpec]] = {}
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
                set_chart_series_error_bars(root, s_idx, spec)

            register_chart_namespaces()
            replacements[part_name] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    if in_p.resolve() == out_p.resolve():
        tmp_fd, tmp_file = tempfile.mkstemp(
            dir=out_p.parent,
            prefix="error_bars_edit_",
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
