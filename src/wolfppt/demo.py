"""Create and verify a deterministic WolfPPT editing demonstration."""

from __future__ import annotations

import argparse
import io
import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from wolfppt import Presentation
from wolfppt.package_diff import diff_packages, package_manifest


EMU_PER_INCH = 914400
BEFORE_SLIDE_COUNT = 5
ORIGINAL_RUN_TEXT = "Original run"
REPLACED_RUN_TEXT = "Verified run"
ORIGINAL_SHAPE_TEXT = "Original shape text"
REPLACED_SHAPE_TEXT = "Verified shape text"
ORIGINAL_CELL_TEXT = "Original cell"
REPLACED_CELL_TEXT = "Verified cell"


@dataclass(frozen=True)
class _ChartSeries:
    """Small duck-typed chart series accepted by the public chart facade."""

    name: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class _ChartData:
    """Small duck-typed category chart data accepted by the public chart facade."""

    categories: tuple[str, ...]
    series: tuple[_ChartSeries, ...]

    def __iter__(self) -> Iterator[_ChartSeries]:
        return iter(self.series)


def run_demo(
    output_dir: Path | None = None,
    fail_injection: bool = False,
) -> dict[str, Any]:
    """Build, edit, and independently verify a deterministic demo presentation."""
    destination = (output_dir or Path("wolfppt-demo-output")).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    before_path = destination / "before.pptx"
    after_path = destination / "after.pptx"
    receipt_path = destination / "receipt.json"

    _build_sample_deck(before_path)
    _apply_surgical_edits(before_path, after_path)
    _verify_before_and_after(before_path, after_path)
    unrelated_parts_changed = _unrelated_parts_changed(before_path, after_path)
    if unrelated_parts_changed:
        raise AssertionError(
            f"package diff contains {unrelated_parts_changed} unrelated changed parts"
        )

    fail_result = _inject_refused_edit(after_path) if fail_injection else None
    receipt: dict[str, Any] = {
        "requested_edits": 4,
        "verified_edits": 4,
        "unrelated_parts_changed": unrelated_parts_changed,
        "reopen_passed": True,
        "validation": {
            "status": "skip",
            "detail": "Open XML validation is optional and is not run by the demo.",
        },
        "artifacts": {
            "before": str(before_path),
            "after": str(after_path),
            "receipt": str(receipt_path),
        },
        "fail_injection": fail_result,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    """Run the demo command and print its compact machine receipt."""
    tokens = list(argv) if argv is not None else sys.argv[1:]
    if tokens[:1] == ["demo"]:
        tokens = tokens[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("wolfppt-demo-output"),
        help="directory for before.pptx, after.pptx, and receipt.json",
    )
    parser.add_argument(
        "--fail-injection",
        action="store_true",
        help="prove that a guarded invalid edit preserves after.pptx",
    )
    args = parser.parse_args(tokens)
    try:
        receipt = run_demo(args.output_dir, fail_injection=args.fail_injection)
    except (AssertionError, IndexError, OSError, RuntimeError, ValueError) as exc:
        print(f"demo verification failed: {exc}")
        return 1

    _print_receipt(receipt)
    if receipt["fail_injection"] is not None:
        print("commit refused")
        print("original destination preserved")
    return 0


def _build_sample_deck(before_path: Path) -> None:
    presentation = Presentation()
    blank_layout: Any = presentation.slide_layouts[6]

    text_slide = presentation.slides.add_slide(blank_layout)
    text_shape = text_slide.shapes.add_textbox(
        EMU_PER_INCH,
        EMU_PER_INCH,
        7 * EMU_PER_INCH,
        2 * EMU_PER_INCH,
    )
    text_shape.text = ORIGINAL_RUN_TEXT
    text_slide.shapes.add_textbox(
        EMU_PER_INCH,
        3 * EMU_PER_INCH,
        7 * EMU_PER_INCH,
        2 * EMU_PER_INCH,
    ).text = "Text-heavy slide\nwith deterministic content\nand a surgical run target."

    shape_slide = presentation.slides.add_slide(blank_layout)
    shape_slide.shapes.add_textbox(
        EMU_PER_INCH,
        EMU_PER_INCH,
        7 * EMU_PER_INCH,
        EMU_PER_INCH,
    ).text = ORIGINAL_SHAPE_TEXT

    table_slide = presentation.slides.add_slide(blank_layout)
    table = table_slide.shapes.add_table(
        2,
        2,
        EMU_PER_INCH,
        EMU_PER_INCH,
        6 * EMU_PER_INCH,
        2 * EMU_PER_INCH,
    ).table
    table.cell(0, 0).text = "Header"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Status"
    table.cell(1, 1).text = ORIGINAL_CELL_TEXT

    picture_slide = presentation.slides.add_slide(blank_layout)
    picture_slide.shapes.add_picture(
        io.BytesIO(_demo_png()),
        2 * EMU_PER_INCH,
        EMU_PER_INCH,
        2 * EMU_PER_INCH,
        2 * EMU_PER_INCH,
    )

    chart_slide = presentation.slides.add_slide(blank_layout)
    chart_slide.shapes.add_chart(
        51,
        EMU_PER_INCH,
        EMU_PER_INCH,
        6 * EMU_PER_INCH,
        3 * EMU_PER_INCH,
        _ChartData(
            categories=("Plan", "Actual"),
            series=(_ChartSeries("Revenue", (3.0, 4.0)),),
        ),
    )
    if len(presentation.slides) != BEFORE_SLIDE_COUNT:
        raise AssertionError("sample deck did not contain five slides")
    presentation.save(before_path)


def _apply_surgical_edits(before_path: Path, after_path: Path) -> None:
    presentation = Presentation(before_path)
    run_shape: Any = presentation.slides[0].shapes[0]
    run_shape.text_frame.paragraphs[0].runs[0].text = REPLACED_RUN_TEXT
    shape_target: Any = presentation.slides[1].shapes[0]
    shape_target.text = REPLACED_SHAPE_TEXT
    table_target: Any = presentation.slides[2].shapes[0]
    table_target.table.cell(1, 1).text = REPLACED_CELL_TEXT
    presentation.slides.duplicate(presentation.slides[0])
    presentation.save(after_path)


def _verify_before_and_after(before_path: Path, after_path: Path) -> None:
    before = Presentation(before_path)
    after = Presentation(after_path)

    if _target_run_text(before) != ORIGINAL_RUN_TEXT:
        raise AssertionError("before deck run was not preserved")
    if _target_shape_text(before) != ORIGINAL_SHAPE_TEXT:
        raise AssertionError("before deck shape text was not preserved")
    if _target_table_text(before) != ORIGINAL_CELL_TEXT:
        raise AssertionError("before deck table cell was not preserved")
    if len(before.slides) != BEFORE_SLIDE_COUNT:
        raise AssertionError("before deck slide count changed")

    if _target_run_text(after) != REPLACED_RUN_TEXT:
        raise AssertionError("replaced text run was not found")
    if _target_shape_text(after) != REPLACED_SHAPE_TEXT:
        raise AssertionError("replaced shape text was not found")
    if _target_table_text(after) != REPLACED_CELL_TEXT:
        raise AssertionError("replaced table cell was not found")
    if len(after.slides) != BEFORE_SLIDE_COUNT + 1:
        raise AssertionError("duplicated slide was not found")
    duplicate: Any = after.slides[-1]
    source: Any = before.slides[0]
    if duplicate.texts != source.texts:
        raise AssertionError("duplicated slide structure was not preserved")


def _target_run_text(presentation: Presentation) -> str:
    shape: Any = presentation.slides[0].shapes[0]
    return str(shape.text_frame.paragraphs[0].runs[0].text)


def _target_shape_text(presentation: Presentation) -> str:
    shape: Any = presentation.slides[1].shapes[0]
    return str(shape.text)


def _target_table_text(presentation: Presentation) -> str:
    shape: Any = presentation.slides[2].shapes[0]
    return str(shape.table.cell(1, 1).text)


def _unrelated_parts_changed(before_path: Path, after_path: Path) -> int:
    before = Presentation(before_path)
    after = Presentation(after_path)
    package_diff = diff_packages(before_path, after_path)
    before_manifest = package_manifest(before_path)
    after_manifest = package_manifest(after_path)

    edited_slide_parts = {
        _part_name(before.slides[index].partname) for index in (0, 1, 2)
    }
    duplicate: Any = after.slides[-1]
    duplicate_part = _part_name(duplicate.partname)
    duplicate_rels_part = _rels_part_name(duplicate.partname)
    before_part_names = {part.name for part in before_manifest.parts}
    after_part_names = {part.name for part in after_manifest.parts}
    if {duplicate_part, duplicate_rels_part} - (after_part_names - before_part_names):
        raise AssertionError("duplicated slide parts were not added to the package")

    expected_parts = {
        *edited_slide_parts,
        "[Content_Types].xml",
        "ppt/presentation.xml",
        "ppt/_rels/presentation.xml.rels",
        duplicate_part,
        duplicate_rels_part,
    }
    for index in (0, 1, 2):
        slide = before.slides[index]
        if slide.has_notes_slide:
            expected_parts.add(_part_name(slide.notes_slide.partname))

    changed_parts = {
        *package_diff.added_parts,
        *package_diff.removed_parts,
        *package_diff.changed_parts,
    }
    return len(changed_parts - expected_parts)


def _inject_refused_edit(after_path: Path) -> dict[str, Any]:
    original_bytes = after_path.read_bytes()
    presentation = Presentation(after_path)
    table_shape: Any = presentation.slides[2].shapes[0]
    try:
        table_shape.table.cell(99, 0).text = "Refused"
    except IndexError as exc:
        preserved = after_path.read_bytes() == original_bytes
        if not preserved:
            raise AssertionError("refused edit rewrote after.pptx")
        return {
            "requested": True,
            "refused": True,
            "original_preserved": preserved,
            "detail": str(exc),
        }
    raise AssertionError("invalid table-cell edit was not refused")


def _part_name(partname: str) -> str:
    return partname.lstrip("/")


def _rels_part_name(partname: str) -> str:
    normalized = _part_name(partname)
    parent, filename = normalized.rsplit("/", 1)
    return f"{parent}/_rels/{filename}.rels"


def _demo_png() -> bytes:
    """Return a fixed 2x2 RGBA PNG using only stdlib binary primitives."""
    width = 2
    height = 2
    raw_rows = b"".join(
        (
            b"\x00\x22\x66\xaa\xff\x77\xaa\xdd\xff",
            b"\x00\xdd\xaa\x77\xff\xaa\x66\x22\xff",
        )
    )
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw_rows)),
            _png_chunk(b"IEND", b""),
        )
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _print_receipt(receipt: dict[str, Any]) -> None:
    validation = receipt["validation"]
    validation_status = str(validation["status"])
    validation_detail = str(validation["detail"])
    print(f"requested edits: {receipt['requested_edits']}")
    print(f"verified edits: {receipt['verified_edits']}")
    print(f"unrelated package parts changed: {receipt['unrelated_parts_changed']}")
    print("reopen: passed")
    if validation_status == "pass":
        print("open xml validation: passed")
    else:
        print(f"open xml validation: skipped ({validation_detail})")


if __name__ == "__main__":
    raise SystemExit(main())
