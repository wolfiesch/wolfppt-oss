"""Line end (headEnd/tailEnd), cap, and join edit support for shapes."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .shape_edit_refs import ShapeEditRef, shape_edit_ref
from .shape_xml import _get_or_add_shape_line_element, _shape_xml_element
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Canonical DrawingML schema enums
VALID_LINE_CAPS: frozenset[str] = frozenset({"rnd", "sq", "flat"})
VALID_LINE_JOINS: frozenset[str] = frozenset({"round", "bevel", "miter"})
VALID_LINE_END_TYPES: frozenset[str] = frozenset(
    {"none", "triangle", "stealth", "diamond", "oval", "arrow"}
)
VALID_LINE_END_WIDTHS: frozenset[str] = frozenset({"sm", "med", "lg"})
VALID_LINE_END_LENGTHS: frozenset[str] = frozenset({"sm", "med", "lg"})

# Schema child element ordering for DrawingML <a:ln> (CT_LineProperties):
# 0: line fill (noFill, solidFill, gradFill, pattFill)
# 1: dash (prstDash, custDash)
# 2: join (round, bevel, miter)
# 3: headEnd
# 4: tailEnd
# 5: extLst
_LINE_CHILD_ORDER: dict[str, int] = {
    f"{{{A_NS}}}noFill": 0,
    f"{{{A_NS}}}solidFill": 0,
    f"{{{A_NS}}}gradFill": 0,
    f"{{{A_NS}}}pattFill": 0,
    f"{{{A_NS}}}prstDash": 1,
    f"{{{A_NS}}}custDash": 1,
    f"{{{A_NS}}}round": 2,
    f"{{{A_NS}}}bevel": 2,
    f"{{{A_NS}}}miter": 2,
    f"{{{A_NS}}}headEnd": 3,
    f"{{{A_NS}}}tailEnd": 4,
    f"{{{A_NS}}}extLst": 5,
}


# --------------------------------------------------------------------------- #
# Validation                                                                  #
# --------------------------------------------------------------------------- #


def validate_line_cap(cap: Any) -> str | None:
    """Validate line cap against canonical DrawingML ST_LineCap enum or None."""
    if cap is None:
        return None
    if not isinstance(cap, str) or cap not in VALID_LINE_CAPS:
        raise ValueError(
            f"invalid line cap {cap!r}; expected one of {sorted(VALID_LINE_CAPS)} or None"
        )
    return cap


def validate_line_join(join: Any) -> str | None:
    """Validate line join choice against canonical DrawingML options or None."""
    if join is None:
        return None
    if not isinstance(join, str) or join not in VALID_LINE_JOINS:
        raise ValueError(
            f"invalid line join {join!r}; expected one of {sorted(VALID_LINE_JOINS)} or None"
        )
    return join


def validate_miter_limit(limit: Any) -> int | None:
    """Validate miter limit as a non-negative ST_PositivePercentage or None."""
    if limit is None:
        return None
    if isinstance(limit, bool):
        raise TypeError("miter limit must be numeric")
    if isinstance(limit, int):
        if limit < 0:
            raise ValueError(f"miter limit must be non-negative, got {limit}")
        return limit
    if isinstance(limit, float):
        if limit < 0:
            raise ValueError(f"miter limit must be non-negative, got {limit}")
        return round(limit * 100000) if limit <= 100 else round(limit)
    if isinstance(limit, str):
        s = limit.strip()
        if s.endswith("%"):
            try:
                val = float(s[:-1])
            except ValueError as exc:
                raise ValueError(f"invalid miter limit percentage: {limit!r}") from exc
            if val < 0:
                raise ValueError(f"miter limit must be non-negative, got {limit}")
            return round(val * 1000)
        try:
            val_int = int(s)
        except ValueError as exc:
            raise ValueError(f"invalid miter limit: {limit!r}") from exc
        if val_int < 0:
            raise ValueError(f"miter limit must be non-negative, got {limit}")
        return val_int
    raise TypeError(
        f"miter limit must be numeric or percentage string, got {type(limit).__name__}"
    )


def validate_line_end_type(end_type: Any) -> str | None:
    """Validate line end type against canonical DrawingML ST_LineEndType enum."""
    if end_type is None:
        return None
    if not isinstance(end_type, str) or end_type not in VALID_LINE_END_TYPES:
        raise ValueError(
            f"invalid line end type {end_type!r}; expected one of {sorted(VALID_LINE_END_TYPES)} or None"
        )
    return end_type


def validate_line_end_width(width: Any) -> str | None:
    """Validate line end width against canonical DrawingML ST_LineEndWidth enum."""
    if width is None:
        return None
    if not isinstance(width, str) or width not in VALID_LINE_END_WIDTHS:
        raise ValueError(
            f"invalid line end width {width!r}; expected one of {sorted(VALID_LINE_END_WIDTHS)} or None"
        )
    return width


def validate_line_end_length(length: Any) -> str | None:
    """Validate line end length against canonical DrawingML ST_LineEndLength enum."""
    if length is None:
        return None
    if not isinstance(length, str) or length not in VALID_LINE_END_LENGTHS:
        raise ValueError(
            f"invalid line end length {length!r}; expected one of {sorted(VALID_LINE_END_LENGTHS)} or None"
        )
    return length


def validate_line_end_spec(spec: Any) -> dict[str, str | None] | None:
    """Validate a dictionary specification for headEnd or tailEnd."""
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise TypeError(
            f"line end spec must be a dict or None, got {type(spec).__name__}"
        )

    valid_keys = {"type", "w", "width", "len", "length"}
    unknown_keys = set(spec.keys()) - valid_keys
    if unknown_keys:
        raise ValueError(f"unknown line end property keys: {sorted(unknown_keys)}")

    end_type = validate_line_end_type(spec.get("type"))
    w_val = spec.get("w") if "w" in spec else spec.get("width")
    width = validate_line_end_width(w_val)
    len_val = spec.get("len") if "len" in spec else spec.get("length")
    length = validate_line_end_length(len_val)

    return {
        "type": end_type,
        "width": width,
        "length": length,
    }


def validate_shape_line_end_edits(edits: dict[str, Any]) -> dict[str, Any]:
    """Validate property-bag dictionary for shape line end/cap/join edits."""
    if not isinstance(edits, dict):
        raise TypeError(f"expected edits dict, got {type(edits).__name__}")
    validated: dict[str, Any] = {}
    if "cap" in edits:
        validated["cap"] = validate_line_cap(edits["cap"])
    if "join" in edits:
        validated["join"] = validate_line_join(edits["join"])
    if "miter_limit" in edits:
        validated["miter_limit"] = validate_miter_limit(edits["miter_limit"])
    if "head_end" in edits:
        validated["head_end"] = validate_line_end_spec(edits["head_end"])
    if "tail_end" in edits:
        validated["tail_end"] = validate_line_end_spec(edits["tail_end"])
    if "head_end_type" in edits:
        validated.setdefault("head_end", {})["type"] = validate_line_end_type(
            edits["head_end_type"]
        )
    if "head_end_width" in edits:
        validated.setdefault("head_end", {})["width"] = validate_line_end_width(
            edits["head_end_width"]
        )
    if "head_end_length" in edits:
        validated.setdefault("head_end", {})["length"] = validate_line_end_length(
            edits["head_end_length"]
        )
    if "tail_end_type" in edits:
        validated.setdefault("tail_end", {})["type"] = validate_line_end_type(
            edits["tail_end_type"]
        )
    if "tail_end_width" in edits:
        validated.setdefault("tail_end", {})["width"] = validate_line_end_width(
            edits["tail_end_width"]
        )
    if "tail_end_length" in edits:
        validated.setdefault("tail_end", {})["length"] = validate_line_end_length(
            edits["tail_end_length"]
        )
    return validated


# --------------------------------------------------------------------------- #
# Shape state assertions                                                      #
# --------------------------------------------------------------------------- #


def _assert_shape_editable(shape: Any) -> None:
    """Refuse deleted shapes or slides before reading or authoring line ends."""
    payload = getattr(shape, "_payload", {})
    if bool(payload.get("_deleted")):
        raise ValueError("cannot edit or read line properties of a deleted shape")
    slide = getattr(shape, "_slide", None)
    if slide is not None and getattr(slide, "_deleted", False):
        raise ValueError("cannot edit or read line properties on a deleted slide")


def _is_pending_shape(shape: Any) -> bool:
    """Return True when the shape is authored but not yet written to the package."""
    payload = getattr(shape, "_payload", {})
    return bool(payload.get("_pending_shape") or payload.get("_pending_group_child"))


def _supports_shape_line_style(shape: Any) -> bool:
    payload = getattr(shape, "_payload", {})
    return payload.get("kind") in {"shape", "connector"}


def _shape_payload(
    slide_payload: dict[str, Any],
    shape_ref: ShapeEditRef,
) -> dict[str, Any]:
    """Resolve shape payload for top-level or group child shape refs."""
    if isinstance(shape_ref, tuple):
        try:
            child_payload = slide_payload["shapes"][shape_ref[0]]
            for child_index in shape_ref[1:]:
                child_payload = child_payload["children"][child_index]
        except IndexError as exc:
            raise IndexError("group child shape index out of range") from exc
        except KeyError as exc:
            raise AttributeError("group child shape payload is unavailable") from exc
        return child_payload
    try:
        return slide_payload["shapes"][shape_ref]
    except IndexError as exc:
        raise IndexError("shape index out of range") from exc


# --------------------------------------------------------------------------- #
# XML authoring helpers                                                       #
# --------------------------------------------------------------------------- #


def _insert_line_child(line: ET.Element, child: ET.Element, order_bucket: int) -> None:
    """Insert a child into <a:ln> maintaining DrawingML schema element order."""
    insert_at = len(line)
    for index, existing in enumerate(list(line)):
        existing_bucket = _LINE_CHILD_ORDER.get(existing.tag, 99)
        if existing_bucket > order_bucket:
            insert_at = index
            break
    line.insert(insert_at, child)


def set_shape_line_cap(shape_properties: ET.Element, cap: str | None) -> None:
    """Set line cap attribute on <a:ln>.

    Correct DrawingML: 'cap' is strictly an attribute on <a:ln>, not an element.
    Removes any stray <a:cap> child elements to guarantee schema compliance.
    """
    cap = validate_line_cap(cap)
    line = _get_or_add_shape_line_element(shape_properties)
    for child in list(line):
        if _xml_local_name(child.tag) == "cap":
            line.remove(child)
    if cap is None:
        line.attrib.pop("cap", None)
    else:
        line.set("cap", cap)


def set_shape_line_join(
    shape_properties: ET.Element,
    join: str | None,
    miter_limit: float | str | None = None,
) -> None:
    """Set line join choice on <a:ln>.

    Enforces mutually exclusive choice between <a:round/>, <a:bevel/>, and
    <a:miter lim="..."/>. Existing join elements are removed before adding the
    new choice to avoid duplicate join children.
    """
    join = validate_line_join(join)
    limit = validate_miter_limit(miter_limit)
    line = _get_or_add_shape_line_element(shape_properties)

    # Remove any existing mutually exclusive join elements
    for child in list(line):
        if _xml_local_name(child.tag) in {"round", "bevel", "miter"}:
            line.remove(child)

    if join is None:
        return

    if join == "round":
        elem = ET.Element(f"{{{A_NS}}}round")
    elif join == "bevel":
        elem = ET.Element(f"{{{A_NS}}}bevel")
    elif join == "miter":
        elem = ET.Element(f"{{{A_NS}}}miter")
        if limit is not None:
            elem.set("lim", str(limit))
    else:
        raise ValueError(f"unsupported line join: {join!r}")

    _insert_line_child(line, elem, order_bucket=2)


def set_shape_line_head_end(
    shape_properties: ET.Element,
    end_type: str | None = None,
    width: str | None = None,
    length: str | None = None,
) -> None:
    """Set or clear <a:headEnd> properties on <a:ln>."""
    end_type = validate_line_end_type(end_type)
    width = validate_line_end_width(width)
    length = validate_line_end_length(length)

    line = _get_or_add_shape_line_element(shape_properties)
    for child in list(line):
        if _xml_local_name(child.tag) == "headEnd":
            line.remove(child)

    if end_type is None and width is None and length is None:
        return

    elem = ET.Element(f"{{{A_NS}}}headEnd")
    if end_type is not None:
        elem.set("type", end_type)
    if width is not None:
        elem.set("w", width)
    if length is not None:
        elem.set("len", length)
    _insert_line_child(line, elem, order_bucket=3)


def set_shape_line_tail_end(
    shape_properties: ET.Element,
    end_type: str | None = None,
    width: str | None = None,
    length: str | None = None,
) -> None:
    """Set or clear <a:tailEnd> properties on <a:ln>."""
    end_type = validate_line_end_type(end_type)
    width = validate_line_end_width(width)
    length = validate_line_end_length(length)

    line = _get_or_add_shape_line_element(shape_properties)
    for child in list(line):
        if _xml_local_name(child.tag) == "tailEnd":
            line.remove(child)

    if end_type is None and width is None and length is None:
        return

    elem = ET.Element(f"{{{A_NS}}}tailEnd")
    if end_type is not None:
        elem.set("type", end_type)
    if width is not None:
        elem.set("w", width)
    if length is not None:
        elem.set("len", length)
    _insert_line_child(line, elem, order_bucket=4)


def set_shape_line_end_properties(
    shape_properties: ET.Element,
    edits: dict[str, Any],
) -> None:
    """Apply a property-bag dictionary of line end/cap/join edits to shape_properties."""
    if "cap" in edits:
        set_shape_line_cap(shape_properties, edits["cap"])

    if "join" in edits or "miter_limit" in edits:
        join = edits.get("join")
        limit = edits.get("miter_limit")
        if join is not None or limit is not None:
            effective_join = join if join is not None else "miter"
            set_shape_line_join(shape_properties, effective_join, limit)
        elif "join" in edits and join is None:
            set_shape_line_join(shape_properties, None)

    if "head_end" in edits:
        head_spec = edits["head_end"]
        if head_spec is None:
            set_shape_line_head_end(shape_properties, None, None, None)
        else:
            set_shape_line_head_end(
                shape_properties,
                end_type=head_spec.get("type"),
                width=head_spec.get("width") or head_spec.get("w"),
                length=head_spec.get("length") or head_spec.get("len"),
            )
    elif any(
        k in edits for k in ("head_end_type", "head_end_width", "head_end_length")
    ):
        set_shape_line_head_end(
            shape_properties,
            end_type=edits.get("head_end_type"),
            width=edits.get("head_end_width"),
            length=edits.get("head_end_length"),
        )

    if "tail_end" in edits:
        tail_spec = edits["tail_end"]
        if tail_spec is None:
            set_shape_line_tail_end(shape_properties, None, None, None)
        else:
            set_shape_line_tail_end(
                shape_properties,
                end_type=tail_spec.get("type"),
                width=tail_spec.get("width") or tail_spec.get("w"),
                length=tail_spec.get("length") or tail_spec.get("len"),
            )
    elif any(
        k in edits for k in ("tail_end_type", "tail_end_width", "tail_end_length")
    ):
        set_shape_line_tail_end(
            shape_properties,
            end_type=edits.get("tail_end_type"),
            width=edits.get("tail_end_width"),
            length=edits.get("tail_end_length"),
        )


# --------------------------------------------------------------------------- #
# Inspection / Readback                                                       #
# --------------------------------------------------------------------------- #


def _get_active_queue_edit(shape: Any) -> dict[str, Any] | None:
    """Retrieve queued edits for shape from presentation._shape_line_end_edits if any."""
    prs = getattr(getattr(shape, "_slide", None), "_presentation", None)
    if prs is None:
        return None
    queue = getattr(prs, "_shape_line_end_edits", None)
    if not isinstance(queue, dict):
        return None
    key = (shape._slide._index, shape_edit_ref(shape))
    return queue.get(key)


def _inspect_line_element(shape: Any) -> ET.Element | None:
    """Inspect underlying XML <a:ln> element from package for saved shape.

    Pending shapes have no package XML yet; their authored line end state lives
    only in the payload and the active edit queue, so there is nothing to read.
    """
    _assert_shape_editable(shape)
    if not _supports_shape_line_style(shape) or _is_pending_shape(shape):
        return None
    prs = shape._slide._presentation
    with zipfile.ZipFile(prs.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    return shape_properties.find(f"{{{A_NS}}}ln")


def get_shape_line_cap(shape: Any) -> str | None:
    """Get active line cap for shape (queued or saved in XML)."""
    _assert_shape_editable(shape)
    if not _supports_shape_line_style(shape):
        return None
    queue_edit = _get_active_queue_edit(shape)
    if queue_edit is not None and "cap" in queue_edit:
        return queue_edit["cap"]
    payload_val = shape._payload.get("line_cap")
    if payload_val is not None:
        return payload_val
    line = _inspect_line_element(shape)
    if line is None:
        return None
    return line.attrib.get("cap")


def get_shape_line_join(shape: Any) -> str | None:
    """Get active line join choice for shape (queued or saved in XML)."""
    _assert_shape_editable(shape)
    if not _supports_shape_line_style(shape):
        return None
    queue_edit = _get_active_queue_edit(shape)
    if queue_edit is not None and "join" in queue_edit:
        return queue_edit["join"]
    payload_val = shape._payload.get("line_join")
    if payload_val is not None:
        return payload_val
    line = _inspect_line_element(shape)
    if line is None:
        return None
    for join_tag in ("round", "bevel", "miter"):
        if line.find(f"{{{A_NS}}}{join_tag}") is not None:
            return join_tag
    return None


def get_shape_line_miter_limit(shape: Any) -> int | None:
    """Get active miter limit for shape (queued or saved in XML)."""
    _assert_shape_editable(shape)
    if not _supports_shape_line_style(shape):
        return None
    queue_edit = _get_active_queue_edit(shape)
    if queue_edit is not None and "miter_limit" in queue_edit:
        return queue_edit["miter_limit"]
    payload_val = shape._payload.get("line_miter_limit")
    if payload_val is not None:
        return payload_val
    line = _inspect_line_element(shape)
    if line is None:
        return None
    miter = line.find(f"{{{A_NS}}}miter")
    if miter is None:
        return None
    lim_str = miter.attrib.get("lim")
    return int(lim_str) if lim_str is not None else None


def get_shape_line_head_end(shape: Any) -> dict[str, str | None]:
    """Get active headEnd properties for shape (queued or saved in XML)."""
    _assert_shape_editable(shape)
    if not _supports_shape_line_style(shape):
        return {"type": None, "width": None, "length": None}
    queue_edit = _get_active_queue_edit(shape)
    if queue_edit is not None and "head_end" in queue_edit:
        head = queue_edit["head_end"]
        if head is None:
            return {"type": None, "width": None, "length": None}
        return {
            "type": head.get("type"),
            "width": head.get("width") or head.get("w"),
            "length": head.get("length") or head.get("len"),
        }
    line = _inspect_line_element(shape)
    if line is None:
        return {"type": None, "width": None, "length": None}
    head = line.find(f"{{{A_NS}}}headEnd")
    if head is None:
        return {"type": None, "width": None, "length": None}
    return {
        "type": head.attrib.get("type"),
        "width": head.attrib.get("w"),
        "length": head.attrib.get("len"),
    }


def get_shape_line_tail_end(shape: Any) -> dict[str, str | None]:
    """Get active tailEnd properties for shape (queued or saved in XML)."""
    _assert_shape_editable(shape)
    if not _supports_shape_line_style(shape):
        return {"type": None, "width": None, "length": None}
    queue_edit = _get_active_queue_edit(shape)
    if queue_edit is not None and "tail_end" in queue_edit:
        tail = queue_edit["tail_end"]
        if tail is None:
            return {"type": None, "width": None, "length": None}
        return {
            "type": tail.get("type"),
            "width": tail.get("width") or tail.get("w"),
            "length": tail.get("length") or tail.get("len"),
        }
    line = _inspect_line_element(shape)
    if line is None:
        return {"type": None, "width": None, "length": None}
    tail = line.find(f"{{{A_NS}}}tailEnd")
    if tail is None:
        return {"type": None, "width": None, "length": None}
    return {
        "type": tail.attrib.get("type"),
        "width": tail.attrib.get("w"),
        "length": tail.attrib.get("len"),
    }


def get_shape_line_head_end_type(shape: Any) -> str | None:
    return get_shape_line_head_end(shape)["type"]


def get_shape_line_head_end_width(shape: Any) -> str | None:
    return get_shape_line_head_end(shape)["width"]


def get_shape_line_head_end_length(shape: Any) -> str | None:
    return get_shape_line_head_end(shape)["length"]


def get_shape_line_tail_end_type(shape: Any) -> str | None:
    return get_shape_line_tail_end(shape)["type"]


def get_shape_line_tail_end_width(shape: Any) -> str | None:
    return get_shape_line_tail_end(shape)["width"]


def get_shape_line_tail_end_length(shape: Any) -> str | None:
    return get_shape_line_tail_end(shape)["length"]


# --------------------------------------------------------------------------- #
# Application during presentation save                                       #
# --------------------------------------------------------------------------- #


def apply_shape_line_end_edits(
    input_path: Path,
    output_path: Path,
    line_end_edits: (
        list[tuple[tuple[int, ShapeEditRef], dict[str, Any]]]
        | dict[tuple[int, ShapeEditRef], dict[str, Any]]
    ),
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    """Apply line end, cap, and join property-bag edits to PPTX package during save."""
    if isinstance(line_end_edits, dict):
        edits_list = list(line_end_edits.items())
    else:
        edits_list = list(line_end_edits)

    if not edits_list:
        shutil.copyfile(input_path, output_path)
        return

    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )

    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeEditRef, dict[str, Any]]]] = {}
    for (slide_index, shape_ref), edits in edits_list:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, edits))

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            if slide_index < 0 or slide_index >= len(slides):
                raise IndexError(f"slide index {slide_index} out of range")
            slide_payload = slides[slide_index]
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, edits in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                shape_tag = _xml_local_name(shape_element.tag)
                if shape_tag not in {"sp", "cxnSp"}:
                    raise AttributeError(
                        "shape line style editing is only supported for shape and connector elements"
                    )
                shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
                if shape_properties is None:
                    shape_properties = ET.Element(f"{{{P_NS}}}spPr")
                    shape_element.append(shape_properties)
                set_shape_line_end_properties(shape_properties, edits)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    _copy_package_with_replacements(input_path, output_path, replacements)


__all__ = [
    "VALID_LINE_CAPS",
    "VALID_LINE_END_LENGTHS",
    "VALID_LINE_END_TYPES",
    "VALID_LINE_END_WIDTHS",
    "VALID_LINE_JOINS",
    "apply_shape_line_end_edits",
    "get_shape_line_cap",
    "get_shape_line_head_end",
    "get_shape_line_head_end_length",
    "get_shape_line_head_end_type",
    "get_shape_line_head_end_width",
    "get_shape_line_join",
    "get_shape_line_miter_limit",
    "get_shape_line_tail_end",
    "get_shape_line_tail_end_length",
    "get_shape_line_tail_end_type",
    "get_shape_line_tail_end_width",
    "set_shape_line_cap",
    "set_shape_line_end_properties",
    "set_shape_line_head_end",
    "set_shape_line_join",
    "set_shape_line_tail_end",
    "validate_line_cap",
    "validate_line_end_length",
    "validate_line_end_spec",
    "validate_line_end_type",
    "validate_line_end_width",
    "validate_line_join",
    "validate_miter_limit",
    "validate_shape_line_end_edits",
]
