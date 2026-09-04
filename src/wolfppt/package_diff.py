"""Normalized package comparison for PPTX/PPTM files."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.dom import minidom


@dataclass(frozen=True)
class PartRecord:
    name: str
    size: int
    sha256: str
    kind: str


@dataclass(frozen=True)
class PackageManifest:
    path: str
    parts: list[PartRecord]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class PackageDiff:
    left: str
    right: str
    added_parts: list[str]
    removed_parts: list[str]
    changed_parts: list[str]

    @property
    def clean(self) -> bool:
        return not (self.added_parts or self.removed_parts or self.changed_parts)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def package_manifest(path: str | Path) -> PackageManifest:
    package = Path(path)
    records: list[PartRecord] = []
    with zipfile.ZipFile(package) as zf:
        for name in sorted(zf.namelist()):
            payload = zf.read(name)
            normalized = _normalize_part(name, payload)
            records.append(
                PartRecord(
                    name=name,
                    size=len(normalized),
                    sha256=hashlib.sha256(normalized).hexdigest(),
                    kind=_part_kind(name),
                )
            )
    return PackageManifest(path=str(package), parts=records)


def diff_packages(left: str | Path, right: str | Path) -> PackageDiff:
    left_manifest = package_manifest(left)
    right_manifest = package_manifest(right)
    left_parts = {part.name: part for part in left_manifest.parts}
    right_parts = {part.name: part for part in right_manifest.parts}

    left_names = set(left_parts)
    right_names = set(right_parts)
    common = left_names & right_names
    changed = [
        name
        for name in sorted(common)
        if left_parts[name].sha256 != right_parts[name].sha256
    ]
    return PackageDiff(
        left=str(left),
        right=str(right),
        added_parts=sorted(right_names - left_names),
        removed_parts=sorted(left_names - right_names),
        changed_parts=changed,
    )


def _normalize_part(name: str, payload: bytes) -> bytes:
    if not name.endswith(".xml") and not name.endswith(".rels"):
        return payload
    try:
        parsed = minidom.parseString(payload)
    except Exception:
        return payload.strip()
    return parsed.toxml(encoding="utf-8")


def _part_kind(name: str) -> str:
    if name.endswith(".rels"):
        return "relationships"
    if name.endswith(".xml"):
        return "xml"
    if name.startswith("ppt/media/"):
        return "media"
    if name.startswith("ppt/embeddings/"):
        return "embedding"
    if name.endswith("vbaProject.bin"):
        return "vba"
    return "binary"

