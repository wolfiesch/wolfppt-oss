"""Validated package save controls for WolfPPT's public presentation facade."""

from __future__ import annotations

import io
import struct
import zipfile
from copy import copy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .editions import commercial_module
from .package_conformance import (
    normalize_compression_level,
    normalize_conformance,
    rewrite_package,
)
from .package_copy_io import _copy_raw_zip_entry, _raw_zip_entry_spans
from .package_parts import (
    CONTENT_TYPES_NS,
    PKG_REL_NS,
    _content_types_xml,
    _next_relationship_id,
    _set_content_type_override,
    _xml_bytes,
)
from .render_refusals import RenderRefusal

_THUMBNAIL_REL = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"


class ExportOptionsRefusal(ValueError):
    """An invalid or unsupported export option refused before destination writes."""


def save_package_with_options(
    presentation: Any,
    path: Any,
    *,
    password: str | None = None,
    conformance: str | None = None,
    compression_level: int | None = None,
    zip64: bool | None = None,
    thumbnail: bool = False,
    thumbnail_fonts: tuple[str, ...] = (),
) -> None:
    """Implement ``Presentation.save`` controls without changing its default route.

    All options are admitted before serializing edits. Rewrites, commercial
    thumbnail rendering and encryption finish before publication. Filesystem
    publication is atomic; streams receive one complete payload (I/O failures can
    still partially write a stream). A refusal never writes the destination.
    """
    from .presentation import _encrypt_package, _publish_bytes
    from .presentation_formats import OdpFormatError

    if password is not None and (not isinstance(password, str) or not password):
        raise ValueError("password must be a non-empty string")
    if conformance is not None:
        normalize_conformance(conformance)
    if compression_level is not None:
        normalize_compression_level(compression_level)
    if zip64 is not None and type(zip64) is not bool:
        raise ExportOptionsRefusal("zip64 must be True, False or None")
    if type(thumbnail) is not bool:
        raise ExportOptionsRefusal("thumbnail must be True or False")
    if not isinstance(thumbnail_fonts, tuple) or any(
        not isinstance(spec, str) for spec in thumbnail_fonts
    ):
        raise ExportOptionsRefusal("thumbnail_fonts must be a tuple of font specification strings")
    if thumbnail_fonts and not thumbnail:
        raise ExportOptionsRefusal("thumbnail_fonts requires thumbnail=True")

    rewrite = conformance is not None or compression_level is not None
    controlled = rewrite or zip64 is not None or thumbnail
    file_like = callable(getattr(path, "write", None))
    if (
        (password is not None or controlled)
        and not file_like
        and Path(path).suffix.casefold() == ".odp"
    ):
        if password is not None:
            raise OdpFormatError("ODP output cannot be password-encrypted")
        raise OdpFormatError("ODP output has no OOXML package save controls")

    fonts = None
    if thumbnail:
        render_fonts = commercial_module("render_fonts", "Rendering a presentation thumbnail")

        try:
            fonts = render_fonts.admit_font_specs(thumbnail_fonts)
        except RenderRefusal as exc:
            raise ExportOptionsRefusal(f"thumbnail font admission: {exc}") from exc
    if password is None and not controlled:
        presentation._save_unlocked(path)
        return

    plaintext = io.BytesIO()
    presentation._save_unlocked(plaintext)
    payload = plaintext.getvalue()
    if rewrite:
        payload = rewrite_package(
            payload, conformance=conformance, compression_level=compression_level
        )
    replacements = _thumbnail_replacements(payload, fonts) if thumbnail else {}
    if replacements or zip64 is not None:
        payload = _rewrite_export_package(payload, replacements, zip64, compression_level)
    if password is not None:
        payload = _encrypt_package(payload, password)
    if file_like:
        written = path.write(payload)
        if written is not None and written != len(payload):
            raise OSError("presentation stream did not accept the complete package")
    else:
        _publish_bytes(Path(path), payload)


