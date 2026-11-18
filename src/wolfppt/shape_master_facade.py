"""Master-shape facade objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .shape_action_facade import PlaceholderFormat
    from .shape_locks import ShapeLocks
    from .text_facade import TextFrame
from .facade_values import coerce_emu, rotation_degrees_from_units
from .package_parts import (
    PackagePart,
    XmlElementProxy,
)
from .package_parts import (
    package_xml_element as _package_xml_element,
)
from .shape_inspection import _shape_type_value
from .shape_xml import _find_shape_transform_xml_element, _shape_xml_element
from .xml_helpers import find_ooxml


class MasterShape:
    def __init__(
        self,
        master: Any,
        index: int,
        payload: dict[str, Any],
    ) -> None:
        self._master = master
        self._index = index
        self._payload = dict(payload)

    @property
    def shape_id(self) -> int | str | None:
        raw = self._payload.get("id")
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return raw

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @property
    def shape_type(self) -> Any:
        return _shape_type_value(self)

    @property
    def is_placeholder(self) -> bool:
        return bool(self._payload.get("is_placeholder"))

    @property
    def placeholder_format(self) -> PlaceholderFormat:
        if not self.is_placeholder:
            raise ValueError("shape is not a placeholder")
        from .shape_action_facade import PlaceholderFormat

        return PlaceholderFormat(self)

    @property
    def has_chart(self) -> bool:
        return False

    @property
    def has_table(self) -> bool:
        return False

    @property
    def has_text_frame(self) -> bool:
        return self._payload.get("kind") in {"shape", "freeform"}

    @property
    def part(self) -> PackagePart:
        return self._master.part

    @property
    def text(self) -> str:
        return str(self._payload.get("text") or "")

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        self._payload["text"] = text
        self._master._presentation._queue_part_shape_text(
            self._master.partname,
            self._index,
            text,
        )

    @property
    def text_frame(self) -> TextFrame:
        if not self.has_text_frame:
            raise AttributeError("shape does not have a text frame")
        from .text_facade import TextFrame

        return TextFrame(self)

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._master._presentation.path,
            self._master.partname,
        )
        return XmlElementProxy(_shape_xml_element(root._element, self._payload))

    @property
    def _element(self) -> XmlElementProxy:
        return self.element

    @property
    def locks(self) -> ShapeLocks:
        from .shape_locks import ShapeLocks

        return ShapeLocks(self)

    @property
    def left(self) -> int:
        """Horizontal offset from slide origin in EMU."""
        return _master_shape_transform_value(self, "x")

    @left.setter
    def left(self, value: int) -> None:
        self._set_geometry("x", "left", value)

    @property
    def top(self) -> int:
        """Vertical offset from slide origin in EMU."""
        return _master_shape_transform_value(self, "y")

    @top.setter
    def top(self, value: int) -> None:
        self._set_geometry("y", "top", value)

    @property
    def width(self) -> int:
        """Shape width in EMU."""
        return _master_shape_transform_value(self, "cx")

    @width.setter
    def width(self, value: int) -> None:
        self._set_geometry("cx", "width", value)

    @property
    def height(self) -> int:
        """Shape height in EMU."""
        return _master_shape_transform_value(self, "cy")

    @height.setter
    def height(self, value: int) -> None:
        self._set_geometry("cy", "height", value)

    def _set_geometry(self, key: str, name: str, value: int) -> None:
        from .presentation_slides import NotesMaster

        if not isinstance(self._master, NotesMaster) or not self.is_placeholder:
            raise AttributeError(f"property '{name}' of 'MasterShape' object has no setter")
        emu = coerce_emu(value, name)
        if key in {"cx", "cy"} and emu < 0:
            raise ValueError(f"{name} must not be negative, got {emu}")
        transform = {
            component: _master_shape_transform_value(self, component)
            for component in ("x", "y", "cx", "cy")
        }
        if transform[key] == emu and self._payload.get("transform") is not None:
            return
        transform[key] = emu
        self._master._presentation._queue_shape_geometry(
            self._master.partname,
            self._index,
            transform["x"],
            transform["y"],
            transform["cx"],
            transform["cy"],
        )
        self._payload["transform"] = transform

    @property
    def rotation(self) -> float:
        """Clockwise rotation in degrees from the shape's own ``a:xfrm/@rot``.

        Matches python-pptx: placeholders do not inherit rotation from their
        layout or master, and a missing transform or ``rot`` reads as 0.0.
        """
        raw = self._payload.get("rotation")
        if not isinstance(raw, (int, float)):
            raw = _master_shape_rotation(self)
            self._payload["rotation"] = raw
        return float(raw)


def _master_shape_rotation(shape: MasterShape) -> float:
    try:
        root = _package_xml_element(shape._master._presentation.path, shape._master.partname)
        transform = _find_shape_transform_xml_element(
            _shape_xml_element(root._element, shape._payload)
        )
    except (AttributeError, KeyError):
        return 0.0
    raw = transform.attrib.get("rot") if transform is not None else None
    if raw in (None, ""):
        return 0.0
    try:
        return rotation_degrees_from_units(int(raw))
    except ValueError:
        return 0.0


def _master_shape_transform_value(shape: MasterShape, key: str) -> int:
    """Extract geometry from master shape, resolving inheritance when needed."""
    raw = shape._payload.get("transform")

    # If no transform and this is a placeholder on a layout, inherit from master
    if raw is None and shape._payload.get("is_placeholder"):
        # Check if the parent is a layout (has slide_master)
        master_attr = getattr(shape._master, "slide_master", None)
        if master_attr is not None:
            # This is a layout shape; find matching master placeholder
            from .shape_tree import (
                P_NS,
                _first_transform,
                _transform_box,
            )

            # Try exact match first (type, idx)
            ph_key = (
                str(shape._payload.get("placeholder_type") or "body"),
                str(shape._payload.get("placeholder_idx") or "0"),
            )
            match = _matching_placeholder_fuzzy(master_attr.element._element, ph_key)
            if match is not None:
                inherited = _first_transform([find_ooxml(match, f"{{{P_NS}}}spPr")])
                if inherited is not None:
                    box = _transform_box(inherited)
                    if box is not None:
                        raw = {"x": box.x, "y": box.y, "cx": box.width, "cy": box.height}

    if raw is None:
        raw = {}

    return int(raw.get(key, 0))


def _matching_placeholder_fuzzy(root, key: tuple[str, str]) -> Any:  # ET.Element | None
    """Find placeholder matching by (type, idx), falling back to type-only."""
    from .shape_tree import (
        _matching_placeholder,
        _placeholder_key,
        _tree_elements,
    )

    # Try exact match first
    exact = _matching_placeholder(root, key)
    if exact is not None:
        return exact

    # Fall back to type-only match (for layout inheriting from master with different idx)
    target_type = key[0]
    for element in _tree_elements(root):
        elem_key = _placeholder_key(element)
        if elem_key is not None and elem_key[0] == target_type:
            return element

    return None
