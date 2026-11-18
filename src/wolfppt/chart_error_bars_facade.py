"""Facade for chart series error bars."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import Any, overload
from xml.etree import ElementTree as ET

from .chart_error_bars_xml import (
    SUPPORTED_PLOT_FAMILIES,
    ErrorBarEntry,
    ErrorBars3DPolicyError,
    ErrorBarsDuplicateAxisError,
    ErrorBarsRefusal,
    ErrorBarsSpec,
    ErrorBarsStaleHandleError,
    ErrorBarsUnsupportedError,
    ErrorBarsUnsupportedFamilyError,
    apply_chart_error_bar_edits,
)
from .chart_error_bars_xml import (
    determine_series_point_count as _determine_series_point_count,
)
from .chart_error_bars_xml import (
    is_3d_plot as _is_3d_plot,
)
from .chart_error_bars_xml import (
    normalize_color_hex as _normalize_color_hex,
)
from .chart_error_bars_xml import (
    normalize_direction as _normalize_direction,
)
from .chart_error_bars_xml import (
    normalize_value_type as _normalize_value_type,
)
from .chart_error_bars_xml import (
    parse_error_bar_element as _parse_error_bar_element,
)
from .chart_error_bars_xml import (
    resolve_series_and_plot as _resolve_series_and_plot,
)
from .chart_error_bars_xml import (
    supported_axes_for_plot as _supported_axes_for_plot,
)
from .chart_error_bars_xml import (
    validate_error_bar_parameters as _validate_error_bar_parameters,
)
from .chart_facade_helpers import (
    shape_chart_part as _shape_chart_part,
)
from .chart_facade_helpers import (
    shape_chart_root as _shape_chart_root,
)
from .xml_helpers import xml_local_name as _xml_local_name

__all__ = [
    "ChartErrorBar",
    "ChartErrorBars",
    "ErrorBarEntry",
    "ErrorBars3DPolicyError",
    "ErrorBarsDuplicateAxisError",
    "ErrorBarsRefusal",
    "ErrorBarsSpec",
    "ErrorBarsStaleHandleError",
    "ErrorBarsUnsupportedError",
    "ErrorBarsUnsupportedFamilyError",
    "apply_chart_error_bar_edits",
]


def _get_presentation(series: Any) -> Any:
    chart = getattr(series, "_chart", None)
    shape = getattr(chart, "_shape", None)
    if shape is None:
        raise AttributeError("series is not associated with a chart shape")
    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise AttributeError("chart shape is not associated with any slide")
    prs = getattr(slide, "_presentation", None)
    if prs is None:
        raise AttributeError("slide is not associated with a presentation")
    return prs


def _check_shape_and_slide_live(shape: Any) -> None:
    payload = getattr(shape, "_payload", {})
    if isinstance(payload, dict):
        if payload.get("_deleted"):
            raise ValueError("cannot edit or read error bars of a deleted shape")
        if payload.get("_stale"):
            raise ValueError("cannot edit or read error bars of a stale shape")
        if payload.get("_pending_shape") or payload.get("_pending_group_child"):
            raise ValueError("cannot edit or read error bars of an unsaved shape")

    if getattr(shape, "_deleted", False):
        raise ValueError("cannot edit or read error bars of a deleted shape")

    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise ValueError("chart shape is not associated with any slide")
    if getattr(slide, "_deleted", False):
        raise ValueError("cannot edit or read error bars on a deleted slide")

    prs = getattr(slide, "_presentation", None)
    if prs is not None:
        slides = getattr(prs, "_slides", None)
        if slides is not None and slide not in slides:
            raise ValueError("cannot edit or read error bars on a deleted slide")
        slide_deletions = getattr(prs, "_slide_deletions", None)
        if slide_deletions and getattr(slide, "partname", None) in slide_deletions:
            raise ValueError("cannot edit or read error bars on a deleted slide")
        shape_deletes = getattr(prs, "_shape_deletes", None)
        shape_index = getattr(shape, "_index", None)
        if (
            shape_deletes
            and getattr(slide, "partname", None) in shape_deletes
            and shape_index is not None
            and shape_index in shape_deletes[slide.partname]
        ):
            raise ValueError("cannot edit or read error bars of a deleted shape")


class _SeriesErrorBarsState:
    """Authoritative state for a series' error bars, attached to Presentation."""

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
        self.plot_elem: ET.Element | None = None
        self.family_error: ErrorBarsRefusal | None = None
        self.entries: list[ErrorBarEntry] = []
        self.live_handles: dict[int, ChartErrorBar] = {}
        self.stale_handle_ids: set[int] = set()
        self.next_handle_id: int = 1
        self._loaded: bool = False

    def load(self) -> None:
        if self._loaded:
            return

        try:
            root = _shape_chart_root(self.shape)
        except Exception as exc:
            raise ErrorBarsRefusal(f"malformed chart error bars source XML: {exc}") from exc

        try:
            series_elem, plot_elem = _resolve_series_and_plot(root, self.series_index)
        except (ErrorBars3DPolicyError, ErrorBarsUnsupportedFamilyError):
            raise
        except Exception as exc:
            raise ErrorBarsRefusal(f"malformed chart series XML: {exc}") from exc

        plot_family = _xml_local_name(plot_elem.tag)
        self.plot_family = plot_family
        self.plot_elem = plot_elem
        if _is_3d_plot(plot_family):
            self.family_error = ErrorBars3DPolicyError(
                f"error bars are not supported on 3-D chart family {plot_family!r}"
            )
        elif plot_family not in SUPPORTED_PLOT_FAMILIES:
            self.family_error = ErrorBarsUnsupportedFamilyError(
                f"error bars are not supported on chart family {plot_family!r}; "
                f"supported families: {sorted(SUPPORTED_PLOT_FAMILIES)}"
            )

        # Check if presentation already holds pending edits for this series
        edits = getattr(self.prs, "_chart_error_bar_edits", None)
        pending_spec: ErrorBarsSpec | None = None
        if isinstance(edits, dict):
            pending_spec = edits.get((self.chart_part, self.series_index))

        if pending_spec is not None:
            self.entries = []
            for entry in pending_spec.entries:
                if entry.handle_id <= 0:
                    entry = replace(entry, handle_id=self._alloc_id())
                elif entry.handle_id >= self.next_handle_id:
                    self.next_handle_id = entry.handle_id + 1
                self.entries.append(entry)
        elif self.family_error is None:
            existing_elems = [c for c in list(series_elem) if _xml_local_name(c.tag) == "errBars"]
            self.entries = []
            for elem in existing_elems:
                handle_id = self._alloc_id()
                try:
                    entry = _parse_error_bar_element(elem, handle_id=handle_id)
                except Exception as exc:
                    raise ErrorBarsRefusal(
                        f"malformed errBars element in source XML: {exc}"
                    ) from exc
                self.entries.append(entry)

        self._loaded = True

    def _alloc_id(self) -> int:
        hid = self.next_handle_id
        self.next_handle_id += 1
        return hid

    def _queue(self) -> None:
        if not hasattr(self.prs, "_queue_chart_error_bars"):
            raise AttributeError(
                "presentation does not implement canonical _queue_chart_error_bars"
            )
        queue_fn = self.prs._queue_chart_error_bars
        if not callable(queue_fn):
            raise TypeError("presentation canonical _queue_chart_error_bars is not callable")
        spec = ErrorBarsSpec(entries=tuple(self.entries))
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
                raise ErrorBars3DPolicyError(
                    f"error bars are not supported on 3-D chart family {plot_family!r}"
                )
            if plot_family not in SUPPORTED_PLOT_FAMILIES:
                raise ErrorBarsUnsupportedFamilyError(
                    f"error bars are not supported on chart family {plot_family!r}; "
                    f"supported families: {sorted(SUPPORTED_PLOT_FAMILIES)}"
                )
        except (ErrorBars3DPolicyError, ErrorBarsUnsupportedFamilyError):
            raise
        except (KeyError, AttributeError, ValueError, IndexError, OSError):
            pass

    def get_handle(self, entry: ErrorBarEntry) -> ChartErrorBar:
        handle = self.live_handles.get(entry.handle_id)
        if handle is None or handle._stale:
            handle = ChartErrorBar(state=self, handle_id=entry.handle_id)
            self.live_handles[entry.handle_id] = handle
        return handle

    def add(
        self,
        type: str = "fixedValue",
        *,
        value_type: str | None = None,
        direction: str = "both",
        value: float | None = None,
        axis: str | None = None,
        end_caps: bool = True,
        plus: Sequence[float] | None = None,
        minus: Sequence[float] | None = None,
        plus_values: Sequence[float] | None = None,
        minus_values: Sequence[float] | None = None,
        line_color: str | None = None,
        line_rgb: str | None = None,
        plus_reference: str | None = None,
        minus_reference: str | None = None,
    ) -> ChartErrorBar:
        self.validate_family()
        root = _shape_chart_root(self.shape)
        series_elem, plot_elem = _resolve_series_and_plot(root, self.series_index)
        plot_family = _xml_local_name(plot_elem.tag)
        supported_axes = _supported_axes_for_plot(plot_elem)

        resolved_axis: str
        if axis is None:
            if plot_family in ("scatterChart", "bubbleChart"):
                resolved_axis = "y"
            elif supported_axes:
                resolved_axis = min(supported_axes)
            else:
                resolved_axis = "y"
        else:
            resolved_axis = axis.strip().lower()

        resolved_val_type = value_type or type
        resolved_color = line_color or line_rgb
        resolved_plus = plus if plus is not None else plus_values
        resolved_minus = minus if minus is not None else minus_values

        existing_axes = {e.axis.lower() for e in self.entries}
        pt_count = _determine_series_point_count(series_elem, axis=resolved_axis)

        _validate_error_bar_parameters(
            resolved_val_type,
            direction=direction,
            value=value,
            axis=resolved_axis,
            end_caps=end_caps,
            plus=resolved_plus,
            minus=resolved_minus,
            line_color=resolved_color,
            series_point_count=pt_count,
            plot_elem=plot_elem,
            existing_axes=existing_axes,
            plus_reference=plus_reference,
            minus_reference=minus_reference,
        )

        norm_dir = _normalize_direction(direction)
        norm_val_type = _normalize_value_type(resolved_val_type)

        norm_plus: tuple[float, ...] | None = None
        norm_minus: tuple[float, ...] | None = None
        if norm_val_type == "custom":
            if resolved_plus is not None:
                norm_plus = tuple(float(x) for x in resolved_plus)
            if resolved_minus is not None:
                norm_minus = tuple(float(x) for x in resolved_minus)
            if norm_dir == "both":
                if norm_plus is None and plus_reference is None:
                    norm_plus = norm_minus
                    plus_reference = minus_reference
                elif norm_minus is None and minus_reference is None:
                    norm_minus = norm_plus
                    minus_reference = plus_reference

        entry = ErrorBarEntry(
            axis=resolved_axis,
            direction=norm_dir,
            value_type=norm_val_type,
            value=float(value) if value is not None else None,
            end_caps=end_caps,
            plus_values=norm_plus,
            minus_values=norm_minus,
            line_color=_normalize_color_hex(resolved_color) if resolved_color else None,
            is_supported=True,
            raw_xml=None,
            handle_id=self._alloc_id(),
            plus_reference=plus_reference,
            minus_reference=minus_reference,
        )
        self.entries.append(entry)
        self._queue()
        return self.get_handle(entry)

    def update(
        self,
        handle_or_index: ChartErrorBar | int,
        *,
        type: str | None = None,
        value_type: str | None = None,
        direction: str | None = None,
        value: float | None = None,
        axis: str | None = None,
        end_caps: bool | None = None,
        plus: Sequence[float] | None = None,
        minus: Sequence[float] | None = None,
        plus_values: Sequence[float] | None = None,
        minus_values: Sequence[float] | None = None,
        line_color: str | None = None,
        line_rgb: str | None = None,
        plus_reference: str | None = None,
        minus_reference: str | None = None,
    ) -> ChartErrorBar:
        self.validate_family()
        target_idx: int
        if isinstance(handle_or_index, ChartErrorBar):
            target_idx = self.index_of_handle(handle_or_index)
        elif isinstance(handle_or_index, int):
            if isinstance(handle_or_index, bool):
                raise TypeError("error bar index must be an integer, not bool")
            idx = handle_or_index
            if idx < 0:
                idx += len(self.entries)
            if idx < 0 or idx >= len(self.entries):
                raise IndexError(
                    f"error bar index {idx} out of range "
                    f"(series has {len(self.entries)} error bars)"
                )
            target_idx = idx
        else:
            raise TypeError(
                f"expected ChartErrorBar or int index, got {type(handle_or_index).__name__}"
            )

        old_entry = self.entries[target_idx]
        if not old_entry.is_supported:
            raise ErrorBarsUnsupportedError(
                "cannot modify unsupported error bar with foreign content"
            )

        root = _shape_chart_root(self.shape)
        series_elem, plot_elem = _resolve_series_and_plot(root, self.series_index)

        new_axis = axis.strip().lower() if axis is not None else old_entry.axis
        other_axes = {e.axis.lower() for i, e in enumerate(self.entries) if i != target_idx}

        new_val_type = value_type or type or old_entry.value_type
        new_direction = direction if direction is not None else old_entry.direction
        new_end_caps = end_caps if end_caps is not None else old_entry.end_caps

        new_color = line_color or line_rgb
        if new_color is None:
            new_color = old_entry.line_color

        explicit_plus = plus if plus is not None else plus_values
        explicit_minus = minus if minus is not None else minus_values
        plus_changed = explicit_plus is not None or plus_reference is not None
        minus_changed = explicit_minus is not None or minus_reference is not None
        new_plus = explicit_plus if plus_changed else old_entry.plus_values
        new_minus = explicit_minus if minus_changed else old_entry.minus_values
        new_plus_reference = plus_reference if plus_changed else old_entry.plus_reference
        new_minus_reference = minus_reference if minus_changed else old_entry.minus_reference

        new_value: float | None
        norm_val_type = _normalize_value_type(new_val_type)
        if norm_val_type in ("custom", "stdErr"):
            new_value = None
        else:
            new_value = value if value is not None else old_entry.value

        pt_count = _determine_series_point_count(series_elem, axis=new_axis)

        _validate_error_bar_parameters(
            norm_val_type,
            direction=new_direction,
            value=new_value,
            axis=new_axis,
            end_caps=new_end_caps,
            plus=(
                None
                if old_entry.plus_reference and old_entry.plus_source_xml and not plus_changed
                else new_plus
            ),
            minus=(
                None
                if old_entry.minus_reference and old_entry.minus_source_xml and not minus_changed
                else new_minus
            ),
            line_color=new_color,
            series_point_count=pt_count,
            plot_elem=plot_elem,
            existing_axes=other_axes,
            plus_reference=new_plus_reference,
            minus_reference=new_minus_reference,
        )

        norm_dir = _normalize_direction(new_direction)
        norm_plus_tuple: tuple[float, ...] | None = None
        norm_minus_tuple: tuple[float, ...] | None = None
        if norm_val_type == "custom":
            if new_plus is not None:
                norm_plus_tuple = tuple(float(x) for x in new_plus)
            if new_minus is not None:
                norm_minus_tuple = tuple(float(x) for x in new_minus)
            if norm_dir == "both":
                if norm_plus_tuple is None and new_plus_reference is None:
                    norm_plus_tuple = norm_minus_tuple
                    new_plus_reference = new_minus_reference
                elif norm_minus_tuple is None and new_minus_reference is None:
                    norm_minus_tuple = norm_plus_tuple
                    new_minus_reference = new_plus_reference

        updated_entry = ErrorBarEntry(
            axis=new_axis,
            direction=norm_dir,
            value_type=norm_val_type,
            value=float(new_value) if new_value is not None else None,
            end_caps=new_end_caps,
            plus_values=norm_plus_tuple,
            minus_values=norm_minus_tuple,
            line_color=_normalize_color_hex(new_color) if new_color else None,
            is_supported=True,
            raw_xml=None,
            handle_id=old_entry.handle_id,
            plus_reference=new_plus_reference,
            minus_reference=new_minus_reference,
            plus_source_xml=None if plus_changed else old_entry.plus_source_xml,
            minus_source_xml=None if minus_changed else old_entry.minus_source_xml,
        )
        self.entries[target_idx] = updated_entry
        self._queue()
        return self.get_handle(updated_entry)

    def remove(self, handle_or_index: ChartErrorBar | int) -> None:
        self.validate_family()
        if isinstance(handle_or_index, ChartErrorBar):
            handle = handle_or_index
            if handle.state is not self:
                raise ErrorBarsStaleHandleError(
                    "error bar handle is stale or from a different series"
                )
            if handle._stale or handle.handle_id in self.stale_handle_ids:
                raise ErrorBarsStaleHandleError("error bar handle is stale or already removed")
            target_idx: int | None = None
            for idx, entry in enumerate(self.entries):
                if entry.handle_id == handle.handle_id:
                    target_idx = idx
                    break
            if target_idx is None:
                raise ErrorBarsStaleHandleError("error bar handle is stale or already removed")
        elif isinstance(handle_or_index, int):
            if isinstance(handle_or_index, bool):
                raise TypeError("error bar index must be an integer, not bool")
            idx = handle_or_index
            if idx < 0:
                idx += len(self.entries)
            if idx < 0 or idx >= len(self.entries):
                raise IndexError(
                    f"error bar index {idx} out of range "
                    f"(series has {len(self.entries)} error bars)"
                )
            target_idx = idx
        else:
            raise TypeError(
                f"expected ChartErrorBar or int index, got {type(handle_or_index).__name__}"
            )

        entry = self.entries[target_idx]
        if not entry.is_supported:
            raise ErrorBarsUnsupportedError("unsupported error bar with foreign content")

        self.stale_handle_ids.add(entry.handle_id)
        if entry.handle_id in self.live_handles:
            self.live_handles[entry.handle_id]._stale = True

        del self.entries[target_idx]
        self._queue()

    def clear(self) -> None:
        self.validate_family()
        preserved: list[ErrorBarEntry] = []
        for entry in self.entries:
            if entry.is_supported:
                self.stale_handle_ids.add(entry.handle_id)
                if entry.handle_id in self.live_handles:
                    self.live_handles[entry.handle_id]._stale = True
            else:
                preserved.append(entry)
        self.entries = preserved
        self._queue()

    def index_of_handle(self, handle: ChartErrorBar) -> int:
        if handle.state is not self:
            raise ErrorBarsStaleHandleError("error bar handle is stale or from a different series")
        if handle._stale or handle.handle_id in self.stale_handle_ids:
            raise ErrorBarsStaleHandleError("error bar handle is stale or already removed")
        for idx, entry in enumerate(self.entries):
            if entry.handle_id == handle.handle_id:
                return idx
        raise ErrorBarsStaleHandleError("error bar handle is stale or already removed")

    def sync(self, shape: Any) -> None:
        _check_shape_and_slide_live(shape)
        self.shape = shape
        edits = getattr(self.prs, "_chart_error_bar_edits", None)
        if isinstance(edits, dict) and (self.chart_part, self.series_index) in edits:
            queued_spec = edits[(self.chart_part, self.series_index)]
            if len(self.entries) != len(queued_spec.entries) or any(
                e.axis != qe.axis or e.value_type != qe.value_type
                for e, qe in zip(self.entries, queued_spec.entries, strict=True)
            ):
                self.entries = list(queued_spec.entries)


