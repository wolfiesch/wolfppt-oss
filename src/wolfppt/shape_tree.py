"""Shape-tree helpers shared by editing and the renderer.

Placeholder keys, drawable children, first transforms, and object identity are
read the same way when a slide is edited and when it is resolved for
rendering, so both sides import them from here.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from xml.etree import ElementTree as ET

from .render_model import Rect
from .xml_helpers import find_ooxml, ooxml_namespace

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _drawable_children(container: ET.Element) -> Iterator[ET.Element]:
    """Yield children from an already selected MC tree, excluding metadata."""
    presentation_ns = ooxml_namespace(container, P_NS)
    for element in container:
        if element.tag in {
            f"{{{presentation_ns}}}extLst",
            f"{{{presentation_ns}}}nvGrpSpPr",
            f"{{{presentation_ns}}}grpSpPr",
        }:
            continue
        yield element


def _flag(element: ET.Element | None, name: str) -> bool:
    if element is None:
        return False
    return element.get(name, "").casefold() in {"1", "true", "on"}


def _identity_element(shape: ET.Element) -> ET.Element | None:
    """Return the ``p:cNvPr`` that numbers and names one drawable object."""
    return find_ooxml(shape, f".//{{{P_NS}}}cNvPr")


def _shape_identity(shape: ET.Element, fallback: str) -> tuple[str, bool]:
    identity = _identity_element(shape)
    if identity is None:
        return (fallback, False)
    return (identity.get("name", fallback), _flag(identity, "hidden"))


def _placeholder_key(shape: ET.Element) -> tuple[str, str] | None:
    namespace = ooxml_namespace(shape, P_NS)
    if shape.tag not in {
        f"{{{namespace}}}sp",
        f"{{{namespace}}}pic",
        f"{{{namespace}}}graphicFrame",
    }:
        return None
    for path in (
        f"./{{{P_NS}}}nvSpPr/{{{P_NS}}}nvPr/{{{P_NS}}}ph",
        f"./{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}nvPr/{{{P_NS}}}ph",
        f"./{{{P_NS}}}nvPicPr/{{{P_NS}}}nvPr/{{{P_NS}}}ph",
    ):
        placeholder = find_ooxml(shape, path)
        if placeholder is not None:
            return (
                placeholder.get("type", "body"),
                placeholder.get("idx", "0"),
            )
    return None


def _tree_elements(root: ET.Element) -> Iterator[ET.Element]:
    tree = find_ooxml(root, f".//{{{P_NS}}}spTree")
    if tree is None:
        return iter(())
    return _drawable_children(tree)


def _placeholder_map(root: ET.Element) -> dict[tuple[str, str], ET.Element]:
    mapping: dict[tuple[str, str], ET.Element] = {}
    for element in _tree_elements(root):
        key = _placeholder_key(element)
        if key is not None:
            mapping.setdefault(key, element)
    return mapping


def _matching_placeholder(
    root: ET.Element, key: tuple[str, str], *, fallback_by_type: bool = False
) -> ET.Element | None:
    """Match a slide/layout index exactly; master indices are independent."""
    fallback = None
    for element in _tree_elements(root):
        candidate = _placeholder_key(element)
        if candidate == key:
            return element
        if (
            fallback_by_type
            and fallback is None
            and candidate is not None
            and candidate[0] == key[0]
        ):
            fallback = element
    return fallback


def _first_transform(
    sources: Sequence[ET.Element | None],
) -> ET.Element | None:
    for source in sources:
        if source is None:
            continue
        transform = find_ooxml(source, f"{{{A_NS}}}xfrm")
        if transform is not None:
            return transform
    return None


def _transform_box(transform: ET.Element) -> Rect | None:
    offset = find_ooxml(transform, f"{{{A_NS}}}off")
    extent = find_ooxml(transform, f"{{{A_NS}}}ext")
    if offset is None or extent is None:
        return None
    return _rect_from(offset, extent)


def _rect_from(offset: ET.Element, extent: ET.Element) -> Rect | None:
    try:
        box = Rect(
            x=int(offset.attrib["x"]),
            y=int(offset.attrib["y"]),
            width=int(extent.attrib["cx"]),
            height=int(extent.attrib["cy"]),
        )
        return box if box.width >= 0 and box.height >= 0 else None
    except (KeyError, ValueError):
        return None
