"""LibreOffice headless render adapter."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LibreOfficeRenderResult:
    input_path: str
    output_path: str
    returncode: int
    output_exists: bool
    ok: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def render_pdf(input_path: str | Path, out_dir: str | Path) -> LibreOfficeRenderResult:
    """Render a deck to PDF using LibreOffice.

    This is a non-authoritative smoke lane. It should never be treated as
    PowerPoint-equivalent visual fidelity.
    """

    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError("LibreOffice/soffice was not found on PATH")

    source = Path(input_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf = out / f"{source.stem}.pdf"
    if pdf.exists():
        pdf.unlink()
    proc = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out),
            str(source),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    output_exists = pdf.exists()
    return LibreOfficeRenderResult(
        input_path=str(source),
        output_path=str(pdf),
        returncode=proc.returncode,
        output_exists=output_exists,
        ok=proc.returncode == 0 and output_exists,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