def _thumbnail_replacements(payload: bytes, fonts: Any) -> dict[str, bytes]:
    """Render the actual first slide, even hidden, and publish its OPC records."""
    renderer = commercial_module("render_tiff", "Rendering a presentation thumbnail")

    try:
        thumbnail = renderer._render_thumbnail(payload, fonts)
        with zipfile.ZipFile(io.BytesIO(payload)) as package:
            types = ET.fromstring(package.read("[Content_Types].xml"))
            if types.tag != f"{{{CONTENT_TYPES_NS}}}Types":
                raise ExportOptionsRefusal("thumbnail requires an OPC content-types root")
            names = set(package.namelist())
            root = (
                ET.fromstring(package.read("_rels/.rels"))
                if "_rels/.rels" in names
                else ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            )
            if root.tag != f"{{{PKG_REL_NS}}}Relationships":
                raise ExportOptionsRefusal("thumbnail requires an OPC root relationships part")
            thumbnails = [node for node in root if node.get("Type") == _THUMBNAIL_REL]
            # Never overwrite an unrelated existing part, even at the customary
            # name. Old thumbnail assets remain preserved but are no longer linked.
            part = "docProps/thumbnail.png"
            index = 1
            while part in names:
                part = f"docProps/thumbnail{index}.png"
                index += 1
            if thumbnails:
                relationship = thumbnails[0]
                for duplicate in thumbnails[1:]:
                    root.remove(duplicate)
            else:
                ids = {node.get("Id", "") for node in root}
                relationship = ET.SubElement(
                    root, f"{{{PKG_REL_NS}}}Relationship", {"Id": _next_relationship_id(ids)}
                )
            relationship.set("Type", _THUMBNAIL_REL)
            relationship.set("Target", part)
            relationship.attrib.pop("TargetMode", None)
            _set_content_type_override(types, f"/{part}", "image/png")
        return {
            part: thumbnail,
            "[Content_Types].xml": _content_types_xml(types),
            "_rels/.rels": _xml_bytes(root),
        }
    except (RenderRefusal, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        raise ExportOptionsRefusal(f"thumbnail generation: {exc}") from exc


def _without_zip64_extra(extra: bytes) -> bytes:
    """Remove only ZIP64 size/offset extras when rebuilding member headers."""
    result: list[bytes] = []
    offset = 0
    while offset < len(extra):
        if len(extra) - offset < 4:
            raise ExportOptionsRefusal("malformed ZIP member extra field")
        kind, size = struct.unpack_from("<HH", extra, offset)
        end = offset + 4 + size
        if end > len(extra):
            raise ExportOptionsRefusal("truncated ZIP member extra field")
        if kind != 1:
            result.append(extra[offset:end])
        offset = end
    return b"".join(result)


def _rewrite_export_package(
    payload: bytes,
    replacements: dict[str, bytes],
    zip64: bool | None,
    compression_level: int | None = None,
) -> bytes:
    """Keep untouched part bytes; preserve raw entries for historical ZIP mode."""
    output = io.BytesIO()
    level = 1 if compression_level is None else compression_level
    try:
        with (
            zipfile.ZipFile(io.BytesIO(payload)) as source,
            zipfile.ZipFile(
                output,
                "w",
                zipfile.ZIP_DEFLATED,
                allowZip64=zip64 is not False,
                compresslevel=1,
            ) as target,
        ):
            infos = source.infolist()
            new_names = replacements.keys() - {info.filename for info in infos}
            if zip64 is False and (
                len(infos) + len(new_names) > zipfile.ZIP_FILECOUNT_LIMIT
                or any(info.file_size > zipfile.ZIP64_LIMIT for info in infos)
            ):
                raise ExportOptionsRefusal("zip64=False forbids a package requiring ZIP64")
            target.comment = source.comment
            spans = _raw_zip_entry_spans(source) if zip64 is None else {}
            for info in infos:
                data = replacements.get(info.filename)
                if (
                    zip64 is None
                    and data is None
                    and _copy_raw_zip_entry(source, target, info, spans)
                ):
                    continue
                if data is None:
                    data = source.read(info)
                entry = copy(info)
                entry.extra = _without_zip64_extra(entry.extra)
                entry.file_size = len(data)
                entry._compresslevel = level or None
                if zip64 is True:
                    with target.open(entry, "w", force_zip64=True) as member:
                        member.write(data)
                else:
                    target.writestr(entry, data, compresslevel=level or None)
            for name in sorted(new_names):
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = (
                    zipfile.ZIP_STORED
                    if level == 0 or name.endswith(".png")
                    else zipfile.ZIP_DEFLATED
                )
                data = replacements[name]
                entry.file_size = len(data)
                entry._compresslevel = level or None
                if zip64 is True:
                    with target.open(entry, "w", force_zip64=True) as member:
                        member.write(data)
                else:
                    target.writestr(entry, data, compresslevel=level or None)
        if zip64 is True:
            _force_zip64_end_records(output, target)
        return output.getvalue()
    except zipfile.LargeZipFile as exc:
        raise ExportOptionsRefusal("zip64=False forbids a package requiring ZIP64") from exc


def _force_zip64_end_records(output: io.BytesIO, archive: zipfile.ZipFile) -> None:
    """Force ZIP64 EOCD and locator, not merely permission for large members."""
    end = output.tell() - 22 - len(archive.comment)
    output.seek(max(0, end - 20))
    if output.read(4) == b"PK\x06\x07":
        return  # zipfile already emitted ZIP64 archive end records.
    count = len(archive.filelist)
    size = end - archive.start_dir
    output.seek(end)
    output.write(
        struct.pack(
            "<4sQ2H2I4Q",
            b"PK\x06\x06",
            44,
            45,
            45,
            0,
            0,
            count,
            count,
            size,
            archive.start_dir,
        )
    )
    output.write(struct.pack("<4sIQI", b"PK\x06\x07", 0, end, 1))
    output.write(
        struct.pack(
            "<4s4H2IH",
            b"PK\x05\x06",
            0,
            0,
            0xFFFF,
            0xFFFF,
            0xFFFFFFFF,
            0xFFFFFFFF,
            len(archive.comment),
        )
    )
    output.write(archive.comment)
