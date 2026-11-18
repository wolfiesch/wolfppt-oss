"""Package-backed authoring of PowerPoint slide masters, layouts and text styles."""

from __future__ import annotations

import copy
import io
import posixpath
import uuid
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr

from .comments_facade import relationships_xml as _relationships_xml
from .package_parts import XmlElementProxy, package_xml_element
from .slide_layout_edits import layout_region
from .slide_master_identity import SlideIdentities, copy_closure, copy_owned_parts
from .xml_helpers import content_types_xml as _content_types_xml
from .xml_helpers import find_ooxml, ooxml_namespace, ooxml_path, percentage_value

if TYPE_CHECKING:
    from .presentation import Presentation
    from .presentation_slides import SlideLayout, SlideMaster

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MASTER_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"
LAYOUT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"
MASTER_REL_TYPE = f"{R_NS}/slideMaster"
LAYOUT_REL_TYPE = f"{R_NS}/slideLayout"
THEME_REL_TYPE = f"{R_NS}/theme"
MASTER_REQUEST_KINDS = frozenset({"add_master", "clone_master", "extend_master"})


def _master_layout_element(presentation: Presentation, partname: str) -> XmlElementProxy:
    """Resolve authored content without publishing or consuming queued work."""
    part = _part(partname)
    for request in getattr(presentation, "_slide_master_authoring_requests", []):
        if request.get("kind") not in MASTER_REQUEST_KINDS:
            continue
        if _part(str(request["master_part"])) == part and request["kind"] != "extend_master":
            if request["kind"] == "add_master":
                return XmlElementProxy(_blank_master(str(request["name"])))
            definition = request
        else:
            definition = next(
                (layout for layout in request["layouts"] if _part(str(layout["part"])) == part),
                None,
            )
            if definition is None:
                continue
            if "layout_type" in definition:
                return XmlElementProxy(
                    _typed_layout(
                        str(definition["name"]),
                        str(definition["layout_type"]),
                        definition["slide_size"],
                    )
                )
            if "source_part" not in definition:
                return XmlElementProxy(
                    _blank_layout(
                        str(definition["name"]),
                        bool(definition["title"]),
                        bool(definition["body"]),
                    )
                )
        source_part = str(definition["source_part"])
        foreign_path = request.get("foreign_source_path")
        if isinstance(foreign_path, str) and foreign_path:
            element = package_xml_element(Path(foreign_path), source_part)
        else:
            element = _master_layout_element(presentation, source_part)
        common_slide = element._element.find(f"{{{P_NS}}}cSld")
        if common_slide is not None:
            common_slide.set("name", str(definition["name"]))
        return element
    return package_xml_element(presentation.path, partname)


def queue_master_add(presentation: Presentation, name: str) -> dict[str, Any]:
    """Stage an empty themed master and expose it through the live facade."""
    request: dict[str, Any] = {
        "kind": "add_master",
        "master_part": _next_partname(presentation, "slideMasters", "slideMaster"),
        "name": _required_name(name, "master"),
        "layouts": [],
    }
    _requests(presentation).append(request)
    return {
        "part": request["master_part"],
        "name": request["name"],
        "layout_parts": [],
        "_layout_parts_explicit": True,
    }


def queue_master_clone(
    presentation: Presentation, source: SlideMaster, name: str
) -> dict[str, Any]:
    """Stage a lossless clone of a master and every layout beneath it."""
    foreign_source = source._presentation is not presentation
    source_part = _part(source.partname)
    if not source_part:
        raise ValueError("the source slide master has no package part")
    request: dict[str, Any] = {
        "kind": "clone_master",
        "source_part": source_part,
        "master_part": _next_partname(presentation, "slideMasters", "slideMaster"),
        "name": _required_name(name, "master"),
        "layouts": [],
        "foreign_source_path": (str(source._presentation.path) if foreign_source else None),
    }
    _requests(presentation).append(request)
    for source_layout in source.slide_layouts:
        request["layouts"].append(
            {
                "source_part": _part(source_layout.partname),
                "part": _next_partname(presentation, "slideLayouts", "slideLayout"),
                "name": source_layout.name,
            }
        )
    layout_payloads = [
        {"part": layout["part"], "name": layout["name"]} for layout in request["layouts"]
    ]
    return {
        "part": request["master_part"],
        "name": request["name"],
        "layout_parts": [layout["part"] for layout in request["layouts"]],
        "_layout_parts_explicit": True,
        "_layout_payloads": layout_payloads,
    }


def queue_layout_add(
    presentation: Presentation,
    master: SlideMaster,
    name: str,
    *,
    title: bool = True,
    body: bool = True,
) -> dict[str, Any]:
    """Stage a title/body custom layout on an existing or new master."""
    if master._presentation is not presentation:
        raise ValueError("target slide master belongs to a different presentation")
    if not title and not body:
        raise ValueError("a custom layout must contain a title or body placeholder")
    placeholder_payloads = []
    if title:
        placeholder_payloads.append(_placeholder_payload("title", None))
    if body:
        placeholder_payloads.append(_placeholder_payload("body", "1"))
    layout = {
        "part": _next_partname(presentation, "slideLayouts", "slideLayout"),
        "name": _required_name(name, "layout"),
        "title": bool(title),
        "body": bool(body),
    }
    _request_for_master(presentation, _part(master.partname))["layouts"].append(layout)
    master._payload.setdefault("layout_parts", []).append(layout["part"])
    return {
        "part": layout["part"],
        "name": layout["name"],
        "_placeholder_payloads": placeholder_payloads,
    }


def queue_layout_clone(
    presentation: Presentation, master: SlideMaster, source: SlideLayout, name: str
) -> dict[str, Any]:
    """Stage a lossless clone of one layout under ``master``."""
    if master._presentation is not presentation or source._presentation is not presentation:
        raise ValueError("master and source layout must belong to this presentation")
    source_part = _part(source.partname)
    if not source_part:
        raise ValueError("the source slide layout has no package part")
    layout = {
        "source_part": source_part,
        "part": _next_partname(presentation, "slideLayouts", "slideLayout"),
        "name": _required_name(name, "layout"),
    }
    _request_for_master(presentation, _part(master.partname))["layouts"].append(layout)
    master._payload.setdefault("layout_parts", []).append(layout["part"])
    return {
        "part": layout["part"],
        "name": layout["name"],
        "_placeholder_payloads": list(source._payload.get("_placeholder_payloads", [])),
    }


# ---------------------------------------------------------------------------
# Typed layout kinds (ST_SlideLayoutType)
# ---------------------------------------------------------------------------

