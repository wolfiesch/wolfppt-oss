"""Chart axis ID normalization helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
import zipfile

C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def normalize_chart_axis_ids_in_package(path: str | Path) -> None:
    """Rewrite python-pptx chart XML quirks into validator-safe XML."""

    package_path = Path(path)
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / package_path.name
        with zipfile.ZipFile(package_path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name.startswith("ppt/charts/") and name.endswith(".xml"):
                    payload = chart_axis_ids_as_openxml_int32(payload)
                target.writestr(name, payload)
        tmp_path.replace(package_path)


def chart_axis_ids_as_openxml_int32(payload: bytes) -> bytes:
    root = ET.fromstring(payload)
    axis_id_map: dict[str, str] = {}
    for element in root.iter():
        if _xml_local_name(element.tag) not in {"axId", "crossAx"}:
            continue
        value = element.attrib.get("val")
        if value is None:
            continue
        try:
            number = int(value)
        except ValueError:
            continue
        if number < 0 or number > 2_147_483_647:
            axis_id_map.setdefault(value, str(1_000_000 + len(axis_id_map)))
            element.set("val", axis_id_map[value])
    _replace_alternate_content_with_fallback(root)
    _remove_radar_series_smooth_elements(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _replace_alternate_content_with_fallback(root: ET.Element) -> None:
    for parent in root.iter():
        for index, child in enumerate(list(parent)):
            if child.tag != f"{{{MC_NS}}}AlternateContent":
                continue
            fallback = child.find(f"{{{MC_NS}}}Fallback")
            if fallback is None:
                continue
            replacement = list(fallback)
            parent.remove(child)
            for offset, fallback_child in enumerate(replacement):
                parent.insert(index + offset, deepcopy(fallback_child))


def _remove_radar_series_smooth_elements(root: ET.Element) -> None:
    for radar_chart in root.findall(f".//{{{C_NS}}}radarChart"):
        for series in radar_chart.findall(f"{{{C_NS}}}ser"):
            for smooth in list(series.findall(f"{{{C_NS}}}smooth")):
                series.remove(smooth)


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
