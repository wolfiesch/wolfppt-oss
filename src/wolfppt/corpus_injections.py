"""Low-level PPTX package injections for deterministic corpus fixtures."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET


def inject_slide_transition(path: Path) -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "ppt/slides/slide1.xml":
                    payload = payload.replace(b"</p:sld>", b"<p:transition/></p:sld>")
                target.writestr(name, payload)
        tmp_path.replace(path)


def inject_grouped_shape(path: Path) -> None:
    group_xml = (
        b'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="2" name="Group 1"/>'
        b"<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        b'<p:grpSpPr><a:xfrm><a:off x="1000" y="2000"/>'
        b'<a:ext cx="4000" cy="4000"/><a:chOff x="0" y="0"/>'
        b'<a:chExt cx="4000" cy="4000"/></a:xfrm></p:grpSpPr>'
        b'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Grouped Text 1"/>'
        b"<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        b'<p:spPr><a:xfrm><a:off x="500" y="600"/>'
        b'<a:ext cx="1000" cy="800"/></a:xfrm><a:prstGeom prst="rect">'
        b"<a:avLst/></a:prstGeom></p:spPr>"
        b"<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Grouped Text"
        b"</a:t></a:r></a:p></p:txBody></p:sp></p:grpSp>"
    )
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "ppt/slides/slide1.xml":
                    payload = payload.replace(
                        b"<p:grpSpPr/>",
                        b"<p:grpSpPr/>" + group_xml,
                    )
                target.writestr(name, payload)
        tmp_path.replace(path)


def inject_slide_timing(path: Path) -> None:
    timing = (
        b'<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" '
        b'restart="never" nodeType="tmRoot"/></p:par></p:tnLst></p:timing>'
    )
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "ppt/slides/slide1.xml":
                    payload = payload.replace(b"</p:sld>", timing + b"</p:sld>")
                target.writestr(name, payload)
        tmp_path.replace(path)


def inject_legacy_comment(path: Path) -> None:
    comment_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<p:cmLst xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        b'<p:cm authorId="0" dt="2026-05-13T00:00:00Z" idx="1">'
        b'<p:pos x="0" y="0"/><p:text>Review this slide.</p:text>'
        b"</p:cm></p:cmLst>\n"
    )
    authors_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<p:cmAuthorLst xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        b'<p:cmAuthor id="0" name="WolfPPT" initials="WP" lastIdx="1" clrIdx="0"/>'
        b"</p:cmAuthorLst>\n"
    )
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "[Content_Types].xml":
                    payload = _insert_before(
                        payload,
                        "</Types>",
                        '<Override PartName="/ppt/comments/comment1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>'
                        '<Override PartName="/ppt/commentAuthors.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml"/>',
                    )
                elif name == "ppt/_rels/presentation.xml.rels":
                    payload = _insert_relationship(
                        payload,
                        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors",
                        "commentAuthors.xml",
                    )
                elif name == "ppt/slides/_rels/slide1.xml.rels":
                    payload = _insert_relationship(
                        payload,
                        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
                        "../comments/comment1.xml",
                    )
                target.writestr(name, payload)
            target.writestr("ppt/comments/comment1.xml", comment_xml)
            target.writestr("ppt/commentAuthors.xml", authors_xml)
        tmp_path.replace(path)


def inject_ole_object(path: Path) -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "[Content_Types].xml":
                    payload = _insert_before(
                        payload,
                        "</Types>",
                        '<Override PartName="/ppt/embeddings/oleObject1.bin" '
                        'ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>',
                    )
                elif name == "ppt/slides/_rels/slide1.xml.rels":
                    payload = _insert_relationship(
                        payload,
                        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
                        "../embeddings/oleObject1.bin",
                    )
                target.writestr(name, payload)
            target.writestr(
                "ppt/embeddings/oleObject1.bin",
                b"wolfppt-placeholder-ole-object",
            )
        tmp_path.replace(path)

def inject_chart_style_parts(path: Path) -> None:
    style_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<cs:chartStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle"/>'
    )
    colors_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<cs:colorStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle" '
        b'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" meth="cycle">'
        b'<a:srgbClr val="4472C4"/></cs:colorStyle>'
    )
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "[Content_Types].xml":
                    payload = _insert_before(
                        payload,
                        "</Types>",
                        '<Override PartName="/ppt/charts/style1.xml" '
                        'ContentType="application/vnd.ms-office.chartstyle+xml"/>'
                        '<Override PartName="/ppt/charts/colors1.xml" '
                        'ContentType="application/vnd.ms-office.chartcolorstyle+xml"/>',
                    )
                elif name == "ppt/charts/_rels/chart1.xml.rels":
                    payload = _insert_relationship(
                        payload,
                        "http://schemas.microsoft.com/office/2011/relationships/chartStyle",
                        "style1.xml",
                    )
                    payload = _insert_relationship(
                        payload,
                        "http://schemas.microsoft.com/office/2011/relationships/chartColorStyle",
                        "colors1.xml",
                    )
                target.writestr(name, payload)
            target.writestr("ppt/charts/style1.xml", style_xml)
            target.writestr("ppt/charts/colors1.xml", colors_xml)
        tmp_path.replace(path)


def write_pptm_from_pptx(pptx_path: Path, pptm_path: Path) -> None:
    with zipfile.ZipFile(pptx_path) as source, zipfile.ZipFile(
        pptm_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "[Content_Types].xml":
                payload = _macro_content_types(payload)
            elif name == "ppt/_rels/presentation.xml.rels":
                payload = _macro_presentation_rels(payload)
            target.writestr(name, payload)
        target.writestr("ppt/vbaProject.bin", b"wolfppt-placeholder-vba")


def _insert_relationship(payload: bytes, relationship_type: str, target: str) -> bytes:
    relationship_id = _next_relationship_id(payload)
    return _insert_before(
        payload,
        "</Relationships>",
        f'<Relationship Id="{relationship_id}" Type="{relationship_type}" Target="{target}"/>',
    )


def _insert_before(payload: bytes, needle: str, insert: str) -> bytes:
    text = payload.decode("utf-8")
    return text.replace(needle, insert + needle).encode("utf-8")


def _next_relationship_id(payload: bytes) -> str:
    ids = [int(value) for value in re.findall(rb'Id="rId(\d+)"', payload)]
    return f"rId{max(ids, default=0) + 1}"


def _macro_content_types(payload: bytes) -> bytes:
    ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", ns)
    root = ET.fromstring(payload)
    for override in root.findall(f"{{{ns}}}Override"):
        if override.attrib.get("PartName") == "/ppt/presentation.xml":
            override.set(
                "ContentType",
                "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml",
            )
    if not any(
        override.attrib.get("PartName") == "/ppt/vbaProject.bin"
        for override in root.findall(f"{{{ns}}}Override")
    ):
        ET.SubElement(
            root,
            f"{{{ns}}}Override",
            {
                "PartName": "/ppt/vbaProject.bin",
                "ContentType": "application/vnd.ms-office.vbaProject",
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _macro_presentation_rels(payload: bytes) -> bytes:
    ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    ET.register_namespace("", ns)
    root = ET.fromstring(payload)
    ids = {rel.attrib.get("Id") for rel in root.findall(f"{{{ns}}}Relationship")}
    next_id = 1
    while f"rId{next_id}" in ids:
        next_id += 1
    ET.SubElement(
        root,
        f"{{{ns}}}Relationship",
        {
            "Id": f"rId{next_id}",
            "Type": "http://schemas.microsoft.com/office/2006/relationships/vbaProject",
            "Target": "vbaProject.bin",
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
