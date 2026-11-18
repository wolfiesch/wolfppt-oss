"""Ordered DrawingML picture image transforms.

The Open XML SDK 3.5.1 drawingml schema, CT_Blip/a:blip, specifies a
repeated choice of 17 effects followed by optional extLst. Effect order is
semantic: effects must NOT be sorted by their names. Attribute units here are
the raw OOXML integers (100000 = 100%, 60000 = one degree, radii in EMU).

Schema source: https://github.com/dotnet/Open-XML-SDK/blob/v3.5.1/data/schemas/
schemas_openxmlformats_org_drawingml_2006_main.json
"""

from __future__ import annotations

import copy
import re
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .shape_picture_correction_edits import (
    A14_CORRECTION_ATTRS,
    A14_NS,
    _a14_effect_records,
    _get_picture_brightness_from_element,
    _get_picture_contrast_from_element,
    _insert_a14_correction,
    _remove_a14_correction,
    _set_picture_correction_on_element,
    _validate_a14_correction,
    validate_picture_correction_value,
)
from .shape_picture_transparency_edits import (
    A_NS,
    _find_blip_in_picture,
    _find_picture_element_by_id,
    _get_picture_transparency_from_element,
    _set_picture_transparency_on_element,
    validate_picture_shape_target,
    validate_picture_transparency_value,
)
from .xml_helpers import xml_local_name

IMAGE_TRANSFORM_NAMES = frozenset(
    {
        "alphaBiLevel",
        "alphaCeiling",
        "alphaFloor",
        "alphaInv",
        "alphaMod",
        "alphaModFix",
        "alphaRepl",
        "biLevel",
        "blur",
        "clrChange",
        "clrRepl",
        "duotone",
        "fillOverlay",
        "grayscl",
        "hsl",
        "lum",
        "tint",
    }
)
_COLORS = frozenset({"srgbClr", "scrgbClr", "hslClr", "sysClr", "schemeClr", "prstClr"})
_ATTRS = {
    "alphaBiLevel": {"thresh": (0, 100000)},
    "alphaModFix": {"amt": (0, 2147483647)},
    "alphaRepl": {"a": (0, 100000)},
    "biLevel": {"thresh": (0, 100000)},
    "blur": {"rad": (0, 2147483647), "grow": "bool"},
    "clrChange": {"useA": "bool"},
    "fillOverlay": {"blend": "blend"},
    "hsl": {"hue": (0, 21599999), "sat": (-100000, 100000), "lum": (-100000, 100000)},
    "lum": {"bright": (-100000, 100000), "contrast": (-100000, 100000)},
    "tint": {"hue": (0, 21599999), "amt": (-100000, 100000)},
}
_REQUIRED = {
    "alphaBiLevel": "thresh",
    "alphaRepl": "a",
    "biLevel": "thresh",
    "fillOverlay": "blend",
}


def _color(value: str | ET.Element) -> ET.Element:
    if isinstance(value, ET.Element):
        result = copy.deepcopy(value)
    elif isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{6}", value):
        result = ET.Element(f"{{{A_NS}}}srgbClr", {"val": value.upper()})
    elif isinstance(value, str) and value.startswith("theme:"):
        name = value[6:]
        if name not in {
            "dk1",
            "lt1",
            "dk2",
            "lt2",
            "accent1",
            "accent2",
            "accent3",
            "accent4",
            "accent5",
            "accent6",
            "hlink",
            "folHlink",
        }:
            raise ValueError(f"invalid theme color {name!r}")
        result = ET.Element(f"{{{A_NS}}}schemeClr", {"val": name})
    else:
        raise ValueError(
            "color must be six RGB hex digits, theme:NAME, or a DrawingML color element"
        )
    if result.tag not in {f"{{{A_NS}}}{name}" for name in _COLORS}:
        raise ValueError("expected a DrawingML color element")
    return result


