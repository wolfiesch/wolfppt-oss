"""Facade for chart series trendlines."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import Any, overload
from xml.etree import ElementTree as ET

from .chart_data_label_text_xml import (
    set_chart_data_label_number_format,
    set_chart_data_label_number_format_source_linked,
    set_chart_data_label_text,
)
from .chart_facade_helpers import (
    shape_chart_part as _shape_chart_part,
)
from .chart_facade_helpers import (
    shape_chart_root as _shape_chart_root,
)
from .chart_trendline_xml import (
    A_NS,
    C_NS,
    SUPPORTED_PLOT_FAMILIES,
    Trendline3DPolicyError,
    TrendlineEntry,
    TrendlineRefusal,
    TrendlineSpec,
    TrendlineStaleHandleError,
    TrendlineUnsupportedError,
    TrendlineUnsupportedFamilyError,
    apply_chart_trendline_edits,
)
from .chart_trendline_xml import (
    is_3d_plot as _is_3d_plot,
)
from .chart_trendline_xml import (
    parse_trendline_element as _parse_trendline_element,
)
from .chart_trendline_xml import (
    resolve_series_and_plot as _resolve_series_and_plot,
)
from .chart_trendline_xml import (
    validate_trendline_parameters as _validate_trendline_parameters,
)
from .xml_helpers import xml_local_name as _xml_local_name

__all__ = [
    "ChartTrendline",
    "ChartTrendlines",
    "Trendline3DPolicyError",
    "TrendlineEntry",
    "TrendlineRefusal",
    "TrendlineSpec",
    "TrendlineStaleHandleError",
    "TrendlineUnsupportedError",
    "TrendlineUnsupportedFamilyError",
    "apply_chart_trendline_edits",
]


def _get_presentation(series: Any) -> Any:
    chart = getattr(series, "_chart", None)
    if chart is None:
        raise AttributeError("series chart is unavailable")
    shape = getattr(chart, "_shape", None)
    if shape is None:
        raise AttributeError("chart shape is unavailable")
    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise AttributeError("shape slide is unavailable")
    prs = getattr(slide, "_presentation", None)
    if prs is None:
        raise AttributeError("slide presentation is unavailable")
    return prs


def _check_shape_and_slide_live(shape: Any) -> None:
    payload = getattr(shape, "_payload", {})
    if isinstance(payload, dict):
        if payload.get("_deleted"):
            raise ValueError("cannot edit or read trendlines of a deleted shape")
        if payload.get("_stale"):
            raise ValueError("cannot edit or read trendlines of a stale shape")
        if payload.get("_pending_shape") or payload.get("_pending_group_child"):
            raise ValueError("cannot edit or read trendlines of an unsaved shape")

    if getattr(shape, "_deleted", False):
        raise ValueError("cannot edit or read trendlines of a deleted shape")

    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise ValueError("chart shape is not associated with any slide")
    if getattr(slide, "_deleted", False):
        raise ValueError("cannot edit or read trendlines on a deleted slide")

    prs = getattr(slide, "_presentation", None)
    if prs is not None:
        slides = getattr(prs, "_slides", None)
        if slides is not None and slide not in slides:
            raise ValueError("cannot edit or read trendlines on a deleted slide")
        slide_deletions = getattr(prs, "_slide_deletions", None)
        if slide_deletions and getattr(slide, "partname", None) in slide_deletions:
            raise ValueError("cannot edit or read trendlines on a deleted slide")
        shape_deletes = getattr(prs, "_shape_deletes", None)
        shape_index = getattr(shape, "_index", None)
        if (
            shape_deletes
            and getattr(slide, "partname", None) in shape_deletes
            and shape_index is not None
            and shape_index in shape_deletes[slide.partname]
        ):
            raise ValueError("cannot edit or read trendlines of a deleted shape")


class _SeriesTrendlineState:
    """Authoritative state for a series' trendlines, attached to Presentation."""

    def __init__(
        self,
        prs: Any,
        chart_part: str,
        series_index: int,
        shape: Any,
    ) -> None:
        self.prs = prs
        self.chart_part = chart_part
        self.series_index = series_index
        self.shape = shape
        self.plot_family: str | None = None
        self.family_error: TrendlineRefusal | None = None
        self.entries: list[TrendlineEntry] = []
        self.live_handles: dict[int, ChartTrendline] = {}
        self.stale_handle_ids: set[int] = set()
        self.next_handle_id: int = 1
        self._loaded: bool = False

    def load(self) -> None:
        if self._loaded:
            return

        # Check plot family & 3D policy from chart root XML
        try:
            root = _shape_chart_root(self.shape)
        except Exception as exc:
            raise TrendlineRefusal(f"malformed chart trendline source XML: {exc}") from exc

        try:
            series_elem, plot_elem = _resolve_series_and_plot(root, self.series_index)
        except (Trendline3DPolicyError, TrendlineUnsupportedFamilyError):
            raise
        except Exception as exc:
            raise TrendlineRefusal(f"malformed chart series XML: {exc}") from exc

        plot_family = _xml_local_name(plot_elem.tag)
        self.plot_family = plot_family
        if _is_3d_plot(plot_family):
            self.family_error = Trendline3DPolicyError(
                f"trendlines are not supported on 3-D chart family {plot_family!r}"
            )
        elif plot_family not in SUPPORTED_PLOT_FAMILIES:
            self.family_error = TrendlineUnsupportedFamilyError(
                f"trendlines are not supported on chart family {plot_family!r}; "
                f"supported families: {sorted(SUPPORTED_PLOT_FAMILIES)}"
            )

        # Check if presentation already holds pending edits for this series
        edits = getattr(self.prs, "_chart_trendline_edits", None)
        pending_spec: TrendlineSpec | None = None
        if isinstance(edits, dict):
            pending_spec = edits.get((self.chart_part, self.series_index))

        if pending_spec is not None:
            self.entries = list(pending_spec.entries)
            for entry in self.entries:
                if entry.handle_id <= 0:
                    entry.handle_id = self._alloc_id()
                elif entry.handle_id >= self.next_handle_id:
                    self.next_handle_id = entry.handle_id + 1
        elif self.family_error is None:
            existing_elems = [c for c in list(series_elem) if _xml_local_name(c.tag) == "trendline"]
            self.entries = []
            for elem in existing_elems:
                handle_id = self._alloc_id()
                try:
                    entry = _parse_trendline_element(elem, handle_id=handle_id)
                except Exception as exc:
                    raise TrendlineRefusal(
                        f"malformed trendline element in source XML: {exc}"
                    ) from exc
                self.entries.append(entry)

        self._loaded = True

    def _alloc_id(self) -> int:
        hid = self.next_handle_id
        self.next_handle_id += 1
        return hid

    def _queue(self) -> None:
        if not hasattr(self.prs, "_queue_chart_trendlines"):
            raise AttributeError(
                "presentation does not implement canonical _queue_chart_trendlines"
            )
        queue_fn = self.prs._queue_chart_trendlines
        if not callable(queue_fn):
            raise TypeError("presentation canonical _queue_chart_trendlines is not callable")
        spec = TrendlineSpec(entries=tuple(self.entries))
        queue_fn(self.chart_part, self.series_index, spec)

    def validate_family(self) -> None:
        _check_shape_and_slide_live(self.shape)
        self.load()
        if self.family_error is not None:
            raise self.family_error

        # Double check on live root in case plot family changed dynamically
        try:
            root = _shape_chart_root(self.shape)
            _, plot_elem = _resolve_series_and_plot(root, self.series_index)
            plot_family = _xml_local_name(plot_elem.tag)
            if _is_3d_plot(plot_family):
                raise Trendline3DPolicyError(
                    f"trendlines are not supported on 3-D chart family {plot_family!r}"
                )
            if plot_family not in SUPPORTED_PLOT_FAMILIES:
                raise TrendlineUnsupportedFamilyError(
                    f"trendlines are not supported on chart family {plot_family!r}; "
                    f"supported families: {sorted(SUPPORTED_PLOT_FAMILIES)}"
                )
        except (Trendline3DPolicyError, TrendlineUnsupportedFamilyError):
            raise
        except (KeyError, AttributeError, ValueError, IndexError, OSError):
            pass

    def get_handle(self, entry: TrendlineEntry) -> ChartTrendline:
        handle = self.live_handles.get(entry.handle_id)
        if handle is None or handle._stale:
            handle = ChartTrendline(state=self, handle_id=entry.handle_id)
            self.live_handles[entry.handle_id] = handle
        return handle

    def add(
        self,
        type: str = "linear",
        *,
        order: int | None = None,
        period: int | None = None,
        forward: float | None = None,
        backward: float | None = None,
        intercept: float | None = None,
        display_equation: bool = False,
        display_r_squared: bool = False,
    ) -> ChartTrendline:
        self.validate_family()
        _validate_trendline_parameters(
            type,
            order=order,
            period=period,
            forward=forward,
            backward=backward,
            intercept=intercept,
            display_equation=display_equation,
            display_r_squared=display_r_squared,
        )
        entry = TrendlineEntry(
            type=type,
            order=order,
            period=period,
            forward=float(forward) if forward is not None else None,
            backward=float(backward) if backward is not None else None,
            intercept=float(intercept) if intercept is not None else None,
            display_equation=display_equation,
            display_r_squared=display_r_squared,
            is_supported=True,
            raw_xml=None,
            handle_id=self._alloc_id(),
        )
        self.entries.append(entry)
        self._queue()
        return self.get_handle(entry)

    def remove(self, handle_or_index: ChartTrendline | int) -> None:
        self.validate_family()
        if isinstance(handle_or_index, ChartTrendline):
            handle = handle_or_index
            if handle.state is not self:
                raise TrendlineStaleHandleError(
                    "trendline handle is stale or from a different series"
                )
            if handle._stale or handle.handle_id in self.stale_handle_ids:
                raise TrendlineStaleHandleError("trendline handle is stale or already removed")
            target_idx: int | None = None
            for idx, entry in enumerate(self.entries):
                if entry.handle_id == handle.handle_id:
                    target_idx = idx
                    break
            if target_idx is None:
                raise TrendlineStaleHandleError("trendline handle is stale or already removed")
        elif isinstance(handle_or_index, int):
            if isinstance(handle_or_index, bool):
                raise TypeError("trendline index must be an integer, not bool")
            idx = handle_or_index
            if idx < 0:
                idx += len(self.entries)
            if idx < 0 or idx >= len(self.entries):
                raise IndexError(
                    f"trendline index {idx} out of range "
                    f"(series has {len(self.entries)} trendlines)"
                )
            target_idx = idx
        else:
            raise TypeError(
                f"expected ChartTrendline or int index, got {type(handle_or_index).__name__}"
            )

        entry = self.entries[target_idx]
        if not entry.is_supported:
            raise TrendlineUnsupportedError("unsupported trendline with foreign content")

        self.stale_handle_ids.add(entry.handle_id)
        if entry.handle_id in self.live_handles:
            self.live_handles[entry.handle_id]._stale = True

        del self.entries[target_idx]
        self._queue()

    def clear(self) -> None:
        self.validate_family()
        preserved: list[TrendlineEntry] = []
        for entry in self.entries:
            if entry.is_supported:
                self.stale_handle_ids.add(entry.handle_id)
                if entry.handle_id in self.live_handles:
                    self.live_handles[entry.handle_id]._stale = True
            else:
                preserved.append(entry)
        self.entries = preserved
        self._queue()

    def index_of_handle(self, handle: ChartTrendline) -> int:
        if handle.state is not self:
            raise TrendlineStaleHandleError("trendline handle is stale or from a different series")
        if handle._stale or handle.handle_id in self.stale_handle_ids:
            raise TrendlineStaleHandleError("trendline handle is stale or already removed")
        for idx, entry in enumerate(self.entries):
            if entry.handle_id == handle.handle_id:
                return idx
        raise TrendlineStaleHandleError("trendline handle is stale or already removed")

    def sync(self, shape: Any) -> None:
        _check_shape_and_slide_live(shape)
        self.shape = shape
        edits = getattr(self.prs, "_chart_trendline_edits", None)
        if isinstance(edits, dict) and (self.chart_part, self.series_index) in edits:
            queued_spec = edits[(self.chart_part, self.series_index)]
            if tuple(e.type for e in self.entries) != tuple(e.type for e in queued_spec.entries):
                self.entries = list(queued_spec.entries)