# ST_SlideLayoutType value -> (snake-case alias, PowerPoint default name,
# placeholder plan).  A plan entry is ``(placeholder kind, region)`` where the
# kind is a ``p:ph/@type`` (``obj`` is the schema default and written without a
# type) optionally suffixed with ``:vert`` for vertical text placeholders.
_TITLE = ("title", "title")
LAYOUT_TYPES: dict[str, tuple[str, str, tuple[tuple[str, str], ...]]] = {
    "title": (
        "title_slide",
        "Title Slide",
        (("ctrTitle", "center_title"), ("subTitle", "subtitle")),
    ),
    "tx": ("text", "Title and Text", (_TITLE, ("body", "full"))),
    "twoColTx": (
        "two_column_text",
        "Title and Two Column Text",
        (_TITLE, ("body", "left"), ("body", "right")),
    ),
    "tbl": ("table", "Title and Table", (_TITLE, ("tbl", "full"))),
    "txAndChart": (
        "text_and_chart",
        "Title, Text and Chart",
        (_TITLE, ("body", "left"), ("chart", "right")),
    ),
    "chartAndTx": (
        "chart_and_text",
        "Title, Chart and Text",
        (_TITLE, ("chart", "left"), ("body", "right")),
    ),
    "dgm": ("diagram", "Title and Diagram", (_TITLE, ("dgm", "full"))),
    "chart": ("chart", "Title and Chart", (_TITLE, ("chart", "full"))),
    "txAndClipArt": (
        "text_and_clip_art",
        "Title, Text and Clip Art",
        (_TITLE, ("body", "left"), ("clipArt", "right")),
    ),
    "clipArtAndTx": (
        "clip_art_and_text",
        "Title, Clip Art and Text",
        (_TITLE, ("clipArt", "left"), ("body", "right")),
    ),
    "titleOnly": ("title_only", "Title Only", (_TITLE,)),
    "blank": ("blank", "Blank", ()),
    "txAndObj": (
        "text_and_object",
        "Title, Text and Content",
        (_TITLE, ("body", "left"), ("obj", "right")),
    ),
    "objAndTx": (
        "object_and_text",
        "Title, Content and Text",
        (_TITLE, ("obj", "left"), ("body", "right")),
    ),
    "objOnly": ("object_only", "Content", (("obj", "whole"),)),
    "obj": ("title_and_content", "Title and Content", (_TITLE, ("obj", "full"))),
    "txAndMedia": (
        "text_and_media",
        "Title, Text and Media",
        (_TITLE, ("body", "left"), ("media", "right")),
    ),
    "mediaAndTx": (
        "media_and_text",
        "Title, Media and Text",
        (_TITLE, ("media", "left"), ("body", "right")),
    ),
    "objOverTx": (
        "object_over_text",
        "Title, Content over Text",
        (_TITLE, ("obj", "top"), ("body", "bottom")),
    ),
    "txOverObj": (
        "text_over_object",
        "Title, Text over Content",
        (_TITLE, ("body", "top"), ("obj", "bottom")),
    ),
    "txAndTwoObj": (
        "text_and_two_objects",
        "Title, Text and Two Content",
        (_TITLE, ("body", "left"), ("obj", "right_top"), ("obj", "right_bottom")),
    ),
    "twoObjAndTx": (
        "two_objects_and_text",
        "Title, Two Content and Text",
        (_TITLE, ("obj", "left_top"), ("obj", "left_bottom"), ("body", "right")),
    ),
    "twoObjOverTx": (
        "two_objects_over_text",
        "Title, Two Content over Text",
        (_TITLE, ("obj", "left_top"), ("obj", "right_top"), ("body", "bottom")),
    ),
    "fourObj": (
        "four_objects",
        "Title and Four Content",
        (
            _TITLE,
            ("obj", "left_top"),
            ("obj", "right_top"),
            ("obj", "left_bottom"),
            ("obj", "right_bottom"),
        ),
    ),
    "vertTx": (
        "vertical_text",
        "Title and Vertical Text",
        (_TITLE, ("body:vert", "full")),
    ),
    "clipArtAndVertTx": (
        "clip_art_and_vertical_text",
        "Title, Clip Art and Vertical Text",
        (_TITLE, ("clipArt", "left"), ("body:vert", "right")),
    ),
    "vertTitleAndTx": (
        "vertical_title_and_text",
        "Vertical Title and Text",
        (("title:vert", "vertical_title"), ("body:vert", "vertical_body")),
    ),
    "vertTitleAndTxOverChart": (
        "vertical_title_and_text_over_chart",
        "Vertical Title and Text Over Chart",
        (
            ("title:vert", "vertical_title"),
            ("body:vert", "vertical_body_top"),
            ("chart", "vertical_body_bottom"),
        ),
    ),
    "twoObj": (
        "two_objects",
        "Two Content",
        (_TITLE, ("obj", "left"), ("obj", "right")),
    ),
    "objAndTwoObj": (
        "object_and_two_objects",
        "Title, Content and Two Content",
        (_TITLE, ("obj", "left"), ("obj", "right_top"), ("obj", "right_bottom")),
    ),
    "twoObjAndObj": (
        "two_objects_and_object",
        "Title, Two Content and Content",
        (_TITLE, ("obj", "left_top"), ("obj", "left_bottom"), ("obj", "right")),
    ),
    "cust": ("custom", "Custom Layout", (_TITLE, ("body", "full"))),
    "secHead": (
        "section_header",
        "Section Header",
        (("title", "section_title"), ("body", "section_body")),
    ),
    "twoTxTwoObj": (
        "comparison",
        "Comparison",
        (
            _TITLE,
            ("body", "left_header"),
            ("obj", "left_under_header"),
            ("body", "right_header"),
            ("obj", "right_under_header"),
        ),
    ),
    "objTx": (
        "content_with_caption",
        "Content with Caption",
        (("title", "caption_title"), ("obj", "caption_main"), ("body", "caption_text")),
    ),
    "picTx": (
        "picture_with_caption",
        "Picture with Caption",
        (("title", "caption_title"), ("pic", "caption_main"), ("body", "caption_text")),
    ),
}
_LAYOUT_TYPE_ALIASES: dict[str, str] = {
    **{value.casefold(): value for value in LAYOUT_TYPES},
    **{alias: value for value, (alias, _, _) in LAYOUT_TYPES.items()},
    "title_and_text": "tx",
    "two_content": "twoObj",
    "title_two_content": "twoObj",
    "object": "obj",
    "content": "objOnly",
    "comparison": "twoTxTwoObj",
    "picture_caption": "picTx",
    "content_caption": "objTx",
}


def layout_type_value(layout_type: str) -> str:
    """Resolve an ST_SlideLayoutType value or its snake-case alias."""
    if not isinstance(layout_type, str):
        raise TypeError("layout type must be a string")
    key = layout_type.strip()
    resolved = _LAYOUT_TYPE_ALIASES.get(key) or _LAYOUT_TYPE_ALIASES.get(
        key.casefold().replace("-", "_").replace(" ", "_")
    )
    if resolved is None:
        raise ValueError(f"unknown slide layout type {layout_type!r}")
    return resolved


