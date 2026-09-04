"""Spire.Presentation round-trip adapter."""

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

SPIRE_SUBPROCESS_ENV = "WOLFPPT_SPIRE_SUBPROCESS"
SPIRE_TIMEOUT_ENV = "WOLFPPT_SPIRE_ROUNDTRIP_TIMEOUT"
DEFAULT_SPIRE_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class SpirePresentationRoundtripResult:
    path: str
    input: str
    part_count: int
    has_vba: bool
    sdk_versions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def spire_presentation_roundtrip_available() -> bool:
    if not _spire_presentation_importable():
        return False
    return _spire_runtime_probe() is None


def _spire_presentation_importable() -> bool:
    if "spire.presentation" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("spire.presentation") is not None
    except (ModuleNotFoundError, ValueError):
        return False


def spire_presentation_roundtrip_unavailable_reason() -> str | None:
    if not _spire_presentation_importable():
        return (
            "spire.presentation was not found; install Spire.Presentation for Python "
            "to run the commercial SDK benchmark lane"
        )
    runtime_reason = _spire_runtime_probe()
    if runtime_reason is not None:
        return runtime_reason
    return None


@cache
def _spire_runtime_probe() -> str | None:
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from wolfppt.adapters.spire_presentation import "
                    "_probe_spire_runtime; "
                    "_probe_spire_runtime()"
                ),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "spire.presentation runtime probe timed out after 30 seconds"
    if proc.returncode == 0:
        return None
    message = (
        proc.stderr.strip()
        or proc.stdout.strip()
        or "Spire.Presentation runtime probe failed"
    )
    return (
        "spire.presentation runtime probe failed: "
        f"{message.splitlines()[0]}"
    )


def _probe_spire_runtime() -> None:
    import spire.presentation as presentation_api  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory(prefix="wolfppt-spire-probe-") as tmpdir:
        output = Path(tmpdir) / "probe.pptx"
        presentation = presentation_api.Presentation()
        try:
            presentation.SaveToFile(
                str(output),
                _save_format_for_suffix(presentation_api.FileFormat, output.suffix),
            )
        finally:
            dispose = getattr(presentation, "Dispose", None)
            if callable(dispose):
                dispose()
        if not output.exists():
            raise RuntimeError("Spire.Presentation probe did not create output")


def roundtrip(
    input_path: str | Path, output_path: str | Path
) -> SpirePresentationRoundtripResult:
    unavailable_reason = spire_presentation_roundtrip_unavailable_reason()
    if unavailable_reason is not None:
        raise RuntimeError(unavailable_reason)

    source = Path(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if _should_use_subprocess():
        return _roundtrip_subprocess(source, output)

    return _roundtrip_in_process(source, output)


def _should_use_subprocess() -> bool:
    return os.environ.get(SPIRE_SUBPROCESS_ENV) != "1"


def _roundtrip_subprocess(
    source: Path,
    output: Path,
) -> SpirePresentationRoundtripResult:
    env = os.environ.copy()
    env[SPIRE_SUBPROCESS_ENV] = "1"
    timeout_seconds = _roundtrip_timeout_seconds()
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "wolfppt.adapters.spire_presentation",
                str(source),
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Spire.Presentation round-trip timed out after {timeout_seconds:g}s"
        ) from exc
    if proc.returncode != 0:
        message = (
            proc.stderr.strip()
            or proc.stdout.strip()
            or "Spire.Presentation subprocess failed"
        )
        raise RuntimeError(message)
    if not output.exists():
        raise RuntimeError(f"Spire.Presentation round-trip did not create {output}")

    summary = extract_semantics(output)
    return SpirePresentationRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        sdk_versions=spire_presentation_sdk_versions(),
    )


def _roundtrip_in_process(
    source: Path,
    output: Path,
) -> SpirePresentationRoundtripResult:
    import spire.presentation as presentation_api  # type: ignore[import-not-found]

    presentation = presentation_api.Presentation()
    try:
        presentation.LoadFromFile(str(source))
        presentation.SaveToFile(
            str(output),
            _save_format_for_suffix(presentation_api.FileFormat, output.suffix),
        )
    finally:
        dispose = getattr(presentation, "Dispose", None)
        if callable(dispose):
            dispose()

    summary = extract_semantics(output)
    return SpirePresentationRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        sdk_versions=spire_presentation_sdk_versions(),
    )


def spire_presentation_sdk_versions() -> dict[str, str]:
    version = installed_package_version("Spire.Presentation", "spire-presentation")
    return {"Spire.Presentation": version} if version else {}


def _roundtrip_timeout_seconds() -> float:
    raw_timeout = os.environ.get(SPIRE_TIMEOUT_ENV)
    if raw_timeout is None:
        return DEFAULT_SPIRE_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise RuntimeError(
            f"{SPIRE_TIMEOUT_ENV} must be a positive number of seconds"
        ) from exc
    if timeout_seconds <= 0:
        raise RuntimeError(
            f"{SPIRE_TIMEOUT_ENV} must be a positive number of seconds"
        )
    return timeout_seconds


def _save_format_for_suffix(file_format: Any, suffix: str) -> Any:
    if suffix.lower() == ".pptm" and hasattr(file_format, "Pptm"):
        return file_format.Pptm
    for name in ("Pptx2016", "Pptx2013", "Pptx2010", "Pptx2007"):
        if hasattr(file_format, name):
            return getattr(file_format, name)
    raise RuntimeError("Spire.Presentation FileFormat has no supported PPTX value")


def _main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m wolfppt.adapters.spire_presentation <input> <output>")
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
