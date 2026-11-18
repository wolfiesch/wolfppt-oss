"""Named SmartArt layout switching for WolfPPT's deterministic fallback layouts.

Use ``shape.smartart.layout = 'organizationchart'`` to switch a standard layout
without changing nodes or relationships. Read the selected layout through the
same property. The fallback renderer supports process, hierarchy, cycle and
pyramid families; this is not a general diagram layout-language interpreter.

A cached drawing cannot yet be regenerated coherently. Data-model layout bindings
also require coordinated updates. Switching either diagram raises
``SmartArtLayoutRefusal`` before queueing an edit. Colour and quick-style XML
remain available through the existing definition accessors, but their visual
interpretation is not supported by this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .shape_core_facade import SmartArt

__all__ = ["SmartArtLayoutRefusal"]


class SmartArtLayoutRefusal(ValueError):
    """An unsupported layout switch; the edit queue remains unchanged.

    ``reason`` identifies an unsupported layout, cache, binding or invalid diagram.
    """

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def _layout_name(diagram: SmartArt) -> str | None:
    root = ET.fromstring(diagram.layout_xml)
    namespace = root.tag.removesuffix("layoutDef")
    title = root.find(f"{namespace}title")
    return None if title is None else title.get("val")


def _has_layout_binding(diagram: SmartArt) -> bool:
    slide = diagram._shape._slide
    if any(
        operation == "smartart" and (args[0], args[2]) == (slide._index, diagram._shape.shape_id)
        for operation, args in slide._presentation._shape_adds
    ):
        return False
    root = ET.fromstring(diagram._definition_xml("data"))
    namespace = root.tag.removesuffix("dataModel")
    return any(point.get("loTypeId") for point in root.iter(f"{namespace}prSet"))


def _switch_layout(diagram: SmartArt, value: str) -> None:
    from .shape_adds import DGM_NS, _smartart_layout, _smartart_layout_xml

    try:
        layout = _smartart_layout(value)
    except (TypeError, ValueError) as exc:
        raise SmartArtLayoutRefusal("unsupported_layout", str(exc)) from exc
    try:
        drawing = diagram.drawing_xml
        current = ET.fromstring(diagram.layout_xml)
        bound = _has_layout_binding(diagram)
    except (KeyError, ValueError, ET.ParseError) as exc:
        raise SmartArtLayoutRefusal("invalid_diagram", str(exc)) from exc
    if drawing is not None:
        raise SmartArtLayoutRefusal(
            "cached_drawing",
            "SmartArt layout switching requires a diagram without a cached drawing",
        )
    if bound:
        raise SmartArtLayoutRefusal(
            "bound_layout",
            "SmartArt layout switching cannot update data-model loTypeId bindings",
        )
    namespace = current.tag.removesuffix("layoutDef")
    replacement = ET.fromstring(_smartart_layout_xml(layout, diagram._nodes))
    # Keep strict and transitional definitions in their source namespace profile.
    if namespace != f"{{{DGM_NS}}}":
        for element in replacement.iter():
            element.tag = element.tag.replace(f"{{{DGM_NS}}}", namespace)
    diagram.layout_xml = ET.tostring(replacement, encoding="utf-8", xml_declaration=True)