def queue_typed_layout_add(
    presentation: Presentation,
    master: SlideMaster,
    layout_type: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Stage a layout of a built-in ``ST_SlideLayoutType`` kind under ``master``."""
    if master._presentation is not presentation:
        raise ValueError("target slide master belongs to a different presentation")
    value = layout_type_value(layout_type)
    layout_name = _required_name(LAYOUT_TYPES[value][1] if name is None else name, "layout")
    slide_size = _presentation_slide_size(presentation)
    layout = {
        "part": _next_partname(presentation, "slideLayouts", "slideLayout"),
        "name": layout_name,
        "layout_type": value,
        "slide_size": slide_size,
    }
    _request_for_master(presentation, _part(master.partname))["layouts"].append(layout)
    master._payload.setdefault("layout_parts", []).append(layout["part"])
    shapes = [_placeholder_spec_payload(spec) for spec in _typed_layout_specs(value, slide_size)]
    return {
        "part": layout["part"],
        "name": layout["name"],
        "layout_type": value,
        "shapes": shapes,
        "_placeholder_payloads": [
            {**copy.deepcopy(shape), "paragraph_line_breaks": [[]]}
            for shape in shapes
            if shape["placeholder_type"] not in LATENT_PLACEHOLDER_TYPES
        ],
    }


def add_layout_of_type(
    master: SlideMaster, layout_type: str, name: str | None = None
) -> SlideLayout:
    """Add a layout of a typed kind (title, title and content, comparison, ...).

    ``layout_type`` takes an ``ST_SlideLayoutType`` value (``"obj"``,
    ``"twoTxTwoObj"``) or its alias (``"title_and_content"``,
    ``"comparison"``); ``name`` defaults to PowerPoint's name for the kind.
    The layout joins ``master.slide_layouts`` and the presentation's layout
    collection, carries the kind's placeholders plus date, footer and slide
    number placeholders, and is written on the next save.
    """
    from .presentation_slides import SlideLayout

    presentation = master._presentation
    payload = queue_typed_layout_add(presentation, master, layout_type, name)
    layouts = presentation.slide_layouts._layouts
    layout = SlideLayout(presentation, len(layouts), payload)
    layout._parent = master
    layouts.append(layout)
    return layout


def layout_type(layout: SlideLayout) -> str:
    """The layout's ``ST_SlideLayoutType`` (``"cust"`` when unspecified)."""
    staged = layout._payload.get("layout_type")
    if isinstance(staged, str):
        return staged
    return str(layout.element._element.get("type") or "cust")


def get_layout_by_type(master: SlideMaster, layout_type_name: str) -> SlideLayout | None:
    """The first layout of ``master`` with the given typed kind, if any."""
    value = layout_type_value(layout_type_name)
    return next(
        (
            layout
            for layout in master.slide_layouts
            if not layout._deleted and layout_type(layout) == value
        ),
        None,
    )


LATENT_PLACEHOLDER_TYPES = frozenset({"dt", "ftr", "sldNum"})
_FOOTER_PLAN = (("dt", "date"), ("ftr", "footer"), ("sldNum", "slide_number"))
_PLACEHOLDER_NAMES = {
    "title": "Title",
    "ctrTitle": "Title",
    "subTitle": "Subtitle",
    "body": "Text Placeholder",
    "obj": "Content Placeholder",
    "chart": "Chart Placeholder",
    "tbl": "Table Placeholder",
    "clipArt": "Clip Art Placeholder",
    "dgm": "SmartArt Placeholder",
    "media": "Media Placeholder",
    "pic": "Picture Placeholder",
    "dt": "Date Placeholder",
    "ftr": "Footer Placeholder",
    "sldNum": "Slide Number Placeholder",
    "hdr": "Header Placeholder",
}
_FOOTER_INDEXES = {"dt": "10", "ftr": "11", "sldNum": "12"}
_FOOTER_SIZES = {"dt": "half", "ftr": "quarter", "sldNum": "quarter"}
_HALF_REGIONS = frozenset({"left", "right", "top", "bottom"})
_QUARTER_REGIONS = frozenset(
    {
        "left_top",
        "right_top",
        "left_bottom",
        "right_bottom",
        "left_header",
        "right_header",
        "left_under_header",
        "right_under_header",
    }
)


def placeholder_spec(
    kind: str,
    shape_id: int,
    idx: int | None,
    box: tuple[int, int, int, int],
    *,
    vertical: bool = False,
    size: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """A placeholder description shared by typed layouts and the placeholder manager."""
    if kind not in _PLACEHOLDER_NAMES:
        raise ValueError(f"unsupported placeholder type {kind!r}")
    x, y, cx, cy = (int(value) for value in box)
    if cx <= 0 or cy <= 0:
        raise ValueError("placeholder width and height must be positive")
    label = _PLACEHOLDER_NAMES[kind]
    if vertical:
        label = "Vertical Title" if kind == "title" else f"Vertical {label}"
    return {
        "id": int(shape_id),
        "name": name or f"{label} {int(shape_id) - 1}",
        "type": kind,
        "idx": None if idx is None else int(idx),
        "orient": "vert" if vertical else None,
        "size": size,
        "box": (x, y, cx, cy),
    }


def placeholder_element(spec: dict[str, Any], part: str) -> ET.Element:
    """Build the ``p:sp`` for a placeholder spec, prompt text and fields included."""
    kind = str(spec["type"])
    shape = ET.Element(f"{{{P_NS}}}sp")
    non_visual = ET.SubElement(shape, f"{{{P_NS}}}nvSpPr")
    ET.SubElement(
        non_visual,
        f"{{{P_NS}}}cNvPr",
        {"id": str(spec["id"]), "name": str(spec["name"])},
    )
    ET.SubElement(
        ET.SubElement(non_visual, f"{{{P_NS}}}cNvSpPr"),
        f"{{{A_NS}}}spLocks",
        {"noGrp": "1"},
    )
    attrs: dict[str, str] = {}
    if kind != "obj":
        attrs["type"] = kind
    if spec.get("orient"):
        attrs["orient"] = str(spec["orient"])
    if spec.get("size"):
        attrs["sz"] = str(spec["size"])
    if spec.get("idx") is not None:
        attrs["idx"] = str(spec["idx"])
    ET.SubElement(ET.SubElement(non_visual, f"{{{P_NS}}}nvPr"), f"{{{P_NS}}}ph", attrs)
    x, y, cx, cy = spec["box"]
    transform = ET.SubElement(ET.SubElement(shape, f"{{{P_NS}}}spPr"), f"{{{A_NS}}}xfrm")
    ET.SubElement(transform, f"{{{A_NS}}}off", {"x": str(x), "y": str(y)})
    ET.SubElement(transform, f"{{{A_NS}}}ext", {"cx": str(cx), "cy": str(cy)})
    text = ET.SubElement(shape, f"{{{P_NS}}}txBody")
    ET.SubElement(
        text,
        f"{{{A_NS}}}bodyPr",
        {"vert": "eaVert"} if spec.get("orient") == "vert" else {},
    )
    ET.SubElement(text, f"{{{A_NS}}}lstStyle")
    paragraph = ET.SubElement(text, f"{{{A_NS}}}p")
    if kind == "sldNum":
        field = ET.SubElement(
            paragraph,
            f"{{{A_NS}}}fld",
            {"id": _field_guid(part, spec["id"]), "type": "slidenum"},
        )
        ET.SubElement(field, f"{{{A_NS}}}rPr", {"lang": "en-US"})
        ET.SubElement(field, f"{{{A_NS}}}t").text = "\u2039#\u203a"
    elif kind in {"title", "ctrTitle"}:
        _prompt_run(paragraph, "Click to edit Master title style")
    elif kind in {"subTitle"}:
        _prompt_run(paragraph, "Click to edit Master subtitle style")
    elif kind in {"body", "obj"}:
        _prompt_run(paragraph, "Click to edit Master text styles")
    ET.SubElement(paragraph, f"{{{A_NS}}}endParaRPr", {"lang": "en-US"})
    return shape


def _prompt_run(paragraph: ET.Element, text: str) -> None:
    run = ET.SubElement(paragraph, f"{{{A_NS}}}r")
    ET.SubElement(run, f"{{{A_NS}}}rPr", {"lang": "en-US"})
    ET.SubElement(run, f"{{{A_NS}}}t").text = text


def _field_guid(part: str, shape_id: object) -> str:
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"wolfppt:{_part(part)}#{shape_id}")
    return "{" + str(value).upper() + "}"


def _placeholder_spec_payload(spec: dict[str, Any]) -> dict[str, Any]:
    """The facade shape payload equivalent to what a reload of ``spec`` reads."""
    x, y, cx, cy = spec["box"]
    kind = str(spec["type"])
    latent = kind in LATENT_PLACEHOLDER_TYPES
    return {
        "id": str(spec["id"]),
        "name": str(spec["name"]),
        "kind": "shape",
        "text": "",
        "paragraphs": [] if latent else [""],
        "paragraph_runs": [] if latent else [[]],
        "is_placeholder": True,
        "locks": {},
        "transform": {"x": x, "y": y, "cx": cx, "cy": cy},
        "placeholder_type": None if kind == "obj" else kind,
        "placeholder_idx": "0" if spec.get("idx") is None else str(spec["idx"]),
        "placeholder_orient": spec.get("orient"),
        "placeholder_size": spec.get("size"),
    }


def _typed_layout_specs(layout_type_name: str, slide_size: tuple[int, int]) -> list[dict[str, Any]]:
    width, height = slide_size
    specs: list[dict[str, Any]] = []
    next_idx = 1
    for entry, region in LAYOUT_TYPES[layout_type_name][2]:
        kind, _, orient = entry.partition(":")
        idx = None
        if kind not in {"title", "ctrTitle"}:
            idx = next_idx
            next_idx += 1
        size = (
            "half" if region in _HALF_REGIONS else "quarter" if region in _QUARTER_REGIONS else None
        )
        specs.append(
            placeholder_spec(
                kind,
                len(specs) + 2,
                idx,
                layout_region(region, width, height),
                vertical=orient == "vert",
                size=size if kind not in {"title", "ctrTitle"} else None,
            )
        )
    for kind, region in _FOOTER_PLAN:
        specs.append(
            placeholder_spec(
                kind,
                len(specs) + 2,
                int(_FOOTER_INDEXES[kind]),
                layout_region(region, width, height),
                size=_FOOTER_SIZES[kind],
            )
        )
    return specs


def _typed_layout(
    name: str, layout_type_name: str, slide_size: tuple[int, int] | list[int]
) -> ET.Element:
    width, height = (int(value) for value in slide_size)
    root = ET.Element(f"{{{P_NS}}}sldLayout", {"type": layout_type_name, "preserve": "1"})
    c_sld = ET.SubElement(root, f"{{{P_NS}}}cSld", {"name": name})
    tree = _shape_tree(c_sld)
    for spec in _typed_layout_specs(layout_type_name, (width, height)):
        tree.append(placeholder_element(spec, f"layout:{name}"))
    override = ET.SubElement(root, f"{{{P_NS}}}clrMapOvr")
    ET.SubElement(override, f"{{{A_NS}}}masterClrMapping")
    return root


def _presentation_slide_size(presentation: Presentation) -> tuple[int, int]:
    root = package_xml_element(presentation.path, "ppt/presentation.xml")._element
    size = root.find(f"{{{P_NS}}}sldSz")
    if size is None:
        return (9144000, 6858000)
    return (int(size.get("cx", "9144000")), int(size.get("cy", "6858000")))


# ---------------------------------------------------------------------------
# Master and notes-master text styles (p:txStyles, p:notesStyle)
# ---------------------------------------------------------------------------

TEXT_STYLE_LEVELS = 9
_LIST_ORDER = ("defPPr", *(f"lvl{n}pPr" for n in range(1, 10)), "extLst")
_TX_STYLES_ORDER = ("titleStyle", "bodyStyle", "otherStyle", "extLst")
_PPR_ORDER = (
    "lnSpc",
    "spcBef",
    "spcAft",
    "buClrTx",
    "buClr",
    "buSzTx",
    "buSzPct",
    "buSzPts",
    "buFontTx",
    "buFont",
    "buNone",
    "buAutoNum",
    "buChar",
    "buBlip",
    "tabLst",
    "defRPr",
    "extLst",
)
_RPR_ORDER = (
    "ln",
    "noFill",
    "solidFill",
    "gradFill",
    "blipFill",
    "pattFill",
    "grpFill",
    "effectLst",
    "effectDag",
    "highlight",
    "uLnTx",
    "uLn",
    "uFillTx",
    "uFill",
    "latin",
    "ea",
    "cs",
    "sym",
    "hlinkClick",
    "hlinkMouseOver",
    "rtl",
    "extLst",
)
_FILLS = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")
_BULLET_KINDS = ("buNone", "buAutoNum", "buChar", "buBlip")
_BULLET_COLORS = ("buClrTx", "buClr")
_BULLET_SIZES = ("buSzTx", "buSzPct", "buSzPts")
_BULLET_FONTS = ("buFontTx", "buFont")
_ALIGNMENTS = frozenset({"l", "ctr", "r", "just", "justLow", "dist", "thaiDist"})
_SCHEME_COLORS = frozenset(
    {
        "bg1",
        "tx1",
        "bg2",
        "tx2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "hlink",
        "folHlink",
        "phClr",
        "dk1",
        "lt1",
        "dk2",
        "lt2",
    }
)
AUTONUMBER_SCHEMES = frozenset(
    {
        "alphaLcParenBoth",
        "alphaUcParenBoth",
        "alphaLcParenR",
        "alphaUcParenR",
        "alphaLcPeriod",
        "alphaUcPeriod",
        "arabicParenBoth",
        "arabicParenR",
        "arabicPeriod",
        "arabicPlain",
        "romanLcParenBoth",
        "romanUcParenBoth",
        "romanLcParenR",
        "romanUcParenR",
        "romanLcPeriod",
        "romanUcPeriod",
        "circleNumDbPlain",
        "circleNumWdBlackPlain",
        "circleNumWdWhitePlain",
        "arabicDbPeriod",
        "arabicDbPlain",
        "ea1ChsPeriod",
        "ea1ChsPlain",
        "ea1ChtPeriod",
        "ea1ChtPlain",
        "ea1JpnChsDbPeriod",
        "ea1JpnKorPlain",
        "ea1JpnKorPeriod",
        "arabic1Minus",
        "arabic2Minus",
        "hebrew2Minus",
        "thaiAlphaPeriod",
        "thaiAlphaParenR",
        "thaiAlphaParenBoth",
        "thaiNumPeriod",
        "thaiNumParenR",
        "thaiNumParenBoth",
        "hindiAlphaPeriod",
        "hindiNumPeriod",
        "hindiNumParenR",
        "hindiAlpha1Period",
    }
)
_MAX_MARGIN = 51206400


class _StyleDocument:
    """Working copy of one part's text-style element, staged as one save request.

    Every facade over the same unsaved part shares the pending request, so
    edits made through different handles accumulate instead of racing.
    """

    def __init__(
        self, presentation: Presentation, part: str, local: str, source: ET.Element
    ) -> None:
        self._presentation = presentation
        pending = next(
            (
                request
                for request in _requests(presentation)
                if request.get("kind") == "text_styles"
                and request.get("part") == part
                and request.get("local") == local
            ),
            None,
        )
        if pending is None:
            existing = find_ooxml(source, f"{{{P_NS}}}{local}")
            element = (
                copy.deepcopy(existing)
                if existing is not None
                else ET.Element(ooxml_path(source, f"{{{P_NS}}}{local}"))
            )
            pending = {
                "kind": "text_styles",
                "part": part,
                "local": local,
                "element": element,
            }
        self._request = pending

    @property
    def element(self) -> ET.Element:
        return self._request["element"]

    def touch(self) -> None:
        requests = _requests(self._presentation)
        if not any(request is self._request for request in requests):
            requests.append(self._request)


class TextStyleLevel:
    """One paragraph level (``a:lvlNpPr``) of a master or notes text style.

    Getters report what this level sets explicitly (``None`` = inherited);
    setters stage the change, and ``None`` removes the explicit value.
    Sizes and spacing are in points, margins and indents in EMU, colours as
    ``"RRGGBB"``.
    """

    def __init__(self, style: TextStyle, level: int) -> None:
        self._style = style
        self._level = level

    @property
    def level(self) -> int:
        """One-based outline level (1-9)."""
        return self._level

    def _ppr(self, create: bool = False) -> ET.Element | None:
        return self._style._level_element(self._level, create)

    def _rpr(self, create: bool = False) -> ET.Element | None:
        ppr = self._ppr(create)
        if ppr is None:
            return None
        rpr = find_ooxml(ppr, f"{{{A_NS}}}defRPr")
        if rpr is None and create:
            rpr = _insert_ordered(ppr, "defRPr", _PPR_ORDER)
        return rpr

    def _child(self, parent: ET.Element | None, local: str) -> ET.Element | None:
        return None if parent is None else find_ooxml(parent, f"{{{A_NS}}}{local}")

    def _set_attr(self, element: ET.Element | None, name: str, value: str | None) -> None:
        if element is None:
            return
        if value is None:
            element.attrib.pop(name, None)
        else:
            element.set(name, value)
        self._style._document.touch()

    # -- run defaults -----------------------------------------------------

    @property
    def font_name(self) -> str | None:
        latin = self._child(self._rpr(), "latin")
        return None if latin is None else latin.get("typeface")

    @font_name.setter
    def font_name(self, value: str | None) -> None:
        if value is None:
            self._remove(self._rpr(), ("latin",))
            return
        if not isinstance(value, str) or not value.strip():
            raise ValueError("font name must be a non-empty string")
        rpr = self._rpr(True)
        _insert_ordered(rpr, "latin", _RPR_ORDER).set("typeface", value.strip())
        self._style._document.touch()

    @property
    def font_size(self) -> float | None:
        rpr = self._rpr()
        raw = None if rpr is None else rpr.get("sz")
        return None if raw is None else int(raw) / 100

    @font_size.setter
    def font_size(self, value: float | None) -> None:
        size = None if value is None else str(_hundredths(value, 1, 4000, "font size"))
        self._set_attr(self._rpr(value is not None), "sz", size)

    @property
    def bold(self) -> bool | None:
        return _xsd_bool(self._rpr(), "b")

    @bold.setter
    def bold(self, value: bool | None) -> None:
        self._set_attr(self._rpr(value is not None), "b", _bool_attr(value))

    @property
    def italic(self) -> bool | None:
        return _xsd_bool(self._rpr(), "i")

    @italic.setter
    def italic(self, value: bool | None) -> None:
        self._set_attr(self._rpr(value is not None), "i", _bool_attr(value))

    @property
    def color(self) -> str | None:
        """Explicit sRGB run colour as ``"RRGGBB"``."""
        rgb = self._child(self._child(self._rpr(), "solidFill"), "srgbClr")
        return None if rgb is None else rgb.get("val")

    @color.setter
    def color(self, value: str | None) -> None:
        if value is None:
            self._remove(self._rpr(), _FILLS)
            return
        rgb = _rgb(value)
        _set_fill(self._rpr(True), "srgbClr", rgb, _RPR_ORDER, _FILLS)
        self._style._document.touch()

    @property
    def theme_color(self) -> str | None:
        """Explicit theme run colour (``"tx1"``, ``"accent2"`` ...)."""
        scheme = self._child(self._child(self._rpr(), "solidFill"), "schemeClr")
        return None if scheme is None else scheme.get("val")

    @theme_color.setter
    def theme_color(self, value: str | None) -> None:
        if value is None:
            self._remove(self._rpr(), _FILLS)
            return
        scheme = _scheme(value)
        _set_fill(self._rpr(True), "schemeClr", scheme, _RPR_ORDER, _FILLS)
        self._style._document.touch()

    # -- paragraph layout -------------------------------------------------

    @property
    def alignment(self) -> str | None:
        ppr = self._ppr()
        return None if ppr is None else ppr.get("algn")

    @alignment.setter
    def alignment(self, value: str | None) -> None:
        if value is not None and value not in _ALIGNMENTS:
            raise ValueError(f"alignment must be one of {sorted(_ALIGNMENTS)}")
        self._set_attr(self._ppr(value is not None), "algn", value)

    @property
    def margin_left(self) -> int | None:
        return _int_attr(self._ppr(), "marL")

    @margin_left.setter
    def margin_left(self, value: int | None) -> None:
        margin = None if value is None else str(_bounded(value, 0, _MAX_MARGIN, "margin"))
        self._set_attr(self._ppr(value is not None), "marL", margin)

    @property
    def indent(self) -> int | None:
        return _int_attr(self._ppr(), "indent")

    @indent.setter
    def indent(self, value: int | None) -> None:
        indent = (
            None if value is None else str(_bounded(value, -_MAX_MARGIN, _MAX_MARGIN, "indent"))
        )
        self._set_attr(self._ppr(value is not None), "indent", indent)

    @property
    def space_before(self) -> float | None:
        return self._spacing("spcBef")

    @space_before.setter
    def space_before(self, value: float | None) -> None:
        self._set_spacing("spcBef", value)

    @property
    def space_after(self) -> float | None:
        return self._spacing("spcAft")

    @space_after.setter
    def space_after(self, value: float | None) -> None:
        self._set_spacing("spcAft", value)

    @property
    def line_spacing(self) -> float | None:
        """Line spacing as a multiple of single spacing (1.0 = 100%)."""
        percent = self._child(self._child(self._ppr(), "lnSpc"), "spcPct")
        raw = None if percent is None else percent.get("val")
        return None if raw is None else percentage_value(percent, raw)

    @line_spacing.setter
    def line_spacing(self, value: float | None) -> None:
        if value is None:
            self._remove(self._ppr(), ("lnSpc",))
            return
        val = _bounded(round(float(value) * 100000), 0, 13200000, "line spacing")
        spacing = _insert_ordered(self._ppr(True), "lnSpc", _PPR_ORDER)
        ET.SubElement(
            spacing,
            ooxml_path(spacing, f"{{{A_NS}}}spcPct"),
            {"val": _percentage_text(spacing, val)},
        )
        self._style._document.touch()

    def _spacing(self, local: str) -> float | None:
        points = self._child(self._child(self._ppr(), local), "spcPts")
        return None if points is None else int(points.get("val", "0")) / 100

    def _set_spacing(self, local: str, value: float | None) -> None:
        if value is None:
            self._remove(self._ppr(), (local,))
            return
        points = str(_hundredths(value, 0, 1584, "paragraph spacing"))
        spacing = _insert_ordered(self._ppr(True), local, _PPR_ORDER)
        ET.SubElement(
            spacing,
            ooxml_path(spacing, f"{{{A_NS}}}spcPts"),
            {"val": points},
        )
        self._style._document.touch()

    # -- bullets ----------------------------------------------------------

    @property
    def bullet_type(self) -> str | None:
        """``"none"``, ``"char"``, ``"numbered"``, ``"picture"`` or ``None``."""
        ppr = self._ppr()
        for local, name in (
            ("buNone", "none"),
            ("buChar", "char"),
            ("buAutoNum", "numbered"),
            ("buBlip", "picture"),
        ):
            if self._child(ppr, local) is not None:
                return name
        return None

    @property
    def bullet_char(self) -> str | None:
        char = self._child(self._ppr(), "buChar")
        return None if char is None else char.get("char")

    @property
    def bullet_font(self) -> str | None:
        font = self._child(self._ppr(), "buFont")
        return None if font is None else font.get("typeface")

    @property
    def bullet_color(self) -> str | None:
        rgb = self._child(self._child(self._ppr(), "buClr"), "srgbClr")
        return None if rgb is None else rgb.get("val")

    @property
    def bullet_size(self) -> float | None:
        """Bullet size relative to the text (1.0 = 100%)."""
        size = self._child(self._ppr(), "buSzPct")
        return None if size is None else percentage_value(size, size.get("val", "0"))

    @property
    def bullet_numbering(self) -> tuple[str, int] | None:
        """``(scheme, start_at)`` of an automatic numbering bullet."""
        number = self._child(self._ppr(), "buAutoNum")
        if number is None:
            return None
        return (str(number.get("type")), int(number.get("startAt", "1")))

    def set_bullet_char(
        self,
        char: str,
        *,
        font: str | None = None,
        color: str | None = None,
        size: float | None = None,
    ) -> None:
        """Use a character bullet, optionally with its own font, colour and size."""
        if not isinstance(char, str) or len(char) != 1:
            raise ValueError("bullet character must be a single character")
        font, color, size = self._bullet_decorations(font, color, size)
        ppr = self._ppr(True)
        self._set_bullet_decorations(ppr, font=font, color=color, size=size)
        _insert_ordered(ppr, "buChar", _PPR_ORDER, _BULLET_KINDS).set("char", char)
        self._style._document.touch()

    def set_bullet_numbered(
        self,
        scheme: str = "arabicPeriod",
        start_at: int | None = None,
        *,
        color: str | None = None,
        size: float | None = None,
    ) -> None:
        """Use automatic numbering (an ``ST_TextAutonumberScheme`` value)."""
        if scheme not in AUTONUMBER_SCHEMES:
            raise ValueError(f"unknown autonumber scheme {scheme!r}")
        start = None if start_at is None else str(_bounded(start_at, 1, 32767, "start value"))
        _, color, size = self._bullet_decorations(None, color, size)
        ppr = self._ppr(True)
        self._set_bullet_decorations(ppr, font=None, color=color, size=size)
        number = _insert_ordered(ppr, "buAutoNum", _PPR_ORDER, _BULLET_KINDS)
        number.set("type", scheme)
        if start is not None:
            number.set("startAt", start)
        self._style._document.touch()

    def set_no_bullet(self) -> None:
        """Suppress bullets at this level."""
        ppr = self._ppr(True)
        _insert_ordered(ppr, "buNone", _PPR_ORDER, _BULLET_KINDS)
        self._style._document.touch()

    def clear_bullet(self) -> None:
        """Inherit bullets again from the theme/presentation defaults."""
        self._remove(
            self._ppr(),
            (*_BULLET_KINDS, *_BULLET_COLORS, *_BULLET_SIZES, *_BULLET_FONTS),
        )

    @staticmethod
    def _bullet_decorations(
        font: str | None, color: str | None, size: float | None
    ) -> tuple[str | None, str | None, int | None]:
        """Validate every decoration before creating or replacing any XML."""
        rgb = None if color is None else _rgb(color)
        pct = (
            None
            if size is None
            else _bounded(round(float(size) * 100000), 25000, 400000, "bullet size")
        )
        if font is not None:
            if not isinstance(font, str) or not font.strip():
                raise ValueError("bullet font must be a non-empty string")
            font = font.strip()
        return font, rgb, pct

    def _set_bullet_decorations(
        self,
        ppr: ET.Element,
        *,
        font: str | None,
        color: str | None,
        size: int | None,
    ) -> None:
        if color is not None:
            _set_fill(ppr, "srgbClr", color, _PPR_ORDER, _BULLET_COLORS, "buClr")
        if size is not None:
            _insert_ordered(ppr, "buSzPct", _PPR_ORDER, _BULLET_SIZES).set(
                "val", _percentage_text(ppr, size)
            )
        if font is not None:
            _insert_ordered(ppr, "buFont", _PPR_ORDER, _BULLET_FONTS).set("typeface", font)

    def _remove(self, parent: ET.Element | None, locals_: Sequence[str]) -> None:
        if parent is None:
            return
        for child in list(parent):
            if _local(child.tag) in locals_:
                parent.remove(child)
        self._style._document.touch()

    def __repr__(self) -> str:
        return f"<TextStyleLevel {self._level} of {self._style.name}>"


class TextStyle(Sequence[TextStyleLevel]):
    """Nine paragraph levels of a master title/body/other or notes text style."""

    def __init__(self, document: _StyleDocument, name: str | None) -> None:
        self._document = document
        self._name = name
        self._levels = [TextStyleLevel(self, level) for level in range(1, TEXT_STYLE_LEVELS + 1)]

    @property
    def name(self) -> str:
        return self._name or self._document._request["local"]

    def level(self, number: int) -> TextStyleLevel:
        """The one-based outline level ``number`` (1-9)."""
        if not 1 <= int(number) <= TEXT_STYLE_LEVELS:
            raise IndexError("text style levels are numbered 1-9")
        return self._levels[int(number) - 1]

    def __getitem__(self, index: int) -> TextStyleLevel:  # type: ignore[override]
        return self._levels[index]

    def __iter__(self) -> Iterator[TextStyleLevel]:
        return iter(self._levels)

    def __len__(self) -> int:
        return TEXT_STYLE_LEVELS

    def _list_element(self, create: bool) -> ET.Element | None:
        root = self._document.element
        if self._name is None:
            return root
        element = find_ooxml(root, f"{{{P_NS}}}{self._name}")
        if element is None and create:
            element = _insert_ordered(root, self._name, _TX_STYLES_ORDER, ns=P_NS)
        return element

    def _level_element(self, level: int, create: bool) -> ET.Element | None:
        container = self._list_element(create)
        if container is None:
            return None
        local = f"lvl{level}pPr"
        element = find_ooxml(container, f"{{{A_NS}}}{local}")
        if element is None and create:
            element = _insert_ordered(container, local, _LIST_ORDER)
        return element

    def __repr__(self) -> str:
        return f"<TextStyle {self.name}>"


class MasterTextStyles:
    """The title, body and other text styles (``p:txStyles``) of a slide master.

    Placeholders and text on the master's layouts and slides inherit these
    styles unless they override them; edits are written on the next save.
    """

    def __init__(self, master: SlideMaster) -> None:
        part = _part(master.partname)
        if not part:
            raise ValueError("the slide master has no package part")
        source = _master_layout_element(master._presentation, part)._element
        self._document = _StyleDocument(master._presentation, part, "txStyles", source)
        self.title_style = TextStyle(self._document, "titleStyle")
        self.body_style = TextStyle(self._document, "bodyStyle")
        self.other_style = TextStyle(self._document, "otherStyle")

    def __iter__(self) -> Iterator[TextStyle]:
        return iter((self.title_style, self.body_style, self.other_style))


def master_text_styles(master: SlideMaster) -> MasterTextStyles:
    """Editable title/body/other text styles of ``master``."""
    return MasterTextStyles(master)


def notes_master_text_style(notes_master: Any) -> TextStyle:
    """Editable nine-level notes text style (``p:notesStyle``) of a notes master."""
    presentation = notes_master._presentation
    part = _part(notes_master.partname)
    source = package_xml_element(presentation.path, part)._element
    return TextStyle(_StyleDocument(presentation, part, "notesStyle", source), None)


def _apply_text_styles(parts: dict[str, bytes], request: dict[str, Any]) -> None:
    part = _existing_part(parts, request["part"], "text style")
    fragment = xml_fragment(request["element"], parts[part])
    parts[part] = splice_root_child(parts[part], str(request["local"]), fragment, ("extLst",))


def _preserve_style_extensions(source: bytes, rewritten: bytes) -> bytes:
    """Keep opaque style extLst bytes and their original namespace bindings."""
    from .presentation_save_state import _element_spans

    original = _element_spans(source)
    output = _element_spans(rewritten)
    root = next(
        (index for index, node in enumerate(original) if node["tag"] == output[0]["tag"]),
        None,
    )
    if root is None:
        return rewritten

    def paths(nodes: list[dict[str, Any]], start: int) -> dict[int, tuple[str, ...]]:
        result = {start: ()}
        for index, node in enumerate(nodes[start + 1 :], start + 1):
            if node["parent"] in result:
                result[index] = (*result[node["parent"]], node["tag"])
        return result

    original_paths = paths(original, root)
    targets = {path: index for index, path in paths(output, 0).items()}
    scopes: list[dict[str, str]] = []
    declarations: list[dict[str, str]] = []
    stack: list[dict[str, str]] = []
    pending: dict[str, str] = {}
    for event, value in ET.iterparse(io.BytesIO(source), events=("start-ns", "start", "end")):
        if event == "start-ns":
            pending[value[0]] = value[1]
        elif event == "start":
            scope = (stack[-1] if stack else {}) | pending
            declarations.append(pending)
            pending = {}
            stack.append(scope)
            scopes.append(scope)
        else:
            stack.pop()
    replacements = []
    for index, path in original_paths.items():
        if not path or _local(path[-1]) != "extLst":
            continue
        if not any(_local(tag) in {"txStyles", "notesStyle"} for tag in (output[0]["tag"], *path)):
            continue
        if any(_local(tag) == "extLst" for tag in path[:-1]) or path not in targets:
            continue
        node = original[index]
        raw = source[node["start"] : node["end"]]
        end = raw.index(b">")
        insert = end - 1 if raw[:end].endswith(b"/") else end
        # Ancestor declarations keep opaque QName-valued attributes meaningful too.
        inherited = "".join(
            f" xmlns{':' + prefix if prefix else ''}={quoteattr(uri)}"
            for prefix, uri in scopes[index].items()
            if prefix not in declarations[index]
        ).encode()
        raw = raw[:insert] + inherited + raw[insert:]
        target = output[targets[path]]
        replacements.append((target["start"], target["end"], raw))
    for start, end, raw in sorted(replacements, reverse=True):
        rewritten = rewritten[:start] + raw + rewritten[end:]
    return rewritten


def xml_fragment(element: ET.Element, payload: bytes) -> bytes:
    """Serialize ``element`` for splicing into ``payload``.

    Declarations the document element already makes for the conventional
    ``a:``/``p:``/``r:`` prefixes are dropped, so the fragment reads exactly
    like PowerPoint-authored markup (native readers match those prefixes).
    """
    from .section_xml import _root_prefixes

    _register_namespaces()
    namespaces = tuple(
        (prefix, ooxml_namespace(element, uri))
        for prefix, uri in (("a", A_NS), ("p", P_NS), ("r", R_NS))
    )
    for prefix, uri in namespaces:
        ET.register_namespace(prefix, uri)
    serialized = ET.tostring(element, encoding="utf-8")
    if _local(element.tag) in {"txStyles", "notesStyle"}:
        serialized = _preserve_style_extensions(payload, serialized)
    text = serialized.decode("utf-8")
    head_end = text.index(">")
    head = text[:head_end]
    declared = _root_prefixes(payload)
    for prefix, uri in namespaces:
        if declared.get(prefix) == uri:
            head = head.replace(f' xmlns:{prefix}="{uri}"', "")
    return (head + text[head_end:]).encode("utf-8")


def splice_root_child(
    payload: bytes, local: str, fragment: bytes, following: Sequence[str]
) -> bytes:
    """Replace (or insert) one PresentationML child of the document element.

    Every other byte is kept, so prefixes, declarations and ``mc:Ignorable``
    tokens keep resolving. A new child goes before the first ``following``
    sibling, or last.
    """
    from .presentation_save_state import _element_spans

    nodes = _element_spans(payload)
    children = [node for node in nodes if node["parent"] == 0]
    namespace = nodes[0]["tag"].split("}")[0] + "}"
    for node in children:
        if node["tag"] == f"{namespace}{local}":
            return payload[: node["start"]] + fragment + payload[node["end"] :]
    anchor = next(
        (
            node["start"]
            for node in children
            if node["tag"] in {f"{namespace}{name}" for name in following}
        ),
        None,
    )
    if anchor is None:
        anchor = payload.rindex(b"</", 0, nodes[0]["end"])
    return payload[:anchor] + fragment + payload[anchor:]


def _insert_ordered(
    parent: ET.Element,
    local: str,
    order: Sequence[str],
    replaces: Sequence[str] = (),
    *,
    ns: str = A_NS,
) -> ET.Element:
    """Insert a fresh ``local`` child at its schema position, dropping rivals."""
    for child in list(parent):
        if _local(child.tag) == local or _local(child.tag) in replaces:
            parent.remove(child)
    rank = order.index(local)
    position = len(parent)
    for index, child in enumerate(parent):
        name = _local(child.tag)
        if name in order and order.index(name) > rank:
            position = index
            break
    element = ET.Element(ooxml_path(parent, f"{{{ns}}}{local}"))
    parent.insert(position, element)
    return element


def _set_fill(
    parent: ET.Element,
    color_local: str,
    value: str,
    order: Sequence[str],
    rivals: Sequence[str],
    local: str = "solidFill",
) -> None:
    holder = _insert_ordered(parent, local, order, rivals)
    ET.SubElement(holder, ooxml_path(holder, f"{{{A_NS}}}{color_local}"), {"val": value})


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _rgb(value: str) -> str:
    text = str(value).lstrip("#").upper()
    if len(text) != 6 or any(char not in "0123456789ABCDEF" for char in text):
        raise ValueError("colour must be a six-digit RRGGBB hex string")
    return text


def _scheme(value: str) -> str:
    if value not in _SCHEME_COLORS:
        raise ValueError(f"theme colour must be one of {sorted(_SCHEME_COLORS)}")
    return value


def _hundredths(value: float, low: float, high: float, label: str) -> int:
    number = float(value)
    if not low <= number <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g} points")
    return round(number * 100)