def _get_or_create_series_trendline_state(series: Any) -> _SeriesTrendlineState:
    prs = _get_presentation(series)
    chart = getattr(series, "_chart", None)
    shape = getattr(chart, "_shape", None)
    if shape is None:
        raise AttributeError("chart shape is unavailable")
    chart_part = _shape_chart_part(shape)
    series_index = int(series.index)
    key = (chart_part, series_index)

    states = getattr(prs, "_chart_trendline_states", None)
    if states is None:
        states = {}
        prs._chart_trendline_states = states

    state = states.get(key)
    if state is None:
        state = _SeriesTrendlineState(prs, chart_part, series_index, shape)
        states[key] = state
        state.load()
    else:
        state.sync(shape)
    return state


class ChartTrendlineLabel:
    """Cached label text and number format; no equation or R-squared calculation."""

    def __init__(self, trendline: ChartTrendline) -> None:
        self._trendline = trendline

    def _element(self) -> ET.Element:
        raw = self._trendline._entry().label_xml
        return ET.fromstring(raw) if raw is not None else ET.Element(f"{{{C_NS}}}trendlineLbl")

    def _set(self, name: str, value: Any) -> None:
        label = self._element()
        if name == "text":
            set_chart_data_label_text(label, value)
        elif name == "number_format":
            set_chart_data_label_number_format(label, value)
        else:
            set_chart_data_label_number_format_source_linked(label, value)
        self._trendline._set("label_xml", ET.tostring(label, encoding="unicode"))

    @property
    def number_format(self) -> str:
        """Number format code, or General when unspecified."""
        num_fmt = self._element().find(f"{{{C_NS}}}numFmt")
        return "General" if num_fmt is None else num_fmt.get("formatCode", "General")

    @number_format.setter
    def number_format(self, value: str) -> None:
        """Set the format code and unlink it from the data source."""
        if not isinstance(value, str):
            raise TypeError("trendline label number_format must be a string")
        self._set("number_format", value)

    @property
    def number_format_is_linked(self) -> bool:
        """Whether the label number format is linked to its data source."""
        num_fmt = self._element().find(f"{{{C_NS}}}numFmt")
        return num_fmt is None or num_fmt.get("sourceLinked", "1") in ("1", "true", "True")

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("trendline label number_format_is_linked must be a bool")
        self._set("number_format_is_linked", value)

    @property
    def text(self) -> str:
        """Cached rich text or string-reference cache, without evaluating formulas."""
        label = self._element()
        rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
        if rich is not None:
            return "\n".join(
                "".join(
                    "\v" if node.tag == f"{{{A_NS}}}br" else node.text or ""
                    for node in paragraph.iter()
                    if node.tag in (f"{{{A_NS}}}t", f"{{{A_NS}}}br")
                )
                for paragraph in rich.findall(f"{{{A_NS}}}p")
            )
        cache = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef/{{{C_NS}}}strCache")
        if cache is None:
            return ""
        return "\n".join(
            point.findtext(f"{{{C_NS}}}v", "") for point in cache.findall(f"{{{C_NS}}}pt")
        )

    @text.setter
    def text(self, value: str) -> None:
        """Replace the cached text with literal rich text, retaining label formatting."""
        if not isinstance(value, str):
            raise TypeError("trendline label text must be a string")
        self._set("text", value)


