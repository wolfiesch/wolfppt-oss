"""Apache POI round-trip adapter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .sdk_versions import maven_dependency_versions


ROOT = Path(__file__).resolve().parents[3]
HELPER_ROOT = ROOT / "tools" / "apache-poi-roundtrip"
HELPER_POM = HELPER_ROOT / "pom.xml"
HELPER_MAVEN_WRAPPER = HELPER_ROOT / "mvnw"
USER_LOCAL_JAVA_HOME = Path.home() / ".local" / "java" / "current"
USER_LOCAL_MAVEN_BIN = Path.home() / ".local" / "maven" / "apache-maven-3.9.11" / "bin"


@dataclass(frozen=True)
class ApachePoiRoundtripResult:
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


def apache_poi_roundtrip_available() -> bool:
    return (
        _java_command() is not None
        and _maven_command() is not None
        and HELPER_POM.exists()
    )


def apache_poi_roundtrip_unavailable_reason() -> str | None:
    if not HELPER_POM.exists():
        return f"Apache POI round-trip project is missing: {HELPER_POM}"
    if _java_command() is None:
        return "Java was not found; install a JDK to run the Apache POI benchmark lane"
    if _maven_command() is None:
        return (
            "Maven was not found; install mvn or add tools/apache-poi-roundtrip/mvnw "
            "to run the Apache POI benchmark lane"
        )
    return None


def roundtrip(input_path: str | Path, output_path: str | Path) -> ApachePoiRoundtripResult:
    unavailable_reason = apache_poi_roundtrip_unavailable_reason()
    if unavailable_reason is not None:
        raise RuntimeError(unavailable_reason)

    source = Path(input_path)
    output = Path(output_path)
    proc = subprocess.run(
        [
            _maven_command() or "mvn",
            "-q",
            "-f",
            str(HELPER_POM),
            "-DskipTests",
            "compile",
            "exec:java",
            "-Dexec.mainClass=Roundtrip",
            f"-Dexec.args={source} {output}",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=_apache_poi_env(),
    )
    try:
        payload = _loads_json_object(proc.stdout)
    except json.JSONDecodeError as exc:
        reason = proc.stderr.strip() or proc.stdout.strip() or "Apache POI helper did not return JSON"
        raise RuntimeError(reason) from exc
    if proc.returncode != 0:
        reason = payload.get("error") or proc.stderr.strip() or "Apache POI round-trip failed"
        raise RuntimeError(str(reason))
    return ApachePoiRoundtripResult(
        path=str(payload["path"]),
        input=str(payload["input"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
        parts=list(payload["parts"]),
        sdk_versions=apache_poi_sdk_versions(),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def apache_poi_sdk_versions() -> dict[str, str]:
    return maven_dependency_versions(HELPER_POM, {"poi-ooxml"})


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


def _maven_command() -> str | None:
    system_maven = shutil.which("mvn")
    if system_maven is not None:
        return "mvn"
    user_local_maven = USER_LOCAL_MAVEN_BIN / "mvn"
    if user_local_maven.exists():
        return str(user_local_maven)
    if HELPER_MAVEN_WRAPPER.exists():
        return str(HELPER_MAVEN_WRAPPER)
    return None


def _java_command() -> str | None:
    java = shutil.which("java")
    if java is None:
        user_local_java = USER_LOCAL_JAVA_HOME / "bin" / "java"
        java = str(user_local_java) if user_local_java.exists() else None
    if java is None:
        return None
    return java if _command_exits_zero([java, "-version"]) else None


def _command_exits_zero(command: list[str]) -> bool:
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    return proc.returncode == 0


def _apache_poi_env() -> dict[str, str]:
    env = dict(os.environ)
    path_entries = []
    java_bin = USER_LOCAL_JAVA_HOME / "bin"
    if java_bin.exists():
        path_entries.append(str(java_bin))
        env.setdefault("JAVA_HOME", str(USER_LOCAL_JAVA_HOME))
    if USER_LOCAL_MAVEN_BIN.exists():
        path_entries.append(str(USER_LOCAL_MAVEN_BIN))
    if path_entries:
        env["PATH"] = os.pathsep.join([*path_entries, env.get("PATH", "")])
    return env