def _bounded(value: int, low: int, high: int, label: str) -> int:
    number = int(value)
    if not low <= number <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return number


def _percentage_text(element: ET.Element, thousandths: int) -> str:
    if ooxml_namespace(element, A_NS) != A_NS:
        return f"{thousandths / 1000:.3f}".rstrip("0").rstrip(".") + "%"
    return str(thousandths)


def _bool_attr(value: bool | None) -> str | None:
    return None if value is None else ("1" if value else "0")


def _xsd_bool(element: ET.Element | None, name: str) -> bool | None:
    raw = None if element is None else element.get(name)
    return None if raw is None else raw in {"1", "true"}


def _int_attr(element: ET.Element | None, name: str) -> int | None:
    raw = None if element is None else element.get(name)
    return None if raw is None else int(raw)


def apply_slide_master_authoring(
    input_path: Path, output_path: Path, requests: list[dict[str, Any]]
) -> None:
    """Apply staged master/layout changes in a single atomic package rewrite."""
    if not requests:
        _copy_package(input_path, output_path, {})
        return
    with zipfile.ZipFile(input_path) as package:
        parts = {info.filename: package.read(info.filename) for info in package.infolist()}
    presentation_part = "ppt/presentation.xml"
    if presentation_part not in parts:
        raise ValueError("PPTX package is missing ppt/presentation.xml")
    presentation = ET.fromstring(parts[presentation_part])
    presentation_rels_name = _rels_partname(presentation_part)
    presentation_rels = ET.fromstring(parts[presentation_rels_name])
    content_types = ET.fromstring(parts["[Content_Types].xml"])
    identities = SlideIdentities(parts, presentation)
    handout_requests: list[dict[str, Any]] = []
    for request in requests:
        kind = request.get("kind")
        if kind == "add_master":
            _apply_new_master(
                parts, presentation, presentation_rels, content_types, identities, request
            )
        elif kind == "clone_master":
            _apply_master_clone(
                parts, presentation, presentation_rels, content_types, identities, request
            )
        elif kind == "extend_master":
            _apply_master_extension(parts, content_types, identities, request)
        elif kind == "text_styles":
            _apply_text_styles(parts, request)
        elif kind == "layout_placeholders":
            from .slide_layout_edits import apply_layout_placeholder_request

            apply_layout_placeholder_request(parts, request)
        elif kind == "handout_header_footer":
            handout_requests.append(request)
        else:
            raise ValueError(f"unsupported slide master authoring request {kind!r}")
    _register_namespaces()
    parts[presentation_part] = ET.tostring(presentation, encoding="utf-8", xml_declaration=True)
    parts[presentation_rels_name] = _relationships_xml(presentation_rels)
    parts["[Content_Types].xml"] = _content_types_xml(content_types)
    if handout_requests:
        # Handout edits rewrite presentation-level parts, so they run on the
        # serialized package after every master/layout request has landed.
        from .handout_master_edits import apply_handout_header_footer_request

        for request in handout_requests:
            apply_handout_header_footer_request(parts, request)
    _copy_package(input_path, output_path, parts)