def _get_or_create_series_error_bars_state(series: Any) -> _SeriesErrorBarsState:
    prs = _get_presentation(series)
    chart = getattr(series, "_chart", None)
    shape = getattr(chart, "_shape", None)
    if shape is None:
        raise AttributeError("chart shape is unavailable")
    chart_part = _shape_chart_part(shape)
    series_index = int(series.index)
    key = (chart_part, series_index)

    states = getattr(prs, "_chart_error_bar_states", None)
    if states is None:
        states = {}
        prs._chart_error_bar_states = states

    state = states.get(key)
    if state is None:
        state = _SeriesErrorBarsState(prs, chart_part, series_index, shape)
        states[key] = state
        state.load()
    else:
        state.sync(shape)
    return state


class ChartErrorBar:
    """Handle representing an individual chart series error bar.

    Exposes parsed properties, mutator property setters, .update(), and .remove().
    If the error bar carries unsupported foreign children or attributes from
    the source document, is_supported is False and direct modification or
    removal is rejected with ErrorBarsUnsupportedError.
    """

    def __init__(
        self,
        state: _SeriesErrorBarsState,
        handle_id: int,
    ) -> None:
        self._state = state
        self._handle_id = handle_id
        self._stale = False

    @property
    def handle_id(self) -> int:
        return self._handle_id

    @property
    def state(self) -> _SeriesErrorBarsState:
        return self._state

    def _entry(self) -> ErrorBarEntry:
        if self._stale or self._handle_id in self._state.stale_handle_ids:
            self._stale = True
            raise ErrorBarsStaleHandleError("error bar handle is stale or already removed")
        for entry in self._state.entries:
            if entry.handle_id == self._handle_id:
                return entry
        self._stale = True
        raise ErrorBarsStaleHandleError("error bar handle is stale or already removed")

    @property
    def axis(self) -> str:
        """Error bar axis ('x' or 'y')."""
        return self._entry().axis

    @axis.setter
    def axis(self, value: str) -> None:
        self.update(axis=value)

    @property
    def direction(self) -> str:
        """Error bar direction ('both', 'plus', or 'minus')."""
        return self._entry().direction

    @direction.setter
    def direction(self, value: str) -> None:
        self.update(direction=value)

    @property
    def value_type(self) -> str:
        """Error bar value type ('fixedValue', 'percentage', 'stdDev', 'stdErr', 'custom')."""
        return self._entry().value_type

    @value_type.setter
    def value_type(self, value: str) -> None:
        self.update(value_type=value)

    @property
    def type(self) -> str:
        """Alias for value_type."""
        return self.value_type

    @type.setter
    def type(self, value: str) -> None:
        self.update(type=value)

    @property
    def value(self) -> float | None:
        """Error bar numeric value for fixedValue, percentage, or stdDev."""
        return self._entry().value

    @value.setter
    def value(self, val: float | None) -> None:
        self.update(value=val)

    @property
    def end_caps(self) -> bool:
        """Whether end caps are displayed on the error bars."""
        return self._entry().end_caps

    @end_caps.setter
    def end_caps(self, value: bool) -> None:
        self.update(end_caps=value)

    @property
    def has_end_caps(self) -> bool:
        """Alias for end_caps."""
        return self.end_caps

    @has_end_caps.setter
    def has_end_caps(self, value: bool) -> None:
        self.update(end_caps=value)

    @property
    def plus(self) -> tuple[float, ...] | None:
        """Custom positive error values tuple, or None."""
        return self._entry().plus_values

    @plus.setter
    def plus(self, values: Sequence[float] | None) -> None:
        self.update(plus=values)

    @property
    def plus_values(self) -> tuple[float, ...] | None:
        """Alias for plus."""
        return self.plus

    @plus_values.setter
    def plus_values(self, values: Sequence[float] | None) -> None:
        self.update(plus=values)

    @property
    def minus(self) -> tuple[float, ...] | None:
        """Custom negative error values tuple, or None."""
        return self._entry().minus_values

    @minus.setter
    def minus(self, values: Sequence[float] | None) -> None:
        self.update(minus=values)

    @property
    def minus_values(self) -> tuple[float, ...] | None:
        """Alias for minus."""
        return self.minus

    @minus_values.setter
    def minus_values(self, values: Sequence[float] | None) -> None:
        self.update(minus=values)

    @property
    def plus_reference(self) -> str | None:
        """Positive c:numRef formula, or None for a literal source.

        Use update(plus_reference="Sheet1!$B$2:$B$4", plus=[1, 2, 3])
        to supply a formula with a numeric cache. Omit plus for no cache.
        Assign plus values alone to replace the reference with literals.
        """
        return self._entry().plus_reference

    @plus_reference.setter
    def plus_reference(self, formula: str) -> None:
        self.update(plus_reference=formula)

    @property
    def minus_reference(self) -> str | None:
        """Negative c:numRef formula; use minus for its optional numeric cache."""
        return self._entry().minus_reference

    @minus_reference.setter
    def minus_reference(self, formula: str) -> None:
        self.update(minus_reference=formula)

    @property
    def line_color(self) -> str | None:
        """Line color in 6-character hex RGB format (e.g. 'FF0000'), or None."""
        return self._entry().line_color

    @line_color.setter
    def line_color(self, color: str | None) -> None:
        self.update(line_color=color)

    @property
    def line_rgb(self) -> str | None:
        """Alias for line_color."""
        return self.line_color

    @line_rgb.setter
    def line_rgb(self, color: str | None) -> None:
        self.update(line_rgb=color)

    @property
    def is_supported(self) -> bool:
        """Whether this error bar conforms to the editable authoring subset."""
        return self._entry().is_supported

    @property
    def index(self) -> int:
        """Current 0-based position of this error bar in the series collection."""
        return self._state.index_of_handle(self)

    def update(
        self,
        *,
        type: str | None = None,
        value_type: str | None = None,
        direction: str | None = None,
        value: float | None = None,
        axis: str | None = None,
        end_caps: bool | None = None,
        plus: Sequence[float] | None = None,
        minus: Sequence[float] | None = None,
        plus_values: Sequence[float] | None = None,
        minus_values: Sequence[float] | None = None,
        line_color: str | None = None,
        line_rgb: str | None = None,
        plus_reference: str | None = None,
        minus_reference: str | None = None,
    ) -> ChartErrorBar:
        """Update properties of this error bar."""
        return self._state.update(
            self,
            type=type,
            value_type=value_type,
            direction=direction,
            value=value,
            axis=axis,
            end_caps=end_caps,
            plus=plus,
            minus=minus,
            plus_values=plus_values,
            minus_values=minus_values,
            line_color=line_color,
            line_rgb=line_rgb,
            plus_reference=plus_reference,
            minus_reference=minus_reference,
        )

    def remove(self) -> None:
        """Remove this error bar from its owning series."""
        self._state.remove(self)

    def __repr__(self) -> str:
        try:
            entry = self._entry()
            return (
                f"<ChartErrorBar axis={entry.axis!r} direction={entry.direction!r} "
                f"type={entry.value_type!r} value={entry.value!r}>"
            )
        except ErrorBarsStaleHandleError:
            return f"<ChartErrorBar (stale handle_id={self._handle_id})>"


