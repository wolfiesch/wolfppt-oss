"""Open XML SDK validator adapter."""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .toolchain import dotnet_command, env_with_user_local_tools


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_ROOT = ROOT / "tools" / "openxml-validator"
VALIDATOR_PROJECT = VALIDATOR_ROOT / "WolfPpt.OpenXmlValidator.csproj"
VALIDATOR_PROGRAM = VALIDATOR_ROOT / "Program.cs"
VALIDATOR_DLL = VALIDATOR_ROOT / "bin" / "Debug" / "net9.0" / "WolfPpt.OpenXmlValidator.dll"
VALIDATOR_LOCK = ROOT / "tools" / "openxml-validator" / ".validator.lock"
DEFAULT_VALIDATOR_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class OpenXmlValidationResult:
    path: str
    valid: bool
    error_count: int
    errors: list[dict[str, Any]]
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validator_available() -> bool:
    return dotnet_command() is not None and VALIDATOR_PROJECT.exists()


def validate(path: str | Path) -> OpenXmlValidationResult:
    if dotnet_command() is None:
        raise RuntimeError("dotnet was not found on PATH")
    if not VALIDATOR_PROJECT.exists():
        raise RuntimeError(f"Open XML validator project is missing: {VALIDATOR_PROJECT}")

    source = Path(path)
    with _validator_lock():
        try:
            proc = subprocess.run(
                _validator_command(source),
                text=True,
                capture_output=True,
                check=False,
                timeout=_validator_timeout_seconds(),
                env=env_with_user_local_tools(),
            )
        except subprocess.TimeoutExpired as exc:
            return OpenXmlValidationResult(
                path=str(source),
                valid=False,
                error_count=1,
                errors=[
                    {
                        "description": "validator timed out",
                        "timeout_seconds": exc.timeout,
                        "stdout": _timeout_stream_text(exc.stdout),
                        "stderr": _timeout_stream_text(exc.stderr),
                    }
                ],
                stdout=_timeout_stream_text(exc.stdout),
                stderr=_timeout_stream_text(exc.stderr),
            )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return OpenXmlValidationResult(
            path=str(source),
            valid=False,
            error_count=1,
            errors=[
                {
                    "description": "validator did not return JSON",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "returncode": proc.returncode,
                }
            ],
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    return OpenXmlValidationResult(
        path=payload["path"],
        valid=bool(payload["valid"]),
        error_count=int(payload["error_count"]),
        errors=list(payload["errors"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _validator_command(source: Path) -> list[str]:
    dotnet = dotnet_command() or "dotnet"
    if _compiled_validator_current():
        return [dotnet, str(VALIDATOR_DLL), str(source)]
    return [dotnet, "run", "--project", str(VALIDATOR_PROJECT), "--", str(source)]


def _compiled_validator_current() -> bool:
    if not VALIDATOR_DLL.exists():
        return False
    try:
        dll_mtime = VALIDATOR_DLL.stat().st_mtime
        inputs = [VALIDATOR_PROJECT, VALIDATOR_PROGRAM]
        return all(not path.exists() or path.stat().st_mtime <= dll_mtime for path in inputs)
    except OSError:
        return False


def _validator_timeout_seconds() -> float:
    raw = os.environ.get("WOLFPPT_OPENXML_VALIDATOR_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_VALIDATOR_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        return DEFAULT_VALIDATOR_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_VALIDATOR_TIMEOUT_SECONDS


def _timeout_stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@contextmanager
def _validator_lock():
    VALIDATOR_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with VALIDATOR_LOCK.open("w", encoding="utf-8") as fh:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):  # pragma: no cover - platform fallback
            yield
        else:
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
