"""LibreOffice headless render and re-save adapters."""

from __future__ import annotations

import atexit
import importlib.util
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from time import perf_counter

LIBREOFFICE_RESAVE_TIMEOUT_ENV = "WOLFPPT_LIBREOFFICE_RESAVE_TIMEOUT"
DEFAULT_LIBREOFFICE_RESAVE_TIMEOUT_SECONDS = 120.0
# Explicit export filters keep the output format independent of LibreOffice's
# default-filter guessing for the target extension.
RESAVE_EXPORT_FILTERS = {
    ".pptx": "pptx:Impress MS PowerPoint 2007 XML",
    ".pptm": "pptm:Impress MS PowerPoint 2007 XML VBA",
}

_resave_profile_dir: Path | None = None


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


@dataclass(frozen=True)
class LibreOfficeResaveResult:
    input_path: str
    output_path: str
    argv: list[str]
    elapsed_ms: float
    timeout_seconds: float
    libreoffice_version: str | None
    stdout: str = ""
    stderr: str = ""

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


def libreoffice_resave_available() -> bool:
    return libreoffice_resave_unavailable_reason() is None


def libreoffice_resave_unavailable_reason() -> str | None:
    if importlib.util.find_spec("pptx") is None:
        return "python-pptx is not installed; install the baseline extra"
    if find_soffice() is None:
        return "LibreOffice soffice was not found on PATH"
    return None


@cache
def libreoffice_version() -> str | None:
    """Return the LibreOffice version reported by ``soffice --version``."""

    soffice = find_soffice()
    if soffice is None:
        return None
    try:
        proc = subprocess.run(
            [soffice, "--version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_libreoffice_version(proc.stdout)


def parse_libreoffice_version(text: str) -> str | None:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "LibreOffice":
            return parts[1]
    return None


def resave_argv(
    soffice: str,
    profile_dir: Path,
    source: Path,
    out_dir: Path,
) -> list[str]:
    export_filter = RESAVE_EXPORT_FILTERS.get(
        source.suffix.lower(), RESAVE_EXPORT_FILTERS[".pptx"]
    )
    return [
        soffice,
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--headless",
        "--invisible",
        "--nodefault",
        "--nologo",
        "--nolockcheck",
        "--norestore",
        "--convert-to",
        export_filter,
        "--outdir",
        str(out_dir),
        str(source),
    ]


def resave(input_path: str | Path, output_path: str | Path) -> LibreOfficeResaveResult:
    """Re-save a PPTX/PPTM package through headless LibreOffice Impress.

    The conversion uses a user profile owned by this process, so a desktop
    LibreOffice session or a concurrent run cannot share state or locks with it.
    ``input_path`` and ``output_path`` may be the same file.
    """

    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError("LibreOffice soffice was not found on PATH")
    source = Path(input_path)
    output = Path(output_path)
    timeout_seconds = _resave_timeout_seconds()
    with tempfile.TemporaryDirectory(prefix="wolfppt-lo-resave-") as work:
        work_dir = Path(work)
        staged = work_dir / "in" / f"deck{source.suffix.lower() or '.pptx'}"
        staged.parent.mkdir()
        shutil.copyfile(source, staged)
        out_dir = work_dir / "out"
        out_dir.mkdir()
        argv = resave_argv(soffice, _resave_profile(), staged, out_dir)
        start = perf_counter()
        try:
            proc = subprocess.run(
                argv,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"LibreOffice re-save timed out after {timeout_seconds:g}s"
            ) from exc
        elapsed_ms = round((perf_counter() - start) * 1000, 3)
        produced = out_dir / staged.name
        if proc.returncode != 0 or not produced.exists():
            reason = (
                proc.stderr.strip()
                or proc.stdout.strip()
                or f"soffice exited with {proc.returncode} without an output file"
            )
            raise RuntimeError(f"LibreOffice re-save failed: {reason}")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(produced, output)
    return LibreOfficeResaveResult(
        input_path=str(source),
        output_path=str(output),
        argv=argv,
        elapsed_ms=elapsed_ms,
        timeout_seconds=timeout_seconds,
        libreoffice_version=libreoffice_version(),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _resave_profile() -> Path:
    """Return the isolated LibreOffice user profile for this process.

    Creating a profile costs several seconds, so it is created once per
    process (the first conversion pays it; benchmark warmup absorbs it) and
    removed at interpreter exit.
    """

    global _resave_profile_dir
    if _resave_profile_dir is None or not _resave_profile_dir.exists():
        _resave_profile_dir = Path(tempfile.mkdtemp(prefix="wolfppt-lo-profile-"))
        atexit.register(shutil.rmtree, _resave_profile_dir, ignore_errors=True)
    return _resave_profile_dir


def _resave_timeout_seconds() -> float:
    raw_timeout = os.environ.get(LIBREOFFICE_RESAVE_TIMEOUT_ENV)
    if raw_timeout is None:
        return DEFAULT_LIBREOFFICE_RESAVE_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise RuntimeError(
            f"{LIBREOFFICE_RESAVE_TIMEOUT_ENV} must be a positive number of seconds"
        ) from exc
    if timeout_seconds <= 0:
        raise RuntimeError(
            f"{LIBREOFFICE_RESAVE_TIMEOUT_ENV} must be a positive number of seconds"
        )
    return timeout_seconds
