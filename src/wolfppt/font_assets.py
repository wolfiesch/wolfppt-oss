"""Public font admission, owned bytes, identity, and sfnt metrics.

Embedded-font editing and substitution require no renderer or Pillow. Admit
explicit single-face bytes against their family/style claim; managers check
embedding permissions before package writes. Font measurement is lazy and uses
only the admitted snapshot through the commercial rendering boundary.
"""

from __future__ import annotations

import functools
import hashlib
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .editions import commercial_module
from .render_refusals import MissingFontRefusal, RenderRefusal

EMU_PER_POINT = 12700

#: FreeType is asked to size glyphs at this many pixels per em before the
#: advance is scaled to a point size.  A large size keeps hinting error far
#: below one EMU while staying well inside FreeType's fixed-point range.
_MEASUREMENT_PIXELS_PER_EM = 1000

#: Native PowerPoint 16.113 advances every glyph by its design advance rounded
#: half up to a whole 1/8 pt, one pixel of a 576 dpi grid (probe deck
#: ppt-text-glyph-advance-model-20260924: every advance of Aptos, Calibri,
#: Arial and Times New Roman at 12/24/40 pt within the PDF writer's half TJ
#: unit of that rule).
ADVANCE_GRID_PER_POINT = 8


class FontRefusal(RenderRefusal):
    """Raised when a font asset cannot be admitted or a text run cannot be set."""


class UnadmittedFontRefusal(FontRefusal, MissingFontRefusal):
    """Raised when text requires a font family and style that was not admitted."""


@dataclass(frozen=True)
class FontRequest:
    """One admitted font asset: a family/style claim plus the file behind it."""

    family: str
    bold: bool
    italic: bool
    path: Path

    @property
    def style_name(self) -> str:
        return (
            "bold italic"
            if self.bold and self.italic
            else ("bold" if self.bold else ("italic" if self.italic else "regular"))
        )

    @property
    def spec(self) -> str:
        """Return the CLI-style admission spec for this asset."""
        return f"{self.family}:{self.style_name}={self.path}"


def parse_font_spec(value: str) -> tuple[str, bool, bool, Path]:
    """Parse ``Family[:style]=/path/to/font.ttf`` into its four facts."""
    if "=" not in value:
        raise FontRefusal(f"font asset {value!r} must look like 'Family[:style]=/path/to/font.ttf'")
    head, _, raw_path = value.partition("=")
    if not raw_path:
        raise FontRefusal(f"font asset {value!r} has no font file path")
    family, _, style = head.partition(":")
    family = family.strip()
    if not family:
        raise FontRefusal(f"font asset {value!r} has no font family")
    normalized_style = style.strip().casefold()
    if normalized_style in {"", "regular", "normal"}:
        bold, italic = False, False
    elif normalized_style in {"bold"}:
        bold, italic = True, False
    elif normalized_style in {"italic", "oblique"}:
        bold, italic = False, True
    elif normalized_style in {
        "bold italic",
        "bold-italic",
        "bolditalic",
        "bold oblique",
    }:
        bold, italic = True, True
    else:
        raise FontRefusal(
            f"font asset {value!r} has unsupported style {style!r}; "
            "use regular, bold, italic, or 'bold italic'"
        )
    return family, bold, italic, Path(raw_path)


def _normalized_font_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _glyph_advance(advances: Sequence[int], glyph_id: int) -> int:
    """Return one glyph's advance width in font units."""
    if glyph_id < 0 or glyph_id >= len(advances):
        raise FontRefusal(f"font has no advance width for glyph {glyph_id}")
    return advances[glyph_id]


def _scaled(value: int, units_per_em: int) -> int:
    """Scale a font-unit metric into PDF glyph space (1000 units per em)."""
    return round(value * 1000 / units_per_em)