def _validate_effect(element: ET.Element) -> None:
    name = xml_local_name(element.tag)
    if element.tag == f"{{{A14_NS}}}{name}":
        _validate_a14_correction(element)
        return
    if element.tag != f"{{{A_NS}}}{name}" or name not in IMAGE_TRANSFORM_NAMES:
        raise ValueError(f"unsupported image transform {name!r}")
    attrs = _ATTRS.get(name, {})
    for attr, value in element.attrib.items():
        if attr not in attrs:
            raise ValueError(f"{name} has unsupported attribute {attr!r}")
        bounds = attrs[attr]
        if bounds == "bool":
            if value not in {"true", "false", "0", "1"}:
                raise ValueError(f"{name}.{attr} must be a boolean")
        elif bounds == "blend":
            if value not in {"over", "mult", "screen", "darken", "lighten"}:
                raise ValueError(f"{name}.{attr} is not a DrawingML blend mode")
        else:
            try:
                integer = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name}.{attr} must be an OOXML integer") from exc
            if not bounds[0] <= integer <= bounds[1]:
                raise ValueError(f"{name}.{attr} must be between {bounds[0]} and {bounds[1]}")
    required = _REQUIRED.get(name)
    if required is not None and required not in element.attrib:
        raise ValueError(f"{name} requires {required}")
    children = list(element)
    if name in {"duotone", "clrRepl"}:
        count = 2 if name == "duotone" else 1
        if len(children) != count or any(
            child.tag not in {f"{{{A_NS}}}{n}" for n in _COLORS} for child in children
        ):
            raise ValueError(f"{name} requires {count} DrawingML colors")
    elif name == "alphaInv":
        if len(children) > 1 or any(
            child.tag not in {f"{{{A_NS}}}{n}" for n in _COLORS} for child in children
        ):
            raise ValueError("alphaInv accepts at most one DrawingML color")
    elif name == "clrChange":
        if [child.tag for child in children] != [
            f"{{{A_NS}}}clrFrom",
            f"{{{A_NS}}}clrTo",
        ]:
            raise ValueError("clrChange requires clrFrom followed by clrTo")
        for child in children:
            if len(child) != 1 or child[0].tag not in {f"{{{A_NS}}}{n}" for n in _COLORS}:
                raise ValueError("clrChange requires a color in each color container")
    elif name == "alphaMod":
        if len(children) != 1 or children[0].tag != f"{{{A_NS}}}cont":
            raise ValueError("alphaMod requires a DrawingML effect container")
    elif name == "fillOverlay":
        if len(children) != 1 or children[0].tag not in {
            f"{{{A_NS}}}{n}"
            for n in {
                "noFill",
                "solidFill",
                "gradFill",
                "blipFill",
                "pattFill",
                "grpFill",
            }
        }:
            raise ValueError("fillOverlay requires one DrawingML fill")
    elif children:
        raise ValueError(f"{name} cannot contain child elements")


@dataclass(frozen=True)
class ImageTransform:
    """Immutable transform snapshot; editing occurs through its collection."""

    xml: str

    @property
    def name(self) -> str:
        return xml_local_name(ET.fromstring(self.xml).tag)

    @property
    def attributes(self) -> Any:
        return MappingProxyType(dict(ET.fromstring(self.xml).attrib))

    def to_element(self) -> ET.Element:
        """Return a detached element, including nested colors/fills/effects."""
        return ET.fromstring(self.xml)


def _make_effect(name: str, attributes: dict[str, Any]) -> ET.Element:
    if name not in IMAGE_TRANSFORM_NAMES and name not in A14_CORRECTION_ATTRS:
        raise ValueError(f"unsupported image transform {name!r}")
    attributes = dict(attributes)
    children = attributes.pop("children", ())
    colors = attributes.pop("colors", ())
    namespace = A14_NS if name in A14_CORRECTION_ATTRS else A_NS
    element = ET.Element(f"{{{namespace}}}{name}")
    for attr, value in attributes.items():
        if isinstance(value, bool):
            if _ATTRS.get(name, {}).get(attr) != "bool":
                raise TypeError(f"{name}.{attr} cannot be a boolean")
            value = "true" if value else "false"
        elif not isinstance(value, (str, int)):
            raise TypeError(f"{name}.{attr} must use raw OOXML integer units")
        element.set(attr, str(value))
    if colors:
        if name == "clrChange":
            for container, color in zip(("clrFrom", "clrTo"), colors, strict=True):
                ET.SubElement(element, f"{{{A_NS}}}{container}").append(_color(color))
        elif name in {"duotone", "clrRepl", "alphaInv"}:
            for color in colors:
                element.append(_color(color))
        else:
            raise ValueError(f"{name} does not accept colors")
    for child in children:
        if not isinstance(child, ET.Element):
            raise TypeError("children must be DrawingML elements")
        element.append(copy.deepcopy(child))
    _validate_effect(element)
    return element


def _queue_key(shape: Any) -> tuple[str, int]:
    validate_picture_shape_target(shape, "picture image transforms")
    return (str(shape._slide.partname).lstrip("/"), shape.shape_id)


def _queued(queue: dict, key: tuple[str, int]) -> Any:
    for candidate in (key, (f"/{key[0]}", key[1])):
        if candidate in queue:
            return queue[candidate]
    return None


