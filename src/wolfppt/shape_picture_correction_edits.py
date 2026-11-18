"""Picture brightness/contrast inspection and editing for DrawingML and Office 2010."""

from __future__ import annotations

import math
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .shape_picture_transparency_edits import (
    A_NS,
    _find_blip_in_picture,
    _find_picture_element_by_id,
    validate_picture_shape_target,
)
from .slide_payloads import load_slide_payloads
from .xml_helpers import xml_local_name

# Integer scale factor for a:lum ST_FixedPercentage attributes:
# 100,000ths integer units (-100000 to +100000 corresponds to -1.0 to +1.0).
LUM_SCALE = 100000
A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"
IMG_PROPS_URI = "{BEBA8EAE-BF5A-486C-A8C5-ECC9F3942E4B}"
A14_CORRECTION_ATTRS = {
    "brightnessContrast": {"bright", "contrast"},
    "sharpenSoften": {"amount"},
}


def _a14_layers(blip: ET.Element) -> list[ET.Element]:
    layers = []
    for ext_lst in blip:
        if xml_local_name(ext_lst.tag) != "extLst":
            continue
        for ext in ext_lst:
            for props in ext:
                if props.tag == f"{{{A14_NS}}}imgProps":
                    layers.extend(props.findall(f"{{{A14_NS}}}imgLayer"))
    return layers


def _a14_effect_records(blip: ET.Element) -> list[tuple[ET.Element, ET.Element]]:
    """Return wrapper/effect pairs in layer order; retain legacy imgEffects containers."""
    records = []
    for layer in _a14_layers(blip):
        for child in layer:
            wrappers = list(child) if child.tag == f"{{{A14_NS}}}imgEffects" else [child]
            for wrapper in wrappers:
                if wrapper.tag != f"{{{A14_NS}}}imgEffect":
                    continue
                for effect in wrapper:
                    if effect.tag in {f"{{{A14_NS}}}{name}" for name in A14_CORRECTION_ATTRS}:
                        records.append((wrapper, effect))
    return records


def _validate_a14_correction(effect: ET.Element) -> None:
    name = xml_local_name(effect.tag)
    if effect.tag != f"{{{A14_NS}}}{name}" or name not in A14_CORRECTION_ATTRS:
        raise ValueError(f"unsupported a14 picture correction {name!r}")
    if len(effect):
        raise ValueError(f"a14:{name} cannot contain child elements")
    for attr, raw in effect.attrib.items():
        if attr not in A14_CORRECTION_ATTRS[name]:
            raise ValueError(f"a14:{name} has unsupported attribute {attr!r}")
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"a14:{name}.{attr} must be an OOXML integer") from exc
        if not -LUM_SCALE <= value <= LUM_SCALE:
            raise ValueError(f"a14:{name}.{attr} must be between -100000 and 100000")


def _insert_a14_correction(
    blip: ET.Element, effect: ET.Element, before: ET.Element | None = None
) -> None:
    layers = _a14_layers(blip)
    if len(layers) > 1:
        raise ValueError("ambiguous a14 correction insertion: multiple image layers")
    if layers:
        layer = layers[0]
    else:
        namespace = blip.tag.rsplit("}", 1)[0] + "}"
        ext_lst = next((child for child in blip if xml_local_name(child.tag) == "extLst"), None)
        if ext_lst is None:
            ext_lst = ET.SubElement(blip, namespace + "extLst")
        ext = ET.SubElement(ext_lst, namespace + "ext", {"uri": IMG_PROPS_URI})
        props = ET.SubElement(ext, f"{{{A14_NS}}}imgProps")
        embed = {key: value for key, value in blip.attrib.items() if key.endswith("}embed")}
        layer = ET.SubElement(props, f"{{{A14_NS}}}imgLayer", embed)
    container = layer
    if len(layer) and layer[-1].tag == f"{{{A14_NS}}}imgEffects":
        container = layer[-1]
    insertion = len(container)
    if before is not None:
        wrapper = next(w for w, child in _a14_effect_records(blip) if child is before)
        container = next(parent for parent in layer.iter() if wrapper in list(parent))
        insertion = list(container).index(wrapper)
    wrapper = ET.Element(f"{{{A14_NS}}}imgEffect")
    wrapper.append(effect)
    container.insert(insertion, wrapper)


