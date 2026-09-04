"""Adapter for the Rust `wolfppt-core` package reader via `wolfppt-cli`."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .toolchain import USER_LOCAL_CARGO, env_with_user_local_tools


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RustInspectResult:
    path: str
    part_count: int
    has_vba: bool
    parts: list[dict[str, Any]]
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "parts": self.parts,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustRoundtripResult:
    path: str
    part_count: int
    has_vba: bool
    parts: list[dict[str, Any]]
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "parts": self.parts,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustSlideAddResult:
    path: str
    slide_part: str
    relationship_id: str
    layout_target: str
    slide_id: int
    slide_count: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_part": self.slide_part,
            "relationship_id": self.relationship_id,
            "layout_target": self.layout_target,
            "slide_id": self.slide_id,
            "slide_count": self.slide_count,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustTextReplacementResult:
    path: str
    replacements: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustTextRunReplacementResult:
    path: str
    slide_index: int
    run_index: int
    replacements: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "run_index": self.run_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustShapeTextSetResult:
    path: str
    slide_index: int
    shape_index: int
    replacements: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "shape_index": self.shape_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustParagraphTextSetResult:
    path: str
    slide_index: int
    shape_index: int
    paragraph_index: int
    replacements: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "shape_index": self.shape_index,
            "paragraph_index": self.paragraph_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustImageReplacementResult:
    path: str
    relationship_id: str
    replacements: int
    replaced_parts: list[str]
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "relationship_id": self.relationship_id,
            "replacements": self.replacements,
            "replaced_parts": self.replaced_parts,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustImageAddResult:
    path: str
    slide_index: int
    slide_part: str
    relationship_id: str
    image_part: str
    shape_id: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "relationship_id": self.relationship_id,
            "image_part": self.image_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustTableCellReplacementResult:
    path: str
    slide_index: int
    table_index: int
    row_index: int
    col_index: int
    replacements: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "table_index": self.table_index,
            "row_index": self.row_index,
            "col_index": self.col_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class RustTableAddResult:
    path: str
    slide_index: int
    slide_part: str
    table_index: int
    shape_id: int
    rows: int
    cols: int
    part_count: int
    has_vba: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "table_index": self.table_index,
            "shape_id": self.shape_id,
            "rows": self.rows,
            "cols": self.cols,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def cargo_command() -> str | None:
    system_cargo = shutil.which("cargo")
    if system_cargo is not None:
        return "cargo"
    return str(USER_LOCAL_CARGO) if USER_LOCAL_CARGO.exists() else None


def rust_cli_available() -> bool:
    return cargo_command() is not None and (ROOT / "Cargo.toml").exists()


def _cargo_or_raise() -> str:
    cargo = cargo_command()
    if cargo is None:
        raise RuntimeError("cargo was not found on PATH")
    return cargo


def inspect(path: str | Path) -> RustInspectResult:
    cargo = _cargo_or_raise()
    source = Path(path)
    proc = subprocess.run(
        [cargo, "run", "--quiet", "-p", "wolfppt-cli", "--", "inspect", str(source)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    parts = list(payload["parts"])
    return RustInspectResult(
        path=payload["path"],
        part_count=len(parts),
        has_vba=any(part["kind"] == "vba" for part in parts),
        parts=parts,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def roundtrip(input_path: str | Path, output_path: str | Path) -> RustRoundtripResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [cargo, "run", "--quiet", "-p", "wolfppt-cli", "--", "roundtrip", str(source), str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    parts = list(payload["parts"])
    return RustRoundtripResult(
        path=payload["path"],
        part_count=len(parts),
        has_vba=any(part["kind"] == "vba" for part in parts),
        parts=parts,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def add_slide(
    input_path: str | Path,
    output_path: str | Path,
    layout_index: int | None = None,
) -> RustSlideAddResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    args = [
        cargo,
        "run",
        "--quiet",
        "-p",
        "wolfppt-cli",
        "--",
        "add-slide",
        str(source),
        str(output),
    ]
    if layout_index is not None:
        args.append(str(layout_index))
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustSlideAddResult(
        path=payload["path"],
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        layout_target=payload["layout_target"],
        slide_id=int(payload["slide_id"]),
        slide_count=int(payload["slide_count"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def replace_text(
    input_path: str | Path,
    output_path: str | Path,
    search: str,
    replacement: str,
    slide_index: int | None = None,
) -> RustTextReplacementResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    command = "replace-text-in-slide" if slide_index is not None else "replace-text"
    args = [
        cargo,
        "run",
        "--quiet",
        "-p",
        "wolfppt-cli",
        "--",
        command,
        str(source),
        str(output),
    ]
    if slide_index is not None:
        args.append(str(slide_index))
    args.extend([search, replacement])
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustTextReplacementResult(
        path=payload["path"],
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def replace_text_run(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    run_index: int,
    replacement: str,
) -> RustTextRunReplacementResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [
            cargo,
            "run",
            "--quiet",
            "-p",
            "wolfppt-cli",
            "--",
            "replace-text-run",
            str(source),
            str(output),
            str(slide_index),
            str(run_index),
            replacement,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustTextRunReplacementResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        run_index=int(payload["run_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def set_shape_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    shape_index: int,
    replacement: str,
) -> RustShapeTextSetResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [
            cargo,
            "run",
            "--quiet",
            "-p",
            "wolfppt-cli",
            "--",
            "set-shape-text",
            str(source),
            str(output),
            str(slide_index),
            str(shape_index),
            replacement,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustShapeTextSetResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        shape_index=int(payload["shape_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def set_paragraph_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    shape_index: int,
    paragraph_index: int,
    replacement: str,
) -> RustParagraphTextSetResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [
            cargo,
            "run",
            "--quiet",
            "-p",
            "wolfppt-cli",
            "--",
            "set-paragraph-text",
            str(source),
            str(output),
            str(slide_index),
            str(shape_index),
            str(paragraph_index),
            replacement,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustParagraphTextSetResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        shape_index=int(payload["shape_index"]),
        paragraph_index=int(payload["paragraph_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def replace_image(
    input_path: str | Path,
    output_path: str | Path,
    relationship_id: str,
    image_path: str | Path,
    slide_index: int | None = None,
) -> RustImageReplacementResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    image = Path(image_path)
    command = "replace-image-in-slide" if slide_index is not None else "replace-image"
    args = [
        cargo,
        "run",
        "--quiet",
        "-p",
        "wolfppt-cli",
        "--",
        command,
        str(source),
        str(output),
    ]
    if slide_index is not None:
        args.append(str(slide_index))
    args.extend([relationship_id, str(image)])
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustImageReplacementResult(
        path=payload["path"],
        relationship_id=payload["relationship_id"],
        replacements=int(payload["replacements"]),
        replaced_parts=list(payload["replaced_parts"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def add_image(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    image_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> RustImageAddResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    image = Path(image_path)
    proc = subprocess.run(
        [
            cargo,
            "run",
            "--quiet",
            "-p",
            "wolfppt-cli",
            "--",
            "add-image",
            str(source),
            str(output),
            str(slide_index),
            str(image),
            str(x_emu),
            str(y_emu),
            str(cx_emu),
            str(cy_emu),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustImageAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        image_part=payload["image_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def replace_table_cell(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    table_index: int,
    row_index: int,
    col_index: int,
    replacement: str,
) -> RustTableCellReplacementResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [
            cargo,
            "run",
            "--quiet",
            "-p",
            "wolfppt-cli",
            "--",
            "replace-table-cell",
            str(source),
            str(output),
            str(slide_index),
            str(table_index),
            str(row_index),
            str(col_index),
            replacement,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustTableCellReplacementResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        table_index=int(payload["table_index"]),
        row_index=int(payload["row_index"]),
        col_index=int(payload["col_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def add_table(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> RustTableAddResult:
    cargo = _cargo_or_raise()
    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [
            cargo,
            "run",
            "--quiet",
            "-p",
            "wolfppt-cli",
            "--",
            "add-table",
            str(source),
            str(output),
            str(slide_index),
            str(rows),
            str(cols),
            str(x_emu),
            str(y_emu),
            str(cx_emu),
            str(cy_emu),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "wolfppt-cli failed")
    payload = json.loads(proc.stdout)
    return RustTableAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        table_index=int(payload["table_index"]),
        shape_id=int(payload["shape_id"]),
        rows=int(payload["rows"]),
        cols=int(payload["cols"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
