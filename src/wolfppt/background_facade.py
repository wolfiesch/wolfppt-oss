"""python-pptx-style background inspection facade."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import (
    color_type_value as _color_type_value,
    fill_type_value as _fill_type_value,
    normalize_rgb as _normalize_rgb,
    normalize_theme_color as _normalize_theme_color,
    rgb_value as _rgb_value,
    theme_color_value as _theme_color_value,
)
from .package_parts import (
    XmlElementProxy,
    normalize_package_partname as _normalize_package_partname,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class Background:
    def __init__(self, presentation: Any, partname: str) -> None:
        self._presentation = presentation
        self._partname = partname

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(
            _common_slide_data_xml_element(self._presentation.path, self._partname)
        )

    @property
    def _element(self) -> XmlElementProxy:
        return self.element

    @property
    def fill(self) -> "BackgroundFillFormat":
        return BackgroundFillFormat(self)


class BackgroundFillFormat:
    def __init__(self, background: Background) -> None:
        self._background = background

    @property
    def type(self) -> Any:
        return _fill_type_value(
            _presentation_background_fill_type(
                self._background._presentation,
                self._background._partname,
            )
        )

    def solid(self) -> None:
        self._background._presentation._queue_background_fill_solid(
            self._background._partname
        )

    def background(self) -> None:
        self._background._presentation._queue_background_fill_background(
            self._background._partname
        )

    @property
    def fore_color(self) -> "BackgroundColorFormat":
        fill_type = _presentation_background_fill_type(
            self._background._presentation,
            self._background._partname,
        )
        if fill_type not in {"solid", "patterned"}:
            raise TypeError(
                "fill type _NoFill has no foreground color, "
                "call .solid() or .patterned() first"
            )
        return BackgroundColorFormat(self._background, "fore")

    @property
    def back_color(self) -> "BackgroundColorFormat":
        fill_type = _presentation_background_fill_type(
            self._background._presentation,
            self._background._partname,
        )
        if fill_type != "patterned":
            fill_name = "_SolidFill" if fill_type == "solid" else "_NoFill"
            raise TypeError(
                f"fill type {fill_name} has no background color, "
                "call .patterned() first"
            )
        return BackgroundColorFormat(self._background, "back")


class BackgroundColorFormat:
    def __init__(self, background: Background, role: str) -> None:
        self._background = background
        self._role = role

    @property
    def rgb(self) -> Any:
        rgb = _presentation_background_fill_rgb(
            self._background._presentation,
            self._background._partname,
            self._role,
        )
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        if self._role != "fore":
            raise TypeError("background fill back_color is not writable")
        self._background._presentation._queue_background_fill_color(
            self._background._partname,
            {"type": "rgb", "value": _normalize_rgb(value), "brightness": 0.0},
        )

    @property
    def brightness(self) -> float:
        payload = _presentation_background_fill_color_payload(
            self._background._presentation,
            self._background._partname,
            self._role,
        )
        return 0.0 if payload is None else float(payload.get("brightness", 0.0))

    @brightness.setter
    def brightness(self, value: Any) -> None:
        if self._role != "fore":
            raise TypeError("background fill back_color is not writable")
        brightness = float(value)
        if not -1.0 <= brightness <= 1.0:
            raise ValueError("brightness must be between -1.0 and 1.0")
        payload = _presentation_background_fill_color_payload(
            self._background._presentation,
            self._background._partname,
            self._role,
        )
        if payload is None:
            return
        if float(payload.get("brightness", 0.0)) == brightness:
            return
        color = dict(payload)
        color["brightness"] = brightness
        self._background._presentation._queue_background_fill_color(
            self._background._partname,
            color,
        )

    @property
    def theme_color(self) -> Any:
        payload = _presentation_background_fill_color_payload(
            self._background._presentation,
            self._background._partname,
            self._role,
        )
        if payload is None or payload.get("type") != "scheme":
            return _theme_color_value("")
        return _theme_color_value(str(payload["value"]))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        if self._role != "fore":
            raise TypeError("background fill back_color is not writable")
        theme_color = _normalize_theme_color(value)
        payload = _presentation_background_fill_color_payload(
            self._background._presentation,
            self._background._partname,
            self._role,
        )
        brightness = 0.0 if payload is None else float(payload.get("brightness", 0.0))
        if (
            payload is not None
            and payload.get("type") == "scheme"
            and payload.get("value") == theme_color
        ):
            return
        self._background._presentation._queue_background_fill_color(
            self._background._partname,
            {"type": "scheme", "value": theme_color, "brightness": brightness},
        )

    @property
    def type(self) -> Any:
        payload = _presentation_background_fill_color_payload(
            self._background._presentation,
            self._background._partname,
            self._role,
        )
        if payload is None:
            return None
        return _color_type_value(str(payload.get("type")))


def _common_slide_data_xml_element(path: Path, partname: str) -> ET.Element:
    normalized = _normalize_package_partname(partname).lstrip("/")
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read(normalized))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ) as exc:
        raise AttributeError("common slide data XML element is unavailable") from exc
    common_slide_data = root.find(f"{{{P_NS}}}cSld")
    if common_slide_data is None:
        raise AttributeError("common slide data XML element is unavailable")
    return common_slide_data


def _background_fill_type(path: Path, partname: str) -> str:
    background_properties = _background_properties_element(path, partname)
    if background_properties is None:
        return "background"
    for child in background_properties:
        if child.tag == f"{{{A_NS}}}solidFill":
            return "solid"
        if child.tag == f"{{{A_NS}}}noFill":
            return "background"
        if child.tag == f"{{{A_NS}}}pattFill":
            return "patterned"
        if child.tag == f"{{{A_NS}}}gradFill":
            return "gradient"
        if child.tag == f"{{{A_NS}}}blipFill":
            return "picture"
        if child.tag == f"{{{A_NS}}}grpFill":
            return "group"
    return "background"


def _presentation_background_fill_type(presentation: Any, partname: str) -> str:
    normalized = _normalize_package_partname(partname)
    if normalized in presentation._background_fill_background_edits:
        return "background"
    if (
        normalized in presentation._background_fill_solid_edits
        or normalized in presentation._background_fill_color_edits
    ):
        return "solid"
    return _background_fill_type(presentation.path, normalized)


def _background_fill_rgb(path: Path, partname: str, role: str) -> str | None:
    payload = _background_fill_color_payload(path, partname, role)
    if payload is None or payload.get("type") != "rgb":
        return None
    value = payload.get("value")
    return str(value).upper() if value else None


def _background_fill_color_payload(
    path: Path,
    partname: str,
    role: str,
) -> dict[str, Any] | None:
    background_properties = _background_properties_element(path, partname)
    if background_properties is None:
        return None
    if role == "fore":
        color_parent = background_properties.find(f"{{{A_NS}}}solidFill")
    else:
        color_parent = background_properties.find(
            f"{{{A_NS}}}pattFill/{{{A_NS}}}bgClr"
        )
    if color_parent is None:
        return None
    rgb = color_parent.find(f"{{{A_NS}}}srgbClr")
    if rgb is not None:
        value = rgb.attrib.get("val")
        return (
            None
            if not value
            else {
                "type": "rgb",
                "value": value.upper(),
                "brightness": _brightness_from_color_element(rgb),
            }
        )
    scheme = color_parent.find(f"{{{A_NS}}}schemeClr")
    if scheme is not None:
        value = scheme.attrib.get("val")
        return (
            None
            if not value
            else {
                "type": "scheme",
                "value": value,
                "brightness": _brightness_from_color_element(scheme),
            }
        )
    return None


def _presentation_background_fill_rgb(
    presentation: Any,
    partname: str,
    role: str,
) -> str | None:
    normalized = _normalize_package_partname(partname)
    if role == "fore" and normalized in presentation._background_fill_color_edits:
        payload = presentation._background_fill_color_edits[normalized]
        if isinstance(payload, str):
            return payload
        if payload.get("type") == "rgb":
            return str(payload["value"]).upper()
        return None
    if normalized in presentation._background_fill_background_edits:
        return None
    if normalized in presentation._background_fill_solid_edits:
        return None
    return _background_fill_rgb(presentation.path, normalized, role)


def _presentation_background_fill_color_payload(
    presentation: Any,
    partname: str,
    role: str,
) -> dict[str, Any] | None:
    normalized = _normalize_package_partname(partname)
    if role == "fore" and normalized in presentation._background_fill_color_edits:
        payload = presentation._background_fill_color_edits[normalized]
        if isinstance(payload, str):
            return {"type": "rgb", "value": payload.upper(), "brightness": 0.0}
        return dict(payload)
    if normalized in presentation._background_fill_background_edits:
        return None
    if normalized in presentation._background_fill_solid_edits:
        return None
    return _background_fill_color_payload(presentation.path, normalized, role)


def _background_properties_element(path: Path, partname: str) -> ET.Element | None:
    common_slide_data = _common_slide_data_xml_element(path, partname)
    background = common_slide_data.find(f"{{{P_NS}}}bg")
    if background is None:
        return None
    return background.find(f"{{{P_NS}}}bgPr")


def _brightness_from_color_element(color: ET.Element) -> float:
    lum_off = color.find(f"{{{A_NS}}}lumOff")
    if lum_off is not None:
        return int(lum_off.attrib.get("val", "0")) / 100000.0
    lum_mod = color.find(f"{{{A_NS}}}lumMod")
    if lum_mod is not None:
        return int(lum_mod.attrib.get("val", "100000")) / 100000.0 - 1.0
    return 0.0