@dataclass(frozen=True)
class SfntTables:
    """Parsed sfnt metrics and Unicode coverage of a single-face font."""

    units_per_em: int
    bbox: tuple[int, int, int, int]
    ascender: int
    descender: int
    cap_height: int
    advances: tuple[int, ...]
    glyph_ids: Mapping[int, int]
    has_true_type_outlines: bool

    def glyph_advance(self, glyph_id: int) -> int:
        return _glyph_advance(self.advances, glyph_id)

    def scaled_advance(self, glyph_id: int) -> int:
        return _scaled(self.glyph_advance(glyph_id), self.units_per_em)

    def scaled(self, value: int) -> int:
        return _scaled(value, self.units_per_em)


def _read_sfnt_tables(payload: bytes) -> dict[str, bytes]:
    if payload[:4] == b"ttcf":
        raise FontRefusal(
            "font collections (.ttc) are not supported; supply a single-face font file"
        )
    if len(payload) < 12:
        raise FontRefusal("font file is too short to hold an sfnt header")
    table_count = struct.unpack_from(">H", payload, 4)[0]
    tables: dict[str, bytes] = {}
    for index in range(table_count):
        record = 12 + index * 16
        if record + 16 > len(payload):
            raise FontRefusal("font file has a truncated table directory")
        tag = payload[record : record + 4].decode("latin-1")
        offset, length = struct.unpack_from(">II", payload, record + 8)
        if offset + length > len(payload):
            raise FontRefusal(f"font table {tag!r} extends past the end of the file")
        tables[tag] = payload[offset : offset + length]
    return tables


def _parse_cmap(tables: Mapping[str, bytes]) -> dict[int, int]:
    cmap = tables.get("cmap")
    if not cmap:
        raise FontRefusal("font file has no cmap table")
    subtables = struct.unpack_from(">H", cmap, 2)[0]
    best: tuple[int, int] | None = None
    for index in range(subtables):
        platform, encoding, offset = struct.unpack_from(">HHI", cmap, 4 + index * 8)
        if offset >= len(cmap):
            continue
        format_code = struct.unpack_from(">H", cmap, offset)[0]
        if format_code not in (4, 12):
            continue
        rank = 0
        if platform == 3 and encoding == 10:
            rank = 4
        elif platform == 3 and encoding == 1:
            rank = 3
        elif platform == 0:
            rank = 2 if format_code == 12 else 1
        if best is None or rank > best[0]:
            best = (rank, offset)
    if best is None:
        raise FontRefusal("font file has no usable Unicode cmap subtable")
    offset = best[1]
    format_code = struct.unpack_from(">H", cmap, offset)[0]
    if format_code == 12:
        return _parse_cmap_format_12(cmap, offset)
    return _parse_cmap_format_4(cmap, offset)


def _parse_cmap_format_4(cmap: bytes, offset: int) -> dict[int, int]:
    segment_count = struct.unpack_from(">H", cmap, offset + 6)[0] // 2
    ends = offset + 14
    starts = ends + segment_count * 2 + 2
    deltas = starts + segment_count * 2
    range_offsets = deltas + segment_count * 2
    glyph_ids: dict[int, int] = {}
    for index in range(segment_count):
        end_code = struct.unpack_from(">H", cmap, ends + index * 2)[0]
        start_code = struct.unpack_from(">H", cmap, starts + index * 2)[0]
        delta = struct.unpack_from(">h", cmap, deltas + index * 2)[0]
        range_offset = struct.unpack_from(">H", cmap, range_offsets + index * 2)[0]
        if start_code == 0xFFFF:
            continue
        for code in range(start_code, end_code + 1):
            if range_offset == 0:
                glyph = (code + delta) & 0xFFFF
            else:
                glyph_position = range_offsets + index * 2 + range_offset + (code - start_code) * 2
                if glyph_position + 2 > len(cmap):
                    continue
                glyph = struct.unpack_from(">H", cmap, glyph_position)[0]
                if glyph != 0:
                    glyph = (glyph + delta) & 0xFFFF
            if glyph != 0:
                glyph_ids[code] = glyph
    return glyph_ids


