"""Python-compatible presentation facade backed by WolfPPT primitives."""

from __future__ import annotations

import hashlib
import io
import os
import posixpath
import tempfile
import threading
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from . import native
from .active_parts import (
    ActiveXControlSnapshot,
    CustomUI,
    VbaSignature,
)
from .active_parts import (
    read_activex_controls as _read_activex_controls,
)
from .active_parts import (
    read_custom_ui as _read_custom_ui,
)
from .active_parts import (
    read_vba_signatures as _read_vba_signatures,
)
from .chart_edits import _apply_chart_data_replace
from .comment_edits import (
    reset_comment_state as _reset_comment_state,
)
from .core_properties import (
    CoreProperties,
)
from .custom_shows import (
    CustomShowCollection,
)
from .custom_shows import (
    load_custom_shows as _load_custom_shows,
)
from .editions import commercial_module
from .facade_values import (
    emu_value as _emu_value,
)
from .notes_slide_edits import (
    default_notes_slide_shape_payloads as _default_notes_slide_shape_payloads,
)
from .notes_slide_edits import (
    next_notes_slide_partname as _next_notes_slide_partname,
)
from .package_coalescing import (
    apply_simple_text_table_chart_replacements as _apply_simple_text_table_chart_replacements,
)
from .package_parts import (
    InMemoryPackageSource,
    PackagePart,
    PresentationElementProxy,
    VbaModule,
    VbaProject,
    WebExtension,
    WebExtensionCollection,
    _validate_vba_module_name,
    _validate_vba_source,
)
from .package_parts import (
    inspect_vba_project as _inspect_vba_project,
)
from .package_read_scope import shared_package_reads as _shared_package_reads
from .presentation_edit_queue import PresentationEditQueueMixin
from .presentation_formats import OdpFormatError
from .presentation_formats import is_odp_package as _is_odp_package
from .presentation_formats import refuse_macro_package_as_pptx as _refuse_macro_package_as_pptx
from .presentation_input import presentation_source_path as _presentation_source_path
from .presentation_size import (
    presentation_slide_size as _presentation_slide_size,
)
from .presentation_slides import (
    HandoutMaster,
    NotesMaster,
    Slide,
    SlideCollection,
    SlideLayout,
    SlideLayoutCollection,
    SlideMaster,
    SlideMasterCollection,
    SlideShowSettings,
    default_handout_master_shape_payloads,
)
from .presentation_state import (
    initialize_presentation_state as _initialize_presentation_state,
)
from .presentation_watermark import (
    _image_extension as _image_extension,
)
from .presentation_watermark import (
    _watermark_box as _watermark_box,
)
from .presentation_watermark import (
    _watermark_plan as _watermark_plan,
)
from .presentation_watermark import (
    _watermark_shape as _watermark_shape,
)
from .presentation_watermark import (
    _WatermarkSpec as _WatermarkSpec,
)
from .shape_picture_correction_edits import (
    apply_picture_correction_edits as _apply_picture_correction_edits,
)
from .slide_edits import (
    _apply_part_shape_text_edits,
    _apply_part_text_edits,
    _apply_part_text_frame_edits,
    _apply_shape_name_edits,
    _apply_shape_rotation_edits,
    _apply_text_frame_auto_size_edits,
    _apply_text_frame_fit_edits,
    _apply_text_frame_margin_edits,
    _apply_text_frame_vertical_anchor_edits,
    _apply_text_frame_word_wrap_edits,
)
from .slide_metadata import (
    next_handout_master_partname as _next_handout_master_partname,
)
from .slide_metadata import (
    presentation_handout_master_partname as _presentation_handout_master_partname,
)
from .slide_metadata import (
    presentation_notes_master_partname as _presentation_notes_master_partname,
)
from .slide_metadata import (
    presentation_partname as _presentation_partname,
)
from .slide_metadata import (
    slide_metadata as _slide_metadata,
)
from .slide_payloads import (
    load_slide_layout_payloads as _load_slide_layout_payloads,
)
from .slide_payloads import (
    load_slide_master_payloads as _load_slide_master_payloads,
)
from .slide_payloads import (
    load_slide_shell_payloads as _load_slide_shell_payloads,
)
from .text_find_replace import (
    TextMatch,
    TextReplaceResult,
)
from .text_find_replace import (
    presentation_find_text as _presentation_find_text,
)
from .text_find_replace import (
    presentation_replace_text as _presentation_replace_text,
)

