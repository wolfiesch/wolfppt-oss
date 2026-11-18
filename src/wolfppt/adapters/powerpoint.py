"""Optional Microsoft PowerPoint visual oracle adapter for macOS."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


POWERPOINT_APP = Path("/Applications/Microsoft PowerPoint.app")
# PowerPoint for Mac is sandboxed: opening or saving outside its own container
# raises a modal "Grant File Access" sheet that stalls the Apple Event, so every
# export is staged inside the container and copied out afterwards.
POWERPOINT_SANDBOX_DOCUMENTS = (
    Path.home() / "Library/Containers/com.microsoft.Powerpoint/Data/Documents"
)
APPLESCRIPT_TIMEOUT_SECONDS = 170
OSASCRIPT_TIMEOUT_SECONDS = APPLESCRIPT_TIMEOUT_SECONDS + 30


@dataclass(frozen=True)
class PowerPointExportResult:
    input_path: str
    output_dir: str
    available: bool
    returncode: int | None
    exported_files: list[str]
    stdout: str
    stderr: str
    method: str = ""

    @property
    def ok(self) -> bool:
        return self.available and self.returncode == 0 and bool(self.exported_files)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def powerpoint_available() -> bool:
    return POWERPOINT_APP.exists()


def export_pdf(input_path: str | Path, out_path: str | Path) -> PowerPointExportResult:
    """Export a deck to one PDF using Microsoft PowerPoint on macOS."""

    source = Path(input_path).resolve()
    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not powerpoint_available():
        return _unavailable(source, target.parent)
    target.unlink(missing_ok=True)

    with _sandbox_stage_dir() as raw_temp_dir:
        temp_dir = Path(raw_temp_dir)
        staged_source = temp_dir / f"input{source.suffix}"
        staged_pdf = temp_dir / "export.pdf"
        shutil.copy2(source, staged_source)
        proc = _run_powerpoint_pdf_export(staged_source, staged_pdf)
        exported: list[str] = []
        stderr = proc.stderr
        if proc.returncode == 0 and staged_pdf.is_file() and staged_pdf.stat().st_size > 0:
            shutil.copy2(staged_pdf, target)
            exported.append(str(target))
        else:
            stderr = _join_streams(stderr, "PowerPoint did not produce PDF output")
        return PowerPointExportResult(
            input_path=str(source),
            output_dir=str(target.parent),
            available=True,
            returncode=proc.returncode,
            exported_files=exported,
            stdout=proc.stdout,
            stderr=stderr,
            method="native-pdf",
        )


def export_png(input_path: str | Path, out_dir: str | Path) -> PowerPointExportResult:
    """Export slides to PNG using Microsoft PowerPoint on macOS."""

    source = Path(input_path).resolve()
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not powerpoint_available():
        return _unavailable(source, out)
    expected_slide_count = _count_slides(source)

    for stale in out.glob("*.png"):
        stale.unlink()

    with _sandbox_stage_dir() as raw_temp_dir:
        temp_dir = Path(raw_temp_dir)
        staged_source = temp_dir / f"input{source.suffix}"
        staged_png_dir = temp_dir / "png"
        staged_png_dir.mkdir()
        shutil.copy2(source, staged_source)

        png_proc = _run_powerpoint_png_export(staged_source, staged_png_dir)
        staged_pngs = sorted(staged_png_dir.rglob("*.png"), key=_slide_order)
        if (
            png_proc.returncode == 0
            and expected_slide_count > 0
            and len(staged_pngs) == expected_slide_count
        ):
            exported = _copy_exported_pngs(staged_pngs, out)
            return PowerPointExportResult(
                input_path=str(source),
                output_dir=str(out),
                available=True,
                returncode=png_proc.returncode,
                exported_files=exported,
                stdout=png_proc.stdout,
                stderr=png_proc.stderr,
                method="native-png",
            )

        staged_pdf = temp_dir / "export.pdf"
        staged_pdf.touch()
        pdf_proc = _run_powerpoint_pdf_export(staged_source, staged_pdf)
        if pdf_proc.returncode == 0 and staged_pdf.exists() and staged_pdf.stat().st_size > 0:
            convert_proc = _convert_pdf_to_png(staged_pdf, out, expected_slide_count)
            exported = [str(path) for path in sorted(out.rglob("*.png"), key=_slide_order)]
            return PowerPointExportResult(
                input_path=str(source),
                output_dir=str(out),
                available=True,
                returncode=convert_proc.returncode,
                exported_files=exported,
                stdout=_join_streams(png_proc.stdout, pdf_proc.stdout, convert_proc.stdout),
                stderr=_join_streams(png_proc.stderr, pdf_proc.stderr, convert_proc.stderr),
                method=convert_proc.method,
            )

        return PowerPointExportResult(
            input_path=str(source),
            output_dir=str(out),
            available=True,
            returncode=pdf_proc.returncode if pdf_proc.returncode != 0 else png_proc.returncode,
            exported_files=[],
            stdout=_join_streams(png_proc.stdout, pdf_proc.stdout),
            stderr=_join_streams(
                png_proc.stderr,
                pdf_proc.stderr,
                "PowerPoint did not produce PNG or PDF output",
            ),
            method="failed",
        )


def _run_powerpoint_png_export(source: Path, out: Path) -> subprocess.CompletedProcess[str]:
    script = f"""
