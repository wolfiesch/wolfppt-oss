"""Opt-in, transactional warning operations over WolfPPT's presentation facade.

Import ``load_with_warnings`` and ``save_with_warnings`` from this module. Both
return ``LoadSaveResult`` with an owned presentation and ordered immutable warnings.
A callback must return ``WarningAction.CONTINUE`` or ``WarningAction.ABORT``;
without a callback any warning aborts. Callback exceptions propagate unchanged.

Load snapshots the caller's bytes and releases its file/stream immediately. The
obsolete ``locking_behavior="legacy_keep_open"`` requests a diagnostic, not a
persistent file lock; continuation uses the same snapshot semantics as the default.
The only admitted repair is removing *identical* duplicate OPC relationships.
Conflicting identities refuse rather than guessing which target the author meant.

A signed deck produces a load diagnostic (presence is not signature verification).
A save that changes its package parts requires explicit approval to remove the old
signature graph. An unedited copy preserves the signature and original ZIP bytes.
Signature graphs outside the standard ``_xmlsignatures/`` directory are refused
when removal is necessary. Use ``wolfppt.security`` for signature verification.

Save stages a copy of the live presentation; it never consumes the caller's edits,
including on success. Continue editing ``result.presentation`` for the new saved
baseline. This functional contract keeps aborts and observer exceptions retryable.
All refusals occur before destination writes or parent-directory creation. File
publication is atomic; a failing caller-owned output stream can partially write.
Output is PPTX only; other formats and encryption use the existing facade APIs.
Warning categories are shared with rendering and Markdown export in ``results``.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from io import BytesIO
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from xml.parsers.expat import ExpatError
from zipfile import BadZipFile, ZipFile

from .package_limits import PPTX_PACKAGE_LIMITS
from .package_parts import (
    CONTENT_TYPES_NS,
    PKG_REL_NS,
    InMemoryPackageSource,
    copy_open_package_with_replacements,
    resolve_package_target,
)
from .presentation import Presentation, _publish_bytes
from .presentation_input import _validate_package_limits
from .presentation_package_validation import PresentationPackageError
from .presentation_save_state import _cut, _element_spans
from .results import (
    LoadSaveResult,
    LoadSaveWarning,
    LoadSaveWarningRefusal,
    WarningAction,
    WarningCategory,
    observe_warnings,
)

WarningCallback = Callable[[LoadSaveWarning], WarningAction]
_SIGNATURE_PREFIX = "_xmlsignatures/"
_SIGNATURE_REL = f"{PKG_REL_NS}/digital-signature/"
_SIGNATURE_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-package.digital-signature-origin",
        "application/vnd.openxmlformats-package.digital-signature-xmlsignature+xml",
    }
)


def _check_callback(callback: WarningCallback | None) -> None:
    if callback is not None and not callable(callback):
        raise LoadSaveWarningRefusal("callback_unsupported", "warning_callback must be callable")


def _read_payload(source: Any) -> bytes:
    limit = PPTX_PACKAGE_LIMITS.max_archive_size
    if isinstance(source, (str, PathLike)):
        with Path(source).open("rb") as stream:
            payload = stream.read(limit + 1)
    elif callable(getattr(source, "read", None)) and callable(getattr(source, "seek", None)):
        position = source.tell()
        try:
            source.seek(0)
            payload = source.read(limit + 1)
        finally:
            source.seek(position)
    else:
        raise LoadSaveWarningRefusal("source_unsupported", "use a path or seekable binary stream")
    if not isinstance(payload, bytes):
        raise LoadSaveWarningRefusal("source_unsupported", "presentation input must be binary")
    if len(payload) > limit:
        raise LoadSaveWarningRefusal("archive_size_limit", "presentation exceeds package limits")
    return payload


def _parts(payload: bytes) -> dict[str, bytes]:
    try:
        source = InMemoryPackageSource(payload)
        try:
            _validate_package_limits(source)
            with source.open() as package:
                return {name: package.read(name) for name in package.namelist()}
        finally:
            source.dispose()
    except (BadZipFile, EOFError) as exc:
        raise LoadSaveWarningRefusal(
            "package_invalid", "input is not a readable ZIP package"
        ) from exc
    except (PresentationPackageError, RuntimeError, NotImplementedError) as exc:
        raise LoadSaveWarningRefusal("package_unsupported", str(exc)) from exc


def _nodes(payload: bytes) -> list[dict[str, Any]]:
    # The byte-splice helper models UTF-8/ASCII XML, not UTF-16 byte offsets.
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in payload[:80]:
        raise LoadSaveWarningRefusal(
            "xml_encoding_unsupported", "metadata repairs require UTF-8 XML"
        )
    try:
        return _element_spans(payload)
    except (ExpatError, ValueError) as exc:
        raise LoadSaveWarningRefusal("package_invalid", "malformed package metadata XML") from exc


def _relationships(parts: dict[str, bytes]):
    for name, payload in parts.items():
        if name.endswith(".rels"):
            nodes = _nodes(payload)
            if nodes[0]["tag"] != f"{{{PKG_REL_NS}}}Relationships":
                raise LoadSaveWarningRefusal(
                    "package_invalid", f"invalid relationships root: {name}"
                )
            yield name, nodes


def _repair_plan(
    parts: dict[str, bytes], phase: str
) -> tuple[dict[str, bytes], list[LoadSaveWarning]]:
    replacements = {}
    warnings = []
    for name, nodes in _relationships(parts):
        seen = {}
        cuts = []
        for index, node in enumerate(nodes):
            if node["parent"] != 0 or node["tag"] != f"{{{PKG_REL_NS}}}Relationship":
                continue
            identity = node["attrib"].get("Id")
            if not identity:
                continue
            if identity in seen:
                first_index = seen[identity]
                first = nodes[first_index]
                if (
                    first["attrib"] != node["attrib"]
                    or parts[name][first["start"] : first["end"]]
                    != parts[name][node["start"] : node["end"]]
                    or any(child["parent"] in (first_index, index) for child in nodes)
                ):
                    raise LoadSaveWarningRefusal(
                        "ambiguous_relationship_identity",
                        f"conflicting relationship {identity} in {name}",
                    )
                cuts.append((node["start"], node["end"]))
                warnings.append(
                    LoadSaveWarning(
                        phase,
                        "duplicate_relationship_repaired",
                        f"Remove identical duplicate relationship {identity}; "
                        "retain its first occurrence",
                        name,
                        WarningCategory.PACKAGE_REPAIR,
                    )
                )
            else:
                seen[identity] = index
        if cuts:
            replacements[name] = _cut(parts[name], cuts)
    return replacements, warnings


def _signed(parts: dict[str, bytes]) -> bool:
    if any(name.casefold().startswith(_SIGNATURE_PREFIX) for name in parts):
        return True
    if "[Content_Types].xml" not in parts:
        raise LoadSaveWarningRefusal("package_invalid", "missing OPC content types")
    if any(
        node["attrib"].get("ContentType") in _SIGNATURE_TYPES
        for node in _nodes(parts["[Content_Types].xml"])
    ):
        return True
    return any(
        node["attrib"].get("Type", "").startswith(_SIGNATURE_REL)
        for _, nodes in _relationships(parts)
        for node in nodes
    )


def _strip_signature_plan(parts: dict[str, bytes]) -> tuple[dict[str, bytes], set[str]]:
    removed = {name for name in parts if name.startswith(_SIGNATURE_PREFIX)}
    if not removed or any(
        name.casefold().startswith(_SIGNATURE_PREFIX) and name not in removed for name in parts
    ):
        raise LoadSaveWarningRefusal(
            "signature_graph_unsupported", "nonstandard signature part names"
        )
    replacements = {}
    types = _nodes(parts["[Content_Types].xml"])
    cuts = []
    for node in types:
        if node["parent"] != 0:
            continue
        attr = node["attrib"]
        part = attr.get("PartName", "").lstrip("/")
        if attr.get("ContentType") in _SIGNATURE_TYPES:
            if node["tag"] == f"{{{CONTENT_TYPES_NS}}}Default":
                extension = attr.get("Extension", "").casefold()
                targets = {
                    name for name in parts if name.rsplit(".", 1)[-1].casefold() == extension
                }
            else:
                targets = {part}
            if not targets or not targets <= removed:
                raise LoadSaveWarningRefusal(
                    "signature_graph_unsupported", "signature content type names nonstandard parts"
                )
            cuts.append((node["start"], node["end"]))
        elif part in removed:
            cuts.append((node["start"], node["end"]))
    if cuts:
        replacements["[Content_Types].xml"] = _cut(parts["[Content_Types].xml"], cuts)
    for name, nodes in _relationships(parts):
        if name in removed:
            continue
        cuts = []
        owner = "" if name == "_rels/.rels" else name.replace("/_rels/", "/").removesuffix(".rels")
        for node in nodes:
            if node["parent"] != 0 or node["tag"] != f"{{{PKG_REL_NS}}}Relationship":
                continue
            attr = node["attrib"]
            target = resolve_package_target(owner, attr.get("Target", ""))
            signature_rel = attr.get("Type", "").startswith(_SIGNATURE_REL)
            if signature_rel:
                if (
                    attr.get("Type")
                    not in {_SIGNATURE_REL + "origin", _SIGNATURE_REL + "signature"}
                    or attr.get("TargetMode", "Internal") != "Internal"
                    or target not in removed
                ):
                    raise LoadSaveWarningRefusal(
                        "signature_graph_unsupported", "unsupported signature relationship"
                    )
                cuts.append((node["start"], node["end"]))
            elif target in removed:
                raise LoadSaveWarningRefusal(
                    "signature_graph_unsupported", "signature part has a nonsignature reference"
                )
        if cuts:
            replacements[name] = _cut(parts[name], cuts)
    return replacements, removed


def _rewrite(payload: bytes, replacements: dict[str, bytes], removed: set[str]) -> bytes:
    if not replacements and not removed:
        return payload
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as package:
        copy_open_package_with_replacements(package, output, replacements, removed)
    return output.getvalue()


def load_with_warnings(
    source: Any,
    *,
    warning_callback: WarningCallback | None = None,
    locking_behavior: str = "snapshot",
) -> LoadSaveResult:
    """Snapshot a real deck, report proposed repairs and obey explicit decisions."""
    _check_callback(warning_callback)
    if locking_behavior not in ("snapshot", "legacy_keep_open"):
        raise LoadSaveWarningRefusal("locking_unsupported", "use snapshot or legacy_keep_open")
    payload = _read_payload(source)
    parts = _parts(payload)
    replacements, warnings = _repair_plan(parts, "load")
    if locking_behavior == "legacy_keep_open":
        warnings.insert(
            0,
            LoadSaveWarning(
                "load",
                "obsolete_locking",
                "Keep-open locking is obsolete; continue with an owned snapshot",
                category=WarningCategory.OBSOLETE_OPTION,
            ),
        )
    removed: set[str] = set()
    if _signed(parts):
        warnings.append(
            LoadSaveWarning(
                "load",
                "signed_deck",
                "Package contains signatures; presence does not verify their validity",
                category=WarningCategory.SECURITY,
            )
        )
        if replacements:
            signature_replacements, removed = _strip_signature_plan({**parts, **replacements})
            replacements.update(signature_replacements)
            warnings.append(
                LoadSaveWarning(
                    "load",
                    "signature_invalidated",
                    "Repair changes a signed package; continue to remove its old signatures",
                    category=WarningCategory.SECURITY,
                )
            )
    observe_warnings(warnings, warning_callback)
    repaired = _rewrite(payload, replacements, removed)
    try:
        presentation = Presentation(BytesIO(repaired))
    except PresentationPackageError as exc:
        raise LoadSaveWarningRefusal("package_unsupported", str(exc), tuple(warnings)) from exc
    return LoadSaveResult(presentation, tuple(warnings))


def save_with_warnings(
    presentation: Presentation,
    destination: Any,
    *,
    warning_callback: WarningCallback | None = None,
) -> LoadSaveResult:
    """Save a copy of pending edits; abort never changes the caller's live facade."""
    _check_callback(warning_callback)
    file_like = callable(getattr(destination, "write", None))
    if not file_like and Path(destination).suffix.casefold() != ".pptx":
        raise LoadSaveWarningRefusal(
            "output_format_unsupported", "warning-controlled output is PPTX only"
        )
    with presentation._mutation_lock:
        if presentation._disposed:
            raise LoadSaveWarningRefusal("presentation_disposed", "presentation is disposed")
        baseline = presentation._source_path.read_bytes()
        before = _parts(baseline)
        # Never copy a TemporaryDirectory finalizer or let staging clean caller-owned state.
        memo = {
            id(value): None
            for value in (presentation._source_tempdir, presentation._odp_workspace)
            if value is not None
        }
        staged = copy.deepcopy(presentation, memo)
    with TemporaryDirectory(prefix="wolfppt-warning-save-") as directory:
        source = Path(directory) / "source.pptx"
        source.write_bytes(baseline)
        staged._source_path = source
        staged._source_tempdir = None
        staged._no_disk = False
        output = BytesIO()
        try:
            staged.save(output)
        finally:
            staged.dispose()
    payload = output.getvalue()
    after = _parts(payload)
    replacements, warnings = _repair_plan(after, "save")
    removed: set[str] = set()
    if _signed(before) and (before != after or replacements):
        signature_replacements, removed = _strip_signature_plan({**after, **replacements})
        replacements.update(signature_replacements)
        warnings.append(
            LoadSaveWarning(
                "save",
                "signature_invalidated",
                "Save changes a signed package; continue to remove its old signatures",
                category=WarningCategory.SECURITY,
            )
        )
    observe_warnings(warnings, warning_callback)
    payload = _rewrite(payload, replacements, removed)
    try:
        saved = Presentation(BytesIO(payload))
    except PresentationPackageError as exc:
        raise LoadSaveWarningRefusal("package_unsupported", str(exc), tuple(warnings)) from exc
    try:
        if file_like:
            written = destination.write(payload)
            if written is not None and written != len(payload):
                raise OSError("presentation stream did not accept the complete package")
        else:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            _publish_bytes(path, payload)
    except BaseException:
        saved.dispose()
        raise
    return LoadSaveResult(saved, tuple(warnings))
