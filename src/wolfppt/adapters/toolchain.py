"""Discovery helpers for locally installed external toolchains."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

USER_LOCAL_DOTNET = Path.home() / ".dotnet" / "dotnet"
USER_LOCAL_CARGO = Path.home() / ".cargo" / "bin" / "cargo"


def dotnet_command() -> str | None:
    system_dotnet = shutil.which("dotnet")
    if system_dotnet is not None:
        return "dotnet"
    return str(USER_LOCAL_DOTNET) if USER_LOCAL_DOTNET.exists() else None


def cargo_command() -> str | None:
    system_cargo = shutil.which("cargo")
    if system_cargo is not None:
        return "cargo"
    return str(USER_LOCAL_CARGO) if USER_LOCAL_CARGO.exists() else None


def env_with_user_local_tools() -> dict[str, str]:
    env = dict(os.environ)
    path_entries = []
    dotnet_root = USER_LOCAL_DOTNET.parent
    cargo_root = USER_LOCAL_CARGO.parent
    if dotnet_root.exists():
        path_entries.append(str(dotnet_root))
        env.setdefault("DOTNET_ROOT", str(dotnet_root))
    if cargo_root.exists():
        path_entries.append(str(cargo_root))
    if path_entries:
        env["PATH"] = os.pathsep.join([*path_entries, env.get("PATH", "")])
    return env
