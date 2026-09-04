"""Smoke test for published wolfppt artifacts.

Run against an installed wheel: builds the deterministic demo deck, applies
the surgical edits, and asserts the verification receipt. Kept dependency-free
so it can run in a bare environment with only the wheel installed.
"""

from __future__ import annotations

import json
import zipfile
from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory

from wolfppt.demo import run_demo

assert version("wolfppt") == "0.1.0"
assert find_spec("wolfppt.wolfppt_native") is not None, "native module missing from wheel"

with TemporaryDirectory() as directory:
    output_dir = Path(directory) / "demo"
    receipt = run_demo(output_dir=output_dir)

    assert receipt["requested_edits"] == 4
    assert receipt["verified_edits"] == 4
    assert receipt["unrelated_parts_changed"] == 0
    assert receipt["reopen_passed"] is True
    assert receipt["validation"]["status"] in {"pass", "skip"}
    assert receipt["fail_injection"] is None

    for artifact in receipt["artifacts"].values():
        path = Path(artifact)
        assert path.is_file(), f"missing artifact: {path}"

    receipt_path = output_dir / "receipt.json"
    assert json.loads(receipt_path.read_text()) == receipt

    for name in ("before.pptx", "after.pptx"):
        package = output_dir / name
        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
        assert "ppt/presentation.xml" in names, f"{name} is not a presentation package"
        assert any(n.startswith("ppt/slides/slide") for n in names), name

print("community artifact smoke: ok")
