"""Docker-backed Aspose.Slides round-trip adapter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..extractor import extract_semantics

ASPOSE_DOCKER_IMAGE_ENV = "WOLFPPT_ASPOSE_DOCKER_IMAGE"
ASPOSE_DOCKER_TIMEOUT_ENV = "WOLFPPT_ASPOSE_DOCKER_TIMEOUT"
DEFAULT_ASPOSE_DOCKER_IMAGE = "wolfppt-aspose-slides:python3.11-bullseye"
DEFAULT_ASPOSE_DOCKER_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class AsposeDockerRoundtripResult:
    path: str
    input: str
    part_count: int
    has_vba: bool
    command: list[str]
    image: str
    timeout_seconds: float
    sdk_versions: dict[str, str]
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aspose_docker_roundtrip_available() -> bool:
    return aspose_docker_roundtrip_unavailable_reason() is None


def aspose_docker_roundtrip_unavailable_reason() -> str | None:
    if shutil.which("docker") is None:
        return "docker was not found; install Docker to run the Aspose Docker lane"
    image = _docker_image()
    proc = subprocess.run(
        ["docker", "image", "inspect", image],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return (
            f"Docker image {image!r} was not found; build "
            "examples/external-roundtrip/aspose-docker first"
        )
    return None


def roundtrip(
    input_path: str | Path, output_path: str | Path
) -> AsposeDockerRoundtripResult:
    unavailable_reason = aspose_docker_roundtrip_unavailable_reason()
    if unavailable_reason is not None:
        raise RuntimeError(unavailable_reason)

    source = Path(input_path).resolve()
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image = _docker_image()
    timeout_seconds = _roundtrip_timeout_seconds()
    command = _docker_command(source, output, image)

    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Aspose Docker round-trip timed out after {timeout_seconds:g}s"
        ) from exc
    if proc.returncode != 0:
        reason = proc.stderr.strip() or proc.stdout.strip() or "Aspose Docker failed"
        raise RuntimeError(reason)
    if not output.exists():
        raise RuntimeError(f"Aspose Docker round-trip did not create {output}")

    summary = extract_semantics(output)
    return AsposeDockerRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        command=command,
        image=image,
        timeout_seconds=timeout_seconds,
        sdk_versions=_sdk_versions_from_stdout(proc.stdout),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _sdk_versions_from_stdout(stdout: str) -> dict[str, str]:
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return {}
    sdk_versions = payload.get("sdk_versions")
    if not isinstance(sdk_versions, dict):
        return {}
    return {
        str(name): str(version)
        for name, version in sdk_versions.items()
        if isinstance(name, str) and isinstance(version, str)
    }


def _docker_command(source: Path, output: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-e",
        "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1",
        "-v",
        f"{source.parent}:/input:ro",
        "-v",
        f"{output.parent}:/output",
        image,
        "python",
        "/opt/wolfppt-aspose-roundtrip/roundtrip.py",
        f"/input/{source.name}",
        f"/output/{output.name}",
    ]


def _docker_image() -> str:
    return os.environ.get(ASPOSE_DOCKER_IMAGE_ENV, DEFAULT_ASPOSE_DOCKER_IMAGE)


def _roundtrip_timeout_seconds() -> float:
    raw_timeout = os.environ.get(ASPOSE_DOCKER_TIMEOUT_ENV)
    if raw_timeout is None:
        return DEFAULT_ASPOSE_DOCKER_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise RuntimeError(
            f"{ASPOSE_DOCKER_TIMEOUT_ENV} must be a positive number of seconds"
        ) from exc
    if timeout_seconds <= 0:
        raise RuntimeError(
            f"{ASPOSE_DOCKER_TIMEOUT_ENV} must be a positive number of seconds"
        )
    return timeout_seconds