if TYPE_CHECKING:
    from .presentation_save_ops import PresentationSaveOps
    from .printing import CupsPrintBackend, PrintJobSettings, PrintSubmissionReport

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
    # Save-only collaborators are bound here so opening and read-only traversal do
    # not import them. The names kept at module scope above are read through this
    # module's globals on every save, so patching them there still takes effect.
    from .background_edits import (
        apply_background_fill_edits as _apply_background_fill_edits,
    )
    from .chart_edits import (
        _apply_chart_add,
        _apply_chart_adds,
        _apply_chart_axis_property_edits,
        _apply_chart_axis_title_edits,
        _apply_chart_data_label_edits,
        _apply_chart_font_edits,
        _apply_chart_legend_edits,
        _apply_chart_plot_property_edits,
        _apply_chart_style_edits,
        _apply_chart_title_edits,
    )
    from .chart_error_bars_xml import (
        apply_chart_error_bar_edits as _apply_chart_error_bar_edits,
    )
    from .chart_trendline_xml import (
        apply_chart_trendline_edits as _apply_chart_trendline_edits,
    )
    from .custom_property_edits import (
        apply_custom_properties_edits as _apply_custom_properties_edits,
    )
    from .extended_property_edits import (
        apply_extended_properties_edits as _apply_extended_properties_edits,
    )
    from .native_batch import native_batch_edits as _native_batch_edits
    from .package_coalescing import (
        simple_package_fast_path_available as _simple_package_fast_path_available,
    )
    from .presentation_save_ops import PresentationSaveOps
    from .presentation_size import (
        apply_presentation_size_edits as _apply_presentation_size_edits,
    )
    from .section_edits import (
        apply_section_edits as _apply_section_edits,
    )
    from .shape_adds import (
        apply_shape_add as _apply_shape_add,
    )
    from .shape_adds import (
        coalesce_auto_shape_adjustments as _coalesce_auto_shape_adjustments,
    )
    from .shape_adds import (
        coalesce_auto_shape_text as _coalesce_auto_shape_text,
    )
    from .shape_adds import (
        coalesce_connected_connector_auto_shapes as _coalesce_connected_connector_auto_shapes,
    )
    from .shape_adds import (
        coalesce_table_cell_text as _coalesce_table_cell_text,
    )
    from .shape_glow_edits import (
        apply_shape_glow_edits as _apply_shape_glow_edits,
    )
    from .shape_line_end_edits import (
        apply_shape_line_end_edits as _apply_shape_line_end_edits,
    )
    from .shape_lock_edits import (
        apply_shape_lock_edits as _apply_shape_lock_edits,
    )
    from .shape_picture_recolor_edits import (
        apply_picture_recolor_edits as _apply_picture_recolor_edits,
    )
    from .shape_picture_transparency_edits import (
        apply_picture_transparency_edits as _apply_picture_transparency_edits,
    )
    from .shape_shadow_edits import (
        apply_shape_effect_edits as _apply_shape_effect_edits,
    )
    from .shape_z_order_edits import (
        _apply_shape_z_order_edits,
    )
    from .slide_animation_edits import (
        apply_slide_animation_edits as _apply_slide_animation_edits,
    )
    from .slide_edits import (
        _apply_connector_connection_edits,
        _apply_group_child_paragraph_alignment_edits,
        _apply_group_child_paragraph_clear_edits,
        _apply_group_child_paragraph_font_edits,
        _apply_group_child_paragraph_level_edits,
        _apply_group_child_paragraph_line_break_edits,
        _apply_group_child_paragraph_spacing_edits,
        _apply_group_child_paragraph_tab_stop_edits,
        _apply_group_child_text_frame_advanced_edits,
        _apply_group_child_text_frame_auto_size_edits,
        _apply_group_child_text_frame_fit_edits,
        _apply_group_child_text_frame_margin_edits,
        _apply_group_child_text_frame_vertical_anchor_edits,
        _apply_group_child_text_frame_word_wrap_edits,
        _apply_group_child_text_run_font_edits,
        _apply_group_child_text_run_hyperlink_edits,
        _apply_nested_group_child_geometry_edits,
        _apply_nested_group_child_shape_text_edits,
        _apply_paragraph_alignment_edits,
        _apply_paragraph_clear_edits,
        _apply_paragraph_font_edits,
        _apply_paragraph_level_edits,
        _apply_paragraph_line_break_edits,
        _apply_paragraph_property_edits,
        _apply_paragraph_spacing_edits,
        _apply_paragraph_tab_stop_edits,
        _apply_part_paragraph_font_edits,
        _apply_part_paragraph_property_edits,
        _apply_part_paragraph_tab_stop_edits,
        _apply_part_shape_hyperlink_edits,
        _apply_part_text_frame_advanced_edits,
        _apply_part_text_frame_auto_size_edits,
        _apply_part_text_frame_margin_edits,
        _apply_part_text_frame_vertical_anchor_edits,
        _apply_part_text_frame_word_wrap_edits,
        _apply_part_text_run_font_edits,
        _apply_part_text_run_hyperlink_edits,
        _apply_picture_crop_edits,
        _apply_shape_adjustment_edits,
        _apply_shape_flip_edits,
        _apply_shape_hyperlink_edits,
        _apply_shape_line_element_edits,
        _apply_shape_style_edits,
        _apply_shape_target_slide_edits,
        _apply_slide_name_edits,
        _apply_text_frame_advanced_edits,
        _apply_text_run_advanced_edits,
        _apply_text_run_font_color_edits,
        _apply_text_run_font_fill_type_edits,
        _apply_text_run_font_language_edits,
        _apply_text_run_hyperlink_edits,
        _part_shape_text_replacements,
        _shape_style_edits,
    )
    from .slide_layout_edits import (
        apply_slide_layout_edits as _apply_slide_layout_edits,
    )
    from .slide_transition_edits import (
        apply_slide_transition_edits as _apply_slide_transition_edits,
    )
    from .table_cell_border_edits import (
        apply_table_cell_border_edits as _apply_table_cell_border_edits,
    )
    from .table_xml import (
        _apply_table_cell_merge_edits,
        _apply_table_cell_property_edits,
        _apply_table_dimension_edits,
        _apply_table_style_edits,
        _apply_table_style_id_edits,
    )

    try:
        from .slide_paragraph_edits import (
            _apply_group_child_paragraph_bullet_edits,  # noqa: F401
            _apply_paragraph_bullet_edits,
            _apply_part_paragraph_bullet_edits,
        )
    except ImportError:

        def _apply_paragraph_bullet_edits(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
            from .slide_paragraph_edits import _apply_paragraph_bullet_edits as fn

            return fn(*args, **kwargs)

        def _apply_part_paragraph_bullet_edits(  # type: ignore[misc]
            *args: Any, **kwargs: Any
        ) -> None:
            from .slide_paragraph_edits import _apply_part_paragraph_bullet_edits as fn

            return fn(*args, **kwargs)

        def _apply_group_child_paragraph_bullet_edits(  # type: ignore[misc]  # noqa: F811
            *args: Any, **kwargs: Any
        ) -> None:
            from .slide_paragraph_edits import (
                _apply_group_child_paragraph_bullet_edits as fn,
            )

            return fn(*args, **kwargs)

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
        _apply_nested_group_child_shape_text_edits=(_apply_nested_group_child_shape_text_edits),
        _apply_part_shape_hyperlink_edits=_apply_part_shape_hyperlink_edits,
        _apply_part_shape_text_edits=_apply_part_shape_text_edits,
        _apply_part_text_run_font_edits=_apply_part_text_run_font_edits,
        _apply_part_text_run_hyperlink_edits=_apply_part_text_run_hyperlink_edits,
        _apply_part_text_frame_auto_size_edits=_apply_part_text_frame_auto_size_edits,
        _apply_part_text_frame_edits=_apply_part_text_frame_edits,
        _apply_part_text_frame_margin_edits=_apply_part_text_frame_margin_edits,
        _apply_part_text_frame_vertical_anchor_edits=(_apply_part_text_frame_vertical_anchor_edits),
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
        _apply_shape_flip_edits=_apply_shape_flip_edits,
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
        _apply_nested_group_child_geometry_edits=(_apply_nested_group_child_geometry_edits),
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
        _apply_extended_properties_edits=_apply_extended_properties_edits,
        _apply_section_edits=_apply_section_edits,
        _apply_table_style_id_edits=_apply_table_style_id_edits,
        _apply_table_cell_border_edits=_apply_table_cell_border_edits,
        _apply_shape_line_end_edits=_apply_shape_line_end_edits,
        _apply_shape_z_order_edits=_apply_shape_z_order_edits,
        _apply_slide_transition_edits=_apply_slide_transition_edits,
        _apply_custom_properties_edits=_apply_custom_properties_edits,
        _apply_paragraph_bullet_edits=_apply_paragraph_bullet_edits,
        _apply_part_paragraph_bullet_edits=_apply_part_paragraph_bullet_edits,
        _apply_chart_trendline_edits=_apply_chart_trendline_edits,
        _apply_chart_error_bar_edits=_apply_chart_error_bar_edits,
        _apply_slide_animation_edits=_apply_slide_animation_edits,
        _apply_picture_transparency_edits=_apply_picture_transparency_edits,
        _apply_picture_correction_edits=_apply_picture_correction_edits,
        _apply_picture_recolor_edits=_apply_picture_recolor_edits,
        _apply_shape_effect_edits=_apply_shape_effect_edits,
        _apply_shape_glow_edits=_apply_shape_glow_edits,
        _apply_shape_lock_edits=_apply_shape_lock_edits,
        _apply_slide_layout_edits=_apply_slide_layout_edits,
        _apply_text_run_advanced_edits=_apply_text_run_advanced_edits,
        _apply_text_frame_advanced_edits=_apply_text_frame_advanced_edits,
        _apply_paragraph_tab_stop_edits=_apply_paragraph_tab_stop_edits,
        _apply_group_child_paragraph_tab_stop_edits=(_apply_group_child_paragraph_tab_stop_edits),
        _apply_part_paragraph_tab_stop_edits=_apply_part_paragraph_tab_stop_edits,
        _apply_group_child_text_frame_advanced_edits=(_apply_group_child_text_frame_advanced_edits),
        _apply_part_text_frame_advanced_edits=_apply_part_text_frame_advanced_edits,
    )