def _current_picture(shape: Any) -> ET.Element:
    key = _queue_key(shape)
    presentation = shape._slide._presentation
    with zipfile.ZipFile(presentation.path) as package:
        root = ET.fromstring(package.read(key[0]))
    picture = _find_picture_element_by_id(root, key[1])
    if picture is None:
        raise ValueError(f"picture {key[1]!r} not found in {key[0]}")
    transforms = _queued(getattr(presentation, "_picture_recolor_edits", {}), key)
    if transforms is not None:
        _replace_transforms(picture, transforms)
    correction = _queued(presentation._picture_correction_edits, key)
    if correction is not None:
        _set_picture_correction_on_element(picture, correction)
    transparency_queue = presentation._picture_transparency_edits
    if key in transparency_queue or (f"/{key[0]}", key[1]) in transparency_queue:
        _set_picture_transparency_on_element(picture, _queued(transparency_queue, key))
    return picture


def _replace_transforms(picture: ET.Element, transforms: Sequence[str]) -> None:
    _, blip = _find_blip_in_picture(picture)
    if blip is None:
        raise AttributeError("picture blip is unavailable")
    elements = [ET.fromstring(xml) for xml in transforms]
    for element in elements:
        if xml_local_name(element.tag) != "extLst":
            _validate_effect(element)
    # Older queued snapshots contain only DrawingML effects. New snapshots also
    # carry the complete extension list, preserving untouched layers and extensions.
    includes_extensions = any(xml_local_name(el.tag) == "extLst" for el in elements)
    for child in list(blip):
        if includes_extensions or xml_local_name(child.tag) != "extLst":
            blip.remove(child)
    for index, element in enumerate(elements):
        blip.insert(index, element)


def _store(shape: Any, elements: Sequence[ET.Element]) -> None:
    key = _queue_key(shape)
    presentation = shape._slide._presentation
    presentation._picture_recolor_edits[key] = [
        ET.tostring(element, encoding="unicode") for element in elements
    ]
    for queue in (
        presentation._picture_transparency_edits,
        presentation._picture_correction_edits,
    ):
        queue.pop(key, None)
        queue.pop((f"/{key[0]}", key[1]), None)


class ImageTransformCollection(Sequence[ImageTransform]):
    """Live ordered DrawingML effects followed by Office 2010 corrections.

    Use ``add('brightnessContrast', bright=10000, contrast=20000)`` or
    ``add('sharpenSoften', amount=25000)`` for a14 corrections in raw OOXML
    integer units (-100000 to 100000). ``edit(index, ...)`` patches attributes;
    ``remove(index)`` removes one occurrence. Correction insertion indexes
    address the extension portion, DrawingML indexes the direct blip portion.
    Preserve image-layer relationships, wrapper metadata, unknown effects and
    extensions during every edit. New corrections use imgLayer/imgEffect.
    """

    def __init__(self, shape: Any):
        self._shape = shape
        _queue_key(shape)

    def _picture_elements(self) -> tuple[ET.Element, ET.Element, list[ET.Element]]:
        picture = _current_picture(self._shape)
        _, blip = _find_blip_in_picture(picture)
        if blip is None:
            raise AttributeError("picture blip is unavailable")
        elements = [child for child in blip if xml_local_name(child.tag) != "extLst"]
        elements.extend(effect for _, effect in _a14_effect_records(blip))
        return picture, blip, elements

    def _elements(self) -> list[ET.Element]:
        return self._picture_elements()[2]

    def __len__(self) -> int:
        return len(self._elements())

    def __getitem__(self, index: int | slice) -> ImageTransform | list[ImageTransform]:
        values = [
            ImageTransform(ET.tostring(element, encoding="unicode")) for element in self._elements()
        ]
        return values[index]

    def __iter__(self) -> Iterator[ImageTransform]:
        return iter(self[:])

    def add(self, name: str, *, index: int | None = None, **attributes: Any) -> ImageTransform:
        return self.add_xml(_make_effect(name, attributes), index=index)

    def add_xml(self, element: ET.Element, *, index: int | None = None) -> ImageTransform:
        _validate_effect(element)
        _, blip, elements = self._picture_elements()
        direct_count = sum(xml_local_name(child.tag) != "extLst" for child in blip)
        correction = element.tag.startswith(f"{{{A14_NS}}}")
        if index is None:
            index = len(elements) if correction else direct_count
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("transform index must be an integer")
        lower, upper = (direct_count, len(elements)) if correction else (0, direct_count)
        if not lower <= index <= upper:
            raise IndexError("transform insertion index outside its XML effect container")
        element = copy.deepcopy(element)
        if correction:
            before = elements[index] if index < len(elements) else None
            _insert_a14_correction(blip, element, before)
        else:
            blip.insert(index, element)
        _store(self._shape, list(blip))
        return ImageTransform(ET.tostring(element, encoding="unicode"))

    def remove(self, index: int) -> ImageTransform:
        _, blip, elements = self._picture_elements()
        removed = elements[index]
        if removed.tag.startswith(f"{{{A14_NS}}}"):
            _remove_a14_correction(blip, removed)
        else:
            blip.remove(removed)
        _store(self._shape, list(blip))
        return ImageTransform(ET.tostring(removed, encoding="unicode"))

    def edit(self, index: int, **attributes: Any) -> ImageTransform:
        _, blip, elements = self._picture_elements()
        element = elements[index]
        name = xml_local_name(element.tag)
        nested = any(key in attributes for key in ("colors", "children"))
        merged = dict(element.attrib)
        for attr, value in attributes.items():
            if value is None:
                merged.pop(attr, None)
            else:
                merged[attr] = value
        if nested:
            updated = _make_effect(name, merged)
        else:
            updated = _make_effect(name, {**merged, "children": list(element)})
        parent = next(parent for parent in blip.iter() if element in list(parent))
        position = list(parent).index(element)
        parent.remove(element)
        parent.insert(position, updated)
        _store(self._shape, list(blip))
        return ImageTransform(ET.tostring(updated, encoding="unicode"))

    def move(self, index: int, destination: int) -> None:
        """Move a DrawingML effect to its final index in the direct effect stack.

        Office extension corrections stay in their schema-defined extension
        portion; moving across that boundary is refused before queuing an edit.
        """
        _, blip, elements = self._picture_elements()
        effect = elements[index]
        direct = [child for child in blip if xml_local_name(child.tag) != "extLst"]
        if effect not in direct or not 0 <= destination < len(direct):
            raise ValueError("image transform move cannot cross the extension boundary")
        direct.remove(effect)
        direct.insert(destination, effect)
        for child in direct:
            blip.remove(child)
        for position, child in enumerate(direct):
            blip.insert(position, child)
        _store(self._shape, list(blip))

    def clear(self) -> None:
        """Clear admitted image effects while retaining unrelated extensions."""
        _, blip, elements = self._picture_elements()
        for effect in elements:
            if effect.tag.startswith(f"{{{A14_NS}}}"):
                _remove_a14_correction(blip, effect)
            else:
                blip.remove(effect)
        _store(self._shape, list(blip))


