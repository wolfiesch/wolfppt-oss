"""Slide and shape payload loaders for the presentation facade."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import native
from .extractor import PresentationSemantics, _extract_transform, extract_semantics
from .facade_values import centipoints_to_emu
from .package_parts import (
    InMemoryPackageSource,
    natural_key,
    normalize_package_partname,
)
from .slide_metadata import (
    part_common_slide_name,
    presentation_slide_master_partnames,
    read_presentation_slide_metadata,
    related_package_partnames,
)
from .xml_helpers import find_ooxml, findall_ooxml, ooxml_namespace

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def load_slide_payloads(path: Path) -> list[dict[str, Any]]:
    try:
        return [dict(slide) for slide in native.summarize(path).slides]
    except RuntimeError as exc:
        if "wolfppt_native is not installed" not in str(exc):
            raise
        return _slides_from_semantics(extract_semantics(path))


def load_slide_shell_payloads(
    path: Path | InMemoryPackageSource,
) -> list[dict[str, Any]]:
    metadata = read_presentation_slide_metadata(path, include_shape_hints=False)
    if metadata or isinstance(path, InMemoryPackageSource):
        return [
            {
                "part": part,
                "texts": [],
                **dict(payload),
            }
            for part, payload in metadata.items()
        ]
    return [dict(slide) for slide in load_slide_payloads(path)]


def load_slide_layout_payloads(path: Path) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as zf:
            names = sorted(
                [
                    name
                    for name in zf.namelist()
                    if name.startswith("ppt/slideLayouts/slideLayout") and name.endswith(".xml")
                ],
                key=natural_key,
            )
            return [
                {
                    "part": name,
                    "name": _slide_layout_name(zf.read(name), fallback=Path(name).stem),
                }
                for name in names
            ]
    except (FileNotFoundError, zipfile.BadZipFile):
        return []


def load_slide_master_payloads(path: Path) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as package:
            master_parts = presentation_slide_master_partnames(package, path)
            return [
                {
                    "part": part,
                    "name": part_common_slide_name(package, part),
                    "layout_parts": related_package_partnames(
                        package,
                        part,
                        "/slideLayout",
                    ),
                    "shapes": _part_shape_payloads(package, part),
                }
                for part in master_parts
            ]
    except (FileNotFoundError, zipfile.BadZipFile):
        return []


def load_slide_layout_placeholder_payloads(
    path: Path,
    partname: str,
) -> list[dict[str, Any]]:
    return [
        {
            **payload,
            "text": "",
            "paragraphs": [""],
            "paragraph_runs": [[]],
            "paragraph_line_breaks": [[]],
        }
        for payload in load_shape_payloads(path, partname)
        if payload.get("is_placeholder")
        and payload.get("placeholder_type") not in {"dt", "ftr", "sldNum"}
    ]


def load_shape_payloads(path: Path, partname: str) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as package:
            return _part_shape_payloads(package, partname)
    except (FileNotFoundError, zipfile.BadZipFile):
        return []


def shape_element_text(element: ET.Element) -> str:
    return "\n".join(_shape_element_paragraphs(element))


def _part_shape_payloads(
    package: zipfile.ZipFile,
    partname: str,
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(package.read(normalize_package_partname(partname).lstrip("/")))
    except (KeyError, ET.ParseError):
        return []
    shape_tree = find_ooxml(root, f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        return []
    media_playback = _slide_media_playback_payloads(root)
    shapes: list[dict[str, Any]] = []
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        payload = _shape_payload_from_xml(child)
        if payload is not None:
            shape_id = payload.get("id")
            if shape_id in media_playback:
                payload["media_playback"] = media_playback[shape_id]
            shapes.append(payload)
    return shapes


def _shape_payload_from_xml(element: ET.Element) -> dict[str, Any] | None:
    kind_by_tag = {
        "sp": "shape",
        "pic": "picture",
        "graphicFrame": "graphic_frame",
        "cxnSp": "connector",
        "grpSp": "group",
    }
    kind = kind_by_tag.get(_xml_local_name(element.tag))
    if element.tag != f"{{{ooxml_namespace(element, P_NS)}}}{_xml_local_name(element.tag)}":
        return None
    if kind is None:
        return None
    if kind == "picture" and _element_contains_local_name(element, "videoFile"):
        kind = "movie"
    if kind == "picture" and _element_contains_local_name(element, "audioFile"):
        kind = "audio"
    if kind == "graphic_frame" and _element_contains_local_name(element, "oleObj"):
        kind = "ole_object"
    non_visual_properties = find_ooxml(element, f".//{{{P_NS}}}cNvPr")
    # Only the shape's own nvPr may carry p:ph; a group's descendants must not
    # turn the group itself into a placeholder.
    placeholder = find_ooxml(element, f"./*/{{{P_NS}}}nvPr/{{{P_NS}}}ph")
    paragraphs = _shape_element_paragraphs(element)
    paragraph_runs, paragraph_line_breaks = _shape_element_paragraph_runs_and_line_breaks(element)
    payload: dict[str, Any] = {
        "id": None if non_visual_properties is None else non_visual_properties.attrib.get("id"),
        "name": ""
        if non_visual_properties is None
        else non_visual_properties.attrib.get("name", ""),
        "kind": kind,
        "text": "\n".join(paragraphs),
        "paragraphs": paragraphs,
        "paragraph_runs": paragraph_runs,
        "paragraph_line_breaks": paragraph_line_breaks,
        "paragraph_run_bold": _shape_element_paragraph_run_bools(element, "b"),
        "paragraph_run_italic": _shape_element_paragraph_run_bools(element, "i"),
        "paragraph_run_underline": _shape_element_paragraph_run_underline(element),
        "paragraph_run_strike": _shape_element_paragraph_run_strike(element),
        "paragraph_run_font_size": _shape_element_paragraph_run_font_size(element),
        "paragraph_run_font_name": _shape_element_paragraph_run_font_name(element),
        "paragraph_run_font_rgb": _shape_element_paragraph_run_font_rgb(element),
        "paragraph_run_font_fill_type": _shape_element_paragraph_run_font_fill_type(element),
        "paragraph_run_font_language": _shape_element_paragraph_run_font_language(element),
        "is_placeholder": placeholder is not None,
        "locks": _shape_element_locks(element, kind),
        "transform": _transform_payload(_extract_transform(element)),
    }
    if placeholder is not None:
        payload["placeholder_type"] = placeholder.attrib.get("type")
        payload["placeholder_idx"] = placeholder.attrib.get("idx")
        payload["placeholder_orient"] = placeholder.attrib.get("orient")
        payload["placeholder_size"] = placeholder.attrib.get("sz")
    return payload


def _slide_media_playback_payloads(
    root: ET.Element,
) -> dict[str, dict[str, bool | int]]:
    settings: dict[str, dict[str, bool | int]] = {}
    auto_play_targets = _auto_play_media_call_targets(root)
    for media in root.iter():
        if _xml_local_name(media.tag) not in {"audio", "video"}:
            continue
        media_node = find_ooxml(media, f"{{{P_NS}}}cMediaNode")
        target = find_ooxml(media, f".//{{{P_NS}}}spTgt")
        timing = find_ooxml(media, f".//{{{P_NS}}}cTn")
        if media_node is None or target is None or timing is None:
            continue
        shape_id = target.attrib.get("spid")
        if shape_id is None:
            continue
        try:
            volume = round(int(media_node.attrib.get("vol", "80000")) / 1000)
        except ValueError:
            volume = 80
        settings[shape_id] = {
            "loop": timing.attrib.get("repeatCount") == "indefinite",
            "play_across_slides": int(media_node.attrib.get("numSld", "1")) > 1,
            "volume": min(100, max(0, volume)),
            "auto_play": shape_id in auto_play_targets
            # Legacy WolfPPT output started the media node itself at slide begin.
            or any(
                condition.attrib.get("delay") == "0" for condition in timing.iter(f"{{{P_NS}}}cond")
            ),
        }
    return settings


def _auto_play_media_call_targets(root: ET.Element) -> set[str]:
    """Shape IDs PowerPoint starts automatically (Playback > Start: Automatically).

    That setting is a main-sequence media-call effect with a ``playFrom``
    command and an ``afterEffect`` or ``withEffect`` node type.
    """
    targets: set[str] = set()
    for time_node in root.iter(f"{{{P_NS}}}cTn"):
        if time_node.attrib.get("presetClass") != "mediacall" or (
            time_node.attrib.get("nodeType") not in {"afterEffect", "withEffect"}
        ):
            continue
        for command in time_node.iter(f"{{{P_NS}}}cmd"):
            if not command.attrib.get("cmd", "").startswith("playFrom("):
                continue
            targets.update(
                spid
                for target in command.iter(f"{{{P_NS}}}spTgt")
                if (spid := target.attrib.get("spid")) is not None
            )
    return targets


def _shape_element_locks(element: ET.Element, kind: str) -> dict[str, bool]:
    nv_tags = {
        "shape": f"{{{P_NS}}}nvSpPr",
        "freeform": f"{{{P_NS}}}nvSpPr",
        "text_box": f"{{{P_NS}}}nvSpPr",
        "picture": f"{{{P_NS}}}nvPicPr",
        "connector": f"{{{P_NS}}}nvCxnSpPr",
        "group": f"{{{P_NS}}}nvGrpSpPr",
    }
    cnv_tags = {
        "shape": f"{{{P_NS}}}cNvSpPr",
        "freeform": f"{{{P_NS}}}cNvSpPr",
        "text_box": f"{{{P_NS}}}cNvSpPr",
        "picture": f"{{{P_NS}}}cNvPicPr",
        "connector": f"{{{P_NS}}}cNvCxnSpPr",
        "group": f"{{{P_NS}}}cNvGrpSpPr",
    }
    lock_tags = {
        "shape": f"{{{A_NS}}}spLocks",
        "freeform": f"{{{A_NS}}}spLocks",
        "text_box": f"{{{A_NS}}}spLocks",
        "picture": f"{{{A_NS}}}picLocks",
        "connector": f"{{{A_NS}}}cxnSpLocks",
        "group": f"{{{A_NS}}}grpSpLocks",
    }
    nv_tag = nv_tags.get(kind)
    cnv_tag = cnv_tags.get(kind)
    lock_tag = lock_tags.get(kind)
    if nv_tag is None or cnv_tag is None or lock_tag is None:
        return {}
    nv = find_ooxml(element, f"./{nv_tag}")
    if nv is None:
        return {}
    cnv = find_ooxml(nv, f"./{cnv_tag}")
    if cnv is None:
        return {}
    lock_elem = find_ooxml(cnv, f"./{lock_tag}")
    if lock_elem is None:
        return {}
    attr_to_prop = {
        "noMove": "no_move",
        "noResize": "no_resize",
        "noRot": "no_rotate",
        "noSelect": "no_select",
        "noGrp": "no_group",
        "noUngrp": "no_ungroup",
        "noChangeAspect": "no_change_aspect",
        "noEditPoints": "no_edit_points",
        "noAdjustHandles": "no_adjust_handles",
        "noChangeShapeType": "no_change_shape_type",
        "noTextEdit": "no_text_edit",
        "noCrop": "no_crop",
        "noChangeArrowheads": "no_change_arrowheads",
    }
    locks: dict[str, bool] = {}
    for attr, prop in attr_to_prop.items():
        raw = lock_elem.attrib.get(attr)
        if raw is not None:
            lower = str(raw).strip().lower()
            if lower in {"1", "true", "on"}:
                locks[prop] = True
            elif lower in {"0", "false", "off"}:
                locks[prop] = False
    return locks


def _shape_element_paragraphs(element: ET.Element) -> list[str]:
    paragraphs: list[str] = []
    for paragraph in findall_ooxml(element, f".//{{{A_NS}}}p"):
        namespace = ooxml_namespace(paragraph, A_NS)
        text_tag = f"{{{namespace}}}t"
        break_tag = f"{{{namespace}}}br"
        paragraphs.append(
            "".join(
                "\v" if child.tag == break_tag else child.text or ""
                for child in paragraph.iter()
                if child.tag == text_tag or child.tag == break_tag
            )
        )
    return paragraphs


def _shape_element_paragraph_runs_and_line_breaks(
    element: ET.Element,
) -> tuple[list[list[str]], list[list[int]]]:
    paragraphs: list[list[str]] = []
    paragraph_line_breaks: list[list[int]] = []
    for paragraph in findall_ooxml(element, f".//{{{A_NS}}}p"):
        runs: list[str] = []
        line_breaks: list[int] = []
        break_tag = f"{{{ooxml_namespace(paragraph, A_NS)}}}br"
        for run in paragraph:
            if run.tag == break_tag:
                line_breaks.append(len(runs))
                continue
            if _xml_local_name(run.tag) not in {"r", "fld"}:
                continue
            text = find_ooxml(run, f"{{{A_NS}}}t")
            runs.append("" if text is None else text.text or "")
        paragraphs.append(runs)
        paragraph_line_breaks.append(line_breaks)
    return paragraphs, paragraph_line_breaks


def _shape_element_paragraph_run_bools(
    element: ET.Element,
    attr: str,
) -> list[list[bool | None]]:
    return _shape_element_paragraph_run_properties(
        element,
        lambda run_properties: _bool_attribute(run_properties, attr),
    )


def _shape_element_paragraph_run_underline(
    element: ET.Element,
) -> list[list[bool | str | None]]:
    """Run underline states: ``True``/``False`` for ``sng``/``none``, else the style token."""

    def read(run_properties: ET.Element | None) -> bool | str | None:
        if run_properties is None or "u" not in run_properties.attrib:
            return None
        value = run_properties.attrib["u"]
        if value == "sng":
            return True
        if value == "none":
            return False
        return value

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_strike(
    element: ET.Element,
) -> list[list[bool | None]]:
    def read(run_properties: ET.Element | None) -> bool | None:
        if run_properties is None or "strike" not in run_properties.attrib:
            return None
        return run_properties.attrib["strike"] != "noStrike"

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_size(
    element: ET.Element,
) -> list[list[int | None]]:
    def read(run_properties: ET.Element | None) -> int | None:
        if run_properties is None or "sz" not in run_properties.attrib:
            return None
        return centipoints_to_emu(int(run_properties.attrib["sz"]))

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_name(
    element: ET.Element,
) -> list[list[str | None]]:
    def read(run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        latin = find_ooxml(run_properties, f"{{{A_NS}}}latin")
        if latin is None:
            return None
        return latin.attrib.get("typeface")

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_rgb(
    element: ET.Element,
) -> list[list[str | None]]:
    def read(run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        solid_fill = find_ooxml(run_properties, f"{{{A_NS}}}solidFill")
        if solid_fill is None:
            return None
        srgb_color = find_ooxml(solid_fill, f"{{{A_NS}}}srgbClr")
        if srgb_color is None:
            return None
        return srgb_color.attrib.get("val")

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_fill_type(
    element: ET.Element,
) -> list[list[str | None]]:
    def read(run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        if find_ooxml(run_properties, f"{{{A_NS}}}solidFill") is not None:
            return "solid"
        if find_ooxml(run_properties, f"{{{A_NS}}}noFill") is not None:
            return "background"
        return None

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_language(
    element: ET.Element,
) -> list[list[str | None]]:
    return _shape_element_paragraph_run_properties(
        element,
        lambda run_properties: (
            None if run_properties is None else run_properties.attrib.get("lang")
        ),
    )


def _shape_element_paragraph_run_properties(
    element: ET.Element,
    reader: Any,
) -> list[list[Any]]:
    paragraphs: list[list[Any]] = []
    for paragraph in findall_ooxml(element, f".//{{{A_NS}}}p"):
        values: list[Any] = []
        for run in paragraph:
            if _xml_local_name(run.tag) not in {"r", "fld"}:
                continue
            values.append(reader(find_ooxml(run, f"{{{A_NS}}}rPr")))
        paragraphs.append(values)
    return paragraphs


def _bool_attribute(run_properties: ET.Element | None, attr: str) -> bool | None:
    if run_properties is None or attr not in run_properties.attrib:
        return None
    return run_properties.attrib[attr] not in {"0", "false", "False"}


def _element_contains_local_name(element: ET.Element, local_name: str) -> bool:
    return any(_xml_local_name(child.tag) == local_name for child in element.iter())


def _slide_layout_name(payload: bytes, fallback: str) -> str:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return fallback
    common_slide_data = find_ooxml(root, f"{{{P_NS}}}cSld")
    if common_slide_data is None:
        return fallback
    return common_slide_data.attrib.get("name") or fallback


def _slides_from_semantics(summary: PresentationSemantics) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for slide in summary.slides:
        slides.append(
            {
                "part": slide.part,
                "texts": list(slide.texts),
                "shapes": [
                    {
                        "id": shape.id,
                        "name": shape.name,
                        "kind": shape.kind,
                        "text": shape.text,
                        "paragraphs": list(shape.paragraphs),
                        "paragraph_line_breaks": [
                            _paragraph_line_break_slots(paragraph) for paragraph in shape.paragraphs
                        ],
                        "relationship_ids": list(shape.relationship_ids),
                        "transform": _transform_payload(shape.transform),
                        "effective_transform": _transform_payload(shape.effective_transform),
                        "tables": [
                            {
                                "rows": [list(row) for row in table.rows],
                                "row_count": table.row_count,
                                "col_count": table.col_count,
                            }
                            for table in shape.tables
                        ],
                        "has_chart": shape.has_chart,
                        "has_picture": shape.has_picture,
                    }
                    for shape in slide.shapes
                ],
            }
        )
    return slides


def _transform_payload(transform: Any) -> dict[str, int] | None:
    if transform is None:
        return None
    return {
        "x": int(transform.x),
        "y": int(transform.y),
        "cx": int(transform.cx),
        "cy": int(transform.cy),
    }


def _paragraph_line_break_slots(text: str) -> list[int]:
    parts = text.split("\v")
    line_breaks: list[int] = []
    run_slot = 0
    for part in parts[:-1]:
        if part:
            run_slot += 1
        line_breaks.append(run_slot)
    return line_breaks


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