set deckPath to POSIX file "{_escape_applescript(str(source))}"
set outPath to POSIX file "{_escape_applescript(str(out))}"
with timeout of {APPLESCRIPT_TIMEOUT_SECONDS} seconds
  tell application "Microsoft PowerPoint"
    launch
    set previousAutomationSecurity to automation security
    set automation security to msoAutomationSecurityForceDisable
    set deckRef to missing value
    try
      open deckPath
      set deckRef to active presentation
      save deckRef in outPath as save as PNG
      close deckRef saving no
      if previousAutomationSecurity is not missing value then set automation security to previousAutomationSecurity
    on error errMsg number errNum
      try
        if deckRef is not missing value then close deckRef saving no
      end try
      try
        if previousAutomationSecurity is not missing value then set automation security to previousAutomationSecurity
      end try
      error errMsg number errNum
    end try
  end tell
end timeout
"""
    return _run_osascript(script)


def _run_powerpoint_pdf_export(source: Path, out: Path) -> subprocess.CompletedProcess[str]:
    script = f"""
set deckPath to POSIX file "{_escape_applescript(str(source))}" as alias
set outPath to POSIX file "{_escape_applescript(str(out))}"
with timeout of {APPLESCRIPT_TIMEOUT_SECONDS} seconds
  tell application "Microsoft PowerPoint"
    launch
    set previousAutomationSecurity to automation security
    set automation security to msoAutomationSecurityForceDisable
    set deckRef to missing value
    try
      open deckPath
      set deckRef to active presentation
      save deckRef in outPath as save as PDF
      close deckRef saving no
      if previousAutomationSecurity is not missing value then set automation security to previousAutomationSecurity
    on error errMsg number errNum
      try
        if deckRef is not missing value then close deckRef saving no
      end try
      try
        if previousAutomationSecurity is not missing value then set automation security to previousAutomationSecurity
      end try
      error errMsg number errNum
    end try
  end tell
end timeout
"""
    return _run_osascript(script)


def _run_osascript(script: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["osascript", "-e", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=OSASCRIPT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = f"osascript timed out after {exc.timeout} seconds"
        return subprocess.CompletedProcess(exc.cmd, 124, _text(exc.stdout), stderr)


def _text(stream: str | bytes | None) -> str:
    if isinstance(stream, bytes):
        return stream.decode(errors="replace")
    return stream or ""


def _unavailable(source: Path, out: Path) -> PowerPointExportResult:
    return PowerPointExportResult(
        input_path=str(source),
        output_dir=str(out),
        available=False,
        returncode=None,
        exported_files=[],
        stdout="",
        stderr="Microsoft PowerPoint.app was not found",
    )


@dataclass(frozen=True)
class _ConvertResult:
    returncode: int
    stdout: str
    stderr: str
    method: str


def _convert_pdf_to_png(pdf_path: Path, out_dir: Path, expected_slide_count: int) -> _ConvertResult:
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = out_dir / "slide"
        proc = subprocess.run(
            [pdftoppm, "-png", "-r", "144", str(pdf_path), str(prefix)],
            text=True,
            capture_output=True,
            check=False,
        )
        for path in sorted(out_dir.glob("slide-*.png")):
            number = path.stem.rsplit("-", 1)[-1]
            if number.isdigit():
                path.rename(out_dir / f"slide{int(number)}.png")
        exported_count = len(list(out_dir.glob("slide*.png")))
        if proc.returncode == 0 and exported_count != expected_slide_count:
            stderr = _join_streams(
                proc.stderr,
                f"Expected {expected_slide_count} slide PNGs from PowerPoint PDF export, got {exported_count}",
            )
            return _ConvertResult(1, proc.stdout, stderr, "pdf-pdftoppm")
        return _ConvertResult(proc.returncode, proc.stdout, proc.stderr, "pdf-pdftoppm")

    sips = shutil.which("sips")
    if sips:
        if expected_slide_count != 1:
            return _ConvertResult(
                1,
                "",
                f"sips fallback converts only the first PDF page; install pdftoppm for {expected_slide_count} slides",
                "pdf-sips",
            )
        proc = subprocess.run(
            [sips, "-s", "format", "png", str(pdf_path), "--out", str(out_dir / "slide1.png")],
            text=True,
            capture_output=True,
            check=False,
        )
        stderr = _join_streams(proc.stderr, "sips fallback converts only the first PDF page")
        return _ConvertResult(proc.returncode, proc.stdout, stderr, "pdf-sips")

    return _ConvertResult(
        1,
        "",
        "PowerPoint exported PDF, but neither pdftoppm nor sips is available to convert it to PNG",
        "pdf-unconverted",
    )


def _count_slides(path: Path) -> int:
    with zipfile.ZipFile(path) as package:
        return sum(
            1
            for name in package.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )


def _slide_order(path: Path) -> tuple[int, str]:
    """Order slide images by their trailing number, so ``Slide10`` follows ``Slide2``."""

    digits = re.search(r"(\d+)$", path.stem)
    return (int(digits.group(1)) if digits else 0, path.name)


def _copy_exported_pngs(paths: list[Path], out_dir: Path) -> list[str]:
    exported: list[str] = []
    for index, path in enumerate(paths, start=1):
        target = out_dir / f"slide{index}.png"
        shutil.copy2(path, target)
        exported.append(str(target))
    return exported


def _sandbox_stage_dir() -> tempfile.TemporaryDirectory[str]:
    POWERPOINT_SANDBOX_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="wolfppt-", dir=POWERPOINT_SANDBOX_DOCUMENTS)


def _join_streams(*streams: str) -> str:
    return "\n".join(stream.strip() for stream in streams if stream and stream.strip())


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