def _parse_cmap_format_12(cmap: bytes, offset: int) -> dict[int, int]:
    group_count = struct.unpack_from(">I", cmap, offset + 12)[0]
    glyph_ids: dict[int, int] = {}
    for index in range(group_count):
        record = offset + 16 + index * 12
        start_code, end_code, start_glyph = struct.unpack_from(">III", cmap, record)
        if end_code - start_code > 0x10FFFF:
            raise FontRefusal("font cmap group spans more code points than Unicode")
        for code in range(start_code, end_code + 1):
            glyph_ids[code] = start_glyph + (code - start_code)
    return glyph_ids


def parse_sfnt_tables(payload: bytes) -> SfntTables:
    """Return the sfnt facts of one font file, refusing anything unreadable."""
    tables = _read_sfnt_tables(payload)
    head = tables.get("head")
    hhea = tables.get("hhea")
    hmtx = tables.get("hmtx")
    if head is None or hhea is None or hmtx is None:
        raise FontRefusal("font file is missing head, hhea, or hmtx tables")
    if len(head) < 54:
        raise FontRefusal("font head table is truncated")
    units_per_em = struct.unpack_from(">H", head, 18)[0]
    if units_per_em <= 0:
        raise FontRefusal("font head table declares a non-positive em size")
    x_min, y_min, x_max, y_max = struct.unpack_from(">hhhh", head, 36)
    if len(hhea) < 36:
        raise FontRefusal("font hhea table is truncated")
    ascender, descender, _line_gap = struct.unpack_from(">hhh", hhea, 4)
    horizontal_metrics = struct.unpack_from(">H", hhea, 34)[0]
    if horizontal_metrics == 0:
        raise FontRefusal("font hhea table declares no horizontal metrics")
    advances: list[int] = []
    for index in range(horizontal_metrics):
        position = index * 4
        if position + 2 > len(hmtx):
            raise FontRefusal("font hmtx table is truncated")
        advances.append(struct.unpack_from(">H", hmtx, position)[0])
    cap_height = 0
    os2 = tables.get("OS/2")
    if os2 is not None and len(os2) >= 78:
        version = struct.unpack_from(">H", os2, 0)[0]
        if version >= 2 and len(os2) >= 90:
            cap_height = struct.unpack_from(">h", os2, 88)[0]
    if cap_height <= 0:
        cap_height = round(ascender * 0.7)
    return SfntTables(
        units_per_em=units_per_em,
        bbox=(x_min, y_min, x_max, y_max),
        ascender=ascender,
        descender=descender,
        cap_height=cap_height,
        advances=tuple(advances),
        glyph_ids=_parse_cmap(tables),
        has_true_type_outlines="glyf" in tables,
    )


@dataclass(frozen=True)
class _PairSubtable:
    """One GPOS PairPos subtable reduced to its first-glyph x-advance values."""

    coverage: Mapping[int, int]
    #: Format 1: per coverage index, second glyph -> x advance.
    pairs: tuple[Mapping[int, int], ...] | None = None
    #: Format 2: glyph classes and the class1 x class2 x-advance matrix.
    first_classes: Mapping[int, int] | None = None
    second_classes: Mapping[int, int] | None = None
    class_values: tuple[tuple[int, ...], ...] | None = None

    def value(self, first: int, second: int) -> int | None:
        """Return the pair's x advance, or ``None`` when this subtable skips it."""
        index = self.coverage.get(first)
        if index is None:
            return None
        if self.pairs is not None:
            return self.pairs[index].get(second)
        assert self.first_classes is not None and self.second_classes is not None
        assert self.class_values is not None
        row = self.class_values[self.first_classes.get(first, 0)]
        second_class = self.second_classes.get(second, 0)
        return row[second_class] if second_class < len(row) else None


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _coverage(data: bytes, offset: int) -> dict[int, int]:
    format_code = _u16(data, offset)
    count = _u16(data, offset + 2)
    if format_code == 1:
        return {_u16(data, offset + 4 + index * 2): index for index in range(count)}
    if format_code == 2:
        covered: dict[int, int] = {}
        for index in range(count):
            start, end, first_index = struct.unpack_from(">HHH", data, offset + 4 + index * 6)
            for glyph in range(start, end + 1):
                covered[glyph] = first_index + glyph - start
        return covered
    raise FontRefusal(f"font GPOS coverage format {format_code} is unknown")