def _apply_new_master(
    parts: dict[str, bytes],
    presentation: ET.Element,
    presentation_rels: ET.Element,
    content_types: ET.Element,
    identities: SlideIdentities,
    request: dict[str, Any],
) -> None:
    master_part = _new_part(parts, request["master_part"], "slide master")
    master = _blank_master(str(request["name"]))
    rels = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(
        rels,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": THEME_REL_TYPE,
            "Target": _theme_target(parts, presentation, presentation_rels),
        },
    )
    _add_master_to_presentation(presentation, presentation_rels, master_part, identities)
    _ensure_content_type(content_types, master_part, MASTER_CONTENT_TYPE)
    _write_master(parts, master_part, master, rels, content_types, identities, request["layouts"])


def _apply_master_clone(
    parts: dict[str, bytes],
    presentation: ET.Element,
    presentation_rels: ET.Element,
    content_types: ET.Element,
    identities: SlideIdentities,
    request: dict[str, Any],
) -> None:
    source_part = _part(str(request["source_part"]))
    master_part = _part(str(request["master_part"]))
    foreign_source_path = request.get("foreign_source_path")
    if isinstance(foreign_source_path, str) and foreign_source_path:
        with zipfile.ZipFile(foreign_source_path) as package:
            source_parts = {
                info.filename: package.read(info.filename) for info in package.infolist()
            }
        roots = {source_part: master_part} | {
            _part(str(layout["source_part"])): _part(str(layout["part"]))
            for layout in request["layouts"]
        }
        copy_closure(parts, content_types, source_parts, roots)
        _add_master_to_presentation(presentation, presentation_rels, master_part, identities)
        master = ET.fromstring(parts[master_part])
        c_sld = master.find(f"{{{P_NS}}}cSld")
        if c_sld is not None:
            c_sld.set("name", str(request["name"]))
        for layout_id in master.iter(f"{{{P_NS}}}sldLayoutId"):
            layout_id.set("id", str(identities.take()))
        parts[master_part] = _preserve_style_extensions(
            parts[master_part],
            ET.tostring(master, encoding="utf-8", xml_declaration=True),
        )
        for layout in request["layouts"]:
            layout_part = _part(str(layout["part"]))
            layout_xml = ET.fromstring(parts[layout_part])
            layout_c_sld = layout_xml.find(f"{{{P_NS}}}cSld")
            if layout_c_sld is not None:
                layout_c_sld.set("name", str(layout["name"]))
            parts[layout_part] = ET.tostring(layout_xml, encoding="utf-8", xml_declaration=True)
        return
    source_part = _existing_part(parts, request["source_part"], "source slide master")
    master_part = _new_part(parts, request["master_part"], "slide master")
    source_rels_name = _rels_partname(source_part)
    if source_rels_name not in parts:
        raise ValueError("source slide master relationships are missing")
    master = ET.fromstring(parts[source_part])
    c_sld = master.find(f"{{{P_NS}}}cSld")
    if c_sld is not None:
        c_sld.set("name", str(request["name"]))
    source_rels = ET.fromstring(parts[source_rels_name])
    rels = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    for relation in source_rels:
        if relation.get("Type") != LAYOUT_REL_TYPE:
            rels.append(copy.deepcopy(relation))
    copy_owned_parts(parts, content_types, source_part, master_part, rels)
    layout_ids = master.find(f"{{{P_NS}}}sldLayoutIdLst")
    if layout_ids is None:
        layout_ids = ET.SubElement(master, f"{{{P_NS}}}sldLayoutIdLst")
    else:
        layout_ids.clear()
    _add_master_to_presentation(presentation, presentation_rels, master_part, identities)
    _ensure_content_type(content_types, master_part, MASTER_CONTENT_TYPE)
    _write_master(parts, master_part, master, rels, content_types, identities, request["layouts"])
    parts[master_part] = _preserve_style_extensions(parts[source_part], parts[master_part])


