"""XML inspection helpers for benchmark correctness details."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .benchmark_cases import A_NS, P_NS


def run_formatting_for_text(output_path: Path, text: str) -> dict[str, str | None]:
    return run_formatting_by_texts(output_path, [text]).get(
        text,
        {
            "bold": None,
            "italic": None,
            "underline": None,
            "size": None,
            "font_name": None,
            "color_rgb": None,
        },
    )


def run_formatting_by_texts(
    output_path: Path,
    texts: list[str],
) -> dict[str, dict[str, str | None]]:
    wanted = set(texts)
    found: dict[str, dict[str, str | None]] = {}
    root = _slide_root(output_path)
    for run in root.iter(f"{{{A_NS}}}r"):
        text_node = run.find(f"{{{A_NS}}}t")
        if text_node is None or text_node.text not in wanted:
            continue
        run_properties = run.find(f"{{{A_NS}}}rPr")
        if run_properties is None:
            found[text_node.text] = _empty_run_formatting_payload()
            continue
        latin = run_properties.find(f"{{{A_NS}}}latin")
        color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
        found[text_node.text] = {
            "bold": run_properties.get("b"),
            "italic": run_properties.get("i"),
            "underline": run_properties.get("u"),
            "size": run_properties.get("sz"),
            "font_name": None if latin is None else latin.get("typeface"),
            "color_rgb": None if color is None else color.get("val"),
        }
    return found


def run_language_for_text(output_path: Path, text: str) -> str | None:
    root = _slide_root(output_path)
    for run in root.iter(f"{{{A_NS}}}r"):
        text_node = run.find(f"{{{A_NS}}}t")
        if text_node is None or text_node.text != text:
            continue
        run_properties = run.find(f"{{{A_NS}}}rPr")
        return None if run_properties is None else run_properties.get("lang")
    return None


def run_fill_for_text(output_path: Path, text: str) -> dict[str, Any]:
    root = _slide_root(output_path)
    for run in root.iter(f"{{{A_NS}}}r"):
        text_node = run.find(f"{{{A_NS}}}t")
        if text_node is None or text_node.text != text:
            continue
        run_properties = run.find(f"{{{A_NS}}}rPr")
        if run_properties is None:
            return _run_fill_payload(None)
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            color = solid_fill.find(f"{{{A_NS}}}srgbClr")
            return _run_fill_payload({
                "fill_type": "solid",
                "color_rgb": None if color is None else color.get("val"),
            })
        if run_properties.find(f"{{{A_NS}}}noFill") is not None:
            return _run_fill_payload({"fill_type": "background", "color_rgb": None})
        gradient = run_properties.find(f"{{{A_NS}}}gradFill")
        if gradient is not None:
            stops = gradient.findall(f"{{{A_NS}}}gsLst/{{{A_NS}}}gs")
            first_color = (
                None
                if not stops
                else stops[0].find(f"{{{A_NS}}}srgbClr")
            )
            linear = gradient.find(f"{{{A_NS}}}lin")
            return _run_fill_payload(
                {
                    "fill_type": "gradient",
                    "color_rgb": None,
                    "gradient_angle": None
                    if linear is None
                    else linear.attrib.get("ang"),
                    "gradient_stop_count": len(stops),
                    "gradient_first_stop_position": None
                    if not stops
                    else stops[0].attrib.get("pos"),
                    "gradient_first_stop_rgb": None
                    if first_color is None
                    else first_color.attrib.get("val"),
                }
            )
        return _run_fill_payload(None)
    return _run_fill_payload(None)


def _run_fill_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    defaults = {
        "fill_type": None,
        "color_rgb": None,
        "gradient_angle": None,
        "gradient_stop_count": None,
        "gradient_first_stop_position": None,
        "gradient_first_stop_rgb": None,
    }
    if payload:
        defaults.update(payload)
    return defaults


def paragraph_alignment_for_text(output_path: Path, text: str) -> str | None:
    for paragraph in _slide_root(output_path).iter(f"{{{A_NS}}}p"):
        if _paragraph_text(paragraph) != text:
            continue
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        return None if paragraph_properties is None else paragraph_properties.get("algn")
    return None


def paragraph_level_for_text(output_path: Path, text: str) -> int:
    for paragraph in _slide_root(output_path).iter(f"{{{A_NS}}}p"):
        if _paragraph_text(paragraph) != text:
            continue
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        if paragraph_properties is None:
            return 0
        return int(paragraph_properties.get("lvl", "0"))
    return 0


def paragraph_spacing_for_text(
    output_path: Path,
    text: str,
) -> dict[str, int | float | None]:
    for paragraph in _slide_root(output_path).iter(f"{{{A_NS}}}p"):
        if _paragraph_text(paragraph) != text:
            continue
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        return {
            "space_before": _paragraph_spacing_emu(paragraph_properties, "spcBef"),
            "space_after": _paragraph_spacing_emu(paragraph_properties, "spcAft"),
            "line_spacing": _paragraph_line_spacing(paragraph_properties),
        }
    return {"space_before": None, "space_after": None, "line_spacing": None}


def paragraph_content_child_count(
    output_path: Path,
    shape_index: int,
    paragraph_index: int,
) -> int:
    shape = list(_slide_root(output_path).iter(f"{{{P_NS}}}sp"))[shape_index]
    paragraph = shape.findall(f".//{{{A_NS}}}p")[paragraph_index]
    return sum(1 for child in paragraph if child.tag != f"{{{A_NS}}}pPr")


def paragraph_line_break_count(
    output_path: Path,
    shape_index: int,
    paragraph_index: int,
) -> int:
    shape = list(_slide_root(output_path).iter(f"{{{P_NS}}}sp"))[shape_index]
    paragraph = shape.findall(f".//{{{A_NS}}}p")[paragraph_index]
    return sum(1 for child in paragraph if child.tag == f"{{{A_NS}}}br")


def paragraph_font_for_text(output_path: Path, text: str) -> dict[str, str | None]:
    for paragraph in _slide_root(output_path).iter(f"{{{A_NS}}}p"):
        if _paragraph_text(paragraph) != text:
            continue
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        if paragraph_properties is None:
            return _empty_paragraph_font_payload()
        default_run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
        if default_run_properties is None:
            return _empty_paragraph_font_payload()
        latin = default_run_properties.find(f"{{{A_NS}}}latin")
        color = default_run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
        return {
            "bold": default_run_properties.get("b"),
            "italic": default_run_properties.get("i"),
            "underline": default_run_properties.get("u"),
            "size": default_run_properties.get("sz"),
            "language_id": default_run_properties.get("lang"),
            "font_name": None if latin is None else latin.get("typeface"),
            "color_rgb": None if color is None else color.get("val"),
        }
    return _empty_paragraph_font_payload()


def _slide_root(output_path: Path) -> ET.Element:
    with ZipFile(output_path) as package:
        xml = package.read("ppt/slides/slide1.xml")
    return ET.fromstring(xml)


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(
        text_node.text or "" for text_node in paragraph.findall(f".//{{{A_NS}}}t")
    )


def _empty_run_formatting_payload() -> dict[str, str | None]:
    return {
        "bold": None,
        "italic": None,
        "underline": None,
        "size": None,
        "font_name": None,
        "color_rgb": None,
    }


def _empty_paragraph_font_payload() -> dict[str, str | None]:
    return {
        "bold": None,
        "italic": None,
        "underline": None,
        "size": None,
        "language_id": None,
        "font_name": None,
        "color_rgb": None,
    }


def _paragraph_spacing_emu(
    paragraph_properties: ET.Element | None,
    tag: str,
) -> int | None:
    if paragraph_properties is None:
        return None
    spacing = paragraph_properties.find(f"{{{A_NS}}}{tag}")
    if spacing is None:
        return None
    spacing_points = spacing.find(f"{{{A_NS}}}spcPts")
    if spacing_points is None:
        return None
    return int(spacing_points.attrib["val"]) * 127


def _paragraph_line_spacing(
    paragraph_properties: ET.Element | None,
) -> int | float | None:
    if paragraph_properties is None:
        return None
    spacing = paragraph_properties.find(f"{{{A_NS}}}lnSpc")
    if spacing is None:
        return None
    spacing_percent = spacing.find(f"{{{A_NS}}}spcPct")
    if spacing_percent is not None:
        return int(spacing_percent.attrib["val"]) / 100000
    spacing_points = spacing.find(f"{{{A_NS}}}spcPts")
    if spacing_points is not None:
        return int(spacing_points.attrib["val"]) * 127
    return None