def get_picture_component(shape: Any, component: str) -> float:
    key = _queue_key(shape)
    if _queued(shape._slide._presentation._picture_recolor_edits, key) is None:
        from .shape_picture_correction_edits import (
            get_picture_brightness,
            get_picture_contrast,
        )
        from .shape_picture_transparency_edits import get_picture_transparency

        return {
            "brightness": get_picture_brightness,
            "contrast": get_picture_contrast,
            "transparency": get_picture_transparency,
        }[component](shape)
    picture = _current_picture(shape)
    return {
        "brightness": _get_picture_brightness_from_element,
        "contrast": _get_picture_contrast_from_element,
        "transparency": _get_picture_transparency_from_element,
    }[component](picture)


def set_picture_component(shape: Any, component: str, value: Any) -> None:
    if component == "transparency":
        value = validate_picture_transparency_value(value)
    else:
        value = validate_picture_correction_value(value, f"picture {component}")
    key = _queue_key(shape)
    if _queued(shape._slide._presentation._picture_recolor_edits, key) is None:
        from .shape_picture_correction_edits import (
            set_picture_brightness,
            set_picture_contrast,
        )
        from .shape_picture_transparency_edits import set_picture_transparency

        {
            "brightness": set_picture_brightness,
            "contrast": set_picture_contrast,
            "transparency": set_picture_transparency,
        }[component](shape, value)
        return
    picture = _current_picture(shape)
    if component == "transparency":
        _set_picture_transparency_on_element(picture, value)
    else:
        _set_picture_correction_on_element(picture, {component: value})
    _, blip = _find_blip_in_picture(picture)
    _store(shape, list(blip))


def apply_picture_recolor_edits(
    input_path: Path, output_path: Path, edits: Sequence[tuple[str, int, Sequence[str]]]
) -> None:
    """Rewrite only parts with explicitly touched pictures, preserving media."""
    grouped: dict[str, list[tuple[int, Sequence[str]]]] = {}
    for part, shape_id, transforms in edits:
        grouped.setdefault(str(part).lstrip("/"), []).append((shape_id, transforms))
    replacements = {}
    with zipfile.ZipFile(input_path) as package:
        for part, changes in grouped.items():
            root = ET.fromstring(package.read(part))
            for shape_id, transforms in changes:
                picture = _find_picture_element_by_id(root, shape_id)
                if picture is None:
                    raise ValueError(f"picture {shape_id!r} not found in {part}")
                _replace_transforms(picture, transforms)
            replacements[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    copy_package_with_replacements(input_path, output_path, replacements)