class ChartTrendline:
    """Handle representing an individual chart series trendline.

    Exposes editable properties and provides a .remove() convenience method.
    If the trendline carries unsupported foreign children or attributes from
    the source document, is_supported is False and direct modification or
    removal is rejected with TrendlineUnsupportedError.
    """

    def __init__(
        self,
        state: _SeriesTrendlineState,
        handle_id: int,
    ) -> None:
        self._state = state
        self._handle_id = handle_id
        self._stale = False

    @property
    def handle_id(self) -> int:
        return self._handle_id

    @property
    def state(self) -> _SeriesTrendlineState:
        return self._state

    def _entry(self) -> TrendlineEntry:
        if self._stale or self._handle_id in self._state.stale_handle_ids:
            self._stale = True
            raise TrendlineStaleHandleError("trendline handle is stale or already removed")
        for entry in self._state.entries:
            if entry.handle_id == self._handle_id:
                return entry
        self._stale = True
        raise TrendlineStaleHandleError("trendline handle is stale or already removed")

    def _set(self, name: str, value: Any) -> None:
        self._state.validate_family()
        index = self._state.index_of_handle(self)
        entry = self._entry()
        if not entry.is_supported:
            raise TrendlineUnsupportedError(
                "cannot modify unsupported trendline with foreign content"
            )
        changes = {name: value}
        if name == "type":
            changes["order"] = (
                (entry.order if entry.type == "poly" else 2) if value == "poly" else None
            )
            changes["period"] = (
                (entry.period if entry.type == "movingAvg" else 2) if value == "movingAvg" else None
            )
        candidate = replace(entry, **changes)
        _validate_trendline_parameters(
            candidate.type,
            order=candidate.order,
            period=candidate.period,
            forward=candidate.forward,
            backward=candidate.backward,
            intercept=candidate.intercept,
            display_equation=candidate.display_equation,
            display_r_squared=candidate.display_r_squared,
        )
        if name in ("forward", "backward", "intercept") and value is not None:
            candidate = replace(candidate, **{name: float(value)})
        if candidate == entry:
            return
        self._state.entries[index] = replace(candidate, raw_xml=None)
        try:
            self._state._queue()
        except Exception:
            self._state.entries[index] = entry
            raise

    @property
    def type(self) -> str:
        """Trendline type ('linear', 'exp', 'log', 'power', 'poly', 'movingAvg')."""
        return self._entry().type

    @type.setter
    def type(self, value: str) -> None:
        """Change type, clearing incompatible parameters; new order/period defaults to 2."""
        self._set("type", value)

    @property
    def order(self) -> int | None:
        """Polynomial order (2..6) when type is 'poly', else None."""
        return self._entry().order

    @order.setter
    def order(self, value: int | None) -> None:
        self._set("order", value)

    @property
    def period(self) -> int | None:
        """Moving average period (2..255) when type is 'movingAvg', else None."""
        return self._entry().period

    @period.setter
    def period(self, value: int | None) -> None:
        self._set("period", value)

    @property
    def forward(self) -> float | None:
        """Forward forecast periods, or None if unspecified."""
        return self._entry().forward

    @forward.setter
    def forward(self, value: float | None) -> None:
        self._set("forward", value)

    @property
    def backward(self) -> float | None:
        """Backward forecast periods, or None if unspecified."""
        return self._entry().backward

    @backward.setter
    def backward(self, value: float | None) -> None:
        self._set("backward", value)

    @property
    def intercept(self) -> float | None:
        """Value at which the trendline crosses the vertical axis, or None."""
        return self._entry().intercept

    @intercept.setter
    def intercept(self, value: float | None) -> None:
        self._set("intercept", value)

    @property
    def display_equation(self) -> bool:
        """Whether the trendline equation is displayed on the chart."""
        return self._entry().display_equation

    @display_equation.setter
    def display_equation(self, value: bool) -> None:
        self._set("display_equation", value)

    @property
    def display_r_squared(self) -> bool:
        """Whether the R-squared value is displayed on the chart."""
        return self._entry().display_r_squared

    @display_r_squared.setter
    def display_r_squared(self, value: bool) -> None:
        self._set("display_r_squared", value)

    @property
    def label(self) -> ChartTrendlineLabel:
        """Read or edit cached label text and number format, creating XML only on edit."""
        self._entry()
        return ChartTrendlineLabel(self)

    @property
    def is_supported(self) -> bool:
        """Whether this trendline conforms to the editable authoring subset."""
        return self._entry().is_supported

    @property
    def index(self) -> int:
        """Current 0-based position of this trendline in the series collection."""
        return self._state.index_of_handle(self)

    def remove(self) -> None:
        """Remove this trendline from its owning series."""
        self._state.remove(self)

    def __repr__(self) -> str:
        try:
            entry = self._entry()
            return f"<ChartTrendline type={entry.type!r} supported={entry.is_supported}>"
        except TrendlineStaleHandleError:
            return f"<ChartTrendline (stale handle_id={self._handle_id})>"