def _apply_master_extension(
    parts: dict[str, bytes],
    content_types: ET.Element,
    identities: SlideIdentities,
    request: dict[str, Any],
) -> None:
    master_part = _existing_part(parts, request["master_part"], "target slide master")
    rels_name = _rels_partname(master_part)
    if rels_name not in parts:
        raise ValueError("target slide master relationships are missing")
    master = ET.fromstring(parts[master_part])
    rels = ET.fromstring(parts[rels_name])
    _write_master(parts, master_part, master, rels, content_types, identities, request["layouts"])


def _write_master(
    parts: dict[str, bytes],
    master_part: str,
    master: ET.Element,
    rels: ET.Element,
    content_types: ET.Element,
    identities: SlideIdentities,
    layouts: list[dict[str, Any]],
) -> None:
    for layout in layouts:
        _add_layout(parts, content_types, identities, master_part, master, rels, layout)
    parts[master_part] = ET.tostring(master, encoding="utf-8", xml_declaration=True)
    parts[_rels_partname(master_part)] = _relationships_xml(rels)


def _add_layout(
    parts: dict[str, bytes],
    content_types: ET.Element,
    identities: SlideIdentities,
    master_part: str,
    master: ET.Element,
    master_rels: ET.Element,
    layout: dict[str, Any],
) -> None:
    layout_part = _new_part(parts, layout["part"], "slide layout")
    source_part = layout.get("source_part")
    if "layout_type" in layout:
        layout_xml = _typed_layout(
            str(layout["name"]), str(layout["layout_type"]), layout["slide_size"]
        )
    elif source_part is None:
        layout_xml = _blank_layout(str(layout["name"]), bool(layout["title"]), bool(layout["body"]))
    else:
        layout_xml = ET.fromstring(parts[_existing_part(parts, source_part, "source slide layout")])
        c_sld = layout_xml.find(f"{{{P_NS}}}cSld")
        if c_sld is not None:
            c_sld.set("name", str(layout["name"]))
    layout_rels = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    if source_part is not None and (source_rels := parts.get(_rels_partname(source_part))):
        for relation in ET.fromstring(source_rels):
            if relation.get("Type", "").rsplit("/", 1)[-1] == "slideMaster":
                continue
            relation = copy.deepcopy(relation)
            if relation.get("TargetMode", "Internal") == "Internal":
                target = _resolve_target(source_part, relation.get("Target", ""))
                relation.set("Target", _relative_target(layout_part, target))
            layout_rels.append(relation)
    attrs = {"Id": _next_relationship_id(layout_rels), "Type": MASTER_REL_TYPE}
    attrs["Target"] = _relative_target(layout_part, master_part)
    ET.SubElement(layout_rels, f"{{{PKG_REL_NS}}}Relationship", attrs)
    relation_id = _next_relationship_id(master_rels)
    attrs = {"Id": relation_id, "Type": LAYOUT_REL_TYPE}
    attrs["Target"] = _relative_target(master_part, layout_part)
    ET.SubElement(master_rels, f"{{{PKG_REL_NS}}}Relationship", attrs)
    ids = master.find(f"{{{P_NS}}}sldLayoutIdLst")
    if ids is None:
        ids = ET.SubElement(master, f"{{{P_NS}}}sldLayoutIdLst")
    ET.SubElement(
        ids,
        f"{{{P_NS}}}sldLayoutId",
        {
            "id": str(identities.take()),
            f"{{{R_NS}}}id": relation_id,
        },
    )
    if source_part is not None:
        copy_owned_parts(parts, content_types, source_part, layout_part, layout_rels)
    _ensure_content_type(content_types, layout_part, LAYOUT_CONTENT_TYPE)
    parts[layout_part] = ET.tostring(layout_xml, encoding="utf-8", xml_declaration=True)
    parts[_rels_partname(layout_part)] = _relationships_xml(layout_rels)