def _class_definition(data: bytes, offset: int) -> dict[int, int]:
    format_code = _u16(data, offset)
    if format_code == 1:
        start, count = struct.unpack_from(">HH", data, offset + 2)
        return {start + index: _u16(data, offset + 6 + index * 2) for index in range(count)}
    if format_code == 2:
        classes: dict[int, int] = {}
        for index in range(_u16(data, offset + 2)):
            start, end, value = struct.unpack_from(">HHH", data, offset + 4 + index * 6)
            for glyph in range(start, end + 1):
                classes[glyph] = value
        return classes
    raise FontRefusal(f"font GPOS class definition format {format_code} is unknown")


def _x_advance_slot(value_format: int) -> int | None:
    """Byte offset of XAdvance inside a value record, or ``None`` if absent."""
    if not value_format & 0x0004:
        return None
    return 2 * (value_format & 0x0003).bit_count()


def _pair_subtable(data: bytes, offset: int) -> _PairSubtable:
    format_code, coverage_offset, format1, format2 = struct.unpack_from(">HHHH", data, offset)
    size1 = 2 * format1.bit_count()
    size2 = 2 * format2.bit_count()
    slot = _x_advance_slot(format1)
    coverage = _coverage(data, offset + coverage_offset)
    if format_code == 1:
        pairs: list[dict[int, int]] = []
        for index in range(_u16(data, offset + 8)):
            pair_set = offset + _u16(data, offset + 10 + index * 2)
            record_size = 2 + size1 + size2
            values: dict[int, int] = {}
            for record in range(_u16(data, pair_set)):
                position = pair_set + 2 + record * record_size
                values[_u16(data, position)] = (
                    0 if slot is None else struct.unpack_from(">h", data, position + 2 + slot)[0]
                )
            pairs.append(values)
        return _PairSubtable(coverage, pairs=tuple(pairs))
    if format_code == 2:
        class1_offset, class2_offset, class1_count, class2_count = struct.unpack_from(
            ">HHHH", data, offset + 8
        )
        record_size = size1 + size2
        matrix = offset + 16
        rows = tuple(
            tuple(
                0
                if slot is None
                else struct.unpack_from(
                    ">h",
                    data,
                    matrix + (first * class2_count + second) * record_size + slot,
                )[0]
                for second in range(class2_count)
            )
            for first in range(class1_count)
        )
        return _PairSubtable(
            coverage,
            first_classes=_class_definition(data, offset + class1_offset),
            second_classes=_class_definition(data, offset + class2_offset),
            class_values=rows,
        )
    raise FontRefusal(f"font GPOS pair adjustment format {format_code} is unknown")