def _remove_a14_correction(blip: ET.Element, effect: ET.Element) -> None:
    wrapper = next(w for w, child in _a14_effect_records(blip) if child is effect)
    wrapper.remove(effect)
    if not len(wrapper):
        parent = next(parent for parent in blip.iter() if wrapper in list(parent))
        parent.remove(wrapper)


def _luminance_element(blip: ET.Element) -> ET.Element | None:
    _assert_valid_luminance_effects(blip)
    elements = _find_lum_elements_in_blip(blip)
    corrections = [
        effect
        for _, effect in _a14_effect_records(blip)
        if xml_local_name(effect.tag) == "brightnessContrast"
    ]
    if len(corrections) > 1 or (corrections and elements):
        raise ValueError("ambiguous picture brightness/contrast: multiple luminance corrections")
    if corrections:
        _validate_a14_correction(corrections[0])
        return corrections[0]
    return elements[0] if elements else None


def validate_picture_correction_value(
    value: Any, component_name: str = "picture correction"
) -> float | None:
    """Validate a finite float in [-1.0, 1.0], or None to remove the attribute.

    Rejects bool explicitly (since bool is a subclass of int in Python).
    Rejects non-numeric types with TypeError.
    Rejects non-finite values (inf, -inf, nan) with ValueError.
    Rejects out-of-range values (< -1.0 or > 1.0) with ValueError.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{component_name} value cannot be a boolean")
    if not isinstance(value, (int, float)):
        raise TypeError(
            f"{component_name} value must be a float or None, got {type(value).__name__}"
        )
    val = float(value)
    if not math.isfinite(val):
        raise ValueError(f"{component_name} value must be finite, got {val}")
    if val < -1.0 or val > 1.0:
        raise ValueError(f"{component_name} value must be between -1.0 and 1.0, got {val}")
    return val


def validate_picture_correction_target(
    shape: Any, feature_name: str = "picture correction"
) -> None:
    """Validate that shape is a saved, active picture shape target."""
    validate_picture_shape_target(shape, feature_name)


def _find_lum_elements_in_blip(blip: ET.Element) -> list[ET.Element]:
    """Return all a:lum elements directly child of a:blip."""
    return [child for child in blip if xml_local_name(child.tag) == "lum"]


def _assert_valid_luminance_effects(blip: ET.Element, shape_id: Any = None) -> None:
    """Refuse blips with multiple or malformed luminance effects."""
    lum_elements = _find_lum_elements_in_blip(blip)
    if len(lum_elements) > 1:
        target_str = f"picture {shape_id!r}" if shape_id is not None else "picture"
        raise ValueError(
            f"{target_str} applies multiple luminance (a:lum) effects, "
            "which is ambiguous and unsupported"
        )
    if lum_elements:
        lum = lum_elements[0]
        bright_raw = lum.get("bright")
        if bright_raw is not None:
            try:
                int(bright_raw)
            except ValueError as exc:
                raise ValueError(f"a:lum bright attribute is non-numeric: {bright_raw!r}") from exc
        contrast_raw = lum.get("contrast")
        if contrast_raw is not None:
            try:
                int(contrast_raw)
            except ValueError as exc:
                raise ValueError(
                    f"a:lum contrast attribute is non-numeric: {contrast_raw!r}"
                ) from exc


def _get_picture_brightness_from_element(picture_element: ET.Element) -> float:
    """Read a:lum or a14:brightnessContrast brightness; absent attributes return 0.0."""
    _blip_fill, blip = _find_blip_in_picture(picture_element)
    if blip is None:
        raise AttributeError("picture blip is unavailable")
    lum = _luminance_element(blip)
    if lum is None:
        return 0.0
    raw = lum.get("bright")
    if raw is None:
        return 0.0
    try:
        amt = int(raw)
    except ValueError as exc:
        raise ValueError(f"a:lum bright attribute is non-numeric: {raw!r}") from exc
    return max(-1.0, min(1.0, amt / float(LUM_SCALE)))


def _get_picture_contrast_from_element(picture_element: ET.Element) -> float:
    """Read a:lum or a14:brightnessContrast contrast; absent attributes return 0.0."""
    _blip_fill, blip = _find_blip_in_picture(picture_element)
    if blip is None:
        raise AttributeError("picture blip is unavailable")
    lum = _luminance_element(blip)
    if lum is None:
        return 0.0
    raw = lum.get("contrast")
    if raw is None:
        return 0.0
    try:
        amt = int(raw)
    except ValueError as exc:
        raise ValueError(f"a:lum contrast attribute is non-numeric: {raw!r}") from exc
    return max(-1.0, min(1.0, amt / float(LUM_SCALE)))


def _set_picture_correction_on_element(
    picture_element: ET.Element,
    patch: Mapping[str, float | None],
) -> None:
    """Apply brightness/contrast patch to picture element.

    Omitted components in patch are left untouched.
    A component value of None removes that specific attribute.
    Remove the correction element when both attributes are removed. Edit existing
    a14:brightnessContrast in place; otherwise author a:lum.
    Preserves other effects (e.g. alphaModFix), crops, relationships, and blip attributes.
    """
    blip_fill, blip = _find_blip_in_picture(picture_element)
    if blip_fill is None:
        raise AttributeError("picture blipFill is unavailable")
    if blip is None:
        raise AttributeError("picture blip is unavailable")

    lum_elem = _luminance_element(blip)

    # Current raw attribute values
    current_bright_str = lum_elem.get("bright") if lum_elem is not None else None
    current_contrast_str = lum_elem.get("contrast") if lum_elem is not None else None

    # Compute target bright attribute
    if "brightness" in patch:
        b_val = patch["brightness"]
        if b_val is None:
            target_bright_str = None
        else:
            val = validate_picture_correction_value(b_val, "picture brightness")
            target_bright_str = str(max(-LUM_SCALE, min(LUM_SCALE, round(val * LUM_SCALE))))
    else:
        target_bright_str = current_bright_str

    # Compute target contrast attribute
    if "contrast" in patch:
        c_val = patch["contrast"]
        if c_val is None:
            target_contrast_str = None
        else:
            val = validate_picture_correction_value(c_val, "picture contrast")
            target_contrast_str = str(max(-LUM_SCALE, min(LUM_SCALE, round(val * LUM_SCALE))))
    else:
        target_contrast_str = current_contrast_str

    # If both attributes are None, remove a:lum if present
    if target_bright_str is None and target_contrast_str is None:
        if lum_elem is not None:
            if lum_elem.tag == f"{{{A14_NS}}}brightnessContrast":
                _remove_a14_correction(blip, lum_elem)
            else:
                blip.remove(lum_elem)
        return

    # Otherwise ensure a:lum exists
    if lum_elem is None:
        lum_elem = ET.Element(f"{{{A_NS}}}lum")
        # Insert before extLst if present, else append to blip
        ext_lst_index = None
        for index, child in enumerate(list(blip)):
            if xml_local_name(child.tag) == "extLst":
                ext_lst_index = index
                break
        if ext_lst_index is not None:
            blip.insert(ext_lst_index, lum_elem)
        else:
            blip.append(lum_elem)

    # Update bright attribute
    if target_bright_str is not None:
        lum_elem.set("bright", target_bright_str)
    else:
        lum_elem.attrib.pop("bright", None)

    # Update contrast attribute
    if target_contrast_str is not None:
        lum_elem.set("contrast", target_contrast_str)
    else:
        lum_elem.attrib.pop("contrast", None)

    # If no attributes remain, remove lum_elem
    if not lum_elem.attrib and lum_elem in blip:
        blip.remove(lum_elem)


def get_picture_brightness(shape: Any) -> float:
    """Return active or saved picture brightness in [-1.0, 1.0]. Defaults to 0.0."""
    validate_picture_shape_target(shape, "picture brightness")

    slide = shape._slide
    prs = slide._presentation
    slide_part = getattr(slide, "partname", "")
    shape_id = shape.shape_id

    # Check pending presentation edit queue first
    edits = getattr(prs, "_picture_correction_edits", None)
    if edits is not None and isinstance(edits, dict):
        for candidate_part in (
            slide_part,
            str(slide_part).lstrip("/"),
            f"/{str(slide_part).lstrip('/')}",
        ):
            if (candidate_part, shape_id) in edits:
                patch = edits[(candidate_part, shape_id)]
                if isinstance(patch, Mapping) and "brightness" in patch:
                    queued = patch["brightness"]
                    return 0.0 if queued is None else float(queued)
                # If brightness is omitted in this patch, fall through to underlying package
                break

    # Read from underlying presentation package
    pkg_path = getattr(prs, "path", None)
    if pkg_path is None or not Path(pkg_path).exists():
        raise ValueError("presentation package path is unavailable")

    norm_part = str(slide_part).lstrip("/")
    with zipfile.ZipFile(pkg_path) as package:
        raw_xml = package.read(norm_part)
    root = ET.fromstring(raw_xml)
    pic = _find_picture_element_by_id(root, shape_id)
    if pic is None:
        raise ValueError(f"picture shape with id {shape_id!r} not found in {norm_part}")
    return _get_picture_brightness_from_element(pic)


def get_picture_contrast(shape: Any) -> float:
    """Return active or saved picture contrast in [-1.0, 1.0]. Defaults to 0.0."""
    validate_picture_shape_target(shape, "picture contrast")

    slide = shape._slide
    prs = slide._presentation
    slide_part = getattr(slide, "partname", "")
    shape_id = shape.shape_id

    # Check pending presentation edit queue first
    edits = getattr(prs, "_picture_correction_edits", None)
    if edits is not None and isinstance(edits, dict):
        for candidate_part in (
            slide_part,
            str(slide_part).lstrip("/"),
            f"/{str(slide_part).lstrip('/')}",
        ):
            if (candidate_part, shape_id) in edits:
                patch = edits[(candidate_part, shape_id)]
                if isinstance(patch, Mapping) and "contrast" in patch:
                    queued = patch["contrast"]
                    return 0.0 if queued is None else float(queued)
                # If contrast is omitted in this patch, fall through to underlying package
                break

    # Read from underlying presentation package
    pkg_path = getattr(prs, "path", None)
    if pkg_path is None or not Path(pkg_path).exists():
        raise ValueError("presentation package path is unavailable")

    norm_part = str(slide_part).lstrip("/")
    with zipfile.ZipFile(pkg_path) as package:
        raw_xml = package.read(norm_part)
    root = ET.fromstring(raw_xml)
    pic = _find_picture_element_by_id(root, shape_id)
    if pic is None:
        raise ValueError(f"picture shape with id {shape_id!r} not found in {norm_part}")
    return _get_picture_contrast_from_element(pic)


def set_picture_brightness(shape: Any, value: Any) -> None:
    """Validate and enqueue a picture brightness edit on the shape."""
    val = validate_picture_correction_value(value, "picture brightness")
    validate_picture_shape_target(shape, "picture brightness")

    slide = shape._slide
    prs = slide._presentation
    slide_part = getattr(slide, "partname", "")
    shape_id = shape.shape_id

    # Verify existing blip in package does not carry multiple/malformed luminance effects
    pkg_path = getattr(prs, "path", None)
    if pkg_path and Path(pkg_path).exists() and slide_part:
        norm_part = str(slide_part).lstrip("/")
        try:
            with zipfile.ZipFile(pkg_path) as package:
                raw_xml = package.read(norm_part)
            root = ET.fromstring(raw_xml)
            pic = _find_picture_element_by_id(root, shape_id)
            if pic is not None:
                _, blip = _find_blip_in_picture(pic)
                if blip is not None:
                    _luminance_element(blip)
        except (KeyError, zipfile.BadZipFile, ET.ParseError):
            pass

    # Call canonical queue method directly (fails visibly if missing)
    prs._queue_picture_correction(slide_part, shape_id, "brightness", val)


def set_picture_contrast(shape: Any, value: Any) -> None:
    """Validate and enqueue a picture contrast edit on the shape."""
    val = validate_picture_correction_value(value, "picture contrast")
    validate_picture_shape_target(shape, "picture contrast")

    slide = shape._slide
    prs = slide._presentation
    slide_part = getattr(slide, "partname", "")
    shape_id = shape.shape_id

    # Verify existing blip in package does not carry multiple/malformed luminance effects
    pkg_path = getattr(prs, "path", None)
    if pkg_path and Path(pkg_path).exists() and slide_part:
        norm_part = str(slide_part).lstrip("/")
        try:
            with zipfile.ZipFile(pkg_path) as package:
                raw_xml = package.read(norm_part)
            root = ET.fromstring(raw_xml)
            pic = _find_picture_element_by_id(root, shape_id)
            if pic is not None:
                _, blip = _find_blip_in_picture(pic)
                if blip is not None:
                    _luminance_element(blip)
        except (KeyError, zipfile.BadZipFile, ET.ParseError):
            pass

    # Call canonical queue method directly (fails visibly if missing)
    prs._queue_picture_correction(slide_part, shape_id, "contrast", val)


def apply_picture_correction_edits(
    input_path: Path | str,
    output_path: Path | str,
    edits: (
        Mapping[tuple[str | int, int | str], Mapping[str, float | None]]
        | Sequence[tuple[str | int, int | str, Mapping[str, float | None]]]
        | Sequence[tuple[tuple[str | int, int | str], Mapping[str, float | None]]]
    ),
) -> None:
    """Apply picture correction (brightness and contrast) edits to PPTX package during save.

    Consume triples of (slide_part, shape_id, patch) or a mapping keyed by (slide_part, shape_id).
    """
    in_path = Path(input_path)
    out_path = Path(output_path)

    if not edits:
        shutil.copyfile(in_path, out_path)
        return

    triples: list[tuple[str | int, int | str, Mapping[str, float | None]]] = []
    if isinstance(edits, Mapping):
        for (part, shape_id), patch in edits.items():
            triples.append((part, shape_id, patch))
    elif isinstance(edits, Sequence):
        for item in edits:
            if len(item) == 2 and isinstance(item[0], (list, tuple)) and len(item[0]) == 2:
                (part, shape_id), patch = item
                triples.append((part, shape_id, patch))
            elif len(item) == 3:
                part, shape_id, patch = item
                triples.append((part, shape_id, patch))
            else:
                raise ValueError(f"invalid picture correction edit item: {item!r}")
    else:
        raise TypeError(
            f"edits must be a mapping or sequence of edit items, got {type(edits).__name__}"
        )

    slide_payloads: list[dict[str, Any]] | None = None
    edits_by_part: dict[str, list[tuple[int | str, Mapping[str, float | None]]]] = {}
    for part, shape_id, patch in triples:
        if isinstance(part, int):
            if slide_payloads is None:
                slide_payloads = load_slide_payloads(in_path)
            try:
                part = str(slide_payloads[part]["part"])
            except IndexError as exc:
                raise IndexError(f"slide index out of range: {part}") from exc
        norm_part = str(part).strip().lstrip("/")
        edits_by_part.setdefault(norm_part, []).append((shape_id, patch))

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(in_path) as package:
        available_parts = set(package.namelist())
        for norm_part, part_edits in edits_by_part.items():
            if norm_part not in available_parts:
                continue
            xml_bytes = package.read(norm_part)
            root = ET.fromstring(xml_bytes)
            for shape_id, patch in part_edits:
                if not isinstance(patch, Mapping):
                    raise TypeError(
                        f"picture correction patch must be a mapping, got {type(patch).__name__}"
                    )
                pic = _find_picture_element_by_id(root, shape_id)
                if pic is None:
                    raise ValueError(
                        f"picture shape with id {shape_id!r} not found in slide part {norm_part!r}"
                    )
                _set_picture_correction_on_element(pic, patch)
            replacements[norm_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    copy_package_with_replacements(in_path, out_path, replacements)