class ChartTrendlines(Sequence[ChartTrendline]):
    """Collection facade for chart series trendlines.

    Supports iteration, len(), integer indexing, add(), remove(), and clear().
    Multiple trendlines are supported on bar, line, area, scatter, and bubble series.
    Unsupported chart families and 3-D policy cases are refused with named boundaries.
    """

    def __init__(self, series: Any) -> None:
        self._series = series
        self._state = _get_or_create_series_trendline_state(series)

    def __len__(self) -> int:
        self._state.load()
        if self._state.family_error is not None:
            return 0
        return len(self._state.entries)

    def __iter__(self) -> Iterator[ChartTrendline]:
        self._state.load()
        if self._state.family_error is not None:
            return iter(())
        for entry in list(self._state.entries):
            yield self._state.get_handle(entry)

    @overload
    def __getitem__(self, index: int) -> ChartTrendline: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[ChartTrendline]: ...

    def __getitem__(self, index: int | slice) -> ChartTrendline | Sequence[ChartTrendline]:
        self._state.load()
        if self._state.family_error is not None:
            raise IndexError("chart series does not support trendlines")
        if isinstance(index, slice):
            return [self._state.get_handle(e) for e in self._state.entries[index]]
        entry = self._state.entries[index]
        return self._state.get_handle(entry)

    def add(
        self,
        type: str = "linear",
        *,
        order: int | None = None,
        period: int | None = None,
        forward: float | None = None,
        backward: float | None = None,
        intercept: float | None = None,
        display_equation: bool = False,
        display_r_squared: bool = False,
    ) -> ChartTrendline:
        """Add a new trendline to this chart series."""
        return self._state.add(
            type=type,
            order=order,
            period=period,
            forward=forward,
            backward=backward,
            intercept=intercept,
            display_equation=display_equation,
            display_r_squared=display_r_squared,
        )

    def remove(self, handle_or_index: ChartTrendline | int) -> None:
        """Remove a trendline by handle or 0-based integer index."""
        self._state.remove(handle_or_index)

    def clear(self) -> None:
        """Clear all supported trendlines from this series."""
        self._state.clear()

    def index_of_handle(self, handle: ChartTrendline) -> int:
        return self._state.index_of_handle(handle)

    def __repr__(self) -> str:
        self._state.load()
        count = len(self._state.entries) if self._state.family_error is None else 0
        return f"<ChartTrendlines count={count}>"
