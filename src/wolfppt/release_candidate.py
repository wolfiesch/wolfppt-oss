"""Aggregate WolfPPT release-candidate checks into a single evidence card."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal

RowStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class RowResult:
    """The outcome of one release-candidate evidence row."""

    row_id: str
    title: str
    status: RowStatus
    detail: str
    duration_s: float

    def __post_init__(self) -> None:
        if self.status not in {"pass", "fail", "skip"}:
            raise ValueError(f"unsupported release-candidate status: {self.status}")


@dataclass(frozen=True)
class Card:
    """The pure aggregate result for a release candidate."""

    rows: list[RowResult]
    verdict: str
    ready: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "rows": [asdict(row) for row in self.rows],
            "verdict": self.verdict,
            "ready": self.ready,
        }


@dataclass
class CandidateContext:
    """Mutable, command-local state shared by dependent evidence rows."""

    repo_root: Path
    python_executable: str
    fast: bool
    pytest_args: list[str]
    corpus_timeout: int
    confirm_readme_audit: bool = False
    work_dir: Path | None = None
    package_row: RowResult | None = None
    demo_row: RowResult | None = None
    demo_receipt: dict[str, object] | None = None
    demo_deck: Path | None = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    output: str
    duration_s: float
    error: str | None = None


RowCallable = Callable[[CandidateContext], RowResult]


ROW_SPECS: tuple[tuple[str, str, RowCallable], ...] = (
    ("package-build", "package build", lambda context: package_build_row(context)),
    ("unit-regression", "unit / regression", lambda context: unit_regression_row(context)),
    ("python-pptx-parity", "python-pptx parity", lambda context: python_pptx_parity_row(context)),
    ("real-deck-corpus", "real-deck corpus", lambda context: real_deck_corpus_row(context)),
    ("demo-smoke", "demo smoke", lambda context: demo_smoke_row(context)),
    ("visual-oracle", "visual oracle", lambda context: visual_oracle_row(context)),
    ("openxml-validation", "openxml validation", lambda context: openxml_validation_row(context)),
    ("license-audit", "license audit", lambda context: license_audit_row(context)),
    ("platform-clean-install", "platform clean install", lambda context: platform_clean_install_row(context)),
    ("readme-claims-audit", "readme claims audit", lambda context: readme_claims_audit_row(context)),
)


def build_card(rows: list[RowResult], *, strict: bool) -> Card:
    """Aggregate rows without performing I/O.

    A non-strict invocation may return a successful process status despite skips,
    but a human release verdict remains negative until every row passes.
    """

    failures = sum(row.status == "fail" for row in rows)
    skips = sum(row.status == "skip" for row in rows)
    verdict = (
        "READY TO RELEASE"
        if failures == 0 and skips == 0
        else f"NOT READY: {failures} fail, {skips} skip"
    )
    return Card(
        rows=rows,
        verdict=verdict,
        ready=failures == 0 and (skips == 0 or not strict),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone release-candidate argument parser."""

    parser = argparse.ArgumentParser(description="Run WolfPPT release-candidate evidence rows")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="limit the unit/regression row to metadata and parity tests",
    )
    parser.add_argument("--json", dest="json_output", action="store_true", help="emit JSON")
    parser.add_argument("--strict", action="store_true", help="make skipped rows fail the exit status")
    parser.add_argument(
        "--confirm-readme-audit",
        action="store_true",
        help="confirm that README release claims were audited by an operator",
    )
    parser.add_argument("--skip", action="append", default=[], metavar="ROW_ID")
    parser.add_argument("--python", default=sys.executable, metavar="PY")
    parser.add_argument("--corpus-timeout", type=_positive_timeout, default=1800, metavar="SECONDS")
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        default=[],
        metavar="PYTEST_ARG",
        help="arguments passed through to pytest; place this option last",
    )
    return parser


def _positive_timeout(value: str) -> int:
    timeout = int(value)
    if timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than zero")
    return timeout


def package_build_row(context: CandidateContext) -> RowResult:
    """Build and validate the platform wheel and source distribution."""

    script = context.repo_root / "scripts" / "build-release-artifacts.sh"
    if not script.is_file():
        return _row("package-build", "package build", "fail", "build script missing", 0.0)
    result = _run_command(["bash", str(script)], context)
    if not _command_succeeded(result):
        return _command_failure("package-build", "package build", result)
    return _row("package-build", "package build", "pass", "release artifacts verified", result.duration_s)


