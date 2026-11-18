"""python-pptx-style background inspection facade."""

from __future__ import annotations

import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .background_edits import profile_element
from .dml.color import ColorFormatRefusal, ColorTextAndTransforms, fill_color_element
from .dml_fill import color_element, set_color_brightness, validate_text_color_element
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
)
from .dml_fill import (
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .facade_values import (
    coerce_crop_fraction as _coerce_crop_fraction,
)
from .facade_values import (
    color_type_value as _color_type_value,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .image_inputs import (
    InMemoryImage,
)
from .image_inputs import (
    image_source_for_queue as _image_source_for_queue,
)
from .package_parts import (
    XmlElementProxy,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .shape_format_facade import GradientStops
from .shape_picture_inspection import PictureImage
from .slide_relationships import slide_relationship_info as _slide_relationship_info
from .xml_helpers import find_ooxml, ooxml_namespace, xml_bool_value

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_FILL_CLASS_NAMES = {
    "solid": "_SolidFill",
    "patterned": "_PattFill",
    "gradient": "_GradFill",
    "picture": "_PictureFill",
    "group": "_GrpFill",
}


def _extract_blip_fill_from_package(package: zipfile.ZipFile, partname: str) -> ET.Element | None:
    norm = partname.lstrip("/")
    if norm not in package.namelist():
        return None
    root = ET.fromstring(package.read(norm))
    cSld = root.find(f"{{{P_NS}}}cSld")
    if cSld is None:
        return None
    bg = cSld.find(f"{{{P_NS}}}bg")
    if bg is None:
        return None
    bgPr = bg.find(f"{{{P_NS}}}bgPr")
    if bgPr is None:
        bgPr = bg.find(f"{{{A_NS}}}bgPr")
    if bgPr is None:
        return None
    blipFill = bgPr.find(f"{{{A_NS}}}blipFill")
    if blipFill is None:
        blipFill = bgPr.find(f"{{{P_NS}}}blipFill")
    return blipFill


def _find_rel_target(
    package: zipfile.ZipFile, source_part: str, rel_type_suffix: str
) -> str | None:
    norm = source_part.lstrip("/")
    rels_name = _rels_part_for_package_part(norm).lstrip("/")
    if rels_name not in package.namelist():
        return None
    rels_root = ET.fromstring(package.read(rels_name))
    for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type", "").endswith(rel_type_suffix):
            target = rel.attrib.get("Target", "")
            if target:
                return _resolve_package_target(norm, target).lstrip("/")
    return None


def _background_blip_fill(path: Path, partname: str) -> tuple[str, ET.Element] | None:
    normalized = _normalize_package_partname(partname).lstrip("/")
    try:
        with zipfile.ZipFile(path) as package:
            blip_fill = _extract_blip_fill_from_package(package, normalized)
            if blip_fill is not None:
                return normalized, blip_fill

            if "/slides/slide" in f"/{normalized}":
                layout_target = _find_rel_target(package, normalized, "/slideLayout")
                if layout_target:
                    blip_fill = _extract_blip_fill_from_package(package, layout_target)
                    if blip_fill is not None:
                        return layout_target, blip_fill
                    master_target = _find_rel_target(package, layout_target, "/slideMaster")
                    if master_target:
                        blip_fill = _extract_blip_fill_from_package(package, master_target)
                        if blip_fill is not None:
                            return master_target, blip_fill
            elif "/slideLayouts/slideLayout" in f"/{normalized}":
                master_target = _find_rel_target(package, normalized, "/slideMaster")
                if master_target:
                    blip_fill = _extract_blip_fill_from_package(package, master_target)
                    if blip_fill is not None:
                        return master_target, blip_fill
    except (
        KeyError,
        FileNotFoundError,
        ET.ParseError,
        zipfile.BadZipFile,
        AttributeError,
        ValueError,
    ):
        return None
    return None


def _normalize_image_source(image_file: Any) -> str | Path | InMemoryImage:
    if isinstance(image_file, (bytes, bytearray)):
        return InMemoryImage(bytes(image_file))
    if isinstance(image_file, InMemoryImage):
        return image_file
    return _image_source_for_queue(image_file)


def normalize_background_target(target: Any) -> Any:
    if hasattr(target, "_target"):
        return normalize_background_target(target._target)
    if isinstance(target, str):
        part = target.strip()
        if not part:
            raise AttributeError("package part is unavailable")
        return f"/{part.lstrip('/')}"
    if hasattr(target, "_payload") and target._payload.get("_pending_creation"):
        token = target._payload.get("_creation_token")
        if token is not None:
            return token
        return target
    if hasattr(target, "partname") and target.partname:
        return _normalize_package_partname(target.partname)
    return target


class Background:
    def __init__(
        self,
        presentation: Any,
        partname: str = "",
        slide: Any = None,
    ) -> None:
        self._presentation = presentation
        self._stored_partname = str(partname or "")
        self._slide = slide

    def get_effective(self) -> Any:
        """Return this slide background's effective fill and its source
        (commercial edition; see
        :func:`wolfppt.effective_format_readback.background_effective`)."""
        from .editions import commercial_module

        readback = commercial_module("effective_format_readback", "Reading effective formatting")
        return readback.background_effective(self)

    @property
    def _partname(self) -> str:
        if self._slide is not None and self._slide.partname:
            return self._slide.partname
        return self._stored_partname

    @_partname.setter
    def _partname(self, value: str) -> None:
        self._stored_partname = str(value or "")

    @property
    def _target(self) -> Any:
        if self._slide is not None:
            if self._slide._payload.get("_pending_creation"):
                token = self._slide._payload.get("_creation_token")
                if token is not None:
                    return token
                return self._slide
            if self._slide.partname:
                return _normalize_package_partname(self._slide.partname)
        if self._stored_partname:
            return _normalize_package_partname(self._stored_partname)
        raise AttributeError("package part is unavailable")

    @property
    def element(self) -> XmlElementProxy:
        if self._slide is not None and self._slide._payload.get("_pending_creation"):
            raise AttributeError("common slide data XML element is unavailable")
        target = self._target
        part = target if isinstance(target, str) else self._partname
        return XmlElementProxy(_common_slide_data_xml_element(self._presentation.path, part))

    @property
    def _element(self) -> XmlElementProxy:
        return self.element

    @property
    def fill(self) -> BackgroundFillFormat:
        return BackgroundFillFormat(self)

    def _stored_background(self) -> ET.Element | None:
        target = self._target
        if not isinstance(target, str):
            source = self._slide._payload.get("_source_part") if self._slide is not None else None
            if source is None:
                return None
            target = source
        common = _common_slide_data_xml_element(self._presentation.path, target)
        return find_ooxml(common, f"{{{P_NS}}}bg")

    def _pending_edit(self) -> dict[str, Any]:
        target = normalize_background_target(self._target)
        edit = self._presentation._background_fill_color_edits.get(target)
        if isinstance(edit, str):
            return {"type": "rgb", "value": edit, "brightness": 0.0}
        if isinstance(edit, dict):
            return edit
        if target in self._presentation._background_fill_solid_edits:
            return {"type": "solid"}
        if target in self._presentation._background_fill_background_edits:
            return {"type": "background"}
        return {"type": "properties"}

    def _queue_fill(self, payload: dict[str, Any]) -> None:
        properties = dict(self._pending_edit().get("_properties", {}))
        if payload["type"] == "reference":
            properties.pop("shade_to_title", None)
            properties.pop("effects", None)
        self._presentation._queue_background_fill_color(
            self._target, {**payload, "_properties": properties}
        )

    def _queue_property(self, name: str, value: Any) -> None:
        edit = dict(self._pending_edit())
        if name != "bw_mode" and self.style_reference is not None:
            edit = {"type": "background", "_properties": edit.get("_properties", {})}
        edit["_properties"] = {**edit.get("_properties", {}), name: value}
        self._presentation._queue_background_fill_color(self._target, edit)

    @property
    def bw_mode(self) -> str:
        """Stored ``p:bg@bwMode``; ``auto`` when absent. Set None to remove it."""
        pending = self._pending_edit().get("_properties", {})
        if "bw_mode" in pending:
            return pending["bw_mode"] or "auto"
        background = self._stored_background()
        return "auto" if background is None else background.get("bwMode", "auto")

    @bw_mode.setter
    def bw_mode(self, value: str | None) -> None:
        if value is not None and value not in {
            "clr",
            "auto",
            "gray",
            "ltGray",
            "invGray",
            "grayWhite",
            "blackGray",
            "blackWhite",
            "black",
            "white",
            "hidden",
        }:
            raise ValueError(f"invalid background bw_mode: {value!r}")
        self._queue_property("bw_mode", value)

    @property
    def shade_to_title(self) -> bool:
        """Stored ``bgPr@shadeToTitle``, default False. Set None to remove it."""
        pending = self._pending_edit().get("_properties", {})
        if "shade_to_title" in pending:
            return bool(pending["shade_to_title"])
        if self._pending_edit()["type"] == "reference":
            return False
        background = self._stored_background()
        props = None if background is None else find_ooxml(background, f"{{{P_NS}}}bgPr")
        return False if props is None else xml_bool_value(props.get("shadeToTitle"), False)

    @shade_to_title.setter
    def shade_to_title(self, value: bool | None) -> None:
        if value is not None and type(value) is not bool:
            raise TypeError("shade_to_title must be bool or None")
        self._queue_property("shade_to_title", value)

    @property
    def effects(self) -> str | None:
        """Detached ``a:effectLst`` or ``a:effectDag`` XML, or None when absent."""
        pending = self._pending_edit().get("_properties", {})
        if "effects" in pending:
            return pending["effects"]
        if self._pending_edit()["type"] == "reference":
            return None
        background = self._stored_background()
        props = None if background is None else find_ooxml(background, f"{{{P_NS}}}bgPr")
        if props is None:
            return None
        for tag in ("effectLst", "effectDag"):
            effect = find_ooxml(props, f"{{{A_NS}}}{tag}")
            if effect is not None:
                return ET.tostring(effect, encoding="unicode")
        return None

    @effects.setter
    def effects(self, value: str | None) -> None:
        if value is not None:
            element = _background_xml(value)
            namespace = ooxml_namespace(element, A_NS)
            if element.tag not in {f"{{{namespace}}}effectLst", f"{{{namespace}}}effectDag"}:
                raise ValueError("background effects require a:effectLst or a:effectDag")
            value = ET.tostring(element, encoding="unicode")
        self._queue_property("effects", value)

    @property
    def style_reference(self) -> dict[str, Any] | None:
        """Detached ``{'index': uint32, 'color': DrawingML XML}`` for ``p:bgRef``.

        Index 1001 is the first ``bgFillStyleLst`` entry; zero means no fill.
        Assign the complete mapping to replace bgPr with bgRef on save.
        """
        edit = self._pending_edit()
        if edit["type"] == "reference":
            return {"index": edit["index"], "color": edit["color"]}
        if edit["type"] != "properties" or any(
            key in edit.get("_properties", {}) for key in ("shade_to_title", "effects")
        ):
            return None
        background = self._stored_background()
        reference = None if background is None else find_ooxml(background, f"{{{P_NS}}}bgRef")
        if reference is None:
            return None
        if len(reference) != 1:
            raise ValueError("background style reference requires exactly one color")
        return {
            "index": int(reference.get("idx", "0")),
            "color": ET.tostring(reference[0], encoding="unicode"),
        }

    @style_reference.setter
    def style_reference(self, value: dict[str, Any]) -> None:
        if not isinstance(value, dict) or set(value) != {"index", "color"}:
            raise TypeError("style_reference requires index and color")
        index = value["index"]
        if type(index) is not int or not 0 <= index < 2**32:
            raise ValueError("background style reference index must be uint32")
        color = _background_xml(value["color"])
        validate_text_color_element(profile_element(color, ET.Element(f"{{{A_NS}}}color")))
        self._queue_fill(
            {"type": "reference", "index": index, "color": ET.tostring(color, encoding="unicode")}
        )

    @property
    def has_picture(self) -> bool:
        return self.fill.type == _fill_type_value("picture")

    @property
    def image(self) -> PictureImage:
        return self.fill.image

    @property
    def crop_left(self) -> float:
        return self.fill.crop_left

    @crop_left.setter
    def crop_left(self, value: Any) -> None:
        self.fill.crop_left = value

    @property
    def crop_top(self) -> float:
        return self.fill.crop_top

    @crop_top.setter
    def crop_top(self, value: Any) -> None:
        self.fill.crop_top = value

    @property
    def crop_right(self) -> float:
        return self.fill.crop_right

    @crop_right.setter
    def crop_right(self, value: Any) -> None:
        self.fill.crop_right = value

    @property
    def crop_bottom(self) -> float:
        return self.fill.crop_bottom

    @crop_bottom.setter
    def crop_bottom(self, value: Any) -> None:
        self.fill.crop_bottom = value


class BackgroundFillFormat:
    def __init__(self, background: Background) -> None:
        self._background = background
        self._gradient: dict[str, Any] | None = None

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    def _fill_type(self) -> str:
        return _presentation_background_fill_type(
            self._background._presentation,
            self._background._target,
            slide=self._background._slide,
        )

    def solid(self) -> None:
        self._background._queue_fill({"type": "solid"})

    def background(self) -> None:
        self._background._queue_fill({"type": "background"})

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        self._gradient = _default_gradient_payload()
        self._queue_gradient(self._gradient)

    @property
    def gradient_angle(self) -> float | None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return self._gradient_payload().get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        angle = float(value)
        if gradient.get("angle") == angle:
            return
        gradient["angle"] = angle
        self._queue_gradient(gradient)

    @property
    def gradient_stops(self) -> GradientStops:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return GradientStops(self)

    def _gradient_payload(self) -> dict[str, Any]:
        prs = self._background._presentation
        target_key = normalize_background_target(self._background._target)
        edit = prs._background_fill_color_edits.get(target_key)
        if isinstance(edit, dict) and edit.get("type") == "gradient":
            return edit["gradient"]
        if self._gradient is None:
            inherited = _presentation_background_gradient_payload(
                prs, self._background._target, slide=self._background._slide
            )
            self._gradient = (
                _default_gradient_payload() if inherited is None else deepcopy(inherited)
            )
        return self._gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        self._gradient = gradient
        self._background._queue_fill({"type": "gradient", "gradient": gradient})

    def picture(
        self,
        image_file: Any,
        crop_left: float = 0.0,
        crop_top: float = 0.0,
        crop_right: float = 0.0,
        crop_bottom: float = 0.0,
    ) -> None:
        cl = _coerce_crop_fraction(crop_left)
        ct = _coerce_crop_fraction(crop_top)
        cr = _coerce_crop_fraction(crop_right)
        cb = _coerce_crop_fraction(crop_bottom)
        image_source = _normalize_image_source(image_file)
        PictureImage.from_image_input(image_source)
        self._background._queue_fill(
            {
                "type": "picture",
                "image_source": image_source,
                "crop": {"l": cl, "t": ct, "r": cr, "b": cb},
            }
        )

    def replace_image(self, image_file: Any) -> PictureImage:
        cl = self.crop_left
        ct = self.crop_top
        cr = self.crop_right
        cb = self.crop_bottom
        image_source = _normalize_image_source(image_file)
        new_img = PictureImage.from_image_input(image_source)
        self._background._queue_fill(
            {
                "type": "picture",
                "image_source": image_source,
                "crop": {"l": cl, "t": ct, "r": cr, "b": cb},
            }
        )
        return new_img

    @property
    def image(self) -> PictureImage:
        target_key = normalize_background_target(self._background._target)
        prs = self._background._presentation
        if target_key in prs._background_fill_color_edits:
            edit = prs._background_fill_color_edits[target_key]
            if isinstance(edit, dict) and edit.get("type") == "picture":
                return PictureImage.from_image_input(edit["image_source"])
        if not isinstance(target_key, str):
            slide = self._background._slide
            if slide is not None:
                source_part = slide._payload.get("_source_part")
                if source_part:
                    return Background(prs, source_part).image
                layout = getattr(slide, "slide_layout", None)
                if layout is not None and layout.partname:
                    return layout.background.image
            raise TypeError("fill type is not picture")
        found = _background_blip_fill(prs.path, target_key)
        if found is None:
            raise TypeError("fill type is not picture")
        owner_part, blip_fill = found
        blip = blip_fill.find(f"{{{A_NS}}}blip")
        if blip is None:
            raise AttributeError("background blip is unavailable")
        embed = blip.get(f"{{{R_NS}}}embed")
        if not embed:
            raise AttributeError("background blip image relationship is unavailable")
        rel_info = _slide_relationship_info(self._background._presentation.path, owner_part, embed)
        if rel_info is None:
            raise AttributeError("background image part is unavailable")
        _type, target = rel_info
        image_part = _resolve_package_target(owner_part, target)
        return PictureImage.from_package_part(self._background._presentation, image_part)

    def _get_crop(self, key: str) -> float:
        target_key = normalize_background_target(self._background._target)
        prs = self._background._presentation
        if target_key in prs._background_fill_color_edits:
            edit = prs._background_fill_color_edits[target_key]
            if isinstance(edit, dict) and edit.get("type") == "picture":
                crop = edit.get("crop", {})
                if isinstance(crop, (list, tuple)) and len(crop) == 4:
                    idx = {"l": 0, "t": 1, "r": 2, "b": 3}[key]
                    return float(crop[idx])
                if isinstance(crop, dict):
                    return float(crop.get(key, 0.0))
        if isinstance(target_key, str):
            found = _background_blip_fill(prs.path, target_key)
            if found is not None:
                _, blip_fill = found
                src_rect = blip_fill.find(f"{{{A_NS}}}srcRect")
                if src_rect is not None:
                    try:
                        return int(src_rect.get(key, "0")) / 100000.0
                    except ValueError:
                        return 0.0
        elif self._background._slide is not None:
            source_part = self._background._slide._payload.get("_source_part")
            if source_part:
                return Background(prs, source_part).fill._get_crop(key)
            layout = getattr(self._background._slide, "slide_layout", None)
            if layout is not None and layout.partname:
                return layout.background.fill._get_crop(key)
        return 0.0

    def _set_crop(self, key: str, value: Any) -> None:
        fraction = _coerce_crop_fraction(value)
        target_key = normalize_background_target(self._background._target)
        prs = self._background._presentation
        if target_key in prs._background_fill_color_edits:
            edit = prs._background_fill_color_edits[target_key]
            if isinstance(edit, dict) and edit.get("type") == "picture":
                crop = edit.setdefault("crop", {"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.0})
                if isinstance(crop, (list, tuple)):
                    crop = {"l": crop[0], "t": crop[1], "r": crop[2], "b": crop[3]}
                    edit["crop"] = crop
                crop[key] = fraction
                return
        current_image = self.image
        crop = {
            "l": self.crop_left,
            "t": self.crop_top,
            "r": self.crop_right,
            "b": self.crop_bottom,
        }
        crop[key] = fraction
        self._background._queue_fill(
            {
                "type": "picture",
                "image_source": _normalize_image_source(current_image.blob),
                "crop": crop,
            }
        )

    @property
    def crop_left(self) -> float:
        return self._get_crop("l")

    @crop_left.setter
    def crop_left(self, value: Any) -> None:
        self._set_crop("l", value)

    @property
    def crop_top(self) -> float:
        return self._get_crop("t")

    @crop_top.setter
    def crop_top(self, value: Any) -> None:
        self._set_crop("t", value)

    @property
    def crop_right(self) -> float:
        return self._get_crop("r")

    @crop_right.setter
    def crop_right(self, value: Any) -> None:
        self._set_crop("r", value)

    @property
    def crop_bottom(self) -> float:
        return self._get_crop("b")

    @crop_bottom.setter
    def crop_bottom(self, value: Any) -> None:
        self._set_crop("b", value)

    @property
    def fore_color(self) -> BackgroundColorFormat:
        fill_type = self._fill_type()
        if fill_type not in {"solid", "patterned"}:
            raise TypeError(
                f"fill type {_FILL_CLASS_NAMES.get(fill_type, '_NoFill')} "
                "has no foreground color, call .solid() or .patterned() first"
            )
        return BackgroundColorFormat(self._background, "fore")

    @property
    def back_color(self) -> BackgroundColorFormat:
        fill_type = self._fill_type()
        if fill_type != "patterned":
            raise TypeError(
                f"fill type {_FILL_CLASS_NAMES.get(fill_type, '_NoFill')} "
                "has no background color, call .patterned() first"
            )
        return BackgroundColorFormat(self._background, "back")


class BackgroundColorFormat(ColorTextAndTransforms):
    def __init__(self, background: Background, role: str) -> None:
        self._background = background
        self._role = role

    def _color_element(self) -> ET.Element | None:
        background = self._background
        presentation = background._presentation
        target = normalize_background_target(background._target)
        edit = background._pending_edit()
        if edit["type"] == "solid" and isinstance(edit.get("rgb"), dict):
            return color_element(edit["rgb"]) if self._role == "fore" else None
        if edit["type"] in {"rgb", "scheme", "preset", "system", "xml"}:
            return color_element(edit) if self._role == "fore" else None
        if edit["type"] != "properties":
            return None
        if target in presentation._background_fill_solid_edits:
            return None
        if isinstance(target, str):
            properties = _background_properties_element(presentation.path, target)
            return fill_color_element(properties, self._role)
        slide = background._slide
        if slide is not None:
            source = slide._payload.get("_source_part")
            if source:
                return BackgroundColorFormat(
                    Background(presentation, source), self._role
                )._color_element()
            layout = getattr(slide, "slide_layout", None)
            if layout is not None and layout.partname:
                return BackgroundColorFormat(layout.background, self._role)._color_element()
        return None

    def _set_color_element(self, color: ET.Element) -> None:
        if self._background.fill._fill_type() == "patterned":
            raise ColorFormatRefusal(
                "background pattern color edits require "
                "background_edits.apply_background_fill_edits"
            )
        if self._role != "fore":
            raise ColorFormatRefusal("background back_color requires a patterned fill")
        self._background._queue_fill(
            {
                "type": "solid",
                "rgb": {"type": "xml", "value": ET.tostring(color, encoding="unicode")},
            }
        )

    def _set_base(self, tag: str, value: str) -> None:
        color = self._color_element()
        color = ET.Element(f"{{{A_NS}}}{tag}") if color is None else deepcopy(color)
        color.tag = f"{{{A_NS}}}{tag}"
        color.attrib.clear()
        color.set("val", value)
        self._set_color_element(color)

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}srgbClr":
            return None
        return _rgb_value(color.get("val"))

    @rgb.setter
    def rgb(self, value: Any) -> None:
        self._set_base("srgbClr", _normalize_rgb(value))

    @property
    def brightness(self) -> float:
        color = self._color_element()
        return 0.0 if color is None else _brightness_from_color_element(color)

    @brightness.setter
    def brightness(self, value: Any) -> None:
        brightness = float(value)
        if not -1.0 <= brightness <= 1.0:
            raise ValueError("brightness must be between -1.0 and 1.0")
        color = self._color_element()
        color = (
            ET.Element(f"{{{A_NS}}}srgbClr", {"val": "FFFFFF"})
            if color is None
            else deepcopy(color)
        )
        set_color_brightness(color, brightness)
        self._set_color_element(color)

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color is None or color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.get("val"))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        self._set_base("schemeClr", _normalize_theme_color(value))

    @property
    def type(self) -> Any:
        color = self._color_element()
        if color is None:
            return None
        kind = {
            "srgbClr": "rgb",
            "schemeClr": "scheme",
            "prstClr": "preset",
            "sysClr": "system",
        }.get(color.tag.rsplit("}", 1)[-1])
        return None if kind is None else _color_type_value(kind)


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
    common_slide_data = find_ooxml(root, f"{{{P_NS}}}cSld")
    if common_slide_data is None:
        raise AttributeError("common slide data XML element is unavailable")
    return common_slide_data


def _background_fill_type(path: Path, partname: str) -> str:
    background_properties = _background_properties_element(path, partname)
    if background_properties is None:
        return "background"
    for child in background_properties:
        if child.tag == f"{{{ooxml_namespace(child, A_NS)}}}solidFill":
            return "solid"
        if child.tag == f"{{{ooxml_namespace(child, A_NS)}}}noFill":
            return "background"
        if child.tag == f"{{{ooxml_namespace(child, A_NS)}}}pattFill":
            return "patterned"
        if child.tag == f"{{{ooxml_namespace(child, A_NS)}}}gradFill":
            return "gradient"
        if child.tag == f"{{{ooxml_namespace(child, A_NS)}}}blipFill":
            return "picture"
        if child.tag == f"{{{ooxml_namespace(child, A_NS)}}}grpFill":
            return "group"
    return "background"


def _presentation_background_fill_type(presentation: Any, target: Any, slide: Any = None) -> str:
    target_key = normalize_background_target(target)
    if target_key in presentation._background_fill_background_edits:
        return "background"
    edit = presentation._background_fill_color_edits.get(target_key)
    if isinstance(edit, dict) and edit.get("type") in {"reference", "background"}:
        return "background"
    if edit is not None and not (isinstance(edit, dict) and edit.get("type") == "properties"):
        if isinstance(edit, dict) and edit.get("type") in {"picture", "gradient"}:
            return str(edit["type"])
        return "solid"
    if target_key in presentation._background_fill_solid_edits:
        return "solid"
    if isinstance(target_key, str):
        return _background_fill_type(presentation.path, target_key)
    if slide is not None:
        source_part = slide._payload.get("_source_part")
        if source_part:
            return _presentation_background_fill_type(presentation, source_part)
        layout = getattr(slide, "slide_layout", None)
        if layout is not None and layout.partname:
            return _background_fill_type(presentation.path, layout.partname)
    return "background"


def _presentation_background_gradient_payload(
    presentation: Any, target: Any, slide: Any = None
) -> dict[str, Any] | None:
    target_key = normalize_background_target(target)
    edit = presentation._background_fill_color_edits.get(target_key)
    if isinstance(edit, dict) and edit.get("type") == "gradient":
        return edit["gradient"]
    if isinstance(target_key, str):
        return _background_gradient_payload(presentation.path, target_key)
    if slide is not None:
        source_part = slide._payload.get("_source_part")
        if source_part:
            return _presentation_background_gradient_payload(presentation, source_part)
        layout = getattr(slide, "slide_layout", None)
        if layout is not None and layout.partname:
            return _background_gradient_payload(presentation.path, layout.partname)
    return None


def _background_gradient_payload(path: Path, partname: str) -> dict[str, Any] | None:
    background_properties = _background_properties_element(path, partname)
    if background_properties is None:
        return None
    adapted = profile_element(background_properties, ET.Element(f"{{{P_NS}}}bgPr"))
    return _gradient_payload_from_fill_parent(adapted)


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
        color_parent = find_ooxml(background_properties, f"{{{A_NS}}}solidFill")
    else:
        color_parent = find_ooxml(background_properties, f"{{{A_NS}}}pattFill/{{{A_NS}}}bgClr")
    if color_parent is None:
        return None
    rgb = find_ooxml(color_parent, f"{{{A_NS}}}srgbClr")
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
    scheme = find_ooxml(color_parent, f"{{{A_NS}}}schemeClr")
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
    target: Any,
    role: str,
    slide: Any = None,
) -> str | None:
    payload = _presentation_background_fill_color_payload(presentation, target, role, slide)
    if payload is None or payload.get("type") != "rgb":
        return None
    return str(payload["value"]).upper()


def _presentation_background_fill_color_payload(
    presentation: Any,
    target: Any,
    role: str,
    slide: Any = None,
) -> dict[str, Any] | None:
    target_key = normalize_background_target(target)
    payload = presentation._background_fill_color_edits.get(target_key)
    if payload is not None and not (
        isinstance(payload, dict) and payload.get("type") == "properties"
    ):
        if role != "fore":
            return None
        if isinstance(payload, str):
            return {"type": "rgb", "value": payload.upper(), "brightness": 0.0}
        return dict(payload) if payload.get("type") in {"rgb", "scheme"} else None
    if target_key in presentation._background_fill_background_edits:
        return None
    if target_key in presentation._background_fill_solid_edits:
        return None
    if isinstance(target_key, str):
        return _background_fill_color_payload(presentation.path, target_key, role)
    if slide is not None:
        source_part = slide._payload.get("_source_part")
        if source_part:
            return _presentation_background_fill_color_payload(presentation, source_part, role)
        layout = getattr(slide, "slide_layout", None)
        if layout is not None and layout.partname:
            return _background_fill_color_payload(presentation, layout.partname, role)
    return None


def _background_properties_element(path: Path, partname: str) -> ET.Element | None:
    common_slide_data = _common_slide_data_xml_element(path, partname)
    background = find_ooxml(common_slide_data, f"{{{P_NS}}}bg")
    if background is None:
        return None
    return find_ooxml(background, f"{{{P_NS}}}bgPr")


def _brightness_from_color_element(color: ET.Element) -> float:
    lum_off = find_ooxml(color, f"{{{A_NS}}}lumOff")
    if lum_off is not None:
        return int(lum_off.attrib.get("val", "0")) / 100000.0
    lum_mod = find_ooxml(color, f"{{{A_NS}}}lumMod")
    if lum_mod is not None:
        return int(lum_mod.attrib.get("val", "100000")) / 100000.0 - 1.0
    return 0.0


def _background_xml(value: Any) -> ET.Element:
    if not isinstance(value, str):
        raise TypeError("background XML must be str")
    try:
        return ET.fromstring(value)
    except ET.ParseError as error:
        raise ValueError("invalid background XML") from error
