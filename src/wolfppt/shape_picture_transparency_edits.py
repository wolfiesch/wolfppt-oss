"""Picture transparency authoring, inspection, and package applicator for PresentationML."""

from __future__ import annotations

import math
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .xml_helpers import xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# DrawingML image effects that alter alpha channels and cannot be safely
# represented or edited as a scalar uniform transparency.
ALPHA_CHANGING_UNSUPPORTED_EFFECTS: frozenset[str] = frozenset(
    {
        "alphaBiLevel",
        "alphaCeiling",
        "alphaFloor",
        "alphaInv",
        "alphaMod",
        "alphaRepl",
    }
)

# Unsupported effects that alter colors or apply raster filters, but do not alter
# alpha channels. These are preserved byte-for-byte by transparency authoring,
# maintaining the renderer's existing refusal behavior on render-native.
COLOR_AND_FILTER_UNSUPPORTED_EFFECTS: frozenset[str] = frozenset(
    {
        "duotone",
        "grayscl",
        "biLevel",
        "clrChange",
        "clrRepl",
        "blur",
        "fillOverlay",
    }
)

# Full set of image effects unsupported by the built-in renderer (matching render_scene._UNSUPPORTED_IMAGE_EFFECTS).
ALL_RENDERER_UNSUPPORTED_EFFECTS: frozenset[str] = (
    ALPHA_CHANGING_UNSUPPORTED_EFFECTS | COLOR_AND_FILTER_UNSUPPORTED_EFFECTS
)