def _blank_master(name: str) -> ET.Element:
    root = ET.Element(f"{{{P_NS}}}sldMaster")
    c_sld = ET.SubElement(root, f"{{{P_NS}}}cSld", {"name": name})
    _shape_tree(c_sld)
    ET.SubElement(
        root,
        f"{{{P_NS}}}clrMap",
        {
            "bg1": "lt1",
            "tx1": "dk1",
            "bg2": "lt2",
            "tx2": "dk2",
            "accent1": "accent1",
            "accent2": "accent2",
            "accent3": "accent3",
            "accent4": "accent4",
            "accent5": "accent5",
            "accent6": "accent6",
            "hlink": "hlink",
            "folHlink": "folHlink",
        },
    )
    ET.SubElement(root, f"{{{P_NS}}}sldLayoutIdLst")
    styles = ET.SubElement(root, f"{{{P_NS}}}txStyles")
    for style_name in ("titleStyle", "bodyStyle", "otherStyle"):
        ET.SubElement(ET.SubElement(styles, f"{{{P_NS}}}{style_name}"), f"{{{A_NS}}}lvl1pPr")
    return root


def _blank_layout(name: str, title: bool, body: bool) -> ET.Element:
    root = ET.Element(f"{{{P_NS}}}sldLayout", {"type": "cust", "preserve": "1"})
    c_sld = ET.SubElement(root, f"{{{P_NS}}}cSld", {"name": name})
    tree = _shape_tree(c_sld)
    if title:
        tree.append(_placeholder(2, "Title 1", "title", None, 457200, 274320, 8229600, 1143000))
    if body:
        tree.append(
            _placeholder(
                3,
                "Content Placeholder 2",
                "body",
                "1",
                457200,
                1600200,
                8229600,
                3200400,
            )
        )
    override = ET.SubElement(root, f"{{{P_NS}}}clrMapOvr")
    ET.SubElement(override, f"{{{A_NS}}}masterClrMapping")
    return root