class ChartErrorBars(Sequence[ChartErrorBar]):
    """Collection facade for chart series error bars.

    Supports iteration, len(), integer indexing, add(), update(), remove(), and clear().
    Multiple error bars (up to X and Y) are supported on scatter and bubble series.
    Categorical series (bar, line, area) support error bars on their value axis.
    Unsupported chart families and 3-D policy cases are refused with named boundaries.
    """

    def __init__(self, series: Any) -> None:
        self._series = series
        self._state = _get_or_create_series_error_bars_state(series)

    def __len__(self) -> int:
        self._state.load()
        if self._state.family_error is not None:
            return 0
        return len(self._state.entries)

    def __iter__(self) -> Iterator[ChartErrorBar]:
        self._state.load()
        if self._state.family_error is not None:
            return iter(())
        for entry in list(self._state.entries):
            yield self._state.get_handle(entry)

    @overload
    def __getitem__(self, index: int) -> ChartErrorBar: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[ChartErrorBar]: ...

    def __getitem__(self, index: int | slice) -> ChartErrorBar | Sequence[ChartErrorBar]:
        self._state.load()
        if self._state.family_error is not None:
            raise IndexError("chart series does not support error bars")
        if isinstance(index, slice):
            return [self._state.get_handle(e) for e in self._state.entries[index]]
        entry = self._state.entries[index]
        return self._state.get_handle(entry)

    def add(
        self,
        type: str = "fixedValue",
        *,
        value_type: str | None = None,
        direction: str = "both",
        value: float | None = None,
        axis: str | None = None,
        end_caps: bool = True,
        plus: Sequence[float] | None = None,
        minus: Sequence[float] | None = None,
        plus_values: Sequence[float] | None = None,
        minus_values: Sequence[float] | None = None,
        line_color: str | None = None,
        line_rgb: str | None = None,
        plus_reference: str | None = None,
        minus_reference: str | None = None,
    ) -> ChartErrorBar:
        """Add an error bar; custom references use plus/minus as optional caches."""
        return self._state.add(
            type=type,
            value_type=value_type,
            direction=direction,
            value=value,
            axis=axis,
            end_caps=end_caps,
            plus=plus,
            minus=minus,
            plus_values=plus_values,
            minus_values=minus_values,
            line_color=line_color,
            line_rgb=line_rgb,
            plus_reference=plus_reference,
            minus_reference=minus_reference,
        )

    def update(
        self,
        handle_or_index: ChartErrorBar | int,
        *,
        type: str | None = None,
        value_type: str | None = None,
        direction: str | None = None,
        value: float | None = None,
        axis: str | None = None,
        end_caps: bool | None = None,
        plus: Sequence[float] | None = None,
        minus: Sequence[float] | None = None,
        plus_values: Sequence[float] | None = None,
        minus_values: Sequence[float] | None = None,
        line_color: str | None = None,
        line_rgb: str | None = None,
        plus_reference: str | None = None,
        minus_reference: str | None = None,
    ) -> ChartErrorBar:
        """Update an existing error bar by handle or index."""
        return self._state.update(
            handle_or_index,
            type=type,
            value_type=value_type,
            direction=direction,
            value=value,
            axis=axis,
            end_caps=end_caps,
            plus=plus,
            minus=minus,
            plus_values=plus_values,
            minus_values=minus_values,
            line_color=line_color,
            line_rgb=line_rgb,
            plus_reference=plus_reference,
            minus_reference=minus_reference,
        )

    def remove(self, handle_or_index: ChartErrorBar | int) -> None:
        """Remove an error bar by handle or 0-based integer index."""
        self._state.remove(handle_or_index)

    def clear(self) -> None:
        """Clear all supported error bars from this series."""
        self._state.clear()

    def index_of_handle(self, handle: ChartErrorBar) -> int:
        return self._state.index_of_handle(handle)

    def get_by_axis(self, axis: str) -> ChartErrorBar | None:
        """Retrieve the error bar for a given axis ('x' or 'y'), or None if not present."""
        self._state.load()
        if self._state.family_error is not None:
            return None
        norm_axis = axis.strip().lower()
        for entry in self._state.entries:
            if entry.axis.lower() == norm_axis:
                return self._state.get_handle(entry)
        return None

    @property
    def x(self) -> ChartErrorBar | None:
        """Convenience property for X-axis error bar."""
        return self.get_by_axis("x")

    @property
    def y(self) -> ChartErrorBar | None:
        """Convenience property for Y-axis error bar."""
        return self.get_by_axis("y")

    def __repr__(self) -> str:
        self._state.load()
        count = len(self._state.entries) if self._state.family_error is None else 0
        return f"<ChartErrorBars count={count}>"