def _kern_feature_lookups(gpos: bytes) -> list[int]:
    """Return the lookup indices of the Latin (or default) ``kern`` feature."""
    script_list, feature_list = struct.unpack_from(">HH", gpos, 4)
    features = [
        (
            gpos[feature_list + 2 + index * 6 : feature_list + 6 + index * 6],
            feature_list + _u16(gpos, feature_list + 6 + index * 6),
        )
        for index in range(_u16(gpos, feature_list))
    ]
    scripts = {
        gpos[script_list + 2 + index * 6 : script_list + 6 + index * 6]: script_list
        + _u16(gpos, script_list + 6 + index * 6)
        for index in range(_u16(gpos, script_list))
    }
    feature_indices: list[int] | None = None
    for tag in (b"latn", b"DFLT"):
        script = scripts.get(tag)
        if script is None or _u16(gpos, script) == 0:
            continue
        lang_sys = script + _u16(gpos, script)
        required, count = struct.unpack_from(">HH", gpos, lang_sys + 2)
        feature_indices = [_u16(gpos, lang_sys + 6 + index * 2) for index in range(count)]
        if required != 0xFFFF:
            feature_indices.append(required)
        break
    if feature_indices is None:
        feature_indices = list(range(len(features)))
    lookups: list[int] = []
    for index in feature_indices:
        tag, feature = features[index]
        if tag != b"kern":
            continue
        for position in range(_u16(gpos, feature + 2)):
            lookup = _u16(gpos, feature + 4 + position * 2)
            if lookup not in lookups:
                lookups.append(lookup)
    return sorted(lookups)


def parse_gpos_pair_kerning(payload: bytes) -> tuple[tuple[_PairSubtable, ...], ...]:
    """Return the GPOS ``kern`` feature's pair-adjustment lookups.

    Each lookup is a sequence of subtables tried in order; only the first
    glyph's x advance is kept, which is the value native PowerPoint 16.113
    adds to the first glyph's design advance before rounding.  A font without
    a GPOS ``kern`` feature kerns nothing (the legacy ``kern`` table is not
    what PowerPoint applies).
    """
    gpos = _read_sfnt_tables(payload).get("GPOS")
    if not gpos:
        return ()
    try:
        lookup_list = _u16(gpos, 8)
        lookups: list[tuple[_PairSubtable, ...]] = []
        for index in _kern_feature_lookups(gpos):
            lookup = lookup_list + _u16(gpos, lookup_list + 2 + index * 2)
            lookup_type, _flag, count = struct.unpack_from(">HHH", gpos, lookup)
            subtables: list[_PairSubtable] = []
            for position in range(count):
                subtable = lookup + _u16(gpos, lookup + 6 + position * 2)
                kind = lookup_type
                if kind == 9:
                    kind = _u16(gpos, subtable + 2)
                    subtable += struct.unpack_from(">I", gpos, subtable + 4)[0]
                if kind == 2:
                    subtables.append(_pair_subtable(gpos, subtable))
            if subtables:
                lookups.append(tuple(subtables))
    except (struct.error, IndexError) as exc:
        raise FontRefusal("font GPOS table is truncated or malformed") from exc
    return tuple(lookups)


