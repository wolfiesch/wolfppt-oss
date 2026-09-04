"""Aspose.Slides round-trip adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from typing import Any

from ..extractor import extract_semantics
from .sdk_versions import installed_package_version

ASPOSE_SUBPROCESS_ENV = "WOLFPPT_ASPOSE_SUBPROCESS"
DOTNET_GLOBALIZATION_INVARIANT_ENV = "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"


@dataclass(frozen=True)
class AsposeSlidesRoundtripResult:
    path: str
    input: str
    part_count: int
    has_vba: bool
    sdk_versions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aspose_slides_roundtrip_available() -> bool:
    if not _aspose_slides_importable():
        return False
    return _aspose_runtime_probe() is None


def aspose_slides_roundtrip_unavailable_reason() -> str | None:
    if not _aspose_slides_importable():
        return (
            "aspose.slides was not found; install Aspose.Slides for Python "
            "to run the commercial SDK benchmark lane"
        )
    runtime_reason = _aspose_runtime_probe()
    if runtime_reason is not None:
        return runtime_reason
    return None


def _aspose_slides_importable() -> bool:
    if "aspose.slides" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("aspose.slides") is not None
    except (ModuleNotFoundError, ValueError):
        return False


@cache
def _aspose_runtime_probe() -> str | None:
    env = os.environ.copy()
    env.setdefault(DOTNET_GLOBALIZATION_INVARIANT_ENV, "1")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from wolfppt.adapters.aspose_slides import "
                    "_prepare_aspose_runtime_env; "
                    "_prepare_aspose_runtime_env(); "
                    "import aspose.slides as slides; "
                    "presentation = slides.Presentation(); "
                    "dispose = getattr(presentation, 'dispose', None); "
                    "dispose() if dispose is not None else None"
                ),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=env,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "aspose.slides runtime probe timed out after 30 seconds"
    if proc.returncode == 0:
        return None
    message = (proc.stderr.strip() or proc.stdout.strip() or "Aspose runtime probe failed")
    if "No usable version of libssl was found" in message:
        return (
            "aspose.slides runtime probe failed: No usable version of libssl was found"
        )
    if "Couldn't find a valid ICU package" in message:
        return (
            "aspose.slides runtime probe failed: missing ICU/globalization support; "
            f"{DOTNET_GLOBALIZATION_INVARIANT_ENV}=1 is required"
        )
    if "CultureNotFoundException" in message or "invalid culture identifier" in message:
        return (
            "aspose.slides runtime probe failed: globalization/culture support "
            "is unavailable; use the Docker-backed Aspose lane or install a "
            "compatible ICU/globalization runtime"
        )
    return (
        "aspose.slides runtime probe failed: "
        f"{_first_meaningful_probe_line(message)}"
    )


def _first_meaningful_probe_line(message: str) -> str:
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "Traceback (most recent call last):":
            continue
        if stripped.startswith('File "') or stripped.startswith("File '"):
            continue
        return stripped
    return message.splitlines()[0] if message.splitlines() else "Aspose runtime probe failed"


def roundtrip(
    input_path: str | Path, output_path: str | Path
) -> AsposeSlidesRoundtripResult:
    if not aspose_slides_roundtrip_available():
        unavailable_reason = (
            aspose_slides_roundtrip_unavailable_reason()
            or "aspose.slides round-trip adapter is unavailable"
        )
        raise RuntimeError(unavailable_reason)

    source = Path(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if _should_use_subprocess():
        return _roundtrip_subprocess(source, output)

    _prepare_aspose_runtime_env()

    import aspose.slides as slides  # type: ignore[import-not-found]

    save_format = _save_format_for_suffix(slides, output.suffix)
    with slides.Presentation(str(source)) as presentation:
        presentation.save(str(output), save_format)

    summary = extract_semantics(output)
    return AsposeSlidesRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        sdk_versions=aspose_slides_sdk_versions(),
    )


def _save_format_for_suffix(slides: Any, suffix: str) -> Any:
    if suffix.lower() == ".pptm" and hasattr(slides.export.SaveFormat, "PPTM"):
        return slides.export.SaveFormat.PPTM
    return slides.export.SaveFormat.PPTX


def _should_use_subprocess() -> bool:
    return os.environ.get(ASPOSE_SUBPROCESS_ENV) != "1"


def _roundtrip_subprocess(
    source: Path,
    output: Path,
) -> AsposeSlidesRoundtripResult:
    env = os.environ.copy()
    env[ASPOSE_SUBPROCESS_ENV] = "1"
    env.setdefault(DOTNET_GLOBALIZATION_INVARIANT_ENV, "1")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "wolfppt.adapters.aspose_slides",
            str(source),
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "Aspose subprocess failed"
        raise RuntimeError(message)
    summary = extract_semantics(output)
    return AsposeSlidesRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        sdk_versions=aspose_slides_sdk_versions(),
    )


def aspose_slides_sdk_versions() -> dict[str, str]:
    version = installed_package_version("aspose.slides", "aspose-slides")
    return {"aspose.slides": version} if version else {}


def _prepare_aspose_runtime_env() -> None:
    os.environ.setdefault(DOTNET_GLOBALIZATION_INVARIANT_ENV, "1")
    _prepare_macos_libgdiplus_alias()


def _prepare_macos_libgdiplus_alias() -> None:
    if sys.platform != "darwin":
        return
    source = _find_homebrew_libgdiplus()
    if source is None:
        return
    shim_dir = Path(tempfile.gettempdir()) / "wolfppt-aspose-lib"
    shim_dir.mkdir(parents=True, exist_ok=True)
    alias = shim_dir / "liblibgdiplus.dylib"
    if not alias.exists():
        alias.symlink_to(source)
    _prepend_env_path("DYLD_LIBRARY_PATH", shim_dir)


def _find_homebrew_libgdiplus() -> Path | None:
    for path in (
        Path("/opt/homebrew/lib/libgdiplus.dylib"),
        Path("/usr/local/lib/libgdiplus.dylib"),
    ):
        if path.exists():
            return path
    return None


def _prepend_env_path(name: str, path: Path) -> None:
    value = str(path)
    existing = os.environ.get(name)
    if not existing:
        os.environ[name] = value
        return
    parts = existing.split(os.pathsep)
    if value not in parts:
        os.environ[name] = os.pathsep.join([value, *parts])


def _main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m wolfppt.adapters.aspose_slides <input> <output>")
        return 2
    try:
        result = roundtrip(argv[1], argv[2])
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
