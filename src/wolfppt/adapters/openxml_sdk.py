"""Open XML SDK round-trip adapter."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .sdk_versions import dotnet_package_versions
from .toolchain import dotnet_command, env_with_user_local_tools


ROOT = Path(__file__).resolve().parents[3]
ROUNDTRIP_PROJECT = ROOT / "tools" / "openxml-roundtrip" / "WolfPpt.OpenXmlRoundtrip.csproj"


@dataclass(frozen=True)
class OpenXmlSdkRoundtripResult:
    path: str
    input: str
    part_count: int
    has_vba: bool
    parts: list[str]
    sdk_versions: dict[str, str]
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def openxml_sdk_roundtrip_available() -> bool:
    return dotnet_command() is not None and ROUNDTRIP_PROJECT.exists()


def roundtrip(input_path: str | Path, output_path: str | Path) -> OpenXmlSdkRoundtripResult:
    dotnet = dotnet_command()
    if dotnet is None:
        raise RuntimeError("dotnet was not found on PATH")
    if not ROUNDTRIP_PROJECT.exists():
        raise RuntimeError(f"Open XML SDK round-trip project is missing: {ROUNDTRIP_PROJECT}")

    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [dotnet, "run", "--project", str(ROUNDTRIP_PROJECT), "--", str(source), str(output)],
        text=True,
        capture_output=True,
        check=False,
        env=env_with_user_local_tools(),
    )
    try:
        payload = _loads_json_object(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Open XML SDK helper did not return JSON") from exc
    if proc.returncode != 0:
        reason = payload.get("error") or proc.stderr.strip() or "Open XML SDK round-trip failed"
        raise RuntimeError(str(reason))
    return OpenXmlSdkRoundtripResult(
        path=str(payload["path"]),
        input=str(payload["input"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        parts=list(payload["parts"]),
        sdk_versions=openxml_sdk_versions(),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def openxml_sdk_versions() -> dict[str, str]:
    return dotnet_package_versions(ROUNDTRIP_PROJECT, {"DocumentFormat.OpenXml"})


def _loads_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise json.JSONDecodeError("no JSON object found", text, 0)