@dataclass(frozen=True)
class FontAsset:
    """Owned font bytes, checked identity and sfnt metrics; render lazily."""

    request: FontRequest
    sha256: str
    size_bytes: int
    payload: bytes = field(repr=False)
    family: str
    style: str
    units_per_em: int
    glyph_ids: Mapping[int, int]
    advances: tuple[int, ...]
    ascender: int
    descender: int
    cap_height: int
    bbox: tuple[int, int, int, int]
    has_true_type_outlines: bool

    @functools.cached_property
    def _pillow_regular(self) -> Any:
        return self.pillow_font(12)

    @functools.cached_property
    def _pillow_measured(self) -> Any:
        return self.pillow_font(_MEASUREMENT_PIXELS_PER_EM)

    @property
    def bold(self) -> bool:
        return self.request.bold

    @property
    def italic(self) -> bool:
        return self.request.italic

    @property
    def style_name(self) -> str:
        return self.request.style_name

    @property
    def path(self) -> Path:
        return self.request.path

    def pillow_font(self, size: int) -> Any:
        """Return a Pillow font at ``size`` built from the admitted bytes."""
        renderer = commercial_module("render_fonts", "Font measurement and rasterization")
        return renderer._load_pillow_font(
            self.payload, size, label=f"{self.family} {self.style_name}"
        )

    def has_glyphs(self, text: str) -> tuple[str, ...]:
        """Return the characters of ``text`` the font has no glyph for."""
        return tuple(
            character
            for character in text
            if ord(character) not in self.glyph_ids and character != "\n"
        )

    def advance_emu(self, text: str, point_size: float) -> int:
        """Return the measured advance of ``text`` at ``point_size`` in EMU."""
        if not text:
            return 0
        width_points = (
            self._pillow_measured.getlength(text) * point_size / _MEASUREMENT_PIXELS_PER_EM
        )
        return round(width_points * EMU_PER_POINT)

    def line_height_emu(self, point_size: float) -> int:
        """Return the font's own single-spacing line height in EMU."""
        pixels = self._pillow_measured.getmetrics()
        height_points = sum(pixels) * point_size / _MEASUREMENT_PIXELS_PER_EM
        return round(height_points * EMU_PER_POINT)

    def ascent_emu(self, point_size: float) -> int:
        """Return the font's ascent above the baseline in EMU."""
        ascent_pixels = self._pillow_measured.getmetrics()[0]
        return round(ascent_pixels * point_size / _MEASUREMENT_PIXELS_PER_EM * EMU_PER_POINT)

    def descent_emu(self, point_size: float) -> int:
        """Return the font's descent below the baseline in EMU."""
        descent_pixels = self._pillow_measured.getmetrics()[1]
        return round(descent_pixels * point_size / _MEASUREMENT_PIXELS_PER_EM * EMU_PER_POINT)

    def glyph_advance(self, glyph_id: int) -> int:
        """Return one glyph's advance width in font units."""
        return _glyph_advance(self.advances, glyph_id)

    def scaled_advance(self, glyph_id: int) -> int:
        """Return one glyph's advance in PDF glyph space (1000 units per em)."""
        return _scaled(self.glyph_advance(glyph_id), self.units_per_em)

    def scaled(self, value: int) -> int:
        """Scale a font-unit metric into PDF glyph space (1000 units per em)."""
        return _scaled(value, self.units_per_em)

    @functools.cached_property
    def _pair_kerning(self) -> tuple[tuple[_PairSubtable, ...], ...]:
        return parse_gpos_pair_kerning(self.payload)

    def pair_kerning(self, first: int, second: int) -> int:
        """Return the GPOS ``kern`` x-advance adjustment of one glyph pair."""
        total = 0
        for lookup in self._pair_kerning:
            for subtable in lookup:
                value = subtable.value(first, second)
                if value is not None:
                    total += value
                    break
        return total

    def native_advances(
        self,
        text: str,
        size_emu: int,
        *,
        kerning: bool,
        next_character: str | None = None,
    ) -> tuple[tuple[int, ...], int]:
        """Return each glyph's native advance as exact EMU fractions.

        Returns ``(numerators, denominator)``.  Each glyph's design advance at
        ``size_emu`` is rounded half up to the 1/8 pt grid; when ``kerning``,
        the GPOS pair value with the following glyph (``next_character`` for
        the last one) is then added unrounded.  Probe slide 2 (``kern="1200"``,
        Aptos, Calibri, Arial, Times New Roman at 12/24/40 pt) fits this within
        the native PDF writer's own quantization; rounding the kerned sum
        instead misses by up to 0.25 pt per row.
        """
        glyphs = [self.glyph_ids.get(ord(character), 0) for character in text]
        following = self.glyph_ids.get(ord(next_character)) if next_character else None
        denominator = 2 * self.units_per_em
        grid_denominator = 2 * self.units_per_em * EMU_PER_POINT
        emu_per_step = EMU_PER_POINT * 2 * self.units_per_em // ADVANCE_GRID_PER_POINT
        numerators: list[int] = []
        for index, glyph in enumerate(glyphs):
            steps = (
                2 * self.glyph_advance(glyph) * size_emu * ADVANCE_GRID_PER_POINT
                + self.units_per_em * EMU_PER_POINT
            ) // grid_denominator
            numerator = steps * emu_per_step
            if kerning:
                second = glyphs[index + 1] if index + 1 < len(glyphs) else following
                if second is not None:
                    numerator += 2 * self.pair_kerning(glyph, second) * size_emu
            numerators.append(numerator)
        return tuple(numerators), denominator


