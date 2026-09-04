"""Syncfusion .NET round-trip adapter."""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..extractor import extract_semantics
from .sdk_versions import dotnet_package_versions
from .toolchain import dotnet_command, env_with_user_local_tools

SYNCFUSION_LICENSE_KEY_ENV = "SYNCFUSION_LICENSE_KEY"
SYNCFUSION_ALLOW_TRIAL_ENV = "WOLFPPT_SYNCFUSION_ALLOW_TRIAL"
SYNCFUSION_TIMEOUT_ENV = "WOLFPPT_SYNCFUSION_ROUNDTRIP_TIMEOUT"
DEFAULT_SYNCFUSION_TIMEOUT_SECONDS = 120.0
SYNCFUSION_PROJECT = (
    Path(__file__).resolve().parents[3]
    / "examples"
    / "external-roundtrip"
    / "syncfusion-dotnet"
    / "SyncfusionRoundtrip.csproj"
)


@dataclass(frozen=True)
class SyncfusionRoundtripResult:
    path: str
    input: str
    part_count: int
    has_vba: bool
    command: list[str]
    timeout_seconds: float
    trial_allowed: bool
    sdk_versions: dict[str, str]
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def syncfusion_roundtrip_available() -> bool:
    return syncfusion_roundtrip_unavailable_reason() is None


def syncfusion_roundtrip_unavailable_reason() -> str | None:
    if dotnet_command() is None:
        return "dotnet was not found; install .NET 9 to run the Syncfusion benchmark lane"
    if not SYNCFUSION_PROJECT.exists():
        return f"Syncfusion round-trip project was not found at {SYNCFUSION_PROJECT}"
    if _clean_license_missing() and not _trial_allowed():
        return (
            f"{SYNCFUSION_LICENSE_KEY_ENV} is required for clean Syncfusion "
            f"benchmark evidence; set {SYNCFUSION_ALLOW_TRIAL_ENV}=1 only "
            "to inspect trial-watermark behavior"
        )
    return None


def roundtrip(input_path: str | Path, output_path: str | Path) -> SyncfusionRoundtripResult:
    unavailable_reason = syncfusion_roundtrip_unavailable_reason()
    if unavailable_reason is not None:
        raise RuntimeError(unavailable_reason)

    source = Path(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    timeout_seconds = _roundtrip_timeout_seconds()
    dotnet = dotnet_command() or "dotnet"
    command = [
        dotnet,
        "run",
        "--project",
        str(SYNCFUSION_PROJECT),
        "--",
        str(source),
        str(output),
    ]

    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            env=env_with_user_local_tools(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Syncfusion round-trip command timed out after {timeout_seconds:g}s"
        ) from exc
    if proc.returncode != 0:
        reason = proc.stderr.strip() or proc.stdout.strip() or "Syncfusion round-trip failed"
        raise RuntimeError(reason)
    if not output.exists():
        raise RuntimeError(f"Syncfusion round-trip did not create {output}")

    summary = extract_semantics(output)
    return SyncfusionRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        command=command,
        timeout_seconds=timeout_seconds,
        trial_allowed=_trial_allowed(),
        sdk_versions=syncfusion_sdk_versions(),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def syncfusion_sdk_versions() -> dict[str, str]:
    return dotnet_package_versions(
        SYNCFUSION_PROJECT,
        {"Syncfusion.Licensing", "Syncfusion.Presentation.Net.Core"},
    )


def _clean_license_missing() -> bool:
    return not os.environ.get(SYNCFUSION_LICENSE_KEY_ENV, "").strip()


def _trial_allowed() -> bool:
    return os.environ.get(SYNCFUSION_ALLOW_TRIAL_ENV) == "1"


def _roundtrip_timeout_seconds() -> float:
    raw_timeout = os.environ.get(SYNCFUSION_TIMEOUT_ENV)
    if raw_timeout is None:
        return DEFAULT_SYNCFUSION_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise RuntimeError(
            f"{SYNCFUSION_TIMEOUT_ENV} must be a positive number of seconds"
        ) from exc
    if timeout_seconds <= 0:
        raise RuntimeError(
            f"{SYNCFUSION_TIMEOUT_ENV} must be a positive number of seconds"
        )
    return timeout_seconds
