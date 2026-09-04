"""PptxGenJS generation adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HELPER_DIR = ROOT / "tools" / "pptxgenjs-generate"
HELPER_SCRIPT = HELPER_DIR / "generate.mjs"
NODE_MODULE = HELPER_DIR / "node_modules" / "pptxgenjs"


@dataclass(frozen=True)
class PptxGenJsGenerateResult:
    path: str
    fixture_id: str
    fixture_path: str
    bytes: int
    mode: str
    library: str
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pptxgenjs_available() -> bool:
    return shutil.which("node") is not None and HELPER_SCRIPT.exists() and NODE_MODULE.exists()


def generate(fixture_id: str, fixture_path: str | Path, output_path: str | Path) -> PptxGenJsGenerateResult:
    if shutil.which("node") is None:
        raise RuntimeError("node was not found on PATH")
    if not HELPER_SCRIPT.exists():
        raise RuntimeError(f"PptxGenJS helper is missing: {HELPER_SCRIPT}")
    if not NODE_MODULE.exists():
        raise RuntimeError("PptxGenJS dependencies are not installed; run npm install in tools/pptxgenjs-generate")

    source = Path(fixture_path)
    output = Path(output_path)
    proc = subprocess.run(
        ["node", str(HELPER_SCRIPT), fixture_id, str(source), str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = _loads_json_object(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "PptxGenJS helper did not return JSON") from exc
    if proc.returncode != 0:
        reason = payload.get("error") or proc.stderr.strip() or "PptxGenJS generation failed"
        raise RuntimeError(str(reason))
    return PptxGenJsGenerateResult(
        path=str(payload["path"]),
        fixture_id=str(payload["fixture_id"]),
        fixture_path=str(payload["fixture_path"]),
        bytes=int(payload["bytes"]),
        mode=str(payload["mode"]),
        library=str(payload["library"]),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


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
