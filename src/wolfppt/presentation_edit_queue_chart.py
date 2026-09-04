"""Queued chart operations for the presentation facade."""

from __future__ import annotations

from typing import Any


class PresentationChartQueueMixin:
    def _queue_chart_data_replace(
        self,
        slide_index: int,
        shape_index: int,
        chart_data: dict[str, Any],
    ) -> None:
        self._chart_data_edits[(slide_index, shape_index)] = chart_data

    def _queue_chart_title(
        self,
        slide_index: int,
        shape_index: int,
        title: dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        if title.get("has_title") is False:
            self._chart_title_edits[key] = {"has_title": False}
            return
        queued = self._chart_title_edits.setdefault(key, {"has_title": True})
        _merge_chart_title_edit(queued, title)

    def _queue_chart_legend(
        self,
        slide_index: int,
        shape_index: int,
        legend: dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        if legend.get("has_legend") is False:
            self._chart_legend_edits[key] = {"has_legend": False}
            return
        queued = self._chart_legend_edits.setdefault(key, {"has_legend": True})
        queued.update(legend)

    def _queue_chart_font(
        self,
        slide_index: int,
        shape_index: int,
        font: dict[str, Any],
    ) -> None:
        self._chart_font_edits.setdefault((slide_index, shape_index), {}).update(font)

    def _queue_chart_data_labels(
        self,
        slide_index: int,
        shape_index: int,
        data_labels: dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        if data_labels.get("has_data_labels") is False:
            self._chart_data_label_edits[key] = {"has_data_labels": False}
            return
        queued = self._chart_data_label_edits.setdefault(
            key,
            {"has_data_labels": True},
        )
        if "point_labels" in data_labels:
            _merge_scoped_chart_edits(
                queued,
                "point_labels",
                data_labels["point_labels"],
                ("series_index", "point_index"),
            )
            data_labels = {
                attr: value
                for attr, value in data_labels.items()
                if attr != "point_labels"
            }
        if "point_formats" in data_labels:
            _merge_scoped_chart_edits(
                queued,
                "point_formats",
                data_labels["point_formats"],
                ("series_index", "point_index"),
            )
            data_labels = {
                attr: value
                for attr, value in data_labels.items()
                if attr != "point_formats"
            }
        if "point_marker_formats" in data_labels:
            _merge_scoped_chart_edits(
                queued,
                "point_marker_formats",
                data_labels["point_marker_formats"],
                ("series_index", "point_index"),
            )
            data_labels = {
                attr: value
                for attr, value in data_labels.items()
                if attr != "point_marker_formats"
            }
        if "series_formats" in data_labels:
            _merge_scoped_chart_edits(
                queued,
                "series_formats",
                data_labels["series_formats"],
                ("series_index",),
            )
            data_labels = {
                attr: value
                for attr, value in data_labels.items()
                if attr != "series_formats"
            }
        if "series_data_labels" in data_labels:
            queued.setdefault("series_data_labels", []).extend(
                data_labels["series_data_labels"]
            )
            data_labels = {
                attr: value
                for attr, value in data_labels.items()
                if attr != "series_data_labels"
            }
        queued.update(data_labels)

    def _queue_chart_plot_property(
        self,
        slide_index: int,
        shape_index: int,
        attr: str,
        value: Any,
    ) -> None:
        self._chart_plot_property_edits.setdefault(
            (slide_index, shape_index),
            {},
        )[attr] = value

    def _queue_chart_axis_title(
        self,
        slide_index: int,
        shape_index: int,
        axis: str,
        title: dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index, axis)
        if title.get("has_title") is False:
            self._chart_axis_title_edits[key] = {"has_title": False}
            return
        queued = self._chart_axis_title_edits.setdefault(key, {"has_title": True})
        _merge_chart_title_edit(queued, title)

    def _queue_chart_axis_property(
        self,
        slide_index: int,
        shape_index: int,
        axis: str,
        attr: str,
        value: Any,
    ) -> None:
        self._chart_axis_property_edits.setdefault(
            (slide_index, shape_index, axis),
            {},
        )[attr] = value

    def _queue_chart_style(
        self,
        slide_index: int,
        shape_index: int,
        style: int | None,
    ) -> None:
        self._chart_style_edits[(slide_index, shape_index)] = style


def _merge_scoped_chart_edits(
    queued: dict[str, Any],
    key: str,
    incoming: list[dict[str, Any]],
    identity_keys: tuple[str, ...],
) -> None:
    existing = queued.setdefault(key, [])
    for item in incoming:
        match = next(
            (
                candidate
                for candidate in existing
                if all(
                    candidate.get(identity) == item.get(identity)
                    for identity in identity_keys
                )
            ),
            None,
        )
        if match is None:
            existing.append(dict(item))
            continue
        match_properties = match.setdefault("properties", {})
        for attr, value in item.get("properties", {}).items():
            if attr == "run_formats":
                match_properties.setdefault("run_formats", []).extend(value)
                continue
            if attr == "paragraph_formats":
                _merge_scoped_chart_edits(
                    match_properties,
                    "paragraph_formats",
                    value,
                    ("paragraph_index",),
                )
                continue
            if attr == "paragraph_line_breaks":
                match_properties["paragraph_line_breaks"] = list(value)
                continue
            if attr == "font":
                match_properties.setdefault("font", {}).update(value)
                continue
            if attr in {"text", "paragraphs", "paragraph_runs"}:
                for text_attr in ("text", "paragraphs", "paragraph_runs"):
                    if text_attr != attr:
                        match_properties.pop(text_attr, None)
                if attr in {"text", "paragraphs"}:
                    match_properties.pop("paragraph_line_breaks", None)
            match_properties[attr] = value


def _merge_chart_title_edit(
    queued: dict[str, Any],
    incoming: dict[str, Any],
) -> None:
    title = dict(incoming)
    if "format" in title:
        queued.setdefault("format", {}).update(title.pop("format"))
    if "run_formats" in title:
        queued.setdefault("run_formats", []).extend(title.pop("run_formats"))
    if "paragraph_formats" in title:
        _merge_scoped_chart_edits(
            queued,
            "paragraph_formats",
            title.pop("paragraph_formats"),
            ("paragraph_index",),
        )
    for attr in ("text", "paragraphs", "paragraph_runs"):
        if attr not in title:
            continue
        for text_attr in ("text", "paragraphs", "paragraph_runs"):
            if text_attr != attr:
                queued.pop(text_attr, None)
        queued[attr] = title.pop(attr)
    queued.update(title)