class _MutationLock:
    """Re-entrant lock that copies and pickles as a fresh, unlocked lock."""

    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def __enter__(self) -> bool:
        return self._lock.__enter__()

    def __exit__(self, *exc: object) -> None:
        self._lock.__exit__(*exc)

    def __deepcopy__(self, memo: dict[int, Any]) -> _MutationLock:
        return _MutationLock()

    def __copy__(self) -> _MutationLock:
        return _MutationLock()

    def __reduce__(self) -> tuple[type[_MutationLock], tuple[()]]:
        return (_MutationLock, ())


class Presentation(PresentationEditQueueMixin):
    """Open and edit an existing PowerPoint deck.

    ``Presentation(stream, no_disk=True)`` owns an in-memory snapshot from the
    stream's beginning through EOF and restores the caller's original position.
    This mode supports construction, slide-metadata inspection, and ``save()``
    before ``dispose()``; it exposes no filesystem path, and saving keeps the
    saved package as the new in-memory baseline.
    """

    def __init__(self, path: Any = None, *, no_disk: bool = False) -> None:
        self._mutation_lock = _MutationLock()
        # Opening validates the package, then reads slide metadata: one ZIP
        # central directory and one parse per XML part serve every step.
        with _shared_package_reads():
            self._source_path, self._source_tempdir = _presentation_source_path(
                path, no_disk=no_disk
            )
            self._no_disk = isinstance(self._source_path, InMemoryPackageSource)
            self._disposed = False
            self._odp_workspace: tempfile.TemporaryDirectory[str] | None = None
            if not self._no_disk and _is_odp_package(self._source_path):
                odp = commercial_module("odp", "Opening an ODP presentation")
                self._odp_workspace = tempfile.TemporaryDirectory(prefix="wolfppt-odp-")
                converted = Path(self._odp_workspace.name) / "presentation.pptx"
                odp.load_odp_as_pptx(self._source_path, converted)
                self._source_path = converted
            _initialize_presentation_state(self)
            self._load(self._source_path)
        self._pending_vba_modules: list[tuple[str, str]] = []
        self._pending_vba_removal = False
        self._pending_web_extensions: list[WebExtension] = []
        self._lifecycle_tags: dict[Any, Any] = {}
        self._lifecycle_view_state: Any = None
        self._lifecycle_fields: Any = None
        self._slide_show: SlideShowSettings | None = None
        self._theme_edits: Any = None

    def orphan_parts(self) -> tuple[str, ...]:
        """Return unreachable part names in the saved package, excluding pending edits."""
        from .presentation_package_validation import orphan_parts

        if self._disposed:
            raise RuntimeError("presentation is disposed")
        return orphan_parts(self._source_path)

    @property
    def slides(self) -> SlideCollection:
        if self._disposed:
            raise RuntimeError("presentation is disposed")
        return self._slides

    @property
    def slide_layouts(self) -> SlideLayoutCollection:
        if self._slide_layouts is None:
            self._slide_layouts = SlideLayoutCollection(
                self,
                [
                    SlideLayout(self, index, layout)
                    for index, layout in enumerate(_load_slide_layout_payloads(self._source_path))
                ],
            )
        return self._slide_layouts

    @property
    def slide_masters(self) -> SlideMasterCollection:
        if self._slide_masters is None:
            self._slide_masters = SlideMasterCollection(
                self,
                [
                    SlideMaster(self, index, master)
                    for index, master in enumerate(_load_slide_master_payloads(self._source_path))
                ],
            )
        return self._slide_masters

    @property
    def slide_master(self) -> SlideMaster:
        return self.slide_masters[0]

    @property
    def handout_master(self) -> HandoutMaster:
        if self._handout_master is None:
            partname = getattr(self, "_pending_handout_master_partname", None)
            if partname is None:
                try:
                    partname = _presentation_handout_master_partname(self._source_path)
                    payloads = None
                except AttributeError:
                    partname = _next_handout_master_partname(self._source_path)
                    self._pending_handout_master_partname = partname
                    payloads = default_handout_master_shape_payloads()
            else:
                payloads = default_handout_master_shape_payloads()
            self._handout_master = HandoutMaster(self, partname, payloads)
        return self._handout_master

    @property
    def notes_master(self) -> NotesMaster:
        if self._notes_master is None:
            self._notes_master = NotesMaster(
                self,
                _presentation_notes_master_partname(self._source_path),
            )
        return self._notes_master

    @property
    def element(self) -> PresentationElementProxy:
        return PresentationElementProxy(self)

    @property
    def comment_authors(self) -> tuple[Any, ...]:
        """The presentation-scoped legacy comment authors.

        Authors belong to the presentation rather than to one slide, so this
        includes authors registered by comments queued in this session.
        """
        from .comment_edits import presentation_comment_authors

        return presentation_comment_authors(self)

    @property
    def core_properties(self) -> CoreProperties:
        if self._core_properties is None:
            self._core_properties = CoreProperties(self)
        return self._core_properties

    @property
    def tags(self) -> Any:
        """Case-sensitive presentation tags. Use tags_for(owner) for slide/shape tags."""
        return self.tags_for(self)

    def tags_for(self, owner: Any) -> Any:
        """Return the stable owner-bound tag mapping for this presentation."""
        from .presentation_tags import OwnerRef, TagCollection

        OwnerRef.capture(self, owner)
        if owner not in self._lifecycle_tags:
            self._lifecycle_tags[owner] = TagCollection(self, owner)
        return self._lifecycle_tags[owner]

    def theme_for(self, owner: Any) -> Any:
        """The theme of a slide/notes/handout master, or a part's theme override.

        A master returns its :class:`~wolfppt.theme_facade.Theme`; a slide,
        slide layout or notes slide returns its
        :class:`~wolfppt.theme_facade.ThemeOverride`.  Edits publish on save.
        """
        from .theme_facade import theme_edits

        return theme_edits(self).theme_for(owner)

    @property
    def view_state(self) -> Any:
        """Stored values, schema defaults and selective view edit/reset operations."""
        from .presentation_view_state import ViewState

        if self._disposed:
            raise RuntimeError("presentation is disposed")
        if self._lifecycle_view_state is None:
            self._lifecycle_view_state = ViewState(self)
        return self._lifecycle_view_state

    @property
    def fields(self) -> Any:
        """Use fields.for_shape(shape) and fields.refresh(selection, context=...)."""
        from .presentation_fields import PresentationFields

        if self._disposed:
            raise RuntimeError("presentation is disposed")
        if self._lifecycle_fields is None:
            self._lifecycle_fields = PresentationFields(self)
        return self._lifecycle_fields

    @property
    def custom_properties(self) -> Any:
        if self._custom_properties is None:
            from .custom_properties import CustomProperties

            self._custom_properties = CustomProperties(self)
        return self._custom_properties

    @property
    def custom_shows(self) -> CustomShowCollection:
        if self._custom_shows is None:
            self._custom_shows = _load_custom_shows(self)
        return self._custom_shows

    @property
    def slide_show(self) -> SlideShowSettings:
        """Slide show setup (loop, kiosk/browse mode, narration, timings)."""
        if self._disposed:
            raise RuntimeError("presentation is disposed")
        if self._slide_show is None:
            self._slide_show = SlideShowSettings(self)
        return self._slide_show

    @property
    def extended_properties(self) -> Any:
        if self._extended_properties is None:
            from .extended_properties import ExtendedProperties

            self._extended_properties = ExtendedProperties(self)
        return self._extended_properties

    @property
    def sections(self) -> Any:
        if self._sections is None:
            from .sections import SectionCollection

            self._sections = SectionCollection(self)
        return self._sections

    @property
    def web_extensions(self) -> WebExtensionCollection:
        """The Office web extensions declared by the presentation package."""

        if self._web_extensions is None:
            self._web_extensions = WebExtensionCollection(self)
        return self._web_extensions

    def add_web_extension(
        self,
        reference_id: str,
        version: str,
        *,
        store: str = "",
        store_type: str = "SPCatalog",
        instance_id: str | None = None,
        dock_state: str = "right",
        visible: bool = True,
        width: float = 350.0,
        row: int = 0,
        locked: bool = False,
        frozen: bool = False,
    ) -> WebExtension:
        """Queue an Office web-extension reference for the next package save.

        The facade writes MS-OWEXML package metadata only. It never fetches,
        activates, or executes the referenced extension.
        """

        return self.web_extensions.add(
            reference_id,
            version,
            store=store,
            store_type=store_type,
            instance_id=instance_id,
            dock_state=dock_state,
            visible=visible,
            width=width,
            row=row,
            locked=locked,
            frozen=frozen,
        )

    @property
    def custom_ui(self) -> tuple[CustomUI, ...]:
        """Saved Ribbon 2006/2009 XML and image snapshots; callbacks never execute."""
        with self._mutation_lock:
            return _read_custom_ui(self._source_path)

    def add_custom_ui(
        self, xml: str | bytes, *, images: Mapping[str, bytes] | None = None
    ) -> CustomUI:
        """Create or replace the Ribbon CustomUI part that ``xml`` belongs to.

        The root namespace selects the part: the 2006 ``customUI`` writes
        ``customUI/customUI.xml`` and the 2009 ``customUI`` writes
        ``customUI/customUI14.xml``, each with its package relationship and
        content type. An existing part of that namespace is edited in place.
        The XML is stored byte for byte. ``images`` maps a relationship id,
        as named by the XML ``image`` attributes, to PNG, JPEG, GIF, BMP or
        ICO bytes; each id creates or replaces that image relationship and its
        part, and ids not mentioned are kept. Returns the saved snapshot.

        The package is rewritten at once, so save pending edits first. Invalid
        XML, an unsupported root, an invalid image, or an ``image`` attribute
        without an image relationship raises
        :class:`~wolfppt.custom_ui_edits.CustomUIAuthoringError` and leaves
        the presentation unchanged. Callbacks never execute.
        """
        from .custom_ui_edits import custom_ui_parts

        return self._rewrite_package(
            "adding custom UI", lambda package: custom_ui_parts(package, xml, images)
        )

    @property
    def vba_signatures(self) -> tuple[VbaSignature, ...]:
        """Saved opaque VBA signatures, without asserting cryptographic validity."""
        with self._mutation_lock:
            return _read_vba_signatures(self._source_path)

    @property
    def activex_controls(self) -> tuple[ActiveXControlSnapshot, ...]:
        """Immutable saved control snapshots in slide order, without activation."""
        with self._mutation_lock:
            slides = tuple(slide.partname.lstrip("/") for slide in self.slides)
            return _read_activex_controls(self._source_path, slides)

    @property
    def vba_project(self) -> VbaProject | None:
        """Inspect standard VBA modules without evaluating their source."""

        if self._pending_vba_removal:
            return None
        project = _inspect_vba_project(self._source_path)
        modules = [] if project is None else list(project.modules)
        modules.extend(VbaModule(name, source) for name, source in self._pending_vba_modules)
        return None if not modules else VbaProject(tuple(modules))

    @property
    def vba_modules(self) -> tuple[VbaModule, ...]:
        """The standard VBA modules currently visible through this facade."""

        project = self.vba_project
        return () if project is None else project.modules

    def add_vba_module(self, name: str, source: str) -> None:
        """Queue one standard VBA module for the next PPTM save.

        WolfPPT writes source only. It never loads or executes the supplied
        macro text. Invalid names or sources and names that collide
        case-insensitively with a loaded or queued module are refused before
        any pending state changes.
        """

        module_name = _validate_vba_module_name(name)
        module_source = _validate_vba_source(source)
        key = module_name.casefold()
        project = _inspect_vba_project(self._source_path)
        loaded = () if project is None else project.module_names
        pending = (pending_name for pending_name, _ in self._pending_vba_modules)
        if any(existing.casefold() == key for existing in (*loaded, *pending)):
            raise ValueError(f"VBA module already exists: {module_name!r}")
        self._pending_vba_removal = False
        self._pending_vba_modules.append((module_name, module_source))

    def remove_vba_project(self) -> None:
        """Queue removal of the VBA project for the next PPTX save."""

        self._pending_vba_modules.clear()
        self._pending_vba_removal = True

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
        if self._no_disk:
            raise AttributeError("no-disk presentation input has no filesystem path")
        return self._source_path

    def dispose(self) -> None:
        """Release the owned no-disk source; the caller-owned stream stays open."""
        if self._disposed:
            return
        if isinstance(self._source_path, InMemoryPackageSource):
            self._source_path.dispose()
        if self._source_tempdir is not None:
            self._source_tempdir.cleanup()
            self._source_tempdir = None
        if self._odp_workspace is not None:
            self._odp_workspace.cleanup()
            self._odp_workspace = None
        self._disposed = True

    def convert_to_transitional(self, path: Any) -> None:
        """Save pending edits as Transitional OOXML to a path or writable stream.

        Use the same namespace, relationship-type and lexical-value conversion
        as ``save(conformance="transitional")``. The source conformance and the
        default for subsequent saves remain unchanged. Conversion failures occur
        before destination publication; stream I/O failures may partially write.
        """
        self.save(path, conformance="transitional")

    def close(self) -> None:
        """Close the presentation and release owned resources; safe to repeat.

        Same release as :meth:`dispose`. Afterwards ``save`` and ``slides`` raise
        ``RuntimeError``. A caller-owned input stream stays open.
        """
        self.dispose()

    def save(
        self,
        path: Any,
        *,
        password: str | None = None,
        conformance: str | None = None,
        compression_level: int | None = None,
        zip64: bool | None = None,
        thumbnail: bool = False,
        thumbnail_fonts: tuple[str, ...] = (),
    ) -> None:
        """Save to a filesystem path or writable stream.

        Unedited no-disk inputs publish their owned bytes directly, so stream
        targets need no temporary files.  ``password`` writes the package as
        an ECMA-376 Agile-encrypted container (needs the ``encrypted`` extra);
        the container is decrypted and compared with the plaintext package
        before any byte reaches ``path``.  ``conformance`` (``"transitional"``
        or ``"strict"``) rewrites the package to that ECMA-376 conformance
        class and ``compression_level`` (0 stores, 1-9 deflate) sets the zip
        level. ``zip64=None`` preserves the historical save route; ``True``
        forces ZIP64 member headers and archive end records even for small decks;
        ``False`` writes without ZIP64 and refuses packages requiring it.

        ``thumbnail=True`` generates a PNG of the actual first slide (even hidden),
        fitted within 256 by 256 pixels, using WolfPPT's first-party renderer.
        ``thumbnail_fonts`` must explicitly admit the renderable deck's fonts as
        ``Family[:style]=/path/to/font.ttf`` specs; no discovery or substitution
        occurs. A new unused thumbnail part is linked from the OPC package root
        and declared as image/png; old assets and unrelated part bytes remain.
        Invalid controls, missing fonts, unsupported render content and empty
        decks refuse before destination writes. Files publish atomically; streams
        receive one complete payload, but stream I/O failures may partially write.

        Edited saves refuse unsupported required markup before any publication.
        Unedited byte-copy saves preserve that markup without processing it.

        A macro-enabled deck refuses a ``.pptx`` path with ``MacroStateRefusal``
        before any write; call ``remove_vba_project()`` first to save macro-free.
        """
        with self._mutation_lock:
            if self._disposed:
                raise RuntimeError("presentation is disposed")
            _refuse_macro_package_as_pptx(self, path)
            from .export_options import save_package_with_options

            save_package_with_options(
                self,
                path,
                password=password,
                conformance=conformance,
                compression_level=compression_level,
                zip64=zip64,
                thumbnail=thumbnail,
                thumbnail_fonts=thumbnail_fonts,
            )

    def _save_unlocked(self, path: Any) -> None:
        from .comment_edits import has_pending_comment_edits
        from .presentation_save_state import has_pending_save_edits

        if (
            has_pending_save_edits(self)
            or has_pending_comment_edits(self)
            or self._pending_vba_modules
            or self._pending_vba_removal
            or self._pending_web_extensions
            or (self._slide_show is not None and self._slide_show.dirty)
            or (self._theme_edits is not None and self._theme_edits.dirty)
            or self._slides._detached_slides
        ):
            self._validate_required_namespaces()
        self._delete_sldidlst_detached_slides()

        destination = None if callable(getattr(path, "write", None)) else Path(path)
        if destination is not None and destination.suffix.casefold() == ".odp":
            self._save_odp(path)
            return
        from .theme_facade import staged_theme_edits

        with staged_theme_edits(self):
            slide_show = self._slide_show
            if slide_show is None:
                self._save_presentation_package(path)
                return
            with slide_show._staged_for_save():
                self._save_presentation_package(path)

    def print(
        self,
        printer: str,
        *,
        fonts: tuple[str, ...],
        settings: PrintJobSettings | None = None,
        backend: CupsPrintBackend | None = None,
    ) -> PrintSubmissionReport:
        """Submit saved slides, notes or handouts to a named CUPS printer.

        Save pending edits first. Inspect the returned PrintSubmissionReport;
        queue acceptance does not establish physical printing completion.
        See wolfppt.printing for settings and supported platform scope.
        """
        from .printing import submit_print_job

        with self._mutation_lock:
            self._require_saved_package("printing")
            return submit_print_job(
                self._source_path, printer, fonts=fonts, settings=settings, backend=backend
            )

    def to_markdown(self, *, hidden: str = "label") -> str:
        """Export the saved deck as Markdown, labelling or excluding hidden content."""
        from .markdown import pptx_to_markdown

        with self._mutation_lock:
            self._require_saved_package("exporting Markdown")
            return pptx_to_markdown(self._source_path, hidden=hidden)

    def to_chunks(self, *, hidden: str = "label") -> dict[str, Any]:
        """Export per-slide Markdown chunks with shape ids and omissions."""
        from .markdown import pptx_to_chunks

        with self._mutation_lock:
            self._require_saved_package("exporting Markdown chunks")
            return pptx_to_chunks(self._source_path, hidden=hidden)

    def find_text(
        self,
        search: str,
        *,
        regex: bool = False,
        ignore_case: bool = False,
        whole_word: bool = False,
    ) -> tuple[TextMatch, ...]:
        """Return every text match in slides and notes, in presentation order.

        Matches may span runs in shapes, grouped shapes, and table cells.
        """
        return _presentation_find_text(
            self,
            search,
            regex=regex,
            ignore_case=ignore_case,
            whole_word=whole_word,
        )

    def replace_text(
        self,
        search: str,
        replacement: str,
        *,
        regex: bool = False,
        ignore_case: bool = False,
        whole_word: bool = False,
        dry_run: bool = False,
    ) -> TextReplaceResult:
        """Replace text across slides and notes; ``dry_run`` only reports matches.

        Each replacement takes the formatting of the run where its match
        starts; text outside the match keeps its own run formatting. The edit
        applies to the facade immediately and persists on ``save()``. On
        file-backed presentations, existing queued edits and retained text
        handles remain live; dry runs leave those edits untouched.
        Non-dry-run edits refuse unsupported required markup before rewriting.
        """
        with self._mutation_lock:
            if self._disposed:
                raise RuntimeError("presentation is disposed")
            if not dry_run:
                self._validate_required_namespaces()
            return _presentation_replace_text(
                self,
                search,
                replacement,
                regex=regex,
                ignore_case=ignore_case,
                whole_word=whole_word,
                dry_run=dry_run,
                reload=self._reload_package,
            )

    def _validate_required_namespaces(self) -> None:
        """Preflight source OOXML using the same effective MC tree as extraction.

        Validate the package before replacing text or staging queued saves.
        Never serialize the selected tree: opaque source markup stays intact.
        """
        from .extractor import (
            MC_SUPPORTED_NAMESPACE_URIS,
            _parse_with_namespace_scopes,
            _select_effective_mc_children,
        )
        from .package_parts import open_package_source

        supported = MC_SUPPORTED_NAMESPACE_URIS | {
            "http://purl.oclc.org/ooxml/presentationml/main",
            "http://purl.oclc.org/ooxml/drawingml/main",
            "http://purl.oclc.org/ooxml/officeDocument/relationships",
            "http://purl.oclc.org/ooxml/drawingml/chart",
        }
        with open_package_source(self._source_path) as package:
            for part in package.namelist():
                if not part.startswith("ppt/") or not part.endswith(".xml"):
                    continue
                root, scopes = _parse_with_namespace_scopes(package.read(part))
                _select_effective_mc_children(root, scopes, part, supported_namespaces=supported)

    def _reload_package(self, source: Any) -> None:
        _reset_comment_state(self)
        _initialize_presentation_state(self)
        self._lifecycle_tags = {}
        self._lifecycle_view_state = None
        self._lifecycle_fields = None
        self._slide_show = None
        self._load(source)

    # -- slide utilities -------------------------------------------------
    #
    # Each utility below edits the saved package directly and then rebases
    # the facade onto the result, exactly as ``replace_text`` does, so queued
    # facade edits (which address shapes by position) must be saved first.

    def _require_saved_package(self, operation: str) -> None:
        from .comment_edits import has_pending_comment_edits
        from .presentation_save_state import has_pending_save_edits

        if self._disposed:
            raise RuntimeError("presentation is disposed")
        slide_show = self._slide_show
        if (
            has_pending_save_edits(self)
            or has_pending_comment_edits(self)
            or self._pending_vba_modules
            or self._pending_vba_removal
            or self._pending_web_extensions
            or (slide_show is not None and slide_show.dirty)
        ):
            raise ValueError(f"save pending presentation edits before {operation}")

    def _rewrite_package(self, operation: str, plan: Any) -> Any:
        """Rewrite the saved package with ``plan`` and rebase the facade on it.

        ``plan(package)`` returns ``(replacements, removals, result)``; the
        rewrite is staged completely before the facade moves to it, so a
        refusal leaves the presentation unchanged.
        """
        from .package_parts import (
            copy_open_package_with_replacements,
            open_package_source,
        )

        with self._mutation_lock:
            self._require_saved_package(operation)
            source = self._source_path
            staged_dir: tempfile.TemporaryDirectory[str] | None = tempfile.TemporaryDirectory(
                prefix="wolfppt-slide-utility-"
            )
            try:
                staged_path = Path(staged_dir.name) / "presentation.pptx"
                with open_package_source(source) as package:
                    replacements, removals, result = plan(package)
                    copy_open_package_with_replacements(
                        package, staged_path, replacements, removals
                    )
                staged: Any = staged_path
                if isinstance(source, InMemoryPackageSource):
                    staged = InMemoryPackageSource(staged_path.read_bytes())
                    staged_dir.cleanup()
                    staged_dir = None
            except BaseException:
                if staged_dir is not None:
                    staged_dir.cleanup()
                raise
            previous_tempdir = self._source_tempdir
            self._source_path = staged
            if staged_dir is not None:
                self._source_tempdir = staged_dir
                if previous_tempdir is not None:
                    previous_tempdir.cleanup()
            self._reload_package(staged)
            return result

    def _slide_selection(self, slides: Any) -> list[int]:
        count = len(self._slides)
        if slides is None:
            return list(range(count))
        selection = _slide_indexes(slides, count, "slides")
        return sorted(selection)

    def add_watermark(
        self,
        text: str | None = None,
        *,
        image: Any = None,
        slides: Iterable[int] | None = None,
        font_size: float = 60.0,
        font_name: str | None = None,
        bold: bool = True,
        color: str = "808080",
        transparency: float = 0.5,
        rotation: float | None = None,
        left: int | None = None,
        top: int | None = None,
        width: int | None = None,
        height: int | None = None,
        name: str = "Watermark",
    ) -> tuple[Any, ...]:
        """Put a text or image watermark behind the content of slides.

        The watermark becomes the bottom-most shape of each selected slide
        (every slide when ``slides`` is ``None``), so all slide content draws
        over it, and it is locked against selection, moves, resizes and text
        edits.  Text is centred and turned ``rotation`` degrees clockwise
        (default ``-45``, a rising diagonal); an image is centred at up to 60%
        of the slide (default rotation ``0``).  ``transparency`` runs from 0
        (opaque) to just below 1.  Geometry arguments are EMU.  An image is
        stored once and shared by every watermarked slide.  Returns the new
        shapes in slide order.
        """
        from .presentation_tags import xml_string

        if (text is None) == (image is None):
            raise ValueError("add_watermark needs exactly one of text or image")
        if text is not None:
            xml_string(text, "watermark text")
            if not text.strip():
                raise ValueError("watermark text must not be blank")
        xml_string(name, "watermark name")
        if font_name is not None:
            xml_string(font_name, "font_name")
        if not isinstance(transparency, (int, float)) or not 0 <= transparency < 1:
            raise ValueError("transparency must be at least 0 and below 1")
        if not isinstance(font_size, (int, float)) or not 1 <= font_size <= 4000:
            raise ValueError("font_size must be between 1 and 4000 points")
        if (
            not isinstance(color, str)
            or len(color) != 6
            or not all(character in "0123456789abcdefABCDEF" for character in color)
        ):
            raise ValueError("color must be a six-digit RGB hex string")
        angle = (-45.0 if text is not None else 0.0) if rotation is None else rotation
        if not isinstance(angle, (int, float)):
            raise TypeError("rotation must be a number of degrees")
        image_bytes = None
        if image is not None:
            from .image_inputs import image_input_bytes

            image_bytes = image_input_bytes(image)
        with self._mutation_lock:
            self._require_saved_package("adding a watermark")
            selection = self._slide_selection(slides)
            if not selection:
                raise ValueError("watermark selection selects no slide")
            size = _presentation_slide_size(self)
            spec = _WatermarkSpec(
                text=text,
                image=image_bytes,
                slide_width=int(size["cx"]),
                slide_height=int(size["cy"]),
                font_size=float(font_size),
                font_name=font_name,
                bold=bool(bold),
                color=color.upper(),
                opacity=round((1 - float(transparency)) * 100000),
                rotation=float(angle),
                box=(left, top, width, height),
                name=name,
            )
            parts = [self._slides[index].partname for index in selection]
            added = self._rewrite_package(
                "adding a watermark",
                lambda package: _watermark_plan(package, parts, spec),
            )
            return tuple(
                _shape_by_id(self._slides[index], shape_id)
                for index, shape_id in zip(selection, added, strict=True)
            )

    def header_footer(
        self,
        *,
        show_footer: bool | None = None,
        show_slide_number: bool | None = None,
        show_date: bool | None = None,
        footer_text: str | None = None,
        slides: Iterable[int] | None = None,
    ) -> None:
        """Show or hide the footer, slide-number and date placeholders.

        ``True`` copies the placeholder from each selected slide's layout (or
        master) onto slides that lack it; ``False`` removes it and any
        animation that targeted only it; ``None`` leaves it alone.
        ``footer_text`` sets the text of every shown footer.  Without a
        ``slides`` selection the toggles apply to every slide and the masters'
        and layouts' header/footer flags follow, so slides added later agree.
        """
        from .presentation_fields import (
            HEADER_FOOTER_PLACEHOLDERS,
            header_footer_replacements,
        )

        requested = {
            "show_footer": show_footer,
            "show_slide_number": show_slide_number,
            "show_date": show_date,
        }
        toggles: dict[str, bool] = {}
        for argument, value in requested.items():
            if value is None:
                continue
            if not isinstance(value, bool):
                raise TypeError(f"{argument} must be a bool or None")
            toggles[HEADER_FOOTER_PLACEHOLDERS[argument]] = value
        if footer_text is not None and not isinstance(footer_text, str):
            raise TypeError("footer_text must be a str or None")
        if footer_text is not None and show_footer is False:
            raise ValueError("footer_text cannot be set while hiding the footer")
        if not toggles and footer_text is None:
            raise ValueError("header_footer needs at least one setting")
        with self._mutation_lock:
            self._require_saved_package("changing headers and footers")
            selection = self._slide_selection(slides)
            slide_parts = [slide.partname for slide in self._slides]
            self._rewrite_package(
                "changing headers and footers",
                lambda package: (
                    header_footer_replacements(
                        package,
                        slide_parts,
                        selection,
                        toggles=toggles,
                        footer_text=footer_text,
                        update_masters=slides is None,
                    ),
                    set(),
                    None,
                ),
            )

    @property
    def audios(self) -> Any:
        """Indexed reusable audio assets; save pending edits before mutation."""
        from .native_media import MediaCollection

        return MediaCollection(self, "audio")

    @property
    def videos(self) -> Any:
        """Indexed reusable video assets; save pending edits before mutation."""
        from .native_media import MediaCollection

        return MediaCollection(self, "video")

    @property
    def media(self) -> tuple[Any, ...]:
        """Embedded audio/video, slide references first, then retained unplaced assets.

        Each :class:`~wolfppt.native_media.PresentationMedia` exposes the
        exact embedded bytes (``blob``/``extract``) and ``replace``.
        """
        from .native_media import PresentationMedia, inspect_embedded_media
        from .package_parts import open_package_source

        with self._mutation_lock:
            self._require_saved_package("listing media")
            slide_parts = [slide.partname for slide in self._slides]
            with open_package_source(self._source_path) as package:
                found = inspect_embedded_media(package, slide_parts)
            return tuple(PresentationMedia(self, item) for item in found)

    def replace_media(self, media: Any, data: Any, *, content_type: str | None = None) -> Any:
        """Replace one embedded audio or video part's bytes.

        ``media`` is a handle from :attr:`media` or a media part name;
        ``data`` is bytes, a path or a readable stream.  The playing shapes,
        their timing and trigger nodes, and their poster frames are kept; a
        part shared by several shapes is replaced for all of them.  A path
        names its format by extension; otherwise ``content_type`` (default:
        the current one) does, and a different format moves the media to a
        part with that format's extension.  Returns the new handle.
        """
        from .native_media import (
            MediaReplacementRefusal,
            PresentationMedia,
            media_content_type_for_path,
            media_replacement_parts,
        )

        if isinstance(data, (bytes, bytearray)):
            payload = bytes(data)
        elif isinstance(data, (str, os.PathLike)):
            payload = Path(data).read_bytes()
            if content_type is None:
                content_type = media_content_type_for_path(data)
        elif callable(getattr(data, "read", None)):
            payload = data.read()
            if not isinstance(payload, bytes):
                raise TypeError("media stream read() must return bytes")
        else:
            raise TypeError("data must be bytes, a path or a readable stream")
        with self._mutation_lock:
            if isinstance(media, PresentationMedia):
                if media._presentation is not self:
                    raise MediaReplacementRefusal("media belongs to another presentation")
                target = media._media
            elif isinstance(media, str):
                partname = media.lstrip("/")
                target = next(
                    (item._media for item in self.media if item.partname == partname),
                    None,
                )
                if target is None:
                    raise MediaReplacementRefusal(f"no embedded media part {partname}")
            else:
                raise TypeError("media must be a PresentationMedia handle or part name")
            partname = self._rewrite_package(
                "replacing media",
                lambda package: media_replacement_parts(
                    package, target, payload, content_type=content_type
                ),
            )
            return next(item for item in self.media if item.partname == partname)

    def split(
        self,
        ranges: Iterable[Any],
        destination: Any,
        *,
        stem: str = "part",
    ) -> tuple[Path, ...]:
        """Save each slide range as its own presentation.

        Every range is a ``range``, a slide index, or an ascending iterable of
        0-based slide indexes.  ``destination`` is a directory (created when
        missing; files are named ``<stem>-<n>.pptx``, or ``.pptm`` for a macro
        deck) or one path per range.  Each deck keeps its slides' layouts,
        masters, theme, notes, comments, charts and media, removes what only
        the dropped slides used, and drops slide jumps and custom-show entries
        that pointed at dropped slides.  Every deck is built before any is
        written.  Returns the saved paths.
        """
        from .package_parts import open_package_source

        with self._mutation_lock:
            self._require_saved_package("splitting")
            count = len(self._slides)
            selections = [
                _slide_indexes(item, count, f"ranges[{position}]", ordered=True)
                for position, item in enumerate(ranges)
            ]
            if not selections:
                raise ValueError("split needs at least one slide range")
            with open_package_source(self._source_path) as package:
                macro = "ppt/vbaProject.bin" in package.namelist()
            suffix = ".pptm" if macro else ".pptx"
            if isinstance(destination, (str, os.PathLike)):
                directory = Path(destination)
                if not stem or "/" in stem or "\\" in stem:
                    raise ValueError("stem must be a plain file-name stem")
                outputs = [
                    directory / f"{stem}-{number}{suffix}"
                    for number in range(1, len(selections) + 1)
                ]
            else:
                outputs = [Path(item) for item in destination]
                if len(outputs) != len(selections):
                    raise ValueError("split needs one output path per range")
                directory = None
            if len({output.resolve() for output in outputs}) != len(outputs):
                raise ValueError("split output paths must be distinct")
            source = self._source_path
            snapshot = (
                source.read_bytes()
                if isinstance(source, InMemoryPackageSource)
                else Path(source).read_bytes()
            )
            with tempfile.TemporaryDirectory(prefix="wolfppt-split-") as work:
                staged_source = Path(work) / f"source{suffix}"
                staged_source.write_bytes(snapshot)
                staged: list[Path] = []
                for number, selection in enumerate(selections, start=1):
                    output = Path(work) / f"part-{number}{suffix}"
                    deck = Presentation(staged_source)
                    try:
                        dropped = [
                            deck.slides[index] for index in range(count) if index not in selection
                        ]
                        for slide in dropped:
                            deck.slides.remove(slide)
                        deck.save(output)
                    finally:
                        deck.dispose()
                    _drop_dangling_slide_references(output)
                    staged.append(output)
                if directory is not None:
                    directory.mkdir(parents=True, exist_ok=True)
                for built, output in zip(staged, outputs, strict=True):
                    _publish_bytes(output, built.read_bytes())
            return tuple(outputs)

    @staticmethod
    def merge(
        decks: Sequence[Any],
        output: Any,
        *,
        save_options: Mapping[str, Any] | None = None,
        render_options: Mapping[str, Any] | None = None,
    ) -> Path:
        """Append whole slide closures, admitting PPT/ODP through existing loaders.

        Package output requires a supported presentation suffix; ``save_options``
        contains ``save`` keyword controls for PresentationML. With
        ``render_options``, use a new output directory and pass ``RenderOptions``
        keywords (including explicit fonts and formats), excluding source and
        output_dir. All rendered artifacts and the omission receipt are retained.
        Inputs stay unchanged and SHA-256-bound through final atomic publication.
        Unsupported inputs, output formats and lossy conversions refuse before
        publishing. See :mod:`wolfppt.presentation_merge_formats` for boundaries.
        """
        from .presentation_merge_formats import merge_presentations

        return merge_presentations(
            decks, output, save_options=save_options, render_options=render_options
        )

    def _drop_part_rel(self, partname: str, rId: str) -> None:
        """python-pptx ``part.drop_rel`` for presentation-to-slide relationships.

        Dropping the relationship of a slide detached from ``slides._sldIdLst``
        deletes it through ``slides.remove``; for a still-attached slide the
        deletion happens when its entry is removed.
        """
        with self._mutation_lock:
            slides = self._slides
            slide = None
            if partname == self.part.partname:
                slide = next(
                    (s for s in slides if _slide_metadata(s).get("relationship_id") == rId),
                    None,
                )
            if slide is None:
                raise KeyError(
                    f"{partname} has no slide relationship {rId!r}; drop_rel supports "
                    "only presentation-to-slide relationships"
                )
            if any(slide is s for s in slides._detached_slides):
                slides.remove(slide)
            elif not any(slide is s for s in slides._dropped_rel_slides):
                slides._dropped_rel_slides.append(slide)

    def _delete_sldidlst_detached_slides(self) -> None:
        """Delete slides whose ``p:sldId`` entry is detached, like python-pptx save."""
        slides = self._slides
        if any(not slide._deleted for slide in slides._dropped_rel_slides):
            raise ValueError(
                "a slide relationship was dropped with part.drop_rel() but its "
                "slides._sldIdLst entry is still attached; remove the entry "
                "before saving"
            )
        detached = list(slides._detached_slides)
        if detached and len(detached) >= len(slides):
            raise ValueError(
                "every slides._sldIdLst entry is detached; re-insert at least one "
                "because a presentation must keep one slide"
            )
        for slide in detached:
            slides.remove(slide)

    def _save_presentation_package(self, path: Any) -> None:
        if (
            not self._pending_vba_modules
            and not self._pending_vba_removal
            and not self._pending_web_extensions
        ):
            from .presentation_save import save_presentation as _save_presentation

            _save_presentation(self, path, _presentation_save_ops())
            return
        self._save_with_pending_package_parts(path)

    def _save_odp(self, path: Any) -> None:
        from .presentation_save_state import has_pending_lifecycle_edits

        commercial_module("odp", "Saving as ODP")

        if has_pending_lifecycle_edits(self):
            raise OdpFormatError("ODP cannot preserve pending typed lifecycle edits")
        if getattr(self, "_pending_handout_master_partname", None) is not None:
            raise OdpFormatError("ODP cannot preserve handout master relationships")
        if self._pending_vba_modules or self._pending_vba_removal:
            raise OdpFormatError("ODP cannot preserve VBA projects")
        if self._pending_web_extensions:
            raise OdpFormatError("ODP cannot preserve Office web-extension relationships")
        if self._slide_show is not None and self._slide_show.dirty:
            raise OdpFormatError("ODP cannot preserve pending slide show settings")
        if self._theme_edits is not None and self._theme_edits.dirty:
            raise OdpFormatError("ODP cannot preserve pending theme edits")
        from .presentation_save import save_presentation as _save_presentation

        _save_presentation(self, path, _presentation_save_ops())

    def _save_with_pending_package_parts(self, path: Any) -> None:
        file_like = callable(getattr(path, "write", None))
        destination = None if file_like else Path(path)
        if destination is not None and (self._pending_vba_modules or self._pending_vba_removal):
            expected_suffix = ".pptx" if self._pending_vba_removal else ".pptm"
            if destination.suffix.casefold() != expected_suffix:
                raise ValueError(f"VBA lifecycle save requires a {expected_suffix} destination")
        from .presentation_save import save_presentation as _save_presentation

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
            [Slide(self, index, slide) for index, slide in enumerate(slides)],
        )
        self._slide_metadata = _slide_metadata_cache_from_shells(slides)
        self._slide_layouts = None
        self._slide_masters = None
        self._notes_master = None
        self._handout_master = None
        self._core_properties = None
        self._custom_properties = None
        self._custom_shows = None
        self._extended_properties = None
        self._sections = None
        self._web_extensions = None
        self._notes_slide_adds.clear()
        self._pending_notes_slide_payloads.clear()