def unit_regression_row(context: CandidateContext) -> RowResult:
    """Run the configured unit/regression pytest lane."""

    tests = (
        [
            "tests/test_validation_ladder.py",
            "tests/test_file_line_budget.py",
            "tests/test_cli.py",
        ]
        if context.fast
        else []
    )
    result = _run_command(["uv", "run", "pytest", "-q", *tests, *context.pytest_args], context)
    if not _command_succeeded(result):
        return _command_failure("unit-regression", "unit / regression", result)
    return _row(
        "unit-regression",
        "unit / regression",
        "pass",
        _pytest_summary(result.output),
        result.duration_s,
    )


def python_pptx_parity_row(context: CandidateContext) -> RowResult:
    """Run python-pptx parity tests even when their directory is currently empty."""

    result = _run_command(["uv", "run", "pytest", "tests/parity", "-q"], context)
    if not _command_succeeded(result):
        return _command_failure("python-pptx-parity", "python-pptx parity", result)
    return _row(
        "python-pptx-parity",
        "python-pptx parity",
        "pass",
        _pytest_summary(result.output),
        result.duration_s,
    )


def real_deck_corpus_row(context: CandidateContext) -> RowResult:
    """Run the bounded real-deck corpus evidence lane."""

    result = _run_command(
        ["uv", "run", "wolfppt-harness", "run-corpus", "--write-report"],
        context,
        timeout=context.corpus_timeout,
    )
    if not _command_succeeded(result):
        return _command_failure("real-deck-corpus", "real-deck corpus", result)
    return _row(
        "real-deck-corpus",
        "real-deck corpus",
        "pass",
        _tail(result.output),
        result.duration_s,
    )


def demo_smoke_row(context: CandidateContext) -> RowResult:
    """Run the dependency-free public demo and retain its verified artifact path."""

    started = time.monotonic()
    if context.work_dir is None:
        return _row("demo-smoke", "demo smoke", "fail", "demo workspace unavailable", 0.0)
    try:
        from wolfppt.demo import run_demo
    except ImportError as exc:
        return _row(
            "demo-smoke",
            "demo smoke",
            "fail",
            f"demo module unavailable: {exc}",
            time.monotonic() - started,
        )
    try:
        receipt = run_demo(context.work_dir / "demo")
    except Exception as exc:  # The aggregate command must turn demo failures into a row.
        return _row(
            "demo-smoke",
            "demo smoke",
            "fail",
            f"demo raised {type(exc).__name__}: {exc}",
            time.monotonic() - started,
        )
    duration = time.monotonic() - started
    if not isinstance(receipt, dict):
        return _row("demo-smoke", "demo smoke", "fail", "demo receipt is not a dict", duration)

    context.demo_receipt = receipt
    context.demo_deck = _demo_artifact_path(receipt)
    checks = (
        receipt.get("verified_edits") == receipt.get("requested_edits"),
        receipt.get("unrelated_parts_changed") == 0,
        receipt.get("reopen_passed") is True,
        _fail_injection_passes(receipt),
    )
    if not all(checks):
        return _row(
            "demo-smoke",
            "demo smoke",
            "fail",
            "demo receipt verification failed",
            duration,
        )
    return _row("demo-smoke", "demo smoke", "pass", "demo receipt verified", duration)


def visual_oracle_row(context: CandidateContext) -> RowResult:
    """Render the verified demo deck through LibreOffice when it is available."""

    probe = _run_command(["uv", "run", "wolfppt-harness", "render-libreoffice", "--help"], context)
    if not _command_succeeded(probe):
        return _command_failure("visual-oracle", "visual oracle", probe)
    if shutil.which("soffice") is None:
        return _row("visual-oracle", "visual oracle", "skip", "libreoffice not installed", probe.duration_s)
    if context.demo_deck is None or not context.demo_deck.is_file():
        return _row(
            "visual-oracle",
            "visual oracle",
            "skip",
            "demo output unavailable",
            probe.duration_s,
        )
    assert context.work_dir is not None
    render = _run_command(
        [
            "uv",
            "run",
            "wolfppt-harness",
            "render-libreoffice",
            str(context.demo_deck),
            "--out-dir",
            str(context.work_dir / "libreoffice"),
        ],
        context,
    )
    if not _command_succeeded(render):
        return _command_failure("visual-oracle", "visual oracle", render)
    return _row("visual-oracle", "visual oracle", "pass", "demo deck rendered", probe.duration_s + render.duration_s)


