"""Bounded OLE compound-file (MS-CFB) writer for VBA projects."""

from __future__ import annotations

import struct
from dataclasses import dataclass

_CFB_FREESECT = 0xFFFFFFFF
_CFB_ENDOFCHAIN = 0xFFFFFFFE
_CFB_FATSECT = 0xFFFFFFFD
_CFB_DIFSECT = 0xFFFFFFFC
_CFB_NOSTREAM = 0xFFFFFFFF
_CFB_SECTOR_SIZE = 512
_CFB_MINI_SECTOR_SIZE = 64
_CFB_MINI_CUTOFF = 4096
_CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


@dataclass
class _CompoundDirectoryEntry:
    name: str
    entry_type: int
    start_sector: int = _CFB_ENDOFCHAIN
    size: int = 0
    left: int = _CFB_NOSTREAM
    right: int = _CFB_NOSTREAM
    child: int = _CFB_NOSTREAM
    color: int = 1


class _CompoundFileWriter:
    """Small CFB writer for the MS-OVBA storage layout authored by WolfPPT."""

    def __init__(self, streams: dict[tuple[str, ...], bytes]) -> None:
        self._streams = streams

    def to_bytes(self) -> bytes:
        entries, entry_ids = self._directory_entries()
        mini_data, mini_fat = self._assign_stream_locations(entries, entry_ids)
        regular_payloads: list[tuple[int, bytes]] = []
        if mini_data:
            regular_payloads.append((0, mini_data))
        for path, payload in self._streams.items():
            if len(payload) >= _CFB_MINI_CUTOFF:
                regular_payloads.append((entry_ids[path], payload))
        return self._serialize(entries, regular_payloads, mini_fat)

    def _directory_entries(
        self,
    ) -> tuple[list[_CompoundDirectoryEntry], dict[tuple[str, ...], int]]:
        entries = [_CompoundDirectoryEntry("Root Entry", 5)]
        entry_ids: dict[tuple[str, ...], int] = {}
        storages = sorted({path[:depth] for path in self._streams for depth in range(1, len(path))})
        for storage in storages:
            entry_ids[storage] = len(entries)
            entries.append(_CompoundDirectoryEntry(storage[-1], 1, start_sector=0))
        for path in sorted(self._streams, key=lambda item: tuple(part.casefold() for part in item)):
            entry_ids[path] = len(entries)
            entries.append(_CompoundDirectoryEntry(path[-1], 2))
        children: dict[tuple[str, ...], list[int]] = {(): []}
        for storage in storages:
            children.setdefault(storage, [])
            children.setdefault(storage[:-1], []).append(entry_ids[storage])
        for path in self._streams:
            children.setdefault(path[:-1], []).append(entry_ids[path])
        for parent, ids in children.items():
            parent_id = 0 if not parent else entry_ids[parent]
            entries[parent_id].child = _link_compound_siblings(entries, ids)
        return entries, entry_ids

    def _assign_stream_locations(
        self,
        entries: list[_CompoundDirectoryEntry],
        entry_ids: dict[tuple[str, ...], int],
    ) -> tuple[bytes, list[int]]:
        mini_data = bytearray()
        mini_fat: list[int] = []
        for path, payload in self._streams.items():
            if len(payload) >= _CFB_MINI_CUTOFF:
                entries[entry_ids[path]].size = len(payload)
                continue
            entry = entries[entry_ids[path]]
            entry.size = len(payload)
            if not payload:
                continue
            first = len(mini_fat)
            chunks = [
                payload[index : index + _CFB_MINI_SECTOR_SIZE]
                for index in range(0, len(payload), _CFB_MINI_SECTOR_SIZE)
            ]
            for index, chunk in enumerate(chunks):
                mini_data.extend(chunk.ljust(_CFB_MINI_SECTOR_SIZE, b"\x00"))
                mini_fat.append(first + index + 1 if index + 1 < len(chunks) else _CFB_ENDOFCHAIN)
            entry.start_sector = first
        entries[0].size = len(mini_data)
        return bytes(mini_data), mini_fat

    def _serialize(
        self,
        entries: list[_CompoundDirectoryEntry],
        regular_payloads: list[tuple[int, bytes]],
        mini_fat: list[int],
    ) -> bytes:
        from .package_parts import VbaProjectError

        data_sector_count = sum(_sector_count(payload) for _, payload in regular_payloads)
        mini_fat_sector_count = _sector_count(
            b"".join(struct.pack("<I", value) for value in mini_fat)
        )
        directory_sector_count = max(1, (len(entries) + 3) // 4)
        fat_sector_count = 1
        while True:
            total = (
                data_sector_count
                + mini_fat_sector_count
                + directory_sector_count
                + fat_sector_count
            )
            required = (total + 127) // 128
            if required == fat_sector_count:
                break
            fat_sector_count = required
        if fat_sector_count > 109:
            raise VbaProjectError("VBA CFB project requires unsupported DIFAT sectors")
        next_sector = 0
        sectors: list[bytes] = []
        fat = [_CFB_FREESECT] * total
        for entry_id, payload in regular_payloads:
            start, chain = _allocate_compound_chain(sectors, fat, next_sector, payload)
            next_sector += len(chain)
            entries[entry_id].start_sector = start
            entries[entry_id].size = len(payload)
        mini_fat_payload = b"".join(struct.pack("<I", value) for value in mini_fat)
        mini_fat_start = _CFB_ENDOFCHAIN
        if mini_fat_payload:
            mini_fat_start, chain = _allocate_compound_chain(
                sectors, fat, next_sector, mini_fat_payload
            )
            next_sector += len(chain)
        directory_start = next_sector
        directory_payload = b"".join(_serialize_compound_entry(entry) for entry in entries)
        # MS-CFB 2.6.3: unused entries are zero except NOSTREAM sibling/child ids.
        free_entry = bytes(68) + b"\xff" * 12 + bytes(48)
        directory_payload += free_entry * (directory_sector_count * 4 - len(entries))
        _, chain = _allocate_compound_chain(sectors, fat, next_sector, directory_payload)
        next_sector += len(chain)
        fat_sector_ids = list(range(next_sector, next_sector + fat_sector_count))
        for sector_id in fat_sector_ids:
            fat[sector_id] = _CFB_FATSECT
        fat_payload = b"".join(struct.pack("<I", value) for value in fat)
        fat_payload += struct.pack("<I", _CFB_FREESECT) * (
            (fat_sector_count * _CFB_SECTOR_SIZE - len(fat_payload)) // 4
        )
        sectors.extend(
            fat_payload[index : index + _CFB_SECTOR_SIZE]
            for index in range(0, len(fat_payload), _CFB_SECTOR_SIZE)
        )
        if len(sectors) != total:
            raise VbaProjectError("VBA CFB sector allocation is inconsistent")
        header = _compound_header(
            fat_sector_ids,
            directory_start,
            mini_fat_start,
            mini_fat_sector_count,
        )
        return header + b"".join(sectors)


def _link_compound_siblings(
    entries: list[_CompoundDirectoryEntry],
    ids: list[int],
) -> int:
    # MS-CFB 2.6.4 red-black tree order: shorter names first, then uppercase.
    ordered = sorted(ids, key=lambda index: (len(entries[index].name), entries[index].name.upper()))

    def link(start: int, end: int) -> int:
        if start >= end:
            return _CFB_NOSTREAM
        middle = (start + end) // 2
        entry = entries[ordered[middle]]
        entry.left = link(start, middle)
        entry.right = link(middle + 1, end)
        entry.color = 1
        return ordered[middle]

    return link(0, len(ordered))


def _sector_count(payload: bytes) -> int:
    return (len(payload) + _CFB_SECTOR_SIZE - 1) // _CFB_SECTOR_SIZE


def _allocate_compound_chain(
    sectors: list[bytes],
    fat: list[int],
    start_sector: int,
    payload: bytes,
) -> tuple[int, list[int]]:
    count = _sector_count(payload)
    if not count:
        return _CFB_ENDOFCHAIN, []
    chain = list(range(start_sector, start_sector + count))
    for index, sector_id in enumerate(chain):
        fat[sector_id] = chain[index + 1] if index + 1 < len(chain) else _CFB_ENDOFCHAIN
    sectors.extend(
        payload[index : index + _CFB_SECTOR_SIZE].ljust(_CFB_SECTOR_SIZE, b"\x00")
        for index in range(0, len(payload), _CFB_SECTOR_SIZE)
    )
    return chain[0], chain


def _serialize_compound_entry(entry: _CompoundDirectoryEntry) -> bytes:
    name = (entry.name[:31] + "\x00").encode("utf-16le")
    payload = bytearray(128)
    payload[: min(len(name), 64)] = name[:64]
    struct.pack_into("<H", payload, 64, min(len(name), 64))
    payload[66] = entry.entry_type
    payload[67] = entry.color
    struct.pack_into("<III", payload, 68, entry.left, entry.right, entry.child)
    struct.pack_into("<I", payload, 116, entry.start_sector)
    struct.pack_into("<Q", payload, 120, entry.size)
    return bytes(payload)


def _compound_header(
    fat_sector_ids: list[int],
    directory_start: int,
    mini_fat_start: int,
    mini_fat_sector_count: int,
) -> bytes:
    header = bytearray(_CFB_SECTOR_SIZE)
    header[:8] = _CFB_MAGIC
    struct.pack_into("<HHHHH", header, 24, 0x003E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<I", header, 44, len(fat_sector_ids))
    struct.pack_into("<I", header, 48, directory_start)
    struct.pack_into("<I", header, 56, _CFB_MINI_CUTOFF)
    struct.pack_into("<I", header, 60, mini_fat_start)
    struct.pack_into("<I", header, 64, mini_fat_sector_count)
    struct.pack_into("<I", header, 68, _CFB_ENDOFCHAIN)
    struct.pack_into("<I", header, 72, 0)
    for index in range(109):
        value = fat_sector_ids[index] if index < len(fat_sector_ids) else _CFB_FREESECT
        struct.pack_into("<I", header, 76 + index * 4, value)
    return bytes(header)