def _slide_metadata_cache_from_shells(
    slides: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    payload_keys = {"part", "texts", "shapes"}
    return {
        str(slide["part"]): {key: value for key, value in slide.items() if key not in payload_keys}
        for slide in slides
        if slide.get("part")
    }


# -- slide utility helpers ---------------------------------------------------

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_STRICT_REL_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
#: Elements that only carry a slide jump and may go with a dropped slide.
_SLIDE_LINK_TAGS = frozenset(("hlinkClick", "hlinkHover", "hlinkMouseOver", "sld"))


def _slide_indexes(value: Any, count: int, label: str, *, ordered: bool = False) -> list[int]:
    """Admit one slide index, a ``range`` or an iterable of 0-based indexes."""
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a slide index, range or iterable of indexes")
    if isinstance(value, int):
        items = [value]
    elif isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise TypeError(f"{label} must be a slide index, range or iterable of indexes")
    else:
        items = list(value)
    if not items:
        raise ValueError(f"{label} selects no slide")
    for item in items:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{label} slide indexes must be integers")
        if not 0 <= item < count:
            raise IndexError(f"{label} slide index {item} is out of range")
    if len(set(items)) != len(items):
        raise ValueError(f"{label} lists a slide twice")
    if ordered and items != sorted(items):
        raise ValueError(f"{label} must list its slides in deck order")
    return items


def _publish_bytes(path: Path, payload: bytes) -> None:
    """Write ``payload`` beside ``path`` and rename it into place atomically."""
    descriptor, staged = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
    except BaseException:
        if os.path.exists(staged):
            os.unlink(staged)
        raise


def _encrypt_package(plaintext: bytes, password: str) -> bytes:
    """Encrypt a saved package with the qualified ECMA-376 Agile provider.

    The container is decrypted again and must reproduce ``plaintext`` byte
    for byte, so a container this engine cannot open is never returned.
    """
    from .package_limits import PptxPackageLimits
    from .security import (
        AGILE,
        PptxSecurityReport,
        PptxSecurityRequest,
        _container_facts,
        _qualified_provider,
    )

    request = PptxSecurityRequest(
        source=Path("<presentation>"),
        destination=Path("<save>"),
        source_sha256=hashlib.sha256(plaintext).hexdigest(),
        password_env=None,
    )
    provider = _qualified_provider("encrypt", request)
    if isinstance(provider, PptxSecurityReport):
        raise RuntimeError(
            f"password-protected save is unavailable ({provider.code}): {provider.recovery}"
        )
    container = io.BytesIO()
    try:
        provider.ooxml_file(io.BytesIO(plaintext)).encrypt(password, container)
    except Exception:  # noqa: BLE001 - provider text may quote the password
        raise RuntimeError("the encryption provider failed to encrypt the deck") from None
    encrypted = container.getvalue()
    if len(encrypted) > PptxPackageLimits().max_archive_size:
        raise RuntimeError("the encrypted deck exceeds the package archive limit")
    if _container_facts(encrypted, provider) != (AGILE, len(plaintext)):
        raise RuntimeError("the encrypted deck failed verification")
    reopened = io.BytesIO()
    try:
        office = provider.ooxml_file(io.BytesIO(encrypted))
        office.load_key(password=password, verify_password=True)
        office.decrypt(reopened, verify_integrity=True)
    except Exception:  # noqa: BLE001 - an unverified container is a refusal
        raise RuntimeError("the encrypted deck failed verification") from None
    if reopened.getvalue() != plaintext:
        raise RuntimeError("the encrypted deck failed verification")
    return encrypted


def _shape_by_id(slide: Any, shape_id: int) -> Any:
    for shape in slide.shapes:
        if shape.shape_id == shape_id:
            return shape
    raise RuntimeError(f"shape {shape_id} is missing after the rewrite")


def _drop_dangling_slide_references(path: Path) -> None:
    """Drop slide jumps and custom-show entries whose slide a split removed.

    Removing a slide removes its part, so a hyperlink on a kept slide that
    jumped to it, or a custom show that listed it, would name a missing part
    and PowerPoint would repair the file.  Those links and entries go with the
    slide.  Any other reference to a removed slide is refused.
    """
    from .package_parts import copy_open_package_with_replacements
    from .presentation_tags import parse_xml, serialize_xml

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        for rels_name in sorted(name for name in names if name.endswith(".rels")):
            directory, base = posixpath.split(rels_name)
            owner = posixpath.join(posixpath.dirname(directory), base[: -len(".rels")])
            rels = parse_xml(package.read(rels_name))
            dropped: set[str] = set()
            for node in list(rels):
                if not node.get("Type", "").endswith("/slide"):
                    continue
                if node.get("TargetMode", "Internal") != "Internal":
                    continue
                target = node.get("Target", "")
                resolved = (
                    target.lstrip("/")
                    if target.startswith("/")
                    else posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))
                )
                if resolved in names:
                    continue
                dropped.add(node.get("Id", ""))
                rels.remove(node)
            if not dropped or owner not in names:
                continue
            root = parse_xml(package.read(owner))
            for parent in list(root.iter()):
                for child in list(parent):
                    referenced = {
                        value
                        for name, value in child.attrib.items()
                        if name in (f"{{{_REL_NS}}}id", f"{{{_STRICT_REL_NS}}}id")
                    } & dropped
                    if not referenced:
                        continue
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag not in _SLIDE_LINK_TAGS:
                        raise ValueError(
                            f"{owner} references a removed slide through <{tag}>; "
                            "include that slide in the same range"
                        )
                    parent.remove(child)
            replacements[rels_name] = serialize_xml(rels)
            replacements[owner] = serialize_xml(root)
        if not replacements:
            return
        staged = path.with_name(path.name + ".staged")
        copy_open_package_with_replacements(package, staged, replacements)
    os.replace(staged, path)