def openxml_validation_row(context: CandidateContext) -> RowResult:
    """Validate the verified demo deck with the Open XML SDK, when installed."""

    probe = _run_command(["dotnet", "--version"], context)
    if probe.error is not None or probe.returncode != 0:
        return _row(
            "openxml-validation",
            "openxml validation",
            "skip",
            "dotnet/Open XML SDK not installed",
            probe.duration_s,
        )
    if context.demo_deck is None or not context.demo_deck.is_file():
        return _row(
            "openxml-validation",
            "openxml validation",
            "skip",
            "demo output unavailable",
            probe.duration_s,
        )
    validation = _run_command(
        ["uv", "run", "wolfppt-harness", "validate-openxml", str(context.demo_deck)],
        context,
    )
    if not _command_succeeded(validation):
        return _command_failure("openxml-validation", "openxml validation", validation)
    error_count = _openxml_error_count(validation.output)
    if error_count is None:
        return _row(
            "openxml-validation",
            "openxml validation",
            "fail",
            f"validator did not report error_count; {_tail(validation.output)}",
            probe.duration_s + validation.duration_s,
        )
    if error_count > 0:
        return _row(
            "openxml-validation",
            "openxml validation",
            "fail",
            f"Open XML validation reported {error_count} errors",
            probe.duration_s + validation.duration_s,
        )
    return _row(
        "openxml-validation",
        "openxml validation",
        "pass",
        "Open XML validation reported 0 errors",
        probe.duration_s + validation.duration_s,
    )


def license_audit_row(context: CandidateContext) -> RowResult:
    """Check license metadata and the absence of bundled third-party trees."""

    started = time.monotonic()
    findings: list[str] = []
    if not (context.repo_root / "LICENSE").is_file():
        findings.append("LICENSE file missing")
    try:
        with (context.repo_root / "pyproject.toml").open("rb") as config_file:
            project = tomllib.load(config_file).get("project", {})
        if project.get("license") != "MIT":
            findings.append("pyproject project.license is not MIT")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        findings.append(f"could not read pyproject license: {exc}")
    bundled = [name for name in ("vendor", "third_party") if (context.repo_root / name).is_dir()]
    if bundled:
        findings.append(f"bundled third-party directories found: {', '.join(bundled)}")
    duration = time.monotonic() - started
    if findings:
        return _row("license-audit", "license audit", "fail", "; ".join(findings), duration)
    return _row("license-audit", "license audit", "pass", "MIT metadata and notices verified", duration)


def platform_clean_install_row(context: CandidateContext) -> RowResult:
    """Install the platform wheel into an isolated local virtual environment."""

    not_configured = "lane not configured: linux-vps, windows-x86_64"
    if sys.platform != "darwin":
        return _row(
            "platform-clean-install",
            "platform clean install",
            "skip",
            f"macos-local unavailable on {sys.platform}; {not_configured}",
            0.0,
        )
    if context.package_row is None or context.package_row.status != "pass":
        return _row(
            "platform-clean-install",
            "platform clean install",
            "skip",
            f"package-build did not pass; {not_configured}",
            0.0,
        )
    wheels = [
        path
        for path in (context.repo_root / "dist-release").glob("*.whl")
        if not path.name.endswith("-none-any.whl")
    ]
    if len(wheels) != 1:
        return _row(
            "platform-clean-install",
            "platform clean install",
            "fail",
            f"expected one platform wheel in dist-release, found {len(wheels)}",
            0.0,
        )
    if context.work_dir is None:
        return _row("platform-clean-install", "platform clean install", "fail", "workspace unavailable", 0.0)

    started = time.monotonic()
    environment = context.work_dir / "clean-install-venv"
    setup = _run_command([context.python_executable, "-m", "venv", str(environment)], context)
    if not _command_succeeded(setup):
        return _command_failure("platform-clean-install", "platform clean install", setup)
    installed_python = environment / "bin" / "python"
    install = _run_command([str(installed_python), "-m", "pip", "install", str(wheels[0])], context)
    if not _command_succeeded(install):
        return _command_failure("platform-clean-install", "platform clean install", install)
    output = context.work_dir / "clean-install.pptx"
    smoke_code = (
        "from pathlib import Path; from wolfppt import Presentation; "
        f"path = Path({str(output)!r}); presentation = Presentation(); "
        "presentation.save(path); Presentation(path)"
    )
    smoke = _run_command([str(installed_python), "-c", smoke_code], context)
    if not _command_succeeded(smoke):
        return _command_failure("platform-clean-install", "platform clean install", smoke)
    return _row(
        "platform-clean-install",
        "platform clean install",
        "skip",
        f"macos-local passed; {not_configured}",
        time.monotonic() - started,
    )


def readme_claims_audit_row(context: CandidateContext) -> RowResult:
    """Represent the explicitly acknowledged human README claims review."""

    if not context.confirm_readme_audit:
        return _row(
            "readme-claims-audit",
            "readme claims audit",
            "skip",
            "manual audit not confirmed",
            0.0,
        )
    return _row(
        "readme-claims-audit",
        "readme claims audit",
        "pass",
        "operator confirmed README claims match current evidence",
        0.0,
    )