class FontRegistry:
    """Explicitly admitted font assets, keyed by family and style."""

    def __init__(self, assets: Iterable[FontAsset]) -> None:
        self._assets: dict[tuple[str, bool, bool], FontAsset] = {}
        for asset in assets:
            key = (asset.family.casefold(), asset.bold, asset.italic)
            if key in self._assets:
                raise FontRefusal(f"font assets admit {asset.family} {asset.style_name} twice")
            self._assets[key] = asset

    def __len__(self) -> int:
        return len(self._assets)

    def __iter__(self) -> Any:
        return iter(self.ordered())

    def ordered(self) -> list[FontAsset]:
        """Return the admitted assets in deterministic reporting order."""
        return [
            self._assets[key]
            for key in sorted(self._assets, key=lambda item: (item[0], item[1], item[2]))
        ]

    def families(self) -> list[str]:
        return sorted({asset.family for asset in self._assets.values()})

    def resolve(self, family: str, bold: bool, italic: bool) -> FontAsset:
        """Return the admitted asset for one effective font request."""
        key = (family.casefold(), bold, italic)
        asset = self._assets.get(key)
        if asset is not None:
            return asset
        style = (
            "bold italic"
            if bold and italic
            else ("bold" if bold else ("italic" if italic else "regular"))
        )
        available = ", ".join(f"{item.family} ({item.style_name})" for item in self.ordered())
        raise UnadmittedFontRefusal(
            f"text needs {family} {style} but no such font asset was admitted; "
            f"admitted assets: {available or 'none'}",
            family=family,
            bold=bold,
            italic=italic,
            style=style,
        )


def admit_font_asset(
    family: str,
    bold: bool,
    italic: bool,
    path: Path,
) -> FontAsset:
    """Admit one local font file after checking it matches its claim."""
    if not family:
        raise FontRefusal("font asset family must not be empty")
    resolved = path.expanduser()
    if not resolved.is_file():
        raise FontRefusal(f"font file {resolved} does not exist")
    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise FontRefusal(f"font file {resolved} cannot be read") from exc
    return admit_font_bytes(family, bold, italic, payload, path=resolved)


def _font_identity(payload: bytes, *, label: str) -> tuple[str, str]:
    """Read the preferred sfnt family/style without loading a renderer.

    Prefer English Windows Unicode names, then Macintosh English and Unicode
    records. Use WWS names when the OS/2 flag does not declare typographic names
    WWS-compatible, matching FreeType's family/style selection.
    """
    tables = _read_sfnt_tables(payload)
    names = tables.get("name", b"")
    selected: dict[int, tuple[int, str]] = {}
    try:
        _format, count, storage = struct.unpack_from(">HHH", names)
        if storage < 6 + count * 12 or storage > len(names):
            raise FontRefusal(f"font file {label} has a malformed name table")
        for index in range(count):
            platform, encoding, language, name_id, length, offset = struct.unpack_from(
                ">HHHHHH", names, 6 + index * 12
            )
            start = storage + offset
            if start + length > len(names):
                raise FontRefusal(f"font file {label} has a truncated name record")
            if platform == 3 and encoding in (0, 1, 10):
                codec = "utf-16-be"
                rank = 4 if language == 0x409 else 1
            elif platform == 1 and encoding == 0:
                codec = "mac_roman"
                rank = 3 if language == 0 else 0
            elif platform == 0:
                codec, rank = "utf-16-be", 2
            else:
                continue
            try:
                value = names[start : start + length].decode(codec).strip("\x00")
            except UnicodeError:
                continue
            if value and (name_id not in selected or rank > selected[name_id][0]):
                selected[name_id] = (rank, value)
        os2 = tables.get("OS/2", b"")
        wws = len(os2) >= 64 and bool(struct.unpack_from(">H", os2, 62)[0] & 0x100)
        family_ids = (16, 1) if wws else (21, 16, 1)
        style_ids = (17, 2) if wws else (22, 17, 2)
        family = next((selected[key][1] for key in family_ids if key in selected), None)
        style = next((selected[key][1] for key in style_ids if key in selected), None)
        if family is None or style is None:
            raise FontRefusal(f"font file {label} reports no font name")
        return family, style
    except struct.error as exc:
        raise FontRefusal(f"font file {label} has a truncated name table") from exc


