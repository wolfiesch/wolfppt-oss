"""Helpers for path and file-like binary inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InMemoryFile:
    blob: bytes
    filename: str | None = None

    @property
    def display_filename(self) -> str:
        return Path(self.filename or "file.bin").name

    def materialize(self, directory: Path, stem: str | None = None) -> Path:
        if stem is None:
            target = directory / self.display_filename
        else:
            suffix = Path(self.display_filename).suffix or ".bin"
            target = directory / f"{stem}{suffix}"
        target.write_bytes(self.blob)
        return target


@dataclass(frozen=True)
class InMemoryImage(InMemoryFile):
    @property
    def display_filename(self) -> str:
        if self.filename:
            return Path(self.filename).name
        return f"image.{image_extension_from_blob(self.blob)}"


def image_source_for_queue(image_file: Any) -> str | Path | InMemoryImage:
    if isinstance(image_file, (str, Path)):
        return image_file
    return InMemoryImage(_read_file_like_bytes(image_file))


def binary_source_for_queue(
    binary_file: Any,
    default_filename: str,
) -> str | Path | InMemoryFile:
    if isinstance(binary_file, (str, Path)):
        return binary_file
    return InMemoryFile(_read_file_like_bytes(binary_file), default_filename)


def movie_source_for_queue(
    movie_file: Any,
    mime_type: str,
) -> str | Path | InMemoryFile:
    return binary_source_for_queue(movie_file, f"movie.{video_extension(mime_type)}")


def image_input_bytes(image_file: Any) -> bytes:
    if isinstance(image_file, InMemoryFile):
        return image_file.blob
    if isinstance(image_file, (str, Path)):
        return Path(image_file).read_bytes()
    return _read_file_like_bytes(image_file)


def image_input_filename(image_file: Any) -> str | None:
    if isinstance(image_file, InMemoryFile):
        return image_file.display_filename
    if isinstance(image_file, (str, Path)):
        return Path(image_file).name
    return None


@dataclass(frozen=True)
class StoredMediaSource(InMemoryFile):
    """A queued reference to existing package bytes, never a second asset."""

    partname: str = ""
    content_type: str = ""
    sha256: str = ""


def stored_media_source(presentation: Any, value: Any, kind: str) -> StoredMediaSource | None:
    from .native_media import MediaCollectionRefusal, MediaReplacementRefusal, PresentationMedia

    if not isinstance(value, PresentationMedia):
        return None
    if value._presentation is not presentation or value.kind != kind:
        raise MediaCollectionRefusal(f"placement requires this presentation's {kind} asset")
    try:
        payload = value.blob
    except MediaReplacementRefusal as exc:
        raise MediaCollectionRefusal(str(exc)) from exc
    return StoredMediaSource(
        payload, Path(value.partname).name, value.partname, value.content_type, value.sha256
    )


def source_display_filename(source: Any) -> str:
    if isinstance(source, InMemoryFile):
        return source.display_filename
    return Path(source).name


def video_extension(mime_type: str | None) -> str:
    return {
        "video/x-ms-asf": "asf",
        "video/avi": "avi",
        "video/quicktime": "mov",
        "video/mp4": "mp4",
        "video/mpeg": "mpg",
        "video/msvideo": "avi",
        "application/x-shockwave-flash": "swf",
        "video/x-ms-wmv": "wmv",
        "video/x-msvideo": "avi",
    }.get(str(mime_type or "video/unknown"), "vid")


def image_extension_from_blob(blob: bytes) -> str:
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if blob.startswith(b"\xff\xd8"):
        return "jpg"
    if blob.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if blob.startswith(b"BM"):
        return "bmp"
    if blob.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    raise ValueError("unsupported image format")


def _read_file_like_bytes(file_like: Any) -> bytes:
    if not hasattr(file_like, "read"):
        raise TypeError("input must be a path or file-like object")
    if callable(getattr(file_like, "seek", None)):
        file_like.seek(0)
    blob = file_like.read()
    if not isinstance(blob, bytes):
        raise TypeError("file-like read() must return bytes")
    return blob


def collection_input(data: Any, content_type: str | None, kind: str) -> tuple[bytes, str]:
    """Validate opaque asset bytes and their supported declared format before edits."""
    from .native_media import (
        MEDIA_EXTENSIONS,
        MediaCollectionRefusal,
        MediaReplacementRefusal,
        media_content_type_for_path,
    )

    try:
        if isinstance(data, (str, Path)):
            declared = content_type or media_content_type_for_path(data)
            payload = Path(data).read_bytes()
        else:
            declared = content_type
            payload = bytes(data) if isinstance(data, (bytes, bytearray)) else data.read()
    except (AttributeError, TypeError, OSError, MediaReplacementRefusal) as exc:
        raise MediaCollectionRefusal(f"invalid media source: {exc}") from exc
    if not isinstance(payload, bytes) or not payload:
        raise MediaCollectionRefusal("media requires nonempty binary bytes")
    if (
        not isinstance(declared, str)
        or declared not in MEDIA_EXTENSIONS
        or not declared.startswith(kind + "/")
    ):
        raise MediaCollectionRefusal(f"unsupported {kind} content type {declared!r}")
    return payload, declared


def collection_add_parts(
    package: Any, payload: bytes, content_type: str
) -> tuple[dict[str, bytes], set[str], str]:
    import posixpath
    from xml.etree import ElementTree as ET

    from .native_media import (
        _CT_NS,
        _PKG_REL_NS,
        _R_NS,
        MEDIA_EXTENSIONS,
        _resolve,
        ordered_content_types_xml,
        part_content_type,
    )
    from .presentation_tags import parse_xml, serialize_xml

    names = set(package.namelist())
    # Exact bytes and declared format define identity, not source filenames.
    partname = next(
        (
            name
            for name in sorted(names)
            if name.startswith("ppt/media/")
            and part_content_type(package, name) == content_type
            and package.read(name) == payload
        ),
        None,
    )
    replacements = {}
    if partname is None:
        extension = MEDIA_EXTENSIONS[content_type]
        counter = 1
        while f"ppt/media/asset{counter}.{extension}" in names:
            counter += 1
        partname = f"ppt/media/asset{counter}.{extension}"
        replacements[partname] = payload
        types = parse_xml(package.read("[Content_Types].xml"))
        ET.SubElement(
            types,
            f"{{{_CT_NS}}}Override",
            {"PartName": "/" + partname, "ContentType": content_type},
        )
        replacements["[Content_Types].xml"] = ordered_content_types_xml(types)
    rels_name = "ppt/_rels/presentation.xml.rels"
    rels = (
        parse_xml(package.read(rels_name))
        if rels_name in names
        else ET.Element(f"{{{_PKG_REL_NS}}}Relationships")
    )
    kind = content_type.split("/", 1)[0]
    rel_type = _R_NS + "/" + kind
    if not any(
        rel.get("Type") == rel_type
        and rel.get("TargetMode", "Internal") == "Internal"
        and _resolve("ppt/presentation.xml", rel.get("Target", "")) == partname
        for rel in rels
    ):
        ids = {rel.get("Id") for rel in rels}
        counter = 1
        while f"rId{counter}" in ids:
            counter += 1
        ET.SubElement(
            rels,
            f"{{{_PKG_REL_NS}}}Relationship",
            {
                "Id": f"rId{counter}",
                "Type": rel_type,
                "Target": posixpath.relpath(partname, "ppt"),
            },
        )
        replacements[rels_name] = serialize_xml(rels)
    return replacements, set(), partname


def collection_remove_parts(package: Any, asset: Any) -> tuple[dict[str, bytes], set[str], None]:
    import hashlib

    from .native_media import (
        _CT_NS,
        _RELATIONSHIP_NAMESPACES,
        MediaCollectionRefusal,
        _owner_of_rels,
        _resolve,
        ordered_content_types_xml,
        part_content_type,
    )
    from .presentation_tags import parse_xml, serialize_xml

    names = set(package.namelist())
    if (
        asset.partname not in names
        or hashlib.sha256(package.read(asset.partname)).hexdigest() != asset.sha256
        or part_content_type(package, asset.partname) != asset.content_type
    ):
        raise MediaCollectionRefusal("media asset is stale or missing")
    replacements = {}
    for name in sorted(names):
        if not name.endswith(".rels"):
            continue
        owner = _owner_of_rels(name)
        rels = parse_xml(package.read(name))
        changed = False
        for rel in list(rels):
            if (
                rel.get("TargetMode", "Internal") != "Internal"
                or _resolve(owner, rel.get("Target", "")) != asset.partname
            ):
                continue
            if owner != "ppt/presentation.xml" or rel.get("Type") not in {
                namespace + "/" + asset.kind for namespace in _RELATIONSHIP_NAMESPACES
            }:
                raise MediaCollectionRefusal("media asset is still referenced by the package")
            rels.remove(rel)
            changed = True
        if changed:
            replacements[name] = serialize_xml(rels)
    types = parse_xml(package.read("[Content_Types].xml"))
    changed = False
    for node in list(types):
        if (
            node.tag == f"{{{_CT_NS}}}Override"
            and node.get("PartName", "").lstrip("/") == asset.partname
        ):
            types.remove(node)
            changed = True
    if changed:
        replacements["[Content_Types].xml"] = ordered_content_types_xml(types)
    return replacements, {asset.partname}, None