def run_release_candidate(argv: list[str] | None = None) -> int:
    """Run all configured evidence rows, emit a card, and return its gate status."""

    args = build_parser().parse_args(argv)
    context = CandidateContext(
        repo_root=_repo_root(),
        python_executable=args.python,
        fast=args.fast,
        pytest_args=list(args.pytest_args),
        corpus_timeout=args.corpus_timeout,
        confirm_readme_audit=args.confirm_readme_audit,
    )
    skipped = set(args.skip)
    rows: list[RowResult] = []
    with tempfile.TemporaryDirectory(prefix="wolfppt-release-candidate-") as directory:
        context.work_dir = Path(directory)
        for row_id, title, runner in ROW_SPECS:
            if row_id in skipped:
                row = _row(row_id, title, "skip", "skipped by operator", 0.0)
            else:
                row = runner(context)
            rows.append(row)
            if row_id == "package-build":
                context.package_row = row
            elif row_id == "demo-smoke":
                context.demo_row = row

    card = build_card(rows, strict=args.strict)
    version = _version()
    sha = _short_sha(context.repo_root)
    payload = {"version": version, "sha": sha, **card.to_dict()}
    _write_card(context.repo_root, payload)
    if args.json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_card(card, version, sha))
    return 0 if card.ready else 1


def _row(row_id: str, title: str, status: RowStatus, detail: str, duration_s: float) -> RowResult:
    return RowResult(row_id, title, status, detail, round(duration_s, 3))


def _run_command(
    command: list[str], context: CandidateContext, *, timeout: int | None = None
) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=context.repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return CommandResult(None, "", time.monotonic() - started, str(exc))
    except subprocess.TimeoutExpired as exc:
        output = _combine_output(exc.stdout, exc.stderr)
        return CommandResult(None, output, time.monotonic() - started, f"timed out after {timeout}s")
    return CommandResult(
        completed.returncode,
        _combine_output(completed.stdout, completed.stderr),
        time.monotonic() - started,
    )


def _command_succeeded(result: CommandResult) -> bool:
    return result.error is None and result.returncode == 0


def _command_failure(row_id: str, title: str, result: CommandResult) -> RowResult:
    if result.error is not None:
        detail = result.error
    else:
        detail = f"exit {result.returncode}; {_tail(result.output)}"
    return _row(row_id, title, "fail", detail, result.duration_s)


def _combine_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    def decode(value: str | bytes | None) -> str:
        return value.decode(errors="replace") if isinstance(value, bytes) else value or ""

    return "\n".join(part for part in (decode(stdout), decode(stderr)) if part)


def _tail(output: str, *, line_limit: int = 12, character_limit: int = 2000) -> str:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    tail = "\n".join(lines[-line_limit:]) or "no output"
    return tail[-character_limit:]


def _pytest_summary(output: str) -> str:
    counts = {
        label: re.search(rf"(\d+)\s+{label}", output)
        for label in ("passed", "failed")
    }
    parts = [f"{match.group(1)} {label}" for label, match in counts.items() if match]
    return ", ".join(parts) if parts else _tail(output)


def _openxml_error_count(output: str) -> int | None:
    match = re.search(r'"error_count"\s*:\s*(\d+)', output)
    return int(match.group(1)) if match else None


def _demo_artifact_path(receipt: dict[str, object]) -> Path | None:
    artifacts = receipt.get("artifacts")
    if isinstance(artifacts, dict) and isinstance(artifacts.get("after"), str):
        return Path(artifacts["after"])
    for key in ("output_path", "deck_path", "artifact_path"):
        value = receipt.get(key)
        if isinstance(value, str):
            return Path(value)
    return None


def _fail_injection_passes(receipt: dict[str, object]) -> bool:
    for key in ("fail_injection_passed", "fail_injection_ok"):
        if key in receipt:
            return receipt[key] is True
    value = receipt.get("fail_injection")
    if value is None:
        return True
    if isinstance(value, dict):
        if "passed" in value:
            return value["passed"] is True
        return value.get("refused") is True and value.get("original_preserved") is True
    return value is True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _version() -> str:
    try:
        return importlib.metadata.version("wolfppt")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0"


def _short_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def _write_card(repo_root: Path, payload: dict[str, object]) -> Path:
    destination = repo_root / "results" / "release-candidate"
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = destination / f"card-{timestamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _render_card(card: Card, version: str, sha: str) -> str:
    lines = [f"WolfPPT candidate {version} ({sha})", ""]
    for row in card.rows:
        line = f"{row.title:<28}{row.status.upper()}"
        if row.status != "pass":
            line = f"{line:<34}  {row.detail}"
        lines.append(line)
    lines.extend(["", card.verdict])
    return "\n".join(lines)