def admit_font_bytes(
    family: str,
    bold: bool,
    italic: bool,
    payload: bytes,
    *,
    path: Path,
) -> FontAsset:
    """Admit owned font bytes without Pillow or commercial renderer modules.

    ``path`` is an identity label only; measurement and emitters consume the
    admitted snapshot. Embedded-font managers apply embedding permissions
    separately before adding bytes to a package.
    """
    if not isinstance(family, str) or not family.strip():
        raise FontRefusal("font asset family must not be empty")
    if not isinstance(bold, bool) or not isinstance(italic, bool):
        raise FontRefusal("font asset bold and italic must be bools")
    if not isinstance(payload, bytes):
        raise FontRefusal("font asset payload must be bytes")
    resolved = Path(path)
    label = str(resolved)
    reported_family, reported_style = _font_identity(payload, label=label)
    if _normalized_font_name(reported_family) != _normalized_font_name(family):
        raise FontRefusal(
            f"font asset {resolved} reports family {reported_family!r}, not {family!r}"
        )
    normalized_style = _normalized_font_name(reported_style)
    actual_bold = "bold" in normalized_style
    actual_italic = "italic" in normalized_style or "oblique" in normalized_style
    if (actual_bold, actual_italic) != (bold, italic):
        raise FontRefusal(
            f"font asset {resolved} reports style {reported_style!r}, which is "
            f"not the claimed {FontRequest(family, bold, italic, resolved).style_name}"
        )
    sfnt = parse_sfnt_tables(payload)
    return FontAsset(
        request=FontRequest(family, bold, italic, resolved),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        payload=payload,
        family=family,
        style=reported_style,
        units_per_em=sfnt.units_per_em,
        glyph_ids=sfnt.glyph_ids,
        advances=sfnt.advances,
        ascender=sfnt.ascender,
        descender=sfnt.descender,
        cap_height=sfnt.cap_height,
        bbox=sfnt.bbox,
        has_true_type_outlines=sfnt.has_true_type_outlines,
    )


def admit_font_specs(specs: Iterable[str]) -> FontRegistry:
    """Admit every CLI-style font spec into one registry."""
    requests: list[tuple[str, bool, bool, Path]] = []
    for spec in specs:
        family, bold, italic, path = parse_font_spec(spec)
        requests.append((family, bold, italic, path))
    if not requests:
        raise FontRefusal(
            "the built-in renderer needs at least one admitted font asset; "
            "pass --font 'Family[:style]=/path/to/font.ttf'"
        )
    seen: set[tuple[str, bool, bool]] = set()
    for family, bold, italic, _path in requests:
        key = (family.casefold(), bold, italic)
        if key in seen:
            raise FontRefusal(
                f"font asset {family} "
                f"{FontRequest(family, bold, italic, Path('')).style_name} "
                "was admitted twice"
            )
        seen.add(key)
    return FontRegistry(
        admit_font_asset(family, bold, italic, path) for family, bold, italic, path in requests
    )


def font_asset_receipt(asset: FontAsset) -> dict[str, Any]:
    """Return the receipt row for one admitted asset."""
    return {
        "family": asset.family,
        "style": asset.style_name,
        "path": str(asset.path),
        "sha256": asset.sha256,
        "size_bytes": asset.size_bytes,
    }
