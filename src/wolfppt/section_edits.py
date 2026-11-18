"""Package-level presentation section edit applicator for saves."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .section_xml import (
    SectionRecord,
    is_valid_guid,
    read_presentation_slide_ids,
    splice_sections_into_presentation_xml,
)
from .slide_zoom_targets import (
    ZoomTargetError,
    presentation_slide_parts,
    reconcile_section_zoom_targets,
)


class SectionRefusalError(ValueError):
    """Raised when section operations or memberships cannot be safely performed or reconciled."""


@dataclass
class SectionSpec:
    """Specification of one presentation section queued for save."""

    id: str
    name: str
    slide_ids: list[int] = field(default_factory=list)
    slide_indices: list[int] = field(default_factory=list)


@dataclass
class SectionEditsSnapshot:
    """Snapshot of presentation sections queued for save."""

    sections: list[SectionSpec] = field(default_factory=list)
    known_slide_ids: set[int] = field(default_factory=set)
    cleared: bool = False


def apply_section_edits(
    input_path: Path | str,
    output_path: Path | str,
    edits: Any,
) -> None:
    """Apply queued section edits to a presentation package.

    Reconciles slide additions and deletions against the current p:sldIdLst.
    Refuses ambiguous memberships, duplicate GUIDs, duplicate slide IDs,
    non-contiguous slide ranges, or unknown slide IDs.
    Preserves unrelated extensions and other package parts byte-for-byte.
    """
    in_path = Path(input_path)
    out_path = Path(output_path)

    if edits is None:
        if in_path.resolve() != out_path.resolve():
            shutil.copy2(in_path, out_path)
        return

    # Coerce edits
    if isinstance(edits, SectionEditsSnapshot):
        spec_list = edits.sections
        known_ids = edits.known_slide_ids
        cleared = edits.cleared
    elif isinstance(edits, dict):
        spec_list = edits.get("sections", [])
        known_ids = set(edits.get("known_slide_ids", []))
        cleared = edits.get("cleared", False)
    elif isinstance(edits, list):
        spec_list = edits
        known_ids = set()
        cleared = False
    else:
        raise TypeError(
            f"expected SectionEditsSnapshot or dict, got {type(edits).__name__}"
        )

    with zipfile.ZipFile(in_path) as pkg:
        xml_bytes = pkg.read("ppt/presentation.xml")

    root = ET.fromstring(xml_bytes)
    current_slide_ids = read_presentation_slide_ids(root)
    current_slide_ids_set = set(current_slide_ids)

    # Empty sections / cleared
    if cleared or not spec_list:
        _write_sections(in_path, out_path, xml_bytes, root, [])
        return

    # Reconcile specs against settled p:sldIdLst
    reconciled_records: list[SectionRecord] = []
    for spec in spec_list:
        if isinstance(spec, dict):
            sec_id = spec["id"]
            sec_name = spec.get("name", "")
            slide_ids = spec.get("slide_ids", [])
            slide_indices = spec.get("slide_indices", [])
        elif isinstance(spec, SectionSpec):
            sec_id = spec.id
            sec_name = spec.name
            slide_ids = spec.slide_ids
            slide_indices = spec.slide_indices
        elif hasattr(spec, "id") and hasattr(spec, "name"):
            sec_id = spec.id
            sec_name = spec.name
            slide_ids = getattr(spec, "slide_ids", [])
            slide_indices = getattr(spec, "slide_indices", [])
        else:
            raise TypeError(f"invalid section spec type: {type(spec).__name__}")

        if not is_valid_guid(sec_id):
            raise SectionRefusalError(
                f"section {sec_name!r} has invalid GUID identifier: {sec_id!r}"
            )

        # Resolve slide IDs for this section. A position only stands in for a
        # snapshot id that saving renumbered (a pending slide), so it must land
        # on an id the snapshot never knew; otherwise a stale position would
        # hand this section a surviving slide that another entry already owns.
        def at_position(idx: int) -> int | None:
            if 0 <= idx < len(current_slide_ids):
                candidate = current_slide_ids[idx]
                if candidate not in known_ids:
                    return candidate
            return None

        final_sids: list[int] = []
        if slide_ids and any(sid in current_slide_ids_set for sid in slide_ids):
            for i, sid in enumerate(slide_ids):
                if sid in current_slide_ids_set:
                    final_sids.append(sid)
                elif slide_indices and i < len(slide_indices):
                    resolved = at_position(slide_indices[i])
                    if resolved is not None:
                        final_sids.append(resolved)
                elif sid in known_ids:
                    # Legitimate deleted slide reconciled out
                    pass
                else:
                    raise SectionRefusalError(
                        f"section {sec_name!r} references unknown slide id {sid}"
                    )
        elif slide_indices:
            for idx in slide_indices:
                resolved = at_position(idx)
                if resolved is not None:
                    final_sids.append(resolved)
        elif slide_ids:
            for sid in slide_ids:
                if sid in current_slide_ids_set:
                    final_sids.append(sid)
                elif sid in known_ids:
                    # Legitimate deleted slide reconciled out
                    pass
                else:
                    raise SectionRefusalError(
                        f"section {sec_name!r} references unknown slide id {sid}"
                    )
        # Membership is a set; slides reordered after the snapshot keep their
        # section, and the list follows the settled presentation order.
        final_sids.sort(key=current_slide_ids.index)
        reconciled_records.append(
            SectionRecord(id=sec_id, name=sec_name, slide_ids=final_sids)
        )

    # Validate GUID uniqueness
    seen_guids: set[str] = set()
    for rec in reconciled_records:
        norm = rec.id.strip().upper()
        if norm in seen_guids:
            raise SectionRefusalError(f"duplicate section GUID identifier: {rec.id!r}")
        seen_guids.add(norm)

    # Validate slide membership uniqueness across sections
    seen_sids: dict[int, str] = {}
    for rec in reconciled_records:
        for sid in rec.slide_ids:
            if sid in seen_sids:
                raise SectionRefusalError(
                    f"ambiguous membership: slide id {sid} appears in multiple sections "
                    f"({seen_sids[sid]!r} and {rec.name!r})"
                )
            seen_sids[sid] = rec.name

    # Validate contiguous slide membership in presentation order
    for rec in reconciled_records:
        if rec.slide_ids:
            positions = [current_slide_ids.index(sid) for sid in rec.slide_ids]
            expected = list(range(positions[0], positions[0] + len(positions)))
            if positions != expected:
                raise SectionRefusalError(
                    f"section {rec.name!r} has non-contiguous slides in presentation order: "
                    f"slide ids {rec.slide_ids}"
                )

    # Validate section sequence order in presentation order
    last_end = -1
    for rec in reconciled_records:
        if rec.slide_ids:
            start_pos = current_slide_ids.index(rec.slide_ids[0])
            if start_pos < last_end:
                raise SectionRefusalError(
                    "sections must cover contiguous ranges in presentation order"
                )
            last_end = current_slide_ids.index(rec.slide_ids[-1])

    _write_sections(in_path, out_path, xml_bytes, root, reconciled_records)


def _write_sections(
    in_path: Path,
    out_path: Path,
    xml_bytes: bytes,
    root: ET.Element,
    records: list[SectionRecord],
) -> None:
    """Publish the settled sections and keep every section zoom on a live target.

    Only the section extension of ``ppt/presentation.xml`` is rewritten. A
    section zoom whose section disappears or empties refuses the edit; one whose
    section now starts on another slide has its fallback link moved there.
    """
    with zipfile.ZipFile(in_path) as pkg:
        try:
            replacements = reconcile_section_zoom_targets(
                pkg,
                presentation_slide_parts(pkg, root),
                [(record.id, record.slide_ids) for record in records],
            )
        except ZoomTargetError as exc:
            raise SectionRefusalError(str(exc)) from exc
    replacements["ppt/presentation.xml"] = splice_sections_into_presentation_xml(
        xml_bytes, records
    )
    copy_package_with_replacements(in_path, out_path, replacements)


__all__ = [
    "SectionEditsSnapshot",
    "SectionRefusalError",
    "SectionSpec",
    "apply_section_edits",
]
