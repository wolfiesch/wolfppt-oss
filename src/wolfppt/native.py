"""Optional native Python bindings for the Rust package reader."""

from __future__ import annotations

import importlib.util
import json
from typing import Any

from .native_binding import NATIVE_INSTALL_HINT
from .native_media import (
    add_deeper_nested_group_image,
    add_deeper_nested_group_ole_object,
    add_group_image,
    add_group_ole_object,
    add_image,
    add_movie,
    add_nested_group_image,
    add_nested_group_image_in_new_group,
    add_nested_group_ole_object,
    add_nested_group_ole_object_in_new_group,
    add_ole_object,
    replace_image,
)
from .native_group_shapes import (
    add_group_shape,
    add_group_shape_to_deeper_nested_group,
    add_group_shape_to_nested_group,
    add_nested_group_shape,
    group_existing_deeper_nested_group_children,
    group_existing_group_children,
    group_existing_nested_group_children,
)
from .native_read import inspect, roundtrip, summarize, summarize_slide
from .native_results import (
    NativeAutoShapeAddResult,
    NativeConnectorAddResult,
    NativeEditBatchResult,
    NativeFreeformShapeAddResult,
    NativeGroupShapeAddResult,
    NativeImageAddResult,
    NativeImageReplacementResult,
    NativeInspectResult,
    NativeMovieAddResult,
    NativeOleObjectAddResult,
    NativeParagraphTextSetResult,
    NativePlaceholderShapeAddResult,
    NativePlaceholderShapeBatchAddResult,
    NativePresentationSummary,
    NativeShapeTextSetResult,
    NativeSlideAddResult,
    NativeSlideDeleteResult,
    NativeTableAddResult,
    NativeTableCellReplacementResult,
    NativeTextBoxAddResult,
    NativeTextReplacementResult,
    NativeTextRunReplacementResult,
)
from .native_shapes import (
    add_auto_shape,
    add_auto_shape_with_options,
    add_auto_shape_with_text,
    add_connected_connector,
    add_connected_connector_with_auto_shapes,
    add_connected_group_connector,
    add_connected_group_connector_with_auto_shapes,
    add_connector,
    add_deeper_nested_group_auto_shape_with_text,
    add_deeper_nested_group_freeform_shape_with_text,
    add_deeper_nested_group_text_box_with_text,
    add_freeform_shape,
    add_freeform_shape_with_text,
    add_group_auto_shape_with_text,
    add_group_connector,
    add_group_freeform_shape_with_text,
    add_group_text_box_with_text,
    add_deeper_nested_group_connector,
    add_nested_group_auto_shape_with_text,
    add_nested_group_auto_shape_in_new_group_with_text,
    add_nested_group_connector,
    add_nested_group_connector_in_new_group,
    add_nested_group_freeform_shape_in_new_group_with_text,
    add_nested_group_freeform_shape_with_text,
    add_nested_group_text_box_in_new_group_with_text,
    add_nested_group_text_box_with_text,
    add_layout_placeholders,
    add_placeholder_shape,
    add_placeholder_shapes,
    add_slide,
    duplicate_slide,
    delete_slide,
    delete_slides,
    add_table,
    add_table_with_cell_texts,
    add_text_box,
    add_text_box_with_text,
    apply_edit_batch,
    replace_table_cell,
)
from .native_text import (
    replace_text,
    replace_text_run,
    set_paragraph_text,
    set_shape_text,
)


def native_available() -> bool:
    return (
        importlib.util.find_spec("wolfppt_native") is not None
        or importlib.util.find_spec("wolfppt.wolfppt_native") is not None
    )

def native_build_info() -> dict[str, Any]:
    if not native_available():
        return {"installed": False}
    try:
        import wolfppt_native  # type: ignore[import-not-found]
    except ImportError:
        try:
            from wolfppt import wolfppt_native  # type: ignore[attr-defined]
        except ImportError:
            return {"installed": False}

    build_info_json = getattr(wolfppt_native, "build_info_json", None)
    if build_info_json is None:
        return {"installed": True, "build_profile": "unknown"}
    info = json.loads(build_info_json())
    return {"installed": True, **info}


__all__ = [
    "NATIVE_INSTALL_HINT",
    "NativeAutoShapeAddResult",
    "NativeConnectorAddResult",
    "NativeEditBatchResult",
    "NativeFreeformShapeAddResult",
    "NativeGroupShapeAddResult",
    "NativeImageAddResult",
    "NativeImageReplacementResult",
    "NativeInspectResult",
    "NativeMovieAddResult",
    "NativeOleObjectAddResult",
    "NativeParagraphTextSetResult",
    "NativePlaceholderShapeAddResult",
    "NativePlaceholderShapeBatchAddResult",
    "NativePresentationSummary",
    "NativeShapeTextSetResult",
    "NativeSlideAddResult",
    "NativeTableAddResult",
    "NativeTableCellReplacementResult",
    "NativeTextBoxAddResult",
    "NativeTextReplacementResult",
    "NativeTextRunReplacementResult",
    "add_auto_shape",
    "add_auto_shape_with_options",
    "add_auto_shape_with_text",
    "add_connected_connector",
    "add_connected_connector_with_auto_shapes",
    "add_connected_group_connector",
    "add_connected_group_connector_with_auto_shapes",
    "add_connector",
    "add_deeper_nested_group_auto_shape_with_text",
    "add_deeper_nested_group_freeform_shape_with_text",
    "add_deeper_nested_group_text_box_with_text",
    "add_deeper_nested_group_image",
    "add_deeper_nested_group_ole_object",
    "add_freeform_shape",
    "add_freeform_shape_with_text",
    "add_group_auto_shape_with_text",
    "add_group_connector",
    "add_group_freeform_shape_with_text",
    "add_group_image",
    "add_group_ole_object",
    "add_group_shape",
    "add_group_shape_to_deeper_nested_group",
    "add_group_shape_to_nested_group",
    "add_group_text_box_with_text",
    "group_existing_deeper_nested_group_children",
    "group_existing_group_children",
    "group_existing_nested_group_children",
    "add_deeper_nested_group_connector",
    "add_nested_group_auto_shape_with_text",
    "add_nested_group_auto_shape_in_new_group_with_text",
    "add_nested_group_connector",
    "add_nested_group_connector_in_new_group",
    "add_nested_group_freeform_shape_in_new_group_with_text",
    "add_nested_group_freeform_shape_with_text",
    "add_nested_group_image",
    "add_nested_group_image_in_new_group",
    "add_nested_group_ole_object",
    "add_nested_group_ole_object_in_new_group",
    "add_nested_group_shape",
    "add_nested_group_text_box_in_new_group_with_text",
    "add_nested_group_text_box_with_text",
    "add_image",
    "add_layout_placeholders",
    "add_movie",
    "add_ole_object",
    "add_placeholder_shape",
    "add_placeholder_shapes",
    "add_slide",
    "duplicate_slide",
    "add_table",
    "add_table_with_cell_texts",
    "add_text_box",
    "add_text_box_with_text",
    "apply_edit_batch",
    "inspect",
    "native_available",
    "native_build_info",
    "replace_image",
    "replace_table_cell",
    "replace_text",
    "replace_text_run",
    "roundtrip",
    "set_paragraph_text",
    "set_shape_text",
    "summarize",
    "summarize_slide",
]
