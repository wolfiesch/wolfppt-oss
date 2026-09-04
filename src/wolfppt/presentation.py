"""Python-compatible presentation facade backed by WolfPPT primitives."""

from __future__ import annotations

import posixpath
from collections.abc import Iterator, Sequence
from numbers import Number
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

from . import native
from .background_edits import (
    apply_background_fill_edits as _apply_background_fill_edits,
)
from .background_facade import Background
from .chart_xml import chart_type_payload_from_value as _chart_type_payload_from_value
from .chart_edits import (
    _apply_chart_add,
    _apply_chart_adds,
    _apply_chart_axis_property_edits,
    _apply_chart_axis_title_edits,
    _apply_chart_data_label_edits,
    _apply_chart_data_replace,
    _apply_chart_font_edits,
    _apply_chart_legend_edits,
    _apply_chart_plot_property_edits,
    _apply_chart_style_edits,
    _apply_chart_title_edits,
    _normalize_category_chart_data,
)
from .chart_facade import (
    Chart,
    ChartAxis,
    ChartAxisTitle,
    ChartAxisTitleTextFrame,
    ChartPoint,
    ChartPointCollection,
    ChartPlot,
    ChartPlotCollection,
    ChartSeries,
    ChartSeriesCollection,
    ChartTitle,
    ChartTitleTextFrame,
    DataLabel,
    DataLabels,
    Legend,
    MajorGridlines,
    Marker,
    TickLabels,
    _chart_axis_major_gridlines_element,
    _chart_axis_payload,
    _chart_axis_proxy_element,
    _chart_axis_text_default_run_properties,
    _chart_payload,
    _chart_text_default_run_properties,
    _chart_title_proxy_element,
    _shape_chart_part,
    _shape_chart_root,
)
from .chart_format_facade import (
    ChartColorFormat,
    ChartFillFormat,
    ChartFont,
    ChartFontColorFormat,
    ChartFontFillFormat,
    ChartFormat,
    ChartLineFillFormat,
    ChartLineFormat,
    _chart_format_fill_type,
    _chart_format_line_element,
    _chart_format_line_fill_type,
    _chart_format_rgb,
    _chart_format_shape_properties,
    _run_properties_fill_type,
    _run_properties_rgb,
)
from .core_properties import (
    CoreProperties,
)
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
    gradient_stop_element as _gradient_stop_element,
    set_shape_gradient_fill as _set_shape_gradient_fill,
    set_shape_no_fill as _set_shape_no_fill,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    set_shape_pattern_fill_color as _set_shape_pattern_fill_color,
    set_shape_solid_fill as _set_shape_solid_fill,
)
from .facade_values import (
    LANGUAGE_ID_NONE as _LANGUAGE_ID_NONE,
    centipoints_to_emu as _centipoints_to_emu,
    centipoints_value as _centipoints_value,
    color_type_value as _color_type_value,
    coerce_crop_fraction as _coerce_crop_fraction,
    coerce_emu as _coerce_emu,
    coerce_paragraph_level as _coerce_paragraph_level,
    coerce_positive_int as _coerce_positive_int,
    coerce_rotation_degrees as _coerce_rotation_degrees,
    emu_to_centipoints as _emu_to_centipoints,
    emu_value as _emu_value,
    fill_type_value as _fill_type_value,
    language_id_value as _language_id_value,
    line_dash_style_value as _line_dash_style_value,
    normalize_language_id as _normalize_language_id,
    normalize_line_dash_style as _normalize_line_dash_style,
    normalize_line_spacing as _normalize_line_spacing,
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
    normalize_pattern_type as _normalize_pattern_type,
    normalize_rgb as _normalize_rgb,
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
    normalize_theme_color as _normalize_theme_color,
    paragraph_alignment_value as _paragraph_alignment_value,
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
    pattern_type_value as _pattern_type_value,
    rgb_value as _rgb_value,
    rotation_degrees_from_units as _rotation_degrees_from_units,
    text_frame_auto_size_value as _text_frame_auto_size_value,
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
    theme_color_value as _theme_color_value,
)
from .image_dimensions import picture_dimensions as _picture_dimensions
from .native_batch import native_batch_edits as _native_batch_edits
from .notes_slide_edits import (
    default_notes_slide_shape_payloads as _default_notes_slide_shape_payloads,
    next_notes_slide_partname as _next_notes_slide_partname,
)
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    normalize_package_partname as _normalize_package_partname,
    package_xml_element as _package_xml_element,
    resolve_package_target as _resolve_package_target,
)
from .package_coalescing import (
    apply_simple_text_table_chart_replacements as _apply_simple_text_table_chart_replacements,
    simple_package_fast_path_available as _simple_package_fast_path_available,
)
from .presentation_size import (
    apply_presentation_size_edits as _apply_presentation_size_edits,
    coerce_slide_size_emu as _coerce_slide_size_emu,
    presentation_slide_size as _presentation_slide_size,
)
from .presentation_input import presentation_source_path as _presentation_source_path
from .presentation_save import (
    save_presentation as _save_presentation,
)
from .presentation_save_ops import PresentationSaveOps
from .presentation_edit_queue import PresentationEditQueueMixin
from .presentation_state import (
    initialize_presentation_state as _initialize_presentation_state,
)
from .presentation_slides import (
    NotesMaster,
    NotesSlide,
    NotesSlideShapes,
    Slide,
    SlideCollection,
    SlideLayout,
    SlideLayoutCollection,
    SlideMaster,
    SlideMasterCollection,
)
from .shape_payloads import (
    _set_shape_paragraph_font_payload,
    _shape_paragraph_alignments,
    _shape_paragraph_font_value,
    _shape_paragraph_line_breaks,
    _shape_paragraph_levels,
    _shape_paragraph_run_bold,
    _shape_paragraph_run_font_fill_type,
    _shape_paragraph_run_font_language,
    _shape_paragraph_run_font_name,
    _shape_paragraph_run_font_rgb,
    _shape_paragraph_run_font_size,
    _shape_paragraph_run_hyperlink_address,
    _shape_paragraph_run_italic,
    _shape_paragraph_run_underline,
    _shape_paragraph_runs,
    _shape_paragraph_spacing_values,
    _shape_paragraphs,
    _shape_transform,
    _shape_transform_value,
    _sync_shape_text_from_paragraph_runs,
)
from .shape_adds import (
    apply_shape_add as _apply_shape_add,
    coalesce_auto_shape_adjustments as _coalesce_auto_shape_adjustments,
    coalesce_auto_shape_text as _coalesce_auto_shape_text,
    coalesce_connected_connector_auto_shapes as _coalesce_connected_connector_auto_shapes,
    coalesce_table_cell_text as _coalesce_table_cell_text,
)
from .shape_facade import (
    ActionSetting,
    AdjustmentCollection,
    ColorFormat,
    FillFormat,
    GradientStop,
    GradientStopColorFormat,
    GradientStops,
    Hyperlink,
    LineFillFormat,
    LineFormat,
    MasterShape,
    MasterShapeCollection,
    PlaceholderCollection,
    PlaceholderFormat,
    ShadowFormat,
    Shape,
    ShapeCollection,
    _DetachedFillShape,
    _auto_shape_preset_geometry,
    _connector_preset_geometry,
    _detached_fill_parent,
    _notes_placeholder_basename,
    _picture_crop,
    _picture_crop_value,
    _placeholder_basename,
    _placeholder_type_value,
    _placeholder_type_xml,
    _set_picture_crop_value,
    _set_shape_transform_value,
    _shape_adjustment_actuals,
    _shape_adjustment_guides,
    _shape_auto_shape_preset_geometry,
    _shape_auto_shape_type_value,
    _shape_click_action_name,
    _shape_click_action_value,
    _shape_collection_table_count,
    _shape_fill_pattern,
    _shape_fill_type,
    _shape_gradient_fill_payload,
    _shape_hyperlink_address,
    _shape_hyperlink_click,
    _shape_is_text_box,
    _shape_line_dash_style,
    _shape_line_fill_pattern,
    _shape_line_fill_type,
    _shape_line_width,
    _shape_line_xml_element,
    _shape_pattern_rgb,
    _shape_picture_crop,
    _shape_shadow_inherit,
    _shape_style_rgb,
    _shape_target_slide,
    _shape_type_value,
    _supports_shape_line_style,
)
from .shape_xml import (
    _find_shape_transform_xml_element,
    _find_text_body_properties_element,
    _paragraph_xml_element,
    _picture_blip_fill_element,
    _shape_xml_element,
    _text_paragraph_content,
    _text_run_xml_element,
)
from .slide_edits import (
    _apply_group_child_paragraph_alignment_edits,
    _apply_group_child_paragraph_clear_edits,
    _apply_group_child_paragraph_font_edits,
    _apply_group_child_paragraph_line_break_edits,
    _apply_group_child_paragraph_level_edits,
    _apply_group_child_paragraph_spacing_edits,
    _apply_group_child_text_frame_auto_size_edits,
    _apply_group_child_text_frame_fit_edits,
    _apply_group_child_text_frame_margin_edits,
    _apply_group_child_text_frame_vertical_anchor_edits,
    _apply_group_child_text_frame_word_wrap_edits,
    _apply_group_child_text_run_font_edits,
    _apply_group_child_text_run_hyperlink_edits,
    _apply_nested_group_child_geometry_edits,
    _apply_paragraph_alignment_edits,
    _apply_paragraph_clear_edits,
    _apply_paragraph_font_edits,
    _apply_paragraph_level_edits,
    _apply_part_paragraph_font_edits,
    _apply_part_paragraph_property_edits,
    _apply_part_text_edits,
    _apply_nested_group_child_shape_text_edits,
    _apply_part_shape_hyperlink_edits,
    _apply_part_shape_text_edits,
    _apply_part_text_run_font_edits,
    _apply_part_text_run_hyperlink_edits,
    _apply_part_text_frame_auto_size_edits,
    _apply_part_text_frame_edits,
    _apply_part_text_frame_margin_edits,
    _apply_part_text_frame_vertical_anchor_edits,
    _apply_part_text_frame_word_wrap_edits,
    _apply_paragraph_line_break_edits,
    _apply_paragraph_property_edits,
    _apply_paragraph_spacing_edits,
    _apply_picture_crop_edits,
    _apply_connector_connection_edits,
    _apply_shape_adjustment_edits,
    _apply_shape_hyperlink_edits,
    _apply_shape_line_element_edits,
    _apply_shape_name_edits,
    _apply_shape_rotation_edits,
    _apply_shape_style_edits,
    _apply_shape_target_slide_edits,
    _apply_slide_name_edits,
    _apply_text_frame_auto_size_edits,
    _apply_text_frame_fit_edits,
    _apply_text_frame_margin_edits,
    _apply_text_frame_vertical_anchor_edits,
    _apply_text_frame_word_wrap_edits,
    _apply_text_run_font_color_edits,
    _apply_text_run_font_fill_type_edits,
    _apply_text_run_font_language_edits,
    _apply_text_run_hyperlink_edits,
    _part_shape_text_replacements,
    _shape_style_edits,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
    load_slide_layout_placeholder_payloads as _load_slide_layout_placeholder_payloads,
    load_slide_layout_payloads as _load_slide_layout_payloads,
    load_slide_master_payloads as _load_slide_master_payloads,
    load_slide_shell_payloads as _load_slide_shell_payloads,
)
from .text_facade import (
    ParagraphCollection,
    TextFrame,
    TextParagraph,
    TextParagraphFont,
    TextParagraphFontColorFormat,
    TextParagraphFontFillFormat,
    TextRun,
    TextRunCollection,
    TextRunColorFormat,
    TextRunFillFormat,
    TextRunFont,
    TextRunHyperlink,
    _best_fit_text_font_size,
    _is_appended_paragraph,
    _is_appended_run,
    _paragraph_spacing_value,
    _queue_paragraph_alignment_state,
    _queue_paragraph_clear_state,
    _queue_paragraph_font_state,
    _queue_paragraph_level_state,
    _queue_paragraph_line_break_state,
    _queue_paragraph_spacing_state,
    _queue_paragraph_state,
    _queue_run_bold_state,
    _queue_run_font_color_state,
    _queue_run_font_fill_type_state,
    _queue_run_font_language_state,
    _queue_run_font_name_state,
    _queue_run_font_size_state,
    _queue_run_italic_state,
    _queue_run_state,
    _queue_run_underline_state,
    _set_paragraph_spacing_payload,
    _set_text_frame_fit_payload,
    _set_text_frame_margin,
    _shape_rotation,
    _shape_paragraph_font_bold,
    _shape_paragraph_font_fill_type,
    _shape_paragraph_font_italic,
    _shape_paragraph_font_language,
    _shape_paragraph_font_name,
    _shape_paragraph_font_rgb,
    _shape_paragraph_font_size,
    _shape_paragraph_font_underline,
    _shape_paragraph_text,
    _shape_run_count_payload,
    _shape_run_index,
    _shape_text_frame_margins,
    _shape_text_paragraph_alignment,
    _shape_text_paragraph_default_run_properties,
    _shape_text_paragraph_font_bool,
    _shape_text_paragraph_font_fill_type,
    _shape_text_paragraph_font_language,
    _shape_text_paragraph_font_name,
    _shape_text_paragraph_font_rgb,
    _shape_text_paragraph_font_size,
    _shape_text_paragraph_font_underline,
    _shape_text_paragraph_level,
    _shape_text_paragraph_spacing,
    _shape_text_run_fill_type,
    _shape_text_run_hyperlink_address,
    _shape_text_run_language_id,
    _shape_text_run_rgb,
    _text_frame_auto_size,
    _text_frame_extents,
    _text_frame_margin,
    _text_frame_margin_name,
    _text_frame_vertical_anchor,
    _text_frame_word_wrap,
)
from .table_facade import (
    Table,
    TableCell,
    TableCellColorFormat,
    TableCellFillFormat,
    TableCellParagraphCollection,
    TableCellTextFrame,
    TableCellTextParagraph,
    TableColumn,
    TableColumnCollection,
    TableRow,
    TableRowCollection,
    _merge_table_cells,
    _normalize_table_rows,
    _set_table_cell_margin,
    _set_table_cell_text_frame_margin,
    _set_table_cell_text_frame_paragraphs,
    _set_table_cell_text_frame_text,
    _set_table_style_flag,
    _split_table_cell,
    _table_cell_fill_pattern,
    _table_cell_fill_type,
    _table_cell_margin,
    _table_cell_pattern_rgb,
    _table_cell_property_payload,
    _table_cell_solid_rgb,
    _table_cell_span,
    _table_cell_text_frame_auto_size,
    _table_cell_text_frame_margin,
    _table_cell_text_frame_paragraph_texts,
    _table_cell_text_frame_vertical_anchor,
    _table_cell_text_frame_word_wrap,
    _table_cell_vertical_anchor,
    _table_style_flag,
)
from .xml_helpers import (
    optional_bool_xml_attr as _optional_bool_xml_attr,
    xml_bool_value as _xml_bool_value,
    xml_local_name as _xml_local_name,
)
from .table_xml import (
    _apply_table_cell_merge_edits,
    _apply_table_cell_property_edits,
    _apply_table_dimension_edits,
    _apply_table_style_edits,
)
from .slide_metadata import (
    first_slide_master_partname as _first_slide_master_partname,
    package_relationships as _package_relationships,
    part_common_slide_name_from_path as _part_common_slide_name_from_path,
    presentation_notes_master_partname as _presentation_notes_master_partname,
    presentation_partname as _presentation_partname,
    slide_metadata as _slide_metadata,
    slide_name as _slide_name,
    slide_notes_partname as _slide_notes_partname,
)
from .slide_relationships import (
    slide_relationship_info as _slide_relationship_info,
    slide_relationship_target as _slide_relationship_target,
)


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
DCMITYPE_NS = "http://purl.org/dc/dcmitype/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("p", P_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("c", C_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("", PKG_REL_NS)
ET.register_namespace("cp", CP_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("dcterms", DCTERMS_NS)
ET.register_namespace("dcmitype", DCMITYPE_NS)
ET.register_namespace("xsi", XSI_NS)

_TEXT_FRAME_MARGIN_ATTRS = {
    "margin_left": "lIns",
    "margin_right": "rIns",
    "margin_top": "tIns",
    "margin_bottom": "bIns",
}
_TEXT_FRAME_MARGIN_DEFAULTS = {
    "lIns": 91440,
    "rIns": 91440,
    "tIns": 45720,
    "bIns": 45720,
}
_TEXT_FRAME_AUTO_SIZE_TAGS = {"noAutofit", "spAutoFit", "normAutofit"}


def _presentation_save_ops() -> PresentationSaveOps:
    return PresentationSaveOps(
        native=native,
        _apply_chart_add=_apply_chart_add,
        _apply_chart_adds=_apply_chart_adds,
        _apply_chart_axis_property_edits=_apply_chart_axis_property_edits,
        _apply_chart_axis_title_edits=_apply_chart_axis_title_edits,
        _apply_chart_data_label_edits=_apply_chart_data_label_edits,
        _apply_chart_data_replace=_apply_chart_data_replace,
        _apply_chart_font_edits=_apply_chart_font_edits,
        _apply_chart_legend_edits=_apply_chart_legend_edits,
        _apply_chart_plot_property_edits=_apply_chart_plot_property_edits,
        _apply_chart_style_edits=_apply_chart_style_edits,
        _apply_chart_title_edits=_apply_chart_title_edits,
        _apply_background_fill_edits=_apply_background_fill_edits,
        _native_batch_edits=_native_batch_edits,
        _apply_simple_text_table_chart_replacements=_apply_simple_text_table_chart_replacements,
        _simple_package_fast_path_available=_simple_package_fast_path_available,
        _apply_presentation_size_edits=_apply_presentation_size_edits,
        _apply_shape_add=_apply_shape_add,
        _coalesce_auto_shape_adjustments=_coalesce_auto_shape_adjustments,
        _coalesce_connected_connector_auto_shapes=_coalesce_connected_connector_auto_shapes,
        _coalesce_auto_shape_text=_coalesce_auto_shape_text,
        _coalesce_table_cell_text=_coalesce_table_cell_text,
        _apply_paragraph_alignment_edits=_apply_paragraph_alignment_edits,
        _apply_paragraph_clear_edits=_apply_paragraph_clear_edits,
        _apply_paragraph_font_edits=_apply_paragraph_font_edits,
        _apply_paragraph_level_edits=_apply_paragraph_level_edits,
        _apply_part_paragraph_font_edits=_apply_part_paragraph_font_edits,
        _apply_part_paragraph_property_edits=_apply_part_paragraph_property_edits,
        _apply_part_text_edits=_apply_part_text_edits,
        _apply_nested_group_child_shape_text_edits=(
            _apply_nested_group_child_shape_text_edits
        ),
        _apply_part_shape_hyperlink_edits=_apply_part_shape_hyperlink_edits,
        _apply_part_shape_text_edits=_apply_part_shape_text_edits,
        _apply_part_text_run_font_edits=_apply_part_text_run_font_edits,
        _apply_part_text_run_hyperlink_edits=_apply_part_text_run_hyperlink_edits,
        _apply_part_text_frame_auto_size_edits=_apply_part_text_frame_auto_size_edits,
        _apply_part_text_frame_edits=_apply_part_text_frame_edits,
        _apply_part_text_frame_margin_edits=_apply_part_text_frame_margin_edits,
        _apply_part_text_frame_vertical_anchor_edits=(
            _apply_part_text_frame_vertical_anchor_edits
        ),
        _apply_part_text_frame_word_wrap_edits=_apply_part_text_frame_word_wrap_edits,
        _apply_paragraph_line_break_edits=_apply_paragraph_line_break_edits,
        _apply_paragraph_property_edits=_apply_paragraph_property_edits,
        _apply_paragraph_spacing_edits=_apply_paragraph_spacing_edits,
        _apply_picture_crop_edits=_apply_picture_crop_edits,
        _apply_connector_connection_edits=_apply_connector_connection_edits,
        _apply_shape_adjustment_edits=_apply_shape_adjustment_edits,
        _apply_shape_hyperlink_edits=_apply_shape_hyperlink_edits,
        _apply_shape_line_element_edits=_apply_shape_line_element_edits,
        _apply_shape_name_edits=_apply_shape_name_edits,
        _apply_shape_rotation_edits=_apply_shape_rotation_edits,
        _apply_shape_style_edits=_apply_shape_style_edits,
        _apply_shape_target_slide_edits=_apply_shape_target_slide_edits,
        _apply_slide_name_edits=_apply_slide_name_edits,
        _apply_text_frame_auto_size_edits=_apply_text_frame_auto_size_edits,
        _apply_text_frame_fit_edits=_apply_text_frame_fit_edits,
        _apply_text_frame_margin_edits=_apply_text_frame_margin_edits,
        _apply_text_frame_vertical_anchor_edits=_apply_text_frame_vertical_anchor_edits,
        _apply_text_frame_word_wrap_edits=_apply_text_frame_word_wrap_edits,
        _apply_text_run_font_color_edits=_apply_text_run_font_color_edits,
        _apply_text_run_font_fill_type_edits=_apply_text_run_font_fill_type_edits,
        _apply_group_child_text_run_font_edits=_apply_group_child_text_run_font_edits,
        _apply_group_child_text_run_hyperlink_edits=_apply_group_child_text_run_hyperlink_edits,
        _apply_nested_group_child_geometry_edits=(
            _apply_nested_group_child_geometry_edits
        ),
        _apply_group_child_paragraph_alignment_edits=_apply_group_child_paragraph_alignment_edits,
        _apply_group_child_paragraph_clear_edits=_apply_group_child_paragraph_clear_edits,
        _apply_group_child_paragraph_font_edits=_apply_group_child_paragraph_font_edits,
        _apply_group_child_paragraph_line_break_edits=_apply_group_child_paragraph_line_break_edits,
        _apply_group_child_paragraph_level_edits=_apply_group_child_paragraph_level_edits,
        _apply_group_child_paragraph_spacing_edits=_apply_group_child_paragraph_spacing_edits,
        _apply_group_child_text_frame_auto_size_edits=_apply_group_child_text_frame_auto_size_edits,
        _apply_group_child_text_frame_fit_edits=_apply_group_child_text_frame_fit_edits,
        _apply_group_child_text_frame_margin_edits=_apply_group_child_text_frame_margin_edits,
        _apply_group_child_text_frame_vertical_anchor_edits=(
            _apply_group_child_text_frame_vertical_anchor_edits
        ),
        _apply_group_child_text_frame_word_wrap_edits=_apply_group_child_text_frame_word_wrap_edits,
        _apply_text_run_font_language_edits=_apply_text_run_font_language_edits,
        _apply_text_run_hyperlink_edits=_apply_text_run_hyperlink_edits,
        _part_shape_text_replacements=_part_shape_text_replacements,
        _shape_style_edits=_shape_style_edits,
        _apply_table_cell_merge_edits=_apply_table_cell_merge_edits,
        _apply_table_cell_property_edits=_apply_table_cell_property_edits,
        _apply_table_dimension_edits=_apply_table_dimension_edits,
        _apply_table_style_edits=_apply_table_style_edits,
    )


class Presentation(PresentationEditQueueMixin):
    """Open and edit an existing PowerPoint deck.

    This is the first python-pptx-style facade over WolfPPT's loss-aware native
    engine. It intentionally starts with existing-deck open/save plus slide,
    shape, and text access.
    """

    def __init__(self, path: Any = None) -> None:
        self._source_path, self._source_tempdir = _presentation_source_path(path)
        _initialize_presentation_state(self)
        self._load(self._source_path)

    @property
    def slides(self) -> "SlideCollection":
        return self._slides

    @property
    def slide_layouts(self) -> "SlideLayoutCollection":
        if self._slide_layouts is None:
            self._slide_layouts = SlideLayoutCollection(
                self,
                [
                    SlideLayout(self, index, layout)
                    for index, layout in enumerate(
                        _load_slide_layout_payloads(self._source_path)
                    )
                ],
            )
        return self._slide_layouts

    @property
    def slide_masters(self) -> "SlideMasterCollection":
        if self._slide_masters is None:
            self._slide_masters = SlideMasterCollection(
                self,
                [
                    SlideMaster(self, index, master)
                    for index, master in enumerate(
                        _load_slide_master_payloads(self._source_path)
                    )
                ],
            )
        return self._slide_masters

    @property
    def slide_master(self) -> "SlideMaster":
        return self.slide_masters[0]

    @property
    def notes_master(self) -> "NotesMaster":
        if self._notes_master is None:
            self._notes_master = NotesMaster(
                self,
                _presentation_notes_master_partname(self._source_path),
            )
        return self._notes_master

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(
            self._source_path,
            _presentation_partname(self._source_path),
        )

    @property
    def core_properties(self) -> CoreProperties:
        if self._core_properties is None:
            self._core_properties = CoreProperties(self)
        return self._core_properties

    @property
    def part(self) -> PackagePart:
        return PackagePart(
            self,
            _presentation_partname(self._source_path),
            name=None,
        )

    @property
    def slide_width(self) -> Any:
        return _emu_value(_presentation_slide_size(self)["cx"])

    @slide_width.setter
    def slide_width(self, value: Any) -> None:
        self._set_slide_size("cx", value, "slide_width")

    @property
    def slide_height(self) -> Any:
        return _emu_value(_presentation_slide_size(self)["cy"])

    @slide_height.setter
    def slide_height(self, value: Any) -> None:
        self._set_slide_size("cy", value, "slide_height")

    @property
    def path(self) -> Path:
        return self._source_path

    def save(self, path: Any) -> None:
        _save_presentation(self, path, _presentation_save_ops())

    def _ensure_notes_slide_for_slide(self, slide: Slide) -> str:
        metadata = _slide_metadata(slide)
        notes_part = metadata.get("notes_part")
        if notes_part:
            return str(notes_part)
        pending = self._notes_slide_adds.get(slide._index)
        if pending is not None:
            return pending[1]
        reserved = {notes_part for _, notes_part in self._notes_slide_adds.values()}
        notes_part = _next_notes_slide_partname(self._source_path, reserved)
        payloads = _default_notes_slide_shape_payloads()
        self._notes_slide_adds[slide._index] = (slide.partname, notes_part)
        self._pending_notes_slide_payloads[notes_part] = payloads
        self._part_shape_payload_cache[notes_part] = payloads
        if self._slide_metadata is not None:
            slide_metadata = self._slide_metadata.setdefault(slide.partname, {})
            slide_metadata["has_notes_slide"] = True
            slide_metadata["notes_part"] = notes_part
        return notes_part

    def _load(self, path: Path) -> None:
        slides = _load_slide_shell_payloads(path)
        self._slides = SlideCollection(
            self,
            [
                Slide(self, index, slide)
                for index, slide in enumerate(slides)
            ],
        )
        self._slide_metadata = _slide_metadata_cache_from_shells(slides)
        self._slide_layouts = None
        self._slide_masters = None
        self._notes_master = None
        self._core_properties = None
        self._notes_slide_adds.clear()
        self._pending_notes_slide_payloads.clear()


def _slide_metadata_cache_from_shells(
    slides: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    payload_keys = {"part", "texts", "shapes"}
    return {
        str(slide["part"]): {
            key: value
            for key, value in slide.items()
            if key not in payload_keys
        }
        for slide in slides
        if slide.get("part")
    }