def validate_picture_transparency_value(value: Any) -> float | None:
    """Validate that value is a finite float in [0.0, 1.0], or None to clear transparency.

    Rejects bool explicitly (since bool is a subclass of int in Python).
    Rejects non-numeric types with TypeError.
    Rejects non-finite values (inf, -inf, nan) with ValueError.
    Rejects out-of-range values (< 0.0 or > 1.0) with ValueError.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("picture transparency value cannot be a boolean")
    if not isinstance(value, (int, float)):
        raise TypeError(
            f"picture transparency value must be a float or None, got {type(value).__name__}"
        )
    val = float(value)
    if not math.isfinite(val):
        raise ValueError(f"picture transparency value must be finite, got {val}")
    if val < 0.0 or val > 1.0:
        raise ValueError(
            f"picture transparency value must be between 0.0 and 1.0, got {val}"
        )
    return val


def validate_picture_shape_target(
    shape: Any, feature_name: str = "picture transparency"
) -> None:
    """Validate that shape is a saved, active picture shape target.

    Refuses:
    - Non-picture shapes (auto shapes, tables, charts, connectors, movies) with TypeError.
    - Deleted shapes with ValueError.
    - Deleted slides with ValueError.
    - Unsaved / pending shapes with ValueError.
    - Stale shape targets with ValueError.
    """
    if shape is None:
        raise TypeError("shape cannot be None")

    payload = getattr(shape, "_payload", None)
    if not isinstance(payload, dict):
        raise TypeError("expected a Shape instance with internal payload")

    kind = payload.get("kind")
    has_pic = bool(getattr(shape, "has_picture", False)) or kind == "picture"
    if not has_pic or kind == "movie":
        raise TypeError(f"{feature_name} is only supported on picture shapes")

    if payload.get("_deleted"):
        raise ValueError(f"cannot edit or read {feature_name} of a deleted shape")

    if payload.get("_stale"):
        raise ValueError(f"cannot edit or read {feature_name} of a stale shape")

    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise ValueError("picture shape is not associated with any slide")

    if getattr(slide, "_deleted", False):
        raise ValueError(f"cannot edit or read {feature_name} on a deleted slide")

    prs = getattr(slide, "_presentation", None)
    if prs is not None:
        slides = getattr(prs, "_slides", None)
        if slides is not None and slide not in slides:
            raise ValueError(f"cannot edit or read {feature_name} on a deleted slide")
        slide_deletions = getattr(prs, "_slide_deletions", None)
        if slide_deletions and getattr(slide, "partname", None) in slide_deletions:
            raise ValueError(f"cannot edit or read {feature_name} on a deleted slide")
        shape_deletes = getattr(prs, "_shape_deletes", None)
        shape_index = getattr(shape, "_index", None)
        slide_index = getattr(slide, "_index", None)
        if (
            shape_deletes
            and slide_index is not None
            and shape_index is not None
            and (slide_index, shape_index) in shape_deletes
        ):
            raise ValueError(f"cannot edit or read {feature_name} of a deleted shape")
    if (
        payload.get("_pending_shape")
        or payload.get("_pending_creation")
        or not getattr(slide, "partname", None)
    ):
        raise ValueError(
            f"cannot edit or read {feature_name} of an unsaved pending picture shape"
        )

    shape_id = getattr(shape, "shape_id", None)
    if shape_id is None:
        raise ValueError("picture shape has no valid shape_id")

    shapes_col = getattr(slide, "_shapes", None)
    if shapes_col is not None and shape not in shapes_col:
        raise ValueError(
            f"stale shape target: shape {shape_id} is no longer present in slide shapes"
        )


def validate_picture_transparency_target(shape: Any) -> None:
    """Validate that shape is a saved, active picture shape target for transparency."""
    validate_picture_shape_target(shape, "picture transparency")


def _find_shape_element_by_id(
    root: ET.Element, shape_id: int | str
) -> ET.Element | None:
    """Find any top-level or grouped shape element by its cNvPr id."""
    str_id = str(shape_id)
    for elem in root.iter():
        tag = xml_local_name(elem.tag)
        if tag in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp", "contentPart"}:
            for child in elem:
                c_tag = xml_local_name(child.tag)
                if c_tag.startswith("nv") and c_tag.endswith("Pr"):
                    for nv_child in child:
                        if (
                            xml_local_name(nv_child.tag) == "cNvPr"
                            and nv_child.attrib.get("id") == str_id
                        ):
                            return elem


def _find_picture_element_by_id(
    root: ET.Element, shape_id: int | str
) -> ET.Element | None:
    """Find a picture (<p:pic>) element by its cNvPr id."""
    shape_elem = _find_shape_element_by_id(root, shape_id)
    if shape_elem is None:
        return None
    if xml_local_name(shape_elem.tag) != "pic":
        raise TypeError(
            f"shape with id {shape_id!r} is a '{xml_local_name(shape_elem.tag)}', not a picture ('pic')"
        )
    return shape_elem


def _find_blip_in_picture(
    picture_element: ET.Element,
) -> tuple[ET.Element | None, ET.Element | None]:
    """Return (blipFill, blip) element pair from a picture element."""
    blip_fill = None
    for child in picture_element:
        if xml_local_name(child.tag) == "blipFill":
            blip_fill = child
            break
    if blip_fill is None:
        return None, None
    blip = None
    for child in blip_fill:
        if xml_local_name(child.tag) == "blip":
            blip = child
            break
    return blip_fill, blip


def _assert_no_unsupported_alpha_effects(
    blip: ET.Element, shape_id: Any = None
) -> None:
    """Refuse blips with unsupported alpha-altering effects that cannot be safely represented."""
    for child in list(blip):
        effect = xml_local_name(child.tag)
        if effect in ALPHA_CHANGING_UNSUPPORTED_EFFECTS:
            target_str = f"picture {shape_id!r}" if shape_id is not None else "picture"
            raise ValueError(
                f"{target_str} applies unsupported alpha-changing effect {effect!r}, "
                "which cannot be safely represented or edited as uniform transparency"
            )


def _get_picture_transparency_from_element(picture_element: ET.Element) -> float:
    """Read uniform transparency 1 - product(alphaModFix amt / 100000) from picture element."""
    _blip_fill, blip = _find_blip_in_picture(picture_element)
    if blip is None:
        raise AttributeError("picture blip is unavailable")

    _assert_no_unsupported_alpha_effects(blip)

    product = 1.0
    has_alpha_mod = False
    for child in list(blip):
        if xml_local_name(child.tag) == "alphaModFix":
            has_alpha_mod = True
            raw = child.get("amt")
            if raw is None:
                factor = 1.0
            else:
                try:
                    amt = int(raw)
                except ValueError as exc:
                    raise ValueError(
                        f"alphaModFix amt attribute is non-numeric: {raw!r}"
                    ) from exc
                factor = amt / 100000.0
            product *= factor

    if not has_alpha_mod:
        return 0.0

    opacity = max(0.0, min(1.0, product))
    return 1.0 - opacity


def _set_picture_transparency_on_element(
    picture_element: ET.Element, value: float | None
) -> None:
    """Set uniform transparency on picture element.

    Canonicalizes all supported alphaModFix elements to a single modifier inserted
    immediately before a:extLst (or appended if no extLst). When value is None, all
    alphaModFix elements are removed. Unrelated effects (color, filters, etc.) and
    image attributes/crops are preserved.
    """
    blip_fill, blip = _find_blip_in_picture(picture_element)
    if blip_fill is None:
        raise AttributeError("picture blipFill is unavailable")
    if blip is None:
        raise AttributeError("picture blip is unavailable")

    _assert_no_unsupported_alpha_effects(blip)

    # Remove all existing alphaModFix elements
    for child in list(blip):
        if xml_local_name(child.tag) == "alphaModFix":
            blip.remove(child)

    if value is not None:
        opacity = 1.0 - float(value)
        amt = max(0, min(100000, round(opacity * 100000)))
        mod_fix = ET.Element(f"{{{A_NS}}}alphaModFix", {"amt": str(amt)})

        # Insert before extLst if present, else append to blip
        ext_lst_index = None
        for index, child in enumerate(list(blip)):
            if xml_local_name(child.tag) == "extLst":
                ext_lst_index = index
                break
        if ext_lst_index is not None:
            blip.insert(ext_lst_index, mod_fix)
        else:
            blip.append(mod_fix)


def get_picture_transparency(shape: Any) -> float:
    """Return the active or saved uniform picture transparency in [0.0, 1.0]."""
    validate_picture_transparency_target(shape)

    slide = shape._slide
    prs = slide._presentation
    slide_part = getattr(slide, "partname", "")
    shape_id = shape.shape_id

    # Check pending presentation edit queue first
    edits = getattr(prs, "_picture_transparency_edits", None)
    if edits is not None and isinstance(edits, dict):
        for candidate_part in (
            slide_part,
            str(slide_part).lstrip("/"),
            f"/{str(slide_part).lstrip('/')}",
        ):
            if (candidate_part, shape_id) in edits:
                queued = edits[(candidate_part, shape_id)]
                return 0.0 if queued is None else float(queued)

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
    return _get_picture_transparency_from_element(pic)


def set_picture_transparency(shape: Any, value: Any) -> None:
    """Validate and enqueue a uniform picture transparency edit on the shape."""
    val = validate_picture_transparency_value(value)
    validate_picture_transparency_target(shape)

    slide = shape._slide
    prs = slide._presentation
    slide_part = getattr(slide, "partname", "")
    shape_id = shape.shape_id

    # Verify existing blip in package does not carry unsupported alpha-altering effects
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
                    _assert_no_unsupported_alpha_effects(blip, shape_id)
        except (KeyError, zipfile.BadZipFile, ET.ParseError):
            pass

    if hasattr(prs, "_queue_picture_transparency"):
        prs._queue_picture_transparency(slide_part, shape_id, val)
    else:
        if not hasattr(prs, "_picture_transparency_edits"):
            prs._picture_transparency_edits = {}
        prs._picture_transparency_edits[(slide_part, shape_id)] = val


def apply_picture_transparency_edits(
    input_path: Path | str,
    output_path: Path | str,
    edits: (
        Mapping[tuple[str, int | str], float | None]
        | Sequence[tuple[str, int | str, float | None]]
        | Sequence[tuple[tuple[str, int | str], float | None]]
    ),
) -> None:
    """Apply picture transparency edits to PPTX package during save.

    Consumes triples of (slide_part, shape_id, value) or mapping from (slide_part, shape_id) to value.
    """
    in_path = Path(input_path)
    out_path = Path(output_path)

    if not edits:
        shutil.copyfile(in_path, out_path)
        return

    triples: list[tuple[str, int | str, float | None]] = []
    if isinstance(edits, Mapping):
        for (part, shape_id), val in edits.items():
            triples.append((part, shape_id, val))
    elif isinstance(edits, Sequence):
        for item in edits:
            if (
                len(item) == 2
                and isinstance(item[0], (list, tuple))
                and len(item[0]) == 2
            ):
                (part, shape_id), val = item
                triples.append((part, shape_id, val))
            elif len(item) == 3:
                part, shape_id, val = item
                triples.append((part, shape_id, val))
            else:
                raise ValueError(f"invalid picture transparency edit item: {item!r}")
    else:
        raise TypeError(
            f"edits must be a mapping or sequence of edit items, got {type(edits).__name__}"
        )

    edits_by_part: dict[str, list[tuple[int | str, float | None]]] = {}
    for part, shape_id, val in triples:
        norm_part = str(part).strip().lstrip("/")
        edits_by_part.setdefault(norm_part, []).append((shape_id, val))

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(in_path) as package:
        available_parts = set(package.namelist())
        for norm_part, part_edits in edits_by_part.items():
            if norm_part not in available_parts:
                continue
            xml_bytes = package.read(norm_part)
            root = ET.fromstring(xml_bytes)
            for shape_id, transparency_value in part_edits:
                val = validate_picture_transparency_value(transparency_value)
                pic = _find_picture_element_by_id(root, shape_id)
                if pic is None:
                    raise ValueError(
                        f"picture shape with id {shape_id!r} not found in slide part {norm_part!r}"
                    )
                _set_picture_transparency_on_element(pic, val)
            replacements[norm_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    copy_package_with_replacements(in_path, out_path, replacements)
