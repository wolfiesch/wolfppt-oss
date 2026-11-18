"""Shared bounded ZIP admission policy for PPTX package readers."""

from __future__ import annotations

import io
import zipfile
from dataclasses import asdict, dataclass
from xml.parsers import expat


@dataclass(frozen=True)
class PptxPackageLimits:
    max_archive_size: int = 128 * 1024 * 1024
    max_entries: int = 5_000
    max_entry_size: int = 64 * 1024 * 1024
    max_uncompressed_size: int = 256 * 1024 * 1024
    max_compression_ratio: float = 500.0
    max_xml_depth: int = 1_024
    max_xml_text_size: int = 1024 * 1024
    max_text_runs_per_paragraph: int = 4_096
    max_slides: int = 4_096
    max_table_rows: int = 4_096
    max_table_columns: int = 4_096

    def to_dict(self) -> dict[str, int | float]:
        """Return the named bounds, so a caller can report what was applied."""
        return asdict(self)


PPTX_PACKAGE_LIMITS = PptxPackageLimits()
"""The bounds applied to package bytes and the ZIP container."""


@dataclass(frozen=True)
class _EnvelopeRefusal:
    code: str
    recovery: str


def _zip_envelope_refusal(payload: bytes, limits: PptxPackageLimits) -> _EnvelopeRefusal | None:
    """Return the declared ZIP-envelope limit that refuses ``payload``, if any."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            declared = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError, EOFError, RuntimeError):
        return _EnvelopeRefusal(
            "package_invalid",
            "The bytes are not a readable package archive: no ZIP central "
            "directory was found, so no PPTX package could be admitted.",
        )
    return _zip_entries_refusal(declared, limits)


def _zip_entries_refusal(
    declared: list[zipfile.ZipInfo], limits: PptxPackageLimits
) -> _EnvelopeRefusal | None:
    """Check metadata before any member expansion, for byte and path readers."""
    if len(declared) > limits.max_entries:
        return _EnvelopeRefusal(
            "entries_limit",
            f"The package declares {len(declared)} ZIP entries, above the "
            f"{limits.max_entries} entry limit this surface admits.  Repackage the "
            "presentation with fewer parts.",
        )
    entries = [info for info in declared if not info.is_dir()]
    names: set[str] = set()
    for info in declared:
        if info.filename in names:
            return _EnvelopeRefusal(
                "duplicate_entry_names",
                f"The package repeats ZIP entry {info.filename!r}. Repackage with "
                "one entry per part name.",
            )
        names.add(info.filename)
    for info in entries:
        if info.flag_bits & 0x1:
            return _EnvelopeRefusal(
                "zip_encrypted",
                "The package declares ZIP-level encryption on one entry, which no "
                "OPC package carries: package confidentiality belongs to the "
                "container this surface writes, never to a member archive.",
            )
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            return _EnvelopeRefusal(
                "zip_compression_unsupported",
                f"The package declares ZIP compression method "
                f"{info.compress_type} on one entry, and only the stored and "
                "deflate methods an OPC package may use are admitted here.",
            )
    expanded = 0
    for info in entries:
        if info.file_size > limits.max_entry_size:
            return _EnvelopeRefusal(
                "entry_size_limit",
                f"The package expands one entry to {info.file_size} bytes, above the "
                f"{limits.max_entry_size} byte per-entry limit this surface admits.  "
                "Remove or shrink the oversized part.",
            )
        expanded += info.file_size
        if expanded > limits.max_uncompressed_size:
            return _EnvelopeRefusal(
                "expanded_size_limit",
                f"The package expands its declared entries to {expanded} bytes in "
                f"total, above the {limits.max_uncompressed_size} byte expanded-size "
                "limit this surface admits.  Remove or shrink the largest parts.",
            )
        if (
            info.compress_size > 0
            and info.file_size / info.compress_size > limits.max_compression_ratio
        ):
            return _EnvelopeRefusal(
                "compression_ratio_limit",
                f"The package declares a {info.file_size / info.compress_size:.1f}x "
                f"compression ratio, above the "
                f"{limits.max_compression_ratio:g}x ratio limit this surface admits.  "
                "Repackage the presentation without a highly compressible part.",
            )
    return None


class _XmlLimitExceeded(ValueError):
    pass


class _XmlRequiresCallbacks(Exception):
    pass


def _require_xml_callbacks(*_args) -> None:
    raise _XmlRequiresCallbacks


# Expat's expanded names have no leading "{". Match complete names so Strict,
# Transitional, and foreign namespaces keep independent direct-child counts.
_XML_CHILD_LIMITS = {
    f"{namespace}}}{parent}": (
        frozenset(f"{namespace}}}{child}" for child in children),
        field,
        code,
    )
    for namespace in (
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://purl.oclc.org/ooxml/drawingml/main",
    )
    for parent, children, field, code in (
        ("p", ("r", "fld", "br"), "max_text_runs_per_paragraph", "text_runs_limit"),
        ("tbl", ("tr",), "max_table_rows", "table_rows_limit"),
        ("tr", ("tc",), "max_table_columns", "table_columns_limit"),
        ("tblGrid", ("gridCol",), "max_table_columns", "table_columns_limit"),
    )
} | {
    f"{namespace}}}sldIdLst": (
        frozenset((f"{namespace}}}sldId",)),
        "max_slides",
        "slides_limit",
    )
    for namespace in (
        "http://schemas.openxmlformats.org/presentationml/2006/main",
        "http://purl.oclc.org/ooxml/presentationml/main",
    )
}


def _xml_part_refusal(
    member, limits: PptxPackageLimits, *, size: int | None = None
) -> _EnvelopeRefusal | None:
    """Scan XML with bounded callbacks and no retained element tree.

    Limits are engine admission policy, not numerical OOXML requirements.
    Count direct runs per paragraph, slides per list, and rows/columns per table.
    """
    # A start tag needs at least three bytes, and repeated direct children
    # need at least four bytes each. Without a DTD, decoded text/attributes
    # cannot be longer than the owning XML bytes. Below all these bounds,
    # Expat can check XML without allocating Python objects for every event.
    byte_bound = min(
        3 * limits.max_xml_depth,
        limits.max_xml_text_size,
        4 * limits.max_text_runs_per_paragraph,
        4 * limits.max_slides,
        4 * limits.max_table_rows,
        4 * limits.max_table_columns,
    )
    first_chunk = None
    bounded = size is not None and size <= byte_bound
    if size is not None and not bounded and size <= min(65_536, limits.max_xml_text_size):
        first_chunk = member.read(65_536)
        # Every start tag contains a '<' byte in Expat's admitted encodings.
        # Counting all such bytes also counts closing tags and markup, so it
        # conservatively bounds depth and every direct-child count.
        element_bound = min(
            limits.max_xml_depth,
            limits.max_text_runs_per_paragraph,
            limits.max_slides,
            limits.max_table_rows,
            limits.max_table_columns,
        )
        bounded = len(first_chunk) == size and first_chunk.count(b"<") <= element_bound
    if bounded:
        position = member.tell() - (len(first_chunk) if first_chunk is not None else 0)
        parser = expat.ParserCreate(namespace_separator="}")
        # Entity declarations can expand text beyond its source byte length.
        # Stop before expansion and replay through the bounded callbacks.
        parser.StartDoctypeDeclHandler = _require_xml_callbacks
        try:
            if first_chunk is not None:
                parser.Parse(first_chunk, False)
            while chunk := member.read(65_536):
                parser.Parse(chunk, False)
            parser.Parse(b"", True)
        except _XmlRequiresCallbacks:
            member.seek(position)
            first_chunk = None
        except expat.ExpatError:
            return None
        else:
            return None

    stack: list[str] = []
    child_counts: list[int] = []
    text_size = 0

    def refuse(code: str, requested: int, bound: int) -> None:
        raise _XmlLimitExceeded(
            f"{code}: requested {requested}, limit {bound}. "
            "Reduce the owning XML part before opening the presentation."
        )

    def start(name: str, attributes: dict[str, str]) -> None:
        nonlocal text_size
        depth = len(stack) + 1
        if depth > limits.max_xml_depth:
            refuse("xml_depth_limit", depth, limits.max_xml_depth)
        for value in attributes.values():
            if len(value) > limits.max_xml_text_size:
                refuse("xml_text_limit", len(value), limits.max_xml_text_size)
        if stack and (rule := _XML_CHILD_LIMITS.get(stack[-1])) is not None:
            children, field, code = rule
            if name in children:
                count = child_counts[-1] + 1
                child_counts[-1] = count
                bound = getattr(limits, field)
                if count > bound:
                    refuse(code, count, bound)
        stack.append(name)
        child_counts.append(0)
        text_size = 0

    def end(_name: str) -> None:
        nonlocal text_size
        stack.pop()
        child_counts.pop()
        text_size = 0

    def data(value: str) -> None:
        nonlocal text_size
        text_size += len(value)
        if text_size > limits.max_xml_text_size:
            refuse("xml_text_limit", text_size, limits.max_xml_text_size)

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = data
    try:
        if first_chunk is not None:
            parser.Parse(first_chunk, False)
        while chunk := member.read(65_536):
            parser.Parse(chunk, False)
        parser.Parse(b"", True)
    except _XmlLimitExceeded as exc:
        return _EnvelopeRefusal(str(exc).split(":", 1)[0], str(exc))
    except expat.ExpatError:
        # Preserve the existing format validator's malformed-XML error semantics.
        return None
    return None
