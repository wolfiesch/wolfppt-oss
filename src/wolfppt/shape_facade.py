"""Shape facade classes and shape XML readers."""
# ruff: noqa: F401

from __future__ import annotations

from collections.abc import Iterator, Sequence
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
)
from .dml_fill import (
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
)
from .dml_fill import (
    fill_type_from_xml_children as _fill_type_from_xml_children,
)
from .dml_fill import (
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .dml_fill import (
    gradient_stop_element as _gradient_stop_element,
)
from .dml_fill import (
    set_shape_gradient_fill as _set_shape_gradient_fill,
)
from .dml_fill import (
    set_shape_no_fill as _set_shape_no_fill,
)
from .dml_fill import (
    set_shape_pattern_fill as _set_shape_pattern_fill,
)
from .dml_fill import (
    set_shape_pattern_fill_color as _set_shape_pattern_fill_color,
)
from .dml_fill import (
    set_shape_solid_fill as _set_shape_solid_fill,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
)
from .facade_values import (
    coerce_positive_int as _coerce_positive_int,
)
from .facade_values import (
    coerce_rotation_degrees as _coerce_rotation_degrees,
)
from .facade_values import (
    color_type_value as _color_type_value,
)
from .facade_values import (
    emu_value as _emu_value,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    line_dash_style_value as _line_dash_style_value,
)
from .facade_values import (
    normalize_line_dash_style as _normalize_line_dash_style,
)
from .facade_values import (
    normalize_pattern_type as _normalize_pattern_type,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    pattern_type_value as _pattern_type_value,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .image_dimensions import picture_dimensions as _picture_dimensions
from .image_inputs import (
    binary_source_for_queue as _binary_source_for_queue,
)
from .image_inputs import (
    image_source_for_queue as _image_source_for_queue,
)
from .image_inputs import (
    movie_source_for_queue as _movie_source_for_queue,
)
from .image_inputs import (
    source_display_filename as _source_display_filename,
)
from .image_inputs import (
    stored_media_source as _stored_media_source,
)
from .native_shape_connectors import CONNECTOR_PRESET_WRITER_BASE
from .package_parts import (
    PackagePart,
    XmlElementProxy,
)
from .package_parts import (
    package_xml_element as _package_xml_element,
)
from .shape_core_facade import MasterShape, Shape
from .shape_format_facade import (
    ColorFormat,
    FillFormat,
    GradientStop,
    GradientStopColorFormat,
    GradientStops,
    LineFillFormat,
    LineFormat,
    ShadowFormat,
    _detached_fill_parent,
    _DetachedFillShape,
    _shape_fill_pattern,
    _shape_fill_type,
    _shape_gradient_fill_payload,
    _shape_line_dash_style,
    _shape_line_fill_pattern,
    _shape_line_fill_type,
    _shape_line_width,
    _shape_pattern_rgb,
    _shape_shadow_inherit,
    _shape_style_rgb,
)
from .shape_format_inspection import (
    _supports_shape_line_style,
)
from .shape_inspection import (
    PictureImage,
    _auto_shape_preset_geometry,
    _check_shape_transform_edit,
    _cloneable_layout_placeholders,
    _connector_preset_geometry,
    _next_placeholder_name,
    _next_shape_id,
    _notes_placeholder_basename,
    _payload_string,
    _picture_crop,
    _picture_crop_value,
    _picture_image,
    _placeholder_basename,
    _placeholder_raw_value,
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
    _shape_hyperlink_address,
    _shape_hyperlink_click,
    _shape_is_text_box,
    _shape_line_xml_element,
    _shape_picture_crop,
    _shape_target_slide,
    _shape_type_value,
)
from .shape_locks import check_shape_locks, shape_locks_enforced
from .shape_payloads import (
    _shape_paragraph_runs,
    _shape_transform_value,
)
from .shape_placeholder_collections import (
    BaseShapePlaceholderCollection,
    MasterPlaceholderCollection,
    MasterShapeCollection,
    PlaceholderCollection,
)
from .shape_xml import (
    _shape_xml_element,
)

if TYPE_CHECKING:
    from .native_media import LinkedAudio, LinkedVideo
    from .presentation_slides import Slide
    from .shape_freeform import FreeformBuilder

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _pending_shape_identity(shape_id: int) -> dict[str, Any]:
    return {"id": str(shape_id), "_pending_shape": True}


_CONNECTOR_PRESET_BY_TOKEN = {
    name.upper(): name
    for name in (
        "line",
        "bentConnector3",
        "curvedConnector3",
        *CONNECTOR_PRESET_WRITER_BASE,
    )
}


def _connector_create_preset(connector_type: Any) -> str:
    """Resolve an ``MSO_CONNECTOR`` member or an ``ST_ShapeType`` connector preset name."""
    if isinstance(connector_type, str):
        preset = _CONNECTOR_PRESET_BY_TOKEN.get(connector_type.strip().upper())
        if preset is not None:
            return preset
    try:
        return _connector_preset_geometry(connector_type)
    except NotImplementedError:
        raise NotImplementedError(
            "add_connector supports MSO_CONNECTOR.STRAIGHT, ELBOW, and CURVE and the "
            f"connector presets {', '.join(_CONNECTOR_PRESET_BY_TOKEN.values())}; "
            f"got {connector_type!r}"
        ) from None


def _placeholder_queue_spec(
    spec: dict[str, str | bool | None],
) -> dict[str, str | None]:
    return {
        "placeholder_type": _payload_string(spec, "placeholder_type"),
        "placeholder_orient": _payload_string(spec, "placeholder_orient"),
        "placeholder_size": _payload_string(spec, "placeholder_size"),
        "placeholder_idx": _payload_string(spec, "placeholder_idx"),
    }


def _update_edit_references_after_grouping(
    presentation: Any,
    slide_index: int,
    grouped_shape_indices: tuple[int, ...],
    group_final_index: int,
    original_shape_count: int,
) -> None:
    """Update pending edit references after grouping existing shapes.

    When shapes are grouped, their indices change:
    - Grouped shapes are removed from top-level and moved into a group
    - Remaining shapes shift down to fill the gaps
    - A new group shape is added

    This function remaps all pending edit keys that reference shapes on the
    affected slide to use the new indices or group child references.

    Args:
        presentation: Presentation object with edit dictionaries
        slide_index: Index of the slide where grouping occurred
        grouped_shape_indices: Original indices of shapes that were grouped
        group_final_index: Final index of the new group shape
        original_shape_count: Number of shapes before grouping
    """
    # Build mapping from old index to new reference
    old_to_new: dict[int, int | tuple[int, int]] = {}
    grouped_set = set(grouped_shape_indices)

    # Shapes that were grouped now have tuple references (group_index, child_index)
    for child_index, old_index in enumerate(sorted(grouped_shape_indices)):
        old_to_new[old_index] = (group_final_index, child_index)

    # Shapes that stayed at top level get their new indices
    # We need to process ALL original shape indices
    new_index = 0
    for old_index in range(original_shape_count):
        if old_index not in grouped_set:
            old_to_new[old_index] = new_index
            new_index += 1

    # Helper to remap a single key
    def remap_key(key: tuple[int, Any]) -> tuple[int, int | tuple[int, ...]] | None:
        key_slide_index, shape_ref = key
        if key_slide_index != slide_index:
            return None

        if isinstance(shape_ref, int):
            # Simple integer reference
            if shape_ref not in old_to_new:
                return None  # Shape index not affected by this grouping
            new_ref = old_to_new[shape_ref]
            return (slide_index, new_ref)

        if isinstance(shape_ref, tuple) and len(shape_ref) > 0:
            # Tuple reference - remap the group index if needed
            group_index = shape_ref[0]
            if group_index in old_to_new:
                new_group_ref = old_to_new[group_index]
                if isinstance(new_group_ref, int):
                    # Group stayed at top level, just update its index
                    return (slide_index, (new_group_ref, *shape_ref[1:]))
                else:
                    # Group was itself grouped - this shouldn't happen in practice
                    # but handle it anyway
                    return (slide_index, new_group_ref + shape_ref[1:])
            # Group index unchanged
            return None

        return None

    # Update all edit dictionaries
    edit_dicts = [
        presentation._connector_connection_edits,
        presentation._shape_hyperlink_edits,
        presentation._shape_target_slide_edits,
        presentation._shape_rotation_edits,
        presentation._shape_flip_edits,
        presentation._shape_lock_edits,
        presentation._shape_name_edits,
        presentation._shape_adjustment_edits,
        presentation._picture_crop_edits,
        presentation._picture_transparency_edits,
        presentation._picture_correction_edits,
        presentation._shape_shadow_inherit_edits,
        presentation._shape_effect_edits,
        presentation._shape_glow_edits,
        presentation._shape_line_color_edits,
        presentation._shape_line_width_edits,
        presentation._shape_line_dash_edits,
        presentation._shape_line_end_edits,
        presentation._shape_line_pattern_edits,
        presentation._shape_line_pattern_fore_color_edits,
        presentation._shape_line_pattern_back_color_edits,
    ]

    for edit_dict in edit_dicts:
        keys_to_update = []
        for key in list(edit_dict.keys()):
            new_key = remap_key(key)
            if new_key is not None:
                keys_to_update.append((key, new_key))

        for old_key, new_key in keys_to_update:
            value = edit_dict.pop(old_key)
            edit_dict[new_key] = value

    # Update edit lists (z-order edits)
    updated_z_order = []
    for item in presentation._shape_z_order_edits:
        item_slide_index, shape_ref, action = item
        if (
            item_slide_index == slide_index
            and isinstance(shape_ref, int)
            and shape_ref in old_to_new
        ):
            new_ref = old_to_new[shape_ref]
            updated_z_order.append((slide_index, new_ref, action))
        else:
            updated_z_order.append(item)
    presentation._shape_z_order_edits = updated_z_order

    # Update edit sets (solid/background line edits)
    for edit_set_name in [
        "_shape_line_solid_edits",
        "_shape_line_background_edits",
        "_shape_line_element_edits",
    ]:
        edit_set = getattr(presentation, edit_set_name)
        updated_set = set()
        for key in edit_set:
            new_key = remap_key(key)
            if new_key is not None:
                updated_set.add(new_key)
            else:
                updated_set.add(key)
        setattr(presentation, edit_set_name, updated_set)


class _ArrangeProbe:
    """Stand-in that records where Align or Distribute would move a shape."""

    def __init__(self, shape: Shape) -> None:
        self.shape = shape
        self._slide = shape._slide
        self._payload = shape._payload
        self.name = shape.name
        self.rotation = shape.rotation
        self.left, self.top = shape.left, shape.top
        self.width, self.height = shape.width, shape.height


def _check_arrange_locks(arrange: Any, members: list[Shape], mode: str, relative_to: str) -> None:
    """Plan the arrangement and refuse it whole if any moved shape is locked.

    Each shape moves through its own setters, so without this preflight a locked
    shape late in the selection would refuse after earlier shapes had moved.
    """
    if not any(shape_locks_enforced(member) for member in members):
        return
    probes = [_ArrangeProbe(member) for member in members]
    arrange(probes, mode, relative_to=relative_to)
    for probe in probes:
        shape = probe.shape
        if (probe.left, probe.top) != (shape.left, shape.top):
            _check_shape_transform_edit(
                shape, {"x": probe.left, "y": probe.top, "cx": shape.width, "cy": shape.height}
            )


class ShapeCollection(Sequence["Shape"]):
    def __init__(self, slide: Slide, shapes: list[Shape]) -> None:
        self._slide = slide
        self._shapes = shapes
        self._turbo_add_enabled = False

    def __getitem__(self, index: int | slice) -> Shape | list[Shape]:
        return self._shapes[index]

    def __iter__(self) -> Iterator[Shape]:
        return iter(self._shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    def index(self, shape: Shape) -> int:
        for index, candidate in enumerate(self._shapes):
            if candidate is shape:
                return index
        target = shape.element
        for index, candidate in enumerate(self._shapes):
            if getattr(candidate, "_slide", None) is getattr(shape, "_slide", None) and getattr(
                candidate, "_index", None
            ) == getattr(shape, "_index", None):
                return index
        raise ValueError(f"{target!r} is not in list")

    def align(self, shapes: Sequence[Shape], mode: str, *, relative_to: str = "selection") -> None:
        """Align shapes of this slide like PowerPoint's Arrange > Align.

        ``mode`` is ``left``, ``center``, ``right``, ``top``, ``middle``, or ``bottom``;
        ``relative_to`` is ``selection`` or ``slide``. Rotated shapes align by the bounding
        box of their rotated frame; groups move as one object.
        """
        from .shape_arrange import align

        members = self._arranged_members(shapes)
        _check_arrange_locks(align, members, mode, relative_to)
        align(members, mode, relative_to=relative_to)

    def distribute(
        self, shapes: Sequence[Shape], mode: str, *, relative_to: str = "selection"
    ) -> None:
        """Space shapes of this slide evenly like PowerPoint's Arrange > Distribute.

        ``mode`` is ``horizontal`` or ``vertical``; ``relative_to`` is ``selection`` or
        ``slide``.
        """
        from .shape_arrange import distribute

        members = self._arranged_members(shapes)
        _check_arrange_locks(distribute, members, mode, relative_to)
        distribute(members, mode, relative_to=relative_to)

    def _arranged_members(self, shapes: Sequence[Shape]) -> list[Shape]:
        members = list(shapes)
        for shape in members:
            if not any(candidate is shape for candidate in self._shapes):
                raise ValueError(f"shape {getattr(shape, 'name', shape)!r} is not on this slide")
        return members

    def remove(self, shape: Shape) -> None:
        """Remove one existing shape from this slide or parent group."""
        if getattr(shape, "_payload", {}).get("_group_child"):
            raise NotImplementedError("deleting shapes inside a group is not supported yet")
        if getattr(shape, "_slide", None) is not self._slide:
            raise ValueError(f"{shape!r} is not in this shape collection")
        position = next(
            (index for index, candidate in enumerate(self._shapes) if candidate is shape),
            None,
        )
        if position is None:
            raise ValueError(f"{shape!r} is not in this shape collection")
        if not self._slide.partname or shape._payload.get("_pending_shape"):
            raise NotImplementedError("deleting an unsaved shape is not supported yet")

        self._slide._presentation._queue_shape_delete(
            self._slide._index,
            shape._index,
        )
        recolor_edits = self._slide._presentation._picture_recolor_edits
        part = str(self._slide.partname).lstrip("/")
        recolor_edits.pop((part, shape.shape_id), None)
        recolor_edits.pop((f"/{part}", shape.shape_id), None)
        self._shapes.pop(position)
        self._slide._payload["shapes"].pop(position)
        shape._payload["_deleted"] = True
        placeholders = getattr(self._slide, "_placeholders", None)
        if placeholders is not None:
            placeholders._placeholders[:] = [
                placeholder
                for placeholder in placeholders._placeholders
                if placeholder is not shape
            ]

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def parent(self) -> Slide:
        return self._slide

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._slide._presentation.path,
            self._slide.partname,
        )
        element = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if element is None:
            raise AttributeError("shape tree XML element is unavailable")
        return element

    @property
    def title(self) -> Shape | None:
        for shape in self._shapes:
            if _placeholder_type_xml(shape) in {"title", "ctrTitle"}:
                return shape
        return None

    @property
    def placeholders(self) -> PlaceholderCollection:
        return self._slide.placeholders

    @property
    def turbo_add_enabled(self) -> bool:
        return self._turbo_add_enabled

    @turbo_add_enabled.setter
    def turbo_add_enabled(self, value: Any) -> None:
        self._turbo_add_enabled = bool(value)

    def ph_basename(self, ph_type: Any) -> str:
        return _placeholder_basename(ph_type)

    def clone_layout_placeholders(self, slide_layout: Any) -> None:
        slide_part = str(self._slide._payload.get("part") or "")
        queue_layout_placeholders = (
            getattr(slide_layout, "_presentation", None) is self._slide._presentation
            and isinstance(getattr(slide_layout, "index", None), int)
            and hasattr(slide_layout, "_cloneable_placeholder_payloads")
        )
        queue_part_placeholders = (
            queue_layout_placeholders and bool(slide_part) and hasattr(slide_layout, "partname")
        )
        if hasattr(slide_layout, "_cloneable_placeholder_payloads"):
            specs = [
                self._append_placeholder_clone_payload(payload)
                for payload in slide_layout._cloneable_placeholder_payloads()
            ]
        else:
            specs = [
                self._append_placeholder_clone(placeholder)
                for placeholder in _cloneable_layout_placeholders(slide_layout)
            ]
        if specs:
            if queue_part_placeholders:
                for spec in specs:
                    self._slide._presentation._queue_part_placeholder_add(
                        slide_part,
                        spec,
                    )
            elif queue_layout_placeholders:
                self._slide._presentation._queue_layout_placeholders_add(
                    self._slide._index,
                    slide_layout.index,
                )
            else:
                self._slide._presentation._queue_placeholder_shapes_add(
                    self._slide._index,
                    [_placeholder_queue_spec(spec) for spec in specs],
                )

    def clone_placeholder(self, placeholder: Any) -> None:
        spec = self._append_placeholder_clone(placeholder)
        self._slide._presentation._queue_placeholder_shape_add(
            self._slide._index,
            len(self._shapes) - 1,
            spec["placeholder_type"],
            spec["placeholder_orient"],
            spec["placeholder_size"],
            spec["placeholder_idx"],
        )

    def _append_placeholder_clone(
        self,
        placeholder: Any,
    ) -> dict[str, str | bool | None]:
        return self._append_placeholder_clone_payload(
            {
                "placeholder_type": _placeholder_type_xml(placeholder),
                "placeholder_orient": _placeholder_raw_value(
                    placeholder,
                    "placeholder_orient",
                ),
                "placeholder_size": _placeholder_raw_value(
                    placeholder,
                    "placeholder_size",
                ),
                "placeholder_idx": _placeholder_raw_value(
                    placeholder,
                    "placeholder_idx",
                ),
            }
        )

    def _append_placeholder_clone_payload(
        self,
        placeholder_payload: dict[str, Any],
    ) -> dict[str, str | bool | None]:
        placeholder_type = _payload_string(placeholder_payload, "placeholder_type")
        placeholder_orient = _payload_string(placeholder_payload, "placeholder_orient")
        placeholder_size = _payload_string(placeholder_payload, "placeholder_size")
        placeholder_idx = _payload_string(placeholder_payload, "placeholder_idx")
        shape_id = _next_shape_id(self._shapes)
        name = _next_placeholder_name(
            self._shapes,
            shape_id,
            placeholder_type,
            placeholder_orient,
        )
        shape_index = len(self._shapes)
        payload = {
            "id": str(shape_id),
            "name": name,
            "kind": "shape",
            "text": "",
            "paragraphs": [""],
            "paragraph_runs": [[]],
            "is_placeholder": True,
            "placeholder_type": placeholder_type,
            "placeholder_idx": placeholder_idx,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
        }
        shape = Shape(self._slide, shape_index, payload)
        self._shapes.append(shape)
        placeholders = getattr(self._slide, "_placeholders", None)
        if placeholders is None:
            placeholders = PlaceholderCollection(self._slide, self._shapes[:-1])
            self._slide._placeholders = placeholders
        placeholders._placeholders.append(shape)
        return {
            "id": str(shape_id),
            "name": name,
            "placeholder_type": placeholder_type,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
            "placeholder_idx": placeholder_idx,
            "has_text_body": True,
        }

    def add_slide_zoom(
        self,
        target: Any,
        left: int,
        top: int,
        width: int,
        height: int,
        image_file: Any,
        *,
        image_type: str = "preview",
        return_to_parent: bool = True,
        transition_duration: Any = None,
        show_background: bool = True,
    ) -> Shape:
        """Add a slide destination with a custom thumbnail and live preview style."""
        from .zoom_frames import add_zoom_shape

        return add_zoom_shape(
            self,
            "slide",
            [target],
            [image_file],
            left,
            top,
            width,
            height,
            image_type=image_type,
            return_to_parent=return_to_parent,
            transition_duration=transition_duration,
            show_background=show_background,
        )

    def add_section_zoom(
        self,
        target: Any,
        left: int,
        top: int,
        width: int,
        height: int,
        image_file: Any,
        *,
        image_type: str = "preview",
        return_to_parent: bool = True,
        transition_duration: Any = None,
        show_background: bool = True,
    ) -> Shape:
        """Add a section destination. The fallback follows its first slide."""
        from .zoom_frames import add_zoom_shape

        return add_zoom_shape(
            self,
            "section",
            [target],
            [image_file],
            left,
            top,
            width,
            height,
            image_type=image_type,
            return_to_parent=return_to_parent,
            transition_duration=transition_duration,
            show_background=show_background,
        )

    def add_summary_zoom(
        self,
        targets: Sequence[Any],
        left: int,
        top: int,
        width: int,
        height: int,
        images: Sequence[Any],
        *,
        image_type: str = "preview",
        return_to_parent: bool = True,
        transition_duration: Any = None,
        show_background: bool = True,
    ) -> Shape:
        """Add an ordered row of section thumbnails; edit ``shape.zoom.sections``."""
        from .zoom_frames import add_zoom_shape

        return add_zoom_shape(
            self,
            "summary",
            targets,
            images,
            left,
            top,
            width,
            height,
            image_type=image_type,
            return_to_parent=return_to_parent,
            transition_duration=transition_duration,
            show_background=show_background,
        )

    def add_picture(
        self,
        image_file: Any,
        left: int,
        top: int,
        width: int | None = None,
        height: int | None = None,
    ) -> Shape:
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        image_source = _image_source_for_queue(image_file)
        cx_emu, cy_emu = _picture_dimensions(image_source, width, height)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_picture_add(
            self._slide._index,
            image_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Picture {shape_id - 1}",
                "kind": "picture",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "has_picture": True,
                "_image_file": image_source,
            },
        )
        self._shapes.append(shape)
        return shape

    def _linked_presentation(self) -> Any:
        from .native_media import LinkedMediaRefusal

        presentation = self._slide._presentation
        index = self._slide._index
        if (
            not 0 <= index < len(presentation.slides)
            or presentation.slides[index] is not self._slide
        ):
            raise LinkedMediaRefusal("shape collection is stale; reacquire it after package edits")
        return presentation

    @property
    def linked_audio(self) -> tuple[LinkedAudio, ...]:
        """Inspect this slide's saved linked audio without fetching it."""
        from .native_media import linked_audio

        return linked_audio(self._linked_presentation(), self._slide._index)

    @property
    def linked_video(self) -> tuple[LinkedVideo, ...]:
        """Inspect this slide's saved linked video without fetching it."""
        from .native_media import linked_video

        return linked_video(self._linked_presentation(), self._slide._index)

    def add_linked_audio(
        self,
        target: str,
        left: int,
        top: int,
        width: int,
        height: int,
        *,
        poster_frame: bytes,
    ) -> LinkedAudio:
        """Add linked audio using the saved-package audio contract; reacquire shapes."""
        from .native_media import add_linked_audio

        return add_linked_audio(
            self._linked_presentation(),
            self._slide._index,
            target,
            left,
            top,
            width,
            height,
            poster_frame=poster_frame,
        )

    def add_linked_video(
        self,
        target: str,
        left: int,
        top: int,
        width: int,
        height: int,
        *,
        poster_frame: bytes,
    ) -> LinkedVideo:
        """Add linked video using the saved-package contract; reacquire shapes."""
        from .native_media import add_linked_video

        return add_linked_video(
            self._linked_presentation(),
            self._slide._index,
            target,
            left,
            top,
            width,
            height,
            poster_frame=poster_frame,
        )

    def replace_linked_audio(self, audio: LinkedAudio, target: str) -> LinkedAudio:
        """Retarget an audio handle owned by this slide."""
        from .native_media import LinkedAudio, LinkedMediaRefusal, replace_linked_audio

        presentation = self._linked_presentation()
        if not isinstance(audio, LinkedAudio) or audio.slide_index != self._slide._index:
            raise LinkedMediaRefusal("expected a linked audio handle from this slide")
        return replace_linked_audio(presentation, audio, target)

    def replace_linked_video(self, video: LinkedVideo, target: str) -> LinkedVideo:
        """Retarget a video handle owned by this slide."""
        from .native_media import LinkedMediaRefusal, LinkedVideo, replace_linked_video

        presentation = self._linked_presentation()
        if not isinstance(video, LinkedVideo) or video.slide_index != self._slide._index:
            raise LinkedMediaRefusal("expected a linked video handle from this slide")
        return replace_linked_video(presentation, video, target)

    def _add_linked_shape(
        self,
        kind: str,
        source: Any,
        target: str,
        left: int,
        top: int,
        width: int,
        height: int,
        poster: Any,
    ) -> Shape:
        import io

        from PIL import Image, ImageDraw

        from .image_inputs import image_input_bytes
        from .native_media import LinkedMediaRefusal, _linked_media_target

        # A source/link conflict must not even read the supplied source.
        if source is not None:
            raise LinkedMediaRefusal("source and link are mutually exclusive; pass source=None")
        _linked_media_target(target)
        presentation = self._linked_presentation()
        if poster is None:
            image = Image.new("RGB", (64, 64), "#404040")
            ImageDraw.Draw(image).polygon(((24, 16), (24, 48), (48, 32)), fill="white")
            stream = io.BytesIO()
            image.save(stream, "PNG")
            poster_bytes = stream.getvalue()
        else:
            try:
                poster_bytes = poster if isinstance(poster, bytes) else image_input_bytes(poster)
            except (OSError, TypeError, ValueError) as exc:
                raise LinkedMediaRefusal("linked media poster must be readable PNG data") from exc
        add = self.add_linked_audio if kind == "audio" else self.add_linked_video
        handle = add(target, left, top, width, height, poster_frame=poster_bytes)
        return next(
            shape
            for shape in presentation.slides[handle.slide_index].shapes
            if shape.shape_id == handle.shape_id
        )

    def add_movie(
        self,
        movie_file: Any,
        left: int,
        top: int,
        width: int,
        height: int,
        poster_frame_image: Any = None,
        mime_type: str = "video/unknown",
        *,
        link: str | None = None,
    ) -> Shape:
        """Add embedded video, or inert linked video when source is None and link is set."""
        if link is not None:
            return self._add_linked_shape(
                "video",
                movie_file,
                link,
                left,
                top,
                width,
                height,
                poster_frame_image,
            )
        stored_source = _stored_media_source(self._slide._presentation, movie_file, "video")
        mime_type_value = str(mime_type) if stored_source is None else stored_source.content_type
        movie_source = (
            _movie_source_for_queue(movie_file, mime_type_value)
            if stored_source is None
            else stored_source
        )
        poster_source = (
            None if poster_frame_image is None else _image_source_for_queue(poster_frame_image)
        )
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_movie_add(
            self._slide._index,
            movie_source,
            poster_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type_value,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": _source_display_filename(movie_source),
                "kind": "movie",
                "text": "",
                "paragraphs": [],
                "_poster_frame_file": poster_source,
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_audio(
        self,
        audio_file: Any,
        left: int,
        top: int,
        width: int,
        height: int,
        mime_type: str = "audio/unknown",
        poster_frame_image: Any = None,
        *,
        link: str | None = None,
    ) -> Shape:
        """Add embedded audio, or inert linked audio when source is None and link is set."""
        if link is not None:
            return self._add_linked_shape(
                "audio",
                audio_file,
                link,
                left,
                top,
                width,
                height,
                poster_frame_image,
            )
        stored_source = _stored_media_source(self._slide._presentation, audio_file, "audio")
        mime_type_value = str(mime_type) if stored_source is None else stored_source.content_type
        audio_source = (
            _binary_source_for_queue(audio_file, "audio.bin")
            if stored_source is None
            else stored_source
        )
        poster_source = (
            None if poster_frame_image is None else _image_source_for_queue(poster_frame_image)
        )
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_audio_add(
            self._slide._index,
            audio_source,
            poster_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type_value,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": _source_display_filename(audio_source),
                "kind": "audio",
                "text": "",
                "paragraphs": [],
                "_poster_frame_file": poster_source,
                "media_playback": {
                    "loop": False,
                    "play_across_slides": False,
                    "volume": 80,
                    "auto_play": False,
                },
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_ole_object(
        self,
        object_file: Any,
        prog_id: Any,
        left: int,
        top: int,
        width: int | None = None,
        height: int | None = None,
        icon_file: Any = None,
        icon_width: int | None = None,
        icon_height: int | None = None,
    ) -> Shape:
        object_source = _binary_source_for_queue(object_file, "object.bin")
        icon_source = None if icon_file is None else _image_source_for_queue(icon_file)
        prog_id_value = str(getattr(prog_id, "progId", prog_id))
        default_width = int(getattr(prog_id, "width", 965200))
        default_height = int(getattr(prog_id, "height", 609600))
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = default_width if width is None else _coerce_emu(width, "width")
        cy_emu = default_height if height is None else _coerce_emu(height, "height")
        icon_cx_emu = 965200 if icon_width is None else _coerce_emu(icon_width, "icon_width")
        icon_cy_emu = 609600 if icon_height is None else _coerce_emu(icon_height, "icon_height")
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_ole_object_add(
            self._slide._index,
            object_source,
            prog_id_value,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_source,
            icon_cx_emu,
            icon_cy_emu,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Object {len(self._shapes) + 1}",
                "kind": "ole_object",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_table(
        self,
        rows: int,
        cols: int,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Shape:
        row_count = _coerce_positive_int(rows, "rows")
        col_count = _coerce_positive_int(cols, "cols")
        table_index = _shape_collection_table_count(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_table_add(
            self._slide._index,
            table_index,
            row_count,
            col_count,
            _coerce_emu(left, "left"),
            _coerce_emu(top, "top"),
            _coerce_emu(width, "width"),
            _coerce_emu(height, "height"),
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "graphic_frame",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": _coerce_emu(left, "left"),
                    "y": _coerce_emu(top, "top"),
                    "cx": _coerce_emu(width, "width"),
                    "cy": _coerce_emu(height, "height"),
                },
                "tables": [
                    {
                        "rows": [["" for _ in range(col_count)] for _ in range(row_count)],
                        "row_count": row_count,
                        "col_count": col_count,
                    }
                ],
            },
            table_index,
        )
        self._shapes.append(shape)
        return shape

    def add_chart(
        self,
        chart_type: Any,
        x: int,
        y: int,
        cx: int,
        cy: int,
        chart_data: Any,
    ) -> Shape:
        from .chart_edits import _normalize_chart_add_data
        from .chart_xml import chart_type_payload_from_value as _chart_type_payload_from_value

        x_emu = _coerce_emu(x, "x")
        y_emu = _coerce_emu(y, "y")
        cx_emu = _coerce_emu(cx, "cx")
        cy_emu = _coerce_emu(cy, "cy")
        normalized = _normalize_chart_add_data(chart_data)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_chart_add(
            self._slide._index,
            chart_type,
            normalized,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        chart_payload = {
            "chart_type": _chart_type_payload_from_value(chart_type),
            "series": [
                {
                    "name": series["name"],
                    "categories": list(series["categories"]),
                    "x_values": list(series.get("x_values") or []),
                    "bubble_sizes": list(series.get("bubble_sizes") or []),
                    "values": list(series["values"]),
                }
                for series in normalized["series"]
            ],
            "part": "",
            "has_title": False,
            "title_text": "",
            "has_legend": False,
            "legend_position": "r",
            "legend_include_in_layout": True,
            "axes": {},
        }
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Chart {len(self._shapes) + 1}",
                "kind": "graphic_frame",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "has_chart": True,
                "_chart_payload": chart_payload,
            },
        )
        self._shapes.append(shape)
        return shape

    def add_smartart(
        self,
        layout_type: str,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Shape:
        """Add an editable SmartArt graphic frame with one root node."""
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        if not isinstance(layout_type, str):
            raise TypeError("layout_type must be a string")
        if cx_emu <= 0 or cy_emu <= 0:
            raise ValueError("SmartArt width and height must be positive")
        shape_index = len(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        nodes: list[dict[str, str | None]] = [{"id": "2", "text": "", "parent": None}]
        self._slide._presentation._queue_smartart_add(
            self._slide._index,
            shape_index,
            shape_id,
            layout_type,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            nodes,
        )
        shape = Shape(
            self._slide,
            shape_index,
            {
                **_pending_shape_identity(shape_id),
                "name": f"SmartArt {shape_id - 1}",
                "kind": "graphic_frame",
                "text": "",
                "paragraphs": [],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "has_smartart": True,
                "smartart_nodes": nodes,
            },
        )
        self._shapes.append(shape)
        return shape

    def add_financial_chart(
        self,
        spec: Any,
        x: int,
        y: int,
        cx: int,
        cy: int,
    ) -> Shape:
        """Author an editable combination or waterfall chart.

        ``spec`` is a :class:`wolfppt.chart_financial.ComboChartSpec` or
        :class:`wolfppt.chart_financial.WaterfallChartSpec`.  The authored
        chart part stays a normal editable OOXML chart with an embedded
        workbook, so later refresh edits go through the ordinary chart facade.
        """
        from .chart_financial import financial_chart_payload

        normalized = financial_chart_payload(spec)
        return self.add_chart(spec.kind, x, y, cx, cy, normalized)

    def add_extended_chart(
        self,
        spec: Any,
        x: int,
        y: int,
        cx: int,
        cy: int,
    ) -> Shape:
        """Author one Office 2016+ ChartEx chart."""
        from .chart_financial import ExtendedChartSpec, financial_chart_payload

        if not isinstance(spec, ExtendedChartSpec):
            raise TypeError("spec must be an ExtendedChartSpec")
        return self.add_chart(spec.kind, x, y, cx, cy, financial_chart_payload(spec))

    def add_textbox(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Shape:
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_text_box_add(
            self._slide._index,
            len(self._shapes),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        shape = Shape(
            self._slide,
            len(self._shapes),
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "shape",
                "is_text_box": True,
                "text": "",
                "paragraphs": [""],
                "paragraph_runs": [[]],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
            },
        )
        self._shapes.append(shape)
        return shape

    def add_group_shape(self, shapes: Sequence[Shape] = ()) -> Shape:
        grouped_shapes = tuple(shapes)
        if not grouped_shapes:
            shape_id = _next_shape_id(self._shapes)
            self._slide._presentation._queue_group_shape_add(self._slide._index)
            shape = Shape(
                self._slide,
                len(self._shapes),
                {
                    **_pending_shape_identity(shape_id),
                    "name": f"Group {len(self._shapes) + 1}",
                    "kind": "group",
                    "text": "",
                    "paragraphs": [],
                    "paragraph_runs": [],
                    "transform": {
                        "x": 0,
                        "y": 0,
                        "cx": 0,
                        "cy": 0,
                    },
                    "_group_insertion_frame": (0, 0, 0, 0, 0, 0, 0, 0),
                    "children": [],
                    "has_group": True,
                },
            )
            self._shapes.append(shape)
            return shape

        shape_indices = self._grouped_shape_indices(grouped_shapes)
        shape_id = _next_shape_id(self._shapes)
        left, top, width, height = self._grouped_shape_bounds(grouped_shapes)
        for member in grouped_shapes:
            check_shape_locks(member, "grouping", "no_group")
        self._slide._presentation._queue_existing_shape_group_add(
            self._slide._index,
            shape_indices,
        )
        shape = Shape(
            self._slide,
            len(self._shapes) - len(shape_indices),
            {
                **_pending_shape_identity(shape_id),
                "name": f"Group {shape_id - 1}",
                "kind": "group",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "transform": {
                    "x": left,
                    "y": top,
                    "cx": width,
                    "cy": height,
                },
                "_group_insertion_frame": (left, top, width, height) * 2,
                "children": [deepcopy(child._payload) for child in grouped_shapes],
                "has_group": True,
            },
        )
        # Capture original state before modifying shape list
        original_shape_count = len(self._shapes)

        selected = set(shape_indices)
        remaining = [
            candidate for index, candidate in enumerate(self._shapes) if index not in selected
        ]
        self._shapes = [*remaining, shape]
        for index, candidate in enumerate(self._shapes):
            candidate._index = index

        # Update pending edit references to reflect the new shape indices
        _update_edit_references_after_grouping(
            self._slide._presentation,
            self._slide._index,
            shape_indices,
            len(self._shapes) - 1,  # Group is at the end
            original_shape_count,
        )

        return shape

    def _grouped_shape_indices(self, shapes: tuple[Shape, ...]) -> tuple[int, ...]:
        indices: list[int] = []
        for shape in shapes:
            if shape not in self._shapes:
                raise ValueError("shape is not in this shape collection")
            indices.append(self._shapes.index(shape))
        if len(set(indices)) != len(indices):
            raise ValueError("cannot group the same shape more than once")
        return tuple(indices)

    def _grouped_shape_bounds(
        self,
        shapes: tuple[Shape, ...],
    ) -> tuple[int, int, int, int]:
        boxes = [
            (
                _shape_transform_value(shape, "x"),
                _shape_transform_value(shape, "y"),
                _shape_transform_value(shape, "cx"),
                _shape_transform_value(shape, "cy"),
            )
            for shape in shapes
        ]
        left = min(x for x, _y, _cx, _cy in boxes)
        top = min(y for _x, y, _cx, _cy in boxes)
        right = max(x + cx for x, _y, cx, _cy in boxes)
        bottom = max(y + cy for _x, y, _cx, cy in boxes)
        return left, top, right - left, bottom - top

    def build_freeform(
        self,
        start_x: float = 0,
        start_y: float = 0,
        scale: tuple[float, float] | float = 1.0,
    ) -> FreeformBuilder:
        from .shape_freeform import FreeformBuilder

        x_scale, y_scale = scale if isinstance(scale, tuple) else (scale, scale)
        return FreeformBuilder(self, Shape, start_x, start_y, x_scale, y_scale)

    def add_shape(
        self,
        auto_shape_type: Any,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Shape:
        preset_geometry = _auto_shape_preset_geometry(auto_shape_type)
        x_emu = _coerce_emu(left, "left")
        y_emu = _coerce_emu(top, "top")
        cx_emu = _coerce_emu(width, "width")
        cy_emu = _coerce_emu(height, "height")
        shape_index = len(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_auto_shape_add(
            self._slide._index,
            shape_index,
            shape_id,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        shape = Shape(
            self._slide,
            shape_index,
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "shape",
                "text": "",
                "paragraphs": [""],
                "paragraph_runs": [[]],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "preset_geometry": preset_geometry,
            },
        )
        self._shapes.append(shape)
        return shape

    def add_connector(
        self,
        connector_type: Any,
        begin_x: int,
        begin_y: int,
        end_x: int,
        end_y: int,
    ) -> Shape:
        """Add a connector from (begin_x, begin_y) to (end_x, end_y).

        ``connector_type`` is an ``MSO_CONNECTOR`` member (STRAIGHT, ELBOW, CURVE) or a
        connector preset name: ``line``, ``straightConnector1``, ``bentConnector2`` to
        ``bentConnector5``, ``curvedConnector2`` to ``curvedConnector5``. Anything else
        raises ``NotImplementedError`` before queueing.
        """
        preset_geometry = _connector_create_preset(connector_type)
        begin_x_emu = _coerce_emu(begin_x, "begin_x")
        begin_y_emu = _coerce_emu(begin_y, "begin_y")
        end_x_emu = _coerce_emu(end_x, "end_x")
        end_y_emu = _coerce_emu(end_y, "end_y")
        x_emu = min(begin_x_emu, end_x_emu)
        y_emu = min(begin_y_emu, end_y_emu)
        cx_emu = abs(end_x_emu - begin_x_emu)
        cy_emu = abs(end_y_emu - begin_y_emu)
        shape_index = len(self._shapes)
        shape_id = _next_shape_id(self._shapes)
        self._slide._presentation._queue_connector_add(
            self._slide._index,
            shape_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        shape = Shape(
            self._slide,
            shape_index,
            {
                **_pending_shape_identity(shape_id),
                "name": "",
                "kind": "connector",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "begin_x": begin_x_emu,
                "begin_y": begin_y_emu,
                "end_x": end_x_emu,
                "end_y": end_y_emu,
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                "preset_geometry": preset_geometry,
            },
        )
        self._shapes.append(shape)
        return shape
