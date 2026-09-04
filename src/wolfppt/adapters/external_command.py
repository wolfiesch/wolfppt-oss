"""Opt-in external command round-trip adapter."""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..extractor import extract_semantics


EXTERNAL_ROUNDTRIP_ENV = "WOLFPPT_EXTERNAL_ROUNDTRIP_CMD"
EXTERNAL_ROUNDTRIP_TIMEOUT_ENV = "WOLFPPT_EXTERNAL_ROUNDTRIP_TIMEOUT"
EXTERNAL_ROUNDTRIP_SDK_NAME_ENV = "WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_NAME"
EXTERNAL_ROUNDTRIP_SDK_VERSION_ENV = "WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_VERSION"
EXTERNAL_ROUNDTRIP_REQUIRE_SDK_METADATA_ENV = (
    "WOLFPPT_EXTERNAL_ROUNDTRIP_REQUIRE_SDK_METADATA"
)
DEFAULT_EXTERNAL_ROUNDTRIP_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class ExternalCommandRoundtripResult:
    path: str
    input: str
    part_count: int
    has_vba: bool
    command: list[str]
    timeout_seconds: float
    command_executable: str
    command_template_sha256: str
    command_arg_count: int
    command_uses_absolute_executable: bool
    external_sdk_name: str | None = None
    external_sdk_version: str | None = None
    sdk_versions: dict[str, str] | None = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def external_command_roundtrip_available() -> bool:
    return external_command_roundtrip_unavailable_reason() is None


def external_command_roundtrip_unavailable_reason() -> str | None:
    command_template = os.environ.get(EXTERNAL_ROUNDTRIP_ENV)
    if not command_template:
        return (
            f"{EXTERNAL_ROUNDTRIP_ENV} is not set; provide an external "
            "round-trip command with {input} and {output} placeholders"
        )
    command_reason = _command_template_unavailable_reason(command_template)
    if command_reason is not None:
        return command_reason
    if _env_truthy(EXTERNAL_ROUNDTRIP_REQUIRE_SDK_METADATA_ENV):
        missing = [
            name
            for name in (
                EXTERNAL_ROUNDTRIP_SDK_NAME_ENV,
                EXTERNAL_ROUNDTRIP_SDK_VERSION_ENV,
            )
            if _optional_env(name) is None
        ]
        if missing:
            return (
                f"{EXTERNAL_ROUNDTRIP_REQUIRE_SDK_METADATA_ENV} is enabled; "
                "set "
                + " and ".join(missing)
                + " so strict SDK comparison reports identify the measured SDK"
            )
    return None


def _command_template_unavailable_reason(command_template: str) -> str | None:
    if "{input}" not in command_template or "{output}" not in command_template:
        return f"{EXTERNAL_ROUNDTRIP_ENV} must include both {{input}} and {{output}}"
    try:
        parts = shlex.split(command_template)
    except ValueError as exc:
        return f"{EXTERNAL_ROUNDTRIP_ENV} could not be parsed: {exc}"
    if not parts:
        return f"{EXTERNAL_ROUNDTRIP_ENV} must not be empty"
    executable = parts[0]
    if "/" in executable:
        if not Path(executable).exists():
            return f"external round-trip executable was not found at {executable}"
        return None
    if shutil.which(executable) is None:
        return f"external round-trip executable {executable!r} was not found on PATH"
    return None


def roundtrip(
    input_path: str | Path, output_path: str | Path
) -> ExternalCommandRoundtripResult:
    unavailable_reason = external_command_roundtrip_unavailable_reason()
    if unavailable_reason is not None:
        raise RuntimeError(unavailable_reason)
    command_template = os.environ[EXTERNAL_ROUNDTRIP_ENV]

    source = Path(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    template_parts = shlex.split(command_template)
    command = _render_command(command_template, source, output)
    timeout_seconds = _roundtrip_timeout_seconds()

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
            f"external round-trip command timed out after {timeout_seconds:g}s"
        ) from exc
    if proc.returncode != 0:
        reason = proc.stderr.strip() or proc.stdout.strip() or "external round-trip command failed"
        raise RuntimeError(reason)
    if not output.exists():
        raise RuntimeError(f"external round-trip command did not create {output}")

    summary = extract_semantics(output)
    sdk_name = _optional_env(EXTERNAL_ROUNDTRIP_SDK_NAME_ENV)
    sdk_version = _optional_env(EXTERNAL_ROUNDTRIP_SDK_VERSION_ENV)
    return ExternalCommandRoundtripResult(
        path=str(output),
        input=str(source),
        part_count=summary.part_count,
        has_vba=summary.has_vba,
        command=command,
        timeout_seconds=timeout_seconds,
        command_executable=template_parts[0],
        command_template_sha256=_command_template_sha256(command_template),
        command_arg_count=len(command),
        command_uses_absolute_executable="/" in template_parts[0],
        external_sdk_name=sdk_name,
        external_sdk_version=sdk_version,
        sdk_versions=_sdk_versions(sdk_name, sdk_version),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _render_command(command_template: str, source: Path, output: Path) -> list[str]:
    if "{input}" not in command_template or "{output}" not in command_template:
        raise RuntimeError(
            f"{EXTERNAL_ROUNDTRIP_ENV} must include both {{input}} and {{output}}"
        )
    parts = shlex.split(command_template)
    return [
        part.format(input=str(source), output=str(output))
        for part in parts
    ]


def _command_template_sha256(command_template: str) -> str:
    return hashlib.sha256(command_template.encode("utf-8")).hexdigest()


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _sdk_versions(
    sdk_name: str | None, sdk_version: str | None
) -> dict[str, str] | None:
    if sdk_name is None or sdk_version is None:
        return None
    return {sdk_name: sdk_version}


def _roundtrip_timeout_seconds() -> float:
    raw_timeout = os.environ.get(EXTERNAL_ROUNDTRIP_TIMEOUT_ENV)
    if raw_timeout is None:
        return DEFAULT_EXTERNAL_ROUNDTRIP_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise RuntimeError(
            f"{EXTERNAL_ROUNDTRIP_TIMEOUT_ENV} must be a positive number of seconds"
        ) from exc
    if timeout_seconds <= 0:
        raise RuntimeError(
            f"{EXTERNAL_ROUNDTRIP_TIMEOUT_ENV} must be a positive number of seconds"
        )
    return timeout_seconds