def _shape_tree(parent: ET.Element) -> ET.Element:
    tree = ET.SubElement(parent, f"{{{P_NS}}}spTree")
    non_visual = ET.SubElement(tree, f"{{{P_NS}}}nvGrpSpPr")
    ET.SubElement(non_visual, f"{{{P_NS}}}cNvPr", {"id": "1", "name": ""})
    ET.SubElement(non_visual, f"{{{P_NS}}}cNvGrpSpPr")
    ET.SubElement(non_visual, f"{{{P_NS}}}nvPr")
    props = ET.SubElement(tree, f"{{{P_NS}}}grpSpPr")
    transform = ET.SubElement(props, f"{{{A_NS}}}xfrm")
    for tag, attrs in (
        ("off", {"x": "0", "y": "0"}),
        ("ext", {"cx": "0", "cy": "0"}),
        ("chOff", {"x": "0", "y": "0"}),
        ("chExt", {"cx": "0", "cy": "0"}),
    ):
        ET.SubElement(transform, f"{{{A_NS}}}{tag}", attrs)
    return tree


def _placeholder(
    shape_id: int,
    name: str,
    kind: str,
    idx: str | None,
    x: int,
    y: int,
    cx: int,
    cy: int,
) -> ET.Element:
    shape = ET.Element(f"{{{P_NS}}}sp")
    non_visual = ET.SubElement(shape, f"{{{P_NS}}}nvSpPr")
    ET.SubElement(non_visual, f"{{{P_NS}}}cNvPr", {"id": str(shape_id), "name": name})
    ET.SubElement(non_visual, f"{{{P_NS}}}cNvSpPr", {"txBox": "1"})
    placeholder_attrs = {"type": kind}
    if idx is not None:
        placeholder_attrs["idx"] = idx
    ET.SubElement(ET.SubElement(non_visual, f"{{{P_NS}}}nvPr"), f"{{{P_NS}}}ph", placeholder_attrs)
    props = ET.SubElement(shape, f"{{{P_NS}}}spPr")
    transform = ET.SubElement(props, f"{{{A_NS}}}xfrm")
    ET.SubElement(transform, f"{{{A_NS}}}off", {"x": str(x), "y": str(y)})
    ET.SubElement(transform, f"{{{A_NS}}}ext", {"cx": str(cx), "cy": str(cy)})
    ET.SubElement(
        ET.SubElement(props, f"{{{A_NS}}}prstGeom", {"prst": "rect"}),
        f"{{{A_NS}}}avLst",
    )
    text = ET.SubElement(shape, f"{{{P_NS}}}txBody")
    ET.SubElement(text, f"{{{A_NS}}}bodyPr")
    ET.SubElement(text, f"{{{A_NS}}}lstStyle")
    ET.SubElement(text, f"{{{A_NS}}}p")
    return shape


def _add_master_to_presentation(
    presentation: ET.Element, rels: ET.Element, master_part: str, identities: SlideIdentities
) -> None:
    relation_id = _next_relationship_id(rels)
    ET.SubElement(
        rels,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": relation_id,
            "Type": MASTER_REL_TYPE,
            "Target": _relative_target("ppt/presentation.xml", master_part),
        },
    )
    master_ids = presentation.find(f"{{{P_NS}}}sldMasterIdLst")
    if master_ids is None:
        master_ids = ET.Element(f"{{{P_NS}}}sldMasterIdLst")
        presentation.insert(0, master_ids)
    ET.SubElement(
        master_ids,
        f"{{{P_NS}}}sldMasterId",
        {
            "id": str(identities.take()),
            f"{{{R_NS}}}id": relation_id,
        },
    )


def _placeholder_payload(placeholder_type: str, placeholder_idx: str | None) -> dict[str, Any]:
    return {
        "kind": "shape",
        "text": "",
        "paragraphs": [""],
        "paragraph_runs": [[]],
        "is_placeholder": True,
        "placeholder_type": placeholder_type,
        "placeholder_idx": placeholder_idx,
        "placeholder_orient": None,
        "placeholder_size": None,
    }


def _theme_target(parts: dict[str, bytes], presentation: ET.Element, rels: ET.Element) -> str:
    master_ids = presentation.find(f"{{{P_NS}}}sldMasterIdLst")
    if master_ids is None or len(master_ids) == 0:
        raise ValueError("cannot synthesize a master without an existing themed master")
    first_id = next(iter(master_ids)).get(f"{{{R_NS}}}id")
    master_relation = next((rel for rel in rels if rel.get("Id") == first_id), None)
    if master_relation is None:
        raise ValueError("presentation master relationship is missing")
    master_part = _resolve_target("ppt/presentation.xml", master_relation.get("Target", ""))
    master_rels = ET.fromstring(parts[_rels_partname(master_part)])
    theme = next((rel for rel in master_rels if rel.get("Type") == THEME_REL_TYPE), None)
    if theme is None or not theme.get("Target"):
        raise ValueError("existing master has no theme relationship")
    return str(theme.get("Target"))


def _requests(presentation: Presentation) -> list[dict[str, Any]]:
    requests = getattr(presentation, "_slide_master_authoring_requests", None)
    if requests is None:
        requests = []
        presentation._slide_master_authoring_requests = requests
    return requests


def _request_for_master(presentation: Presentation, master_part: str) -> dict[str, Any]:
    if not master_part:
        raise ValueError("the target slide master has no package part")
    for request in _requests(presentation):
        if _part(str(request.get("master_part", ""))) == master_part:
            return request
    request: dict[str, Any] = {
        "kind": "extend_master",
        "master_part": master_part,
        "layouts": [],
    }
    _requests(presentation).append(request)
    return request


def _next_partname(presentation: Presentation, directory: str, stem: str) -> str:
    with zipfile.ZipFile(presentation.path) as package:
        used = set(package.namelist())
    used.update(_part(layout.partname) for layout in presentation.slide_layouts)
    for request in _requests(presentation):
        used.add(_part(str(request.get("master_part", ""))))
        used.update(_part(str(layout["part"])) for layout in request.get("layouts", []))
    index = 1
    while f"ppt/{directory}/{stem}{index}.xml" in used:
        index += 1
    return f"ppt/{directory}/{stem}{index}.xml"


def _required_name(value: str, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{kind} name must be a non-empty string")
    return value.strip()


def _part(value: str) -> str:
    return value.lstrip("/")


def _existing_part(parts: dict[str, bytes], value: object, label: str) -> str:
    part = _part(str(value))
    if part not in parts:
        raise ValueError(f"{label} part {part!r} does not exist")
    return part


def _new_part(parts: dict[str, bytes], value: object, label: str) -> str:
    part = _part(str(value))
    if not part or part in parts:
        raise ValueError(f"{label} part {part!r} already exists")
    return part


def _rels_partname(part: str) -> str:
    directory, filename = posixpath.split(part)
    return f"{directory}/_rels/{filename}.rels"


def _relative_target(source: str, target: str) -> str:
    return posixpath.relpath(target, posixpath.dirname(source))


def _resolve_target(source: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _next_relationship_id(rels: ET.Element) -> str:
    used = {relation.get("Id") for relation in rels}
    index = 1
    while f"rId{index}" in used:
        index += 1
    return f"rId{index}"


def _ensure_content_type(root: ET.Element, part: str, content_type: str) -> None:
    if any(child.get("PartName") == f"/{part}" for child in root):
        return
    ET.SubElement(
        root,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": f"/{part}", "ContentType": content_type},
    )


def _copy_package(input_path: Path, output_path: Path, replacements: dict[str, bytes]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        zipfile.ZipFile(input_path) as source,
        zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            target.writestr(info, replacements.pop(info.filename, source.read(info.filename)))
        for name, payload in sorted(replacements.items()):
            target.writestr(name, payload)


def _register_namespaces() -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
