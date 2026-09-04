"""Validation ladder plans for fast local iteration and heavy VPS gates."""

from __future__ import annotations

import subprocess
from typing import Any

VALIDATION_ENV = "export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.dotnet:$PATH"
VALIDATION_SDK_ENV = (
    "export JAVA_HOME=$HOME/.local/java/current && "
    "export PATH=$HOME/.local/maven/apache-maven-3.9.11/bin:"
    "$HOME/.local/java/current/bin:$HOME/.local/bin:$HOME/.cargo/bin:"
    "$HOME/.dotnet:$PATH"
)
STRICT_EXTERNAL_SDK_METADATA_ENV = (
    "export WOLFPPT_EXTERNAL_ROUNDTRIP_REQUIRE_SDK_METADATA=1"
)

DROPIN_COVERAGE_GATE = (
    "uv run wolfppt-harness dropin-coverage --min-behaviors 149 --min-domains 9 "
    "--min-domain-behaviors charts=39,groups=31,media=16,notes=8,presentation=2 "
    "--min-domain-behaviors shapes=79,slides_layouts=18,tables=14,text=43 "
    "--min-fixture-scenarios 403 --min-adapter-fixture-rows 806 --json"
)

PYTHON_API_SURFACE_GATE = (
    "uv run wolfppt-harness python-api-surface --json --max-real-slides 999 "
    "--max-real-shapes 999 --min-fixtures 33 --min-representative-pairs 64 "
    "--min-real-pairs 1576"
)

RELEASE_FULL_GATE = (
    "uv run wolfppt-harness benchmark-profile release-full --iterations 15 "
    "--warmup 2 --validate-openxml --progress --fail-fast "
    "--min-wolfppt-speedup 1.0 "
    "--min-distinct-fixtures 30 --min-fixture-total-slides 111 "
    "--min-fixture-total-shapes 291 --min-fixture-total-charts 26 "
    "--min-fixtures-with-tables 16 --min-fixtures-with-charts 16 "
    "--min-fixtures-with-media 14 --min-fixtures-with-embedded-objects 17 "
    "--min-openxml-samples 5010 --write-report"
)

RELEASE_SMOKE_GATE = (
    "uv run wolfppt-harness benchmark-profile release-smoke --iterations 15 "
    "--warmup 2 --validate-openxml --progress --fail-fast "
    "--min-wolfppt-speedup 1.0 --min-distinct-fixtures 7 "
    "--min-openxml-samples 500 --write-report"
)

REAL_CORPUS_GATE = (
    "uv run wolfppt-harness benchmark-profile real-corpus --iterations 15 "
    "--warmup 2 --validate-openxml --progress --fail-fast "
    "--min-distinct-fixtures 16 "
    "--min-fixture-total-slides 106 --min-fixture-total-shapes 297 "
    "--min-fixture-total-tables 43 --min-fixture-total-charts 25 "
    "--min-fixture-total-media 15 --min-fixture-total-embedded-objects 36 "
    "--min-fixtures-with-tables 16 --min-fixtures-with-charts 16 "
    "--min-fixtures-with-media 15 --min-fixtures-with-embedded-objects 16 "
    "--min-openxml-samples 960 --write-report"
)

SDK_COMPARISON_GATE = (
    "uv run --with aspose.slides --with Spire.Presentation "
    "wolfppt-harness benchmark-profile sdk-comparison --iterations 5 "
    "--warmup 1 --validate-openxml --progress --fail-fast "
    "--min-distinct-fixtures 16 "
    "--min-fixture-total-slides 106 --min-fixture-total-shapes 297 "
    "--min-fixture-total-tables 43 --min-fixture-total-charts 25 "
    "--min-fixture-total-media 15 --min-fixture-total-embedded-objects 36 "
    "--min-fixtures-with-tables 16 --min-fixtures-with-charts 16 "
    "--min-fixtures-with-media 15 --min-fixtures-with-embedded-objects 16 "
    "--min-sdk-preservation-rows 48 --min-openxml-samples 480 "
    "--require-adapter apache-poi-roundtrip "
    "--require-adapter aspose-docker-roundtrip "
    "--require-adapter spire-presentation-roundtrip --write-report"
)

SDK_COMPARISON_STRICT_GATE = (
    SDK_COMPARISON_GATE.removesuffix(" --write-report")
    + " --require-adapter syncfusion-roundtrip "
    "--require-adapter external-command-roundtrip --write-report"
)

SDK_COMPARISON_CLAIM_GATE = (
    SDK_COMPARISON_GATE.replace("--iterations 5 ", "--iterations 15 ")
    .replace("--warmup 1 ", "--warmup 2 ")
    .replace("--min-openxml-samples 480 ", "--min-openxml-samples 1440 ")
)

SDK_COMPARISON_CLAIM_STRICT_GATE = (
    SDK_COMPARISON_CLAIM_GATE.removesuffix(" --write-report")
    + " --require-adapter syncfusion-roundtrip "
    "--require-adapter external-command-roundtrip --write-report"
)

PRIVATE_DECKS_INVENTORY_GATE = (
    "uv run wolfppt-harness private-decks --json --min-count 5 "
    "--min-distinct-count 5 --min-total-slides 50 --min-total-shapes 100 "
    "--min-total-tables 1 --min-total-charts 1 --min-total-media 1 "
    "--min-total-embedded-objects 1 --min-decks-with-tables 1 "
    "--min-decks-with-charts 1 --min-decks-with-media 1 "
    "--min-decks-with-embedded-objects 1 --min-distinct-decks-with-tables 1 "
    "--min-distinct-decks-with-charts 1 --min-distinct-decks-with-media 1 "
    "--min-distinct-decks-with-embedded-objects 1 --min-slides-per-deck 3 "
    "--min-shapes-per-deck 10"
)

PRIVATE_REAL_DECKS_GATE = (
    "uv run wolfppt-harness benchmark-profile private-real-decks "
    "--iterations 15 --warmup 2 --min-private-decks 5 "
    "--min-distinct-private-decks 5 --min-private-total-slides 50 "
    "--min-private-total-shapes 100 --min-private-total-tables 1 "
    "--min-private-total-charts 1 --min-private-total-media 1 "
    "--min-private-total-embedded-objects 1 --min-private-decks-with-tables 1 "
    "--min-private-decks-with-charts 1 --min-private-decks-with-media 1 "
    "--min-private-decks-with-embedded-objects 1 "
    "--min-private-distinct-decks-with-tables 1 "
    "--min-private-distinct-decks-with-charts 1 "
    "--min-private-distinct-decks-with-media 1 "
    "--min-private-distinct-decks-with-embedded-objects 1 "
    "--min-private-slides-per-deck 3 --min-private-shapes-per-deck 10 "
    "--validate-openxml --progress --fail-fast "
    "--min-native-roundtrip-speedup 1.0 "
    "--min-distinct-fixtures 5 --min-openxml-samples 100 --write-report"
)

PRIVATE_REPORT_CHECK = "uv run wolfppt-harness private-report-check results/benchmarks/latest"

VPS_PR_TOOL_GATE = (
    "uv run wolfppt-harness tools --json --unavailable-only "
    "--require-tool wolfppt-native --require-tool dotnet "
    "--require-tool openxml-sdk-roundtrip"
)

RELEASE_TOOL_GATE = (
    "uv run wolfppt-harness tools --json --unavailable-only "
    "--require-tool wolfppt-native --require-tool dotnet "
    "--require-tool openxml-sdk-roundtrip"
)

SDK_COMPARISON_TOOL_GATE = (
    "uv run --with aspose.slides --with Spire.Presentation "
    "wolfppt-harness tools --json --unavailable-only "
    "--require-tool wolfppt-native --require-tool dotnet "
    "--require-tool openxml-sdk-roundtrip --require-tool apache-poi-roundtrip "
    "--require-tool aspose-docker-roundtrip "
    "--require-tool spire-presentation-roundtrip"
)

SDK_COMPARISON_STRICT_TOOL_GATE = (
    SDK_COMPARISON_TOOL_GATE
    + " --require-tool syncfusion-roundtrip "
    "--require-tool external-command-roundtrip"
)


def validation_tiers() -> tuple[str, ...]:
    return (
        "quick",
        "slice",
        "vps-pr",
        "real-corpus",
        "private-real-decks",
        "sdk-comparison",
        "sdk-comparison-strict",
        "sdk-comparison-claim",
        "sdk-comparison-claim-strict",
        "release-smoke",
        "release",
    )


def impacted_validation_plan(paths: list[str] | None = None) -> dict[str, Any]:
    """Return focused validation commands for the current or supplied file set."""

    changed_paths = _normalize_paths(paths if paths is not None else _git_changed_paths())
    test_nodes = _impacted_pytest_nodes(changed_paths)
    rust_commands = _impacted_rust_commands(changed_paths)
    commands: list[dict[str, str]] = []
    if test_nodes:
        commands.append(
            _cmd(
                "focused-python",
                "scripts/verify-fast.sh " + " ".join(test_nodes),
                "Run the smallest local Python lane for the touched behavior.",
            )
        )
    else:
        commands.append(
            _cmd(
                "fast-default",
                "scripts/verify-fast.sh",
                "Run the default fast local lane when no tighter mapping is known.",
            )
        )
    for index, command in enumerate(rust_commands, start=1):
        commands.append(
            _cmd(
                f"focused-rust-{index}",
                command,
                "Run the focused Rust check for native crate changes.",
            )
        )
    if _touches_benchmark_runtime(changed_paths):
        commands.append(
            _cmd(
                "dev-benchmark-smoke",
                "uv run wolfppt-harness benchmark-profile dev-smoke --iterations 1 --warmup 0",
                "Catch obvious benchmark-runtime regressions without claim-grade timing.",
            )
        )
    commands.append(
        _cmd(
            "slice-checkpoint",
            "scripts/verify-slice.sh " + " ".join(test_nodes)
            if test_nodes
            else "scripts/verify-slice.sh",
            "Use before committing the completed slice.",
        )
    )
    return {
        "kind": "impacted-validation",
        "changed_paths": changed_paths,
        "commands": commands,
        "notes": _impacted_notes(changed_paths, bool(test_nodes)),
    }


def validation_ladder(
    tier: str,
    *,
    vps_host: str = "validation-host",
    vps_path: str = "~/Projects/wolfppt-validation",
) -> dict[str, Any]:
    """Return the recommended validation plan for one development tier."""

    if tier not in validation_tiers():
        raise ValueError(
            f"unknown validation tier {tier!r}; expected one of "
            f"{', '.join(validation_tiers())}"
        )
    sync_command = (
        "rsync -a --delete --exclude .git --exclude .venv ./ "
        f"{vps_host}:{vps_path}/"
    )
    remote_prefix = f"ssh {vps_host} 'cd {vps_path} && {VALIDATION_ENV} && "
    private_remote_prefix = (
        f"ssh {vps_host} 'cd {vps_path} && {VALIDATION_ENV} && "
        "export WOLFPPT_PRIVATE_DECKS_DIR=/remote/private/decks && "
    )
    sdk_remote_prefix = f"ssh {vps_host} 'cd {vps_path} && {VALIDATION_SDK_ENV} && "
    strict_sdk_remote_prefix = (
        f"ssh {vps_host} 'cd {vps_path} && {VALIDATION_SDK_ENV} && "
        f"{STRICT_EXTERNAL_SDK_METADATA_ENV} && "
    )
    if tier == "quick":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "local",
            "purpose": "fast edit feedback for one touched behavior",
            "commands": [
                _cmd(
                    "focused-python",
                    "uv run pytest <focused pytest node ids> -q",
                    "Run only tests that cover the edited behavior.",
                ),
                _cmd(
                    "focused-rust",
                    "cargo test -p wolfppt-core <focused rust test>",
                    "Run only the Rust test for edited native behavior.",
                ),
                _cmd("format", "cargo fmt --check", "Check Rust formatting."),
                _cmd(
                    "python-compile",
                    "uv run python -m compileall -q src/wolfppt",
                    "Catch syntax/import breakage without the full suite.",
                ),
                _cmd("diff-hygiene", "git diff --check", "Catch whitespace errors."),
            ],
            "notes": [
                "Use this while editing; do not run full pytest or release profiles here.",
                "Replace placeholders with the exact pytest node ids or Rust test names.",
            ],
        }
    if tier == "slice":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "local",
            "purpose": "pre-commit proof for a small completed slice",
            "commands": [
                _cmd(
                    "focused-behavior",
                    "uv run pytest <focused pytest node ids> -q",
                    "Prove the behavior changed by the slice.",
                ),
                _cmd(
                    "python-api-surface",
                    PYTHON_API_SURFACE_GATE,
                    "Gate python-pptx public names and readable facade attributes.",
                ),
                _cmd("dropin-coverage", DROPIN_COVERAGE_GATE, "Gate coverage counters."),
                _cmd(
                    "metadata-and-budget",
                    (
                        "uv run pytest tests/test_benchmark_docs.py "
                        "tests/test_benchmark_profiles.py tests/test_dropin_coverage.py "
                        "tests/test_python_api_surface.py tests/test_file_line_budget.py -q"
                    ),
                    "Check generated docs, profiles, coverage, and line budget.",
                ),
                _cmd("format", "cargo fmt --check", "Check Rust formatting."),
                _cmd(
                    "python-compile",
                    "uv run python -m compileall -q src/wolfppt",
                    "Catch syntax/import breakage.",
                ),
                _cmd("diff-hygiene", "git diff --check", "Catch whitespace errors."),
            ],
            "notes": [
                "Use this before committing a narrow parity or benchmark slice.",
                "Escalate to vps-pr when several slices accumulate or a PR is near.",
            ],
        }
    if tier == "vps-pr":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": "full pre-PR validation without blocking local editing",
            "commands": [
                _cmd(
                    "detached-vps-pr",
                    "scripts/start-vps-validation.sh",
                    "Prefer this launcher so full PR validation runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "native-binding",
                    remote_prefix
                    + "uv tool run maturin develop --manifest-path "
                    + "crates/wolfppt-py/Cargo.toml'",
                    "Refresh the debug native binding after dependency sync.",
                ),
                _cmd(
                    "tool-gate",
                    remote_prefix + VPS_PR_TOOL_GATE + "'",
                    "Fail fast if required Python, native, or Open XML tools are unavailable.",
                ),
                _cmd("python-full", remote_prefix + "uv run pytest'", "Run full Python tests."),
                _cmd("rust-full", remote_prefix + "cargo test'", "Run full Rust tests."),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Use this before PRs or after multiple local slices.",
                "Keep release benchmark evidence out of this tier unless the PR updates claims.",
            ],
        }
    if tier == "sdk-comparison":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "commercial and external SDK comparison evidence without making "
                "vendor tools part of the normal release gate"
            ),
            "commands": [
                _cmd(
                    "detached-sdk-comparison",
                    "scripts/start-vps-sdk-comparison.sh",
                    "Prefer this launcher so SDK comparison runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for fair timing.",
                ),
                _cmd(
                    "aspose-docker-image",
                    sdk_remote_prefix
                    + "docker build -t wolfppt-aspose-slides:python3.11-bullseye "
                    + "examples/external-roundtrip/aspose-docker'",
                    "Prepare the Docker-backed Aspose lane on hosts where direct Aspose cannot run.",
                ),
                _cmd(
                    "tool-gate",
                    sdk_remote_prefix + SDK_COMPARISON_TOOL_GATE + "'",
                    "Fail fast if required open-source or commercial SDK lanes are unavailable.",
                ),
                _cmd(
                    "sdk-comparison",
                    sdk_remote_prefix + SDK_COMPARISON_GATE + "'",
                    "Run the current 16-fixture SDK comparison profile.",
                ),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Use this before updating commercial SDK comparison claims.",
                "Direct Aspose may still report a host runtime blocker; the required Aspose lane is the pinned Docker adapter.",
                "Treat third-party failures as comparison evidence, not as a blanket best-in-class claim.",
            ],
        }
    if tier == "sdk-comparison-strict":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "strict commercial SDK comparison evidence that fails unless "
                "Syncfusion and the configured external SDK command are present"
            ),
            "commands": [
                _cmd(
                    "detached-sdk-comparison-strict",
                    "scripts/start-vps-sdk-comparison.sh --strict-commercial",
                    "Prefer this launcher so strict SDK comparison runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for fair timing.",
                ),
                _cmd(
                    "aspose-docker-image",
                    sdk_remote_prefix
                    + "docker build -t wolfppt-aspose-slides:python3.11-bullseye "
                    + "examples/external-roundtrip/aspose-docker'",
                    "Prepare the Docker-backed Aspose lane on hosts where direct Aspose cannot run.",
                ),
                _cmd(
                    "strict-tool-gate",
                    strict_sdk_remote_prefix
                    + SDK_COMPARISON_STRICT_TOOL_GATE
                    + "'",
                    "Fail fast if any required commercial or external SDK lane is unavailable.",
                ),
                _cmd(
                    "sdk-comparison-strict",
                    strict_sdk_remote_prefix + SDK_COMPARISON_STRICT_GATE + "'",
                    "Run the 16-fixture SDK comparison with all strict commercial lanes required.",
                ),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Use this only for a broader commercial-SDK claim, after the normal SDK comparison is healthy.",
                (
                    "The remote shell must already have Syncfusion licensing, "
                    "WOLFPPT_EXTERNAL_ROUNDTRIP_CMD, "
                    "WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_NAME, and "
                    "WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_VERSION configured."
                ),
                "Direct Aspose may still report a host runtime blocker; the required Aspose lane is the pinned Docker adapter.",
            ],
        }
    if tier == "sdk-comparison-claim":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "claim-grade commercial and external SDK comparison evidence "
                "using 15 measured iterations"
            ),
            "commands": [
                _cmd(
                    "detached-sdk-comparison-claim",
                    "scripts/start-vps-sdk-comparison.sh --claim-grade",
                    "Prefer this launcher so claim-grade SDK comparison runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for fair timing.",
                ),
                _cmd(
                    "aspose-docker-image",
                    sdk_remote_prefix
                    + "docker build -t wolfppt-aspose-slides:python3.11-bullseye "
                    + "examples/external-roundtrip/aspose-docker'",
                    "Prepare the Docker-backed Aspose lane on hosts where direct Aspose cannot run.",
                ),
                _cmd(
                    "tool-gate",
                    sdk_remote_prefix + SDK_COMPARISON_TOOL_GATE + "'",
                    "Fail fast if required open-source or commercial SDK lanes are unavailable.",
                ),
                _cmd(
                    "sdk-comparison-claim",
                    sdk_remote_prefix + SDK_COMPARISON_CLAIM_GATE + "'",
                    "Run the SDK comparison profile with 15 measured iterations.",
                ),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Use this before publishing SDK speed or safety comparisons.",
                "Keep the normal sdk-comparison tier for setup and boundary evidence.",
                "Treat third-party failures as comparison evidence, not as a blanket best-in-class claim.",
            ],
        }
    if tier == "sdk-comparison-claim-strict":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "strict claim-grade commercial SDK comparison evidence with "
                "Syncfusion and the configured external SDK command required"
            ),
            "commands": [
                _cmd(
                    "detached-sdk-comparison-claim-strict",
                    "scripts/start-vps-sdk-comparison.sh --claim-grade --strict-commercial",
                    "Prefer this launcher so strict claim-grade SDK comparison runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for fair timing.",
                ),
                _cmd(
                    "aspose-docker-image",
                    sdk_remote_prefix
                    + "docker build -t wolfppt-aspose-slides:python3.11-bullseye "
                    + "examples/external-roundtrip/aspose-docker'",
                    "Prepare the Docker-backed Aspose lane on hosts where direct Aspose cannot run.",
                ),
                _cmd(
                    "strict-tool-gate",
                    strict_sdk_remote_prefix
                    + SDK_COMPARISON_STRICT_TOOL_GATE
                    + "'",
                    "Fail fast if any required commercial or external SDK lane is unavailable.",
                ),
                _cmd(
                    "sdk-comparison-claim-strict",
                    strict_sdk_remote_prefix
                    + SDK_COMPARISON_CLAIM_STRICT_GATE
                    + "'",
                    "Run the 15-iteration SDK comparison with all strict commercial lanes required.",
                ),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Use this only for a broad commercial-SDK claim.",
                (
                    "The remote shell must already have Syncfusion licensing, "
                    "WOLFPPT_EXTERNAL_ROUNDTRIP_CMD, "
                    "WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_NAME, and "
                    "WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_VERSION configured."
                ),
                "Direct Aspose may still report a host runtime blocker; the required Aspose lane is the pinned Docker adapter.",
            ],
        }
    if tier == "real-corpus":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "claim-grade benchmark evidence for checked-in real-world-style "
                "corpus fixtures"
            ),
            "commands": [
                _cmd(
                    "detached-real-corpus",
                    "scripts/start-vps-real-corpus.sh",
                    "Prefer this launcher so real-corpus evidence runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for benchmark evidence.",
                ),
                _cmd(
                    "tool-gate",
                    remote_prefix + RELEASE_TOOL_GATE + "'",
                    "Fail fast if required real-corpus evidence tools are unavailable.",
                ),
                _cmd(
                    "real-corpus",
                    remote_prefix + REAL_CORPUS_GATE + "'",
                    "Run the current 16-fixture real-corpus profile.",
                ),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Use this before updating real-world deck benchmark claims.",
                "This is checked-in corpus evidence; use private-real-decks for uncommitted customer or user decks.",
            ],
        }
    if tier == "private-real-decks":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "claim-grade pressure evidence on uncommitted private decks "
                "without adding those decks to the repository"
            ),
            "commands": [
                _cmd(
                    "detached-private-real-decks",
                    "scripts/start-vps-private-real-decks.sh --private-decks-dir /remote/private/decks",
                    "Start the private real-deck gate as a detached remote job.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for benchmark evidence.",
                ),
                _cmd(
                    "inventory-gate",
                    private_remote_prefix + PRIVATE_DECKS_INVENTORY_GATE + "'",
                    "Fail if the mounted private corpus is too small, duplicated, or trivial.",
                ),
                _cmd(
                    "private-real-decks",
                    private_remote_prefix + PRIVATE_REAL_DECKS_GATE + "'",
                    "Run the private real-deck benchmark profile with breadth gates.",
                ),
                _cmd(
                    "redaction-check",
                    private_remote_prefix + PRIVATE_REPORT_CHECK + "'",
                    "Check generated text reports before sharing or committing evidence.",
                ),
            ],
            "notes": [
                "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
                "Replace /remote/private/decks with the VPS-local private corpus path before running.",
                "Never sync or commit private decks into the repository mirror.",
                "Review generated reports before sharing; redaction removes raw names and paths, but reports can contain semantic metadata.",
            ],
        }
    if tier == "release-smoke":
        return {
            "kind": "validation-ladder",
            "tier": tier,
            "location": "remote validation host",
            "purpose": (
                "claim-grade release checkpoint on representative core and "
                "drop-in lanes without running the exhaustive release profile"
            ),
            "commands": [
                _cmd(
                    "detached-release-smoke",
                    "scripts/start-vps-claims.sh --smoke",
                    "Prefer this launcher so representative release evidence runs in the background.",
                ),
                _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
                _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
                _cmd(
                    "release-native",
                    remote_prefix
                    + "uv tool run maturin develop --release "
                    + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                    "Build the native binding in release mode for benchmark claims.",
                ),
                _cmd(
                    "tool-gate",
                    remote_prefix + RELEASE_TOOL_GATE + "'",
                    "Fail fast if required release-smoke evidence tools are unavailable.",
                ),
                _cmd(
                    "release-smoke",
                    remote_prefix + RELEASE_SMOKE_GATE + "'",
                    "Run the representative release checkpoint gate.",
                ),
            ],
            "notes": [
                "Use this for fast claim-grade checkpoint evidence while developing.",
                "This is not a substitute for release-full when updating broad public release claims.",
                "Run real-corpus or sdk-comparison separately when the claim depends on them.",
            ],
        }
    return {
        "kind": "validation-ladder",
        "tier": tier,
        "location": "remote validation host",
        "purpose": "claim-grade benchmark and release evidence",
        "commands": [
            _cmd(
                "detached-release",
                "scripts/start-vps-claims.sh --full",
                "Prefer this launcher so claim evidence runs in the background.",
            ),
            _cmd("sync", sync_command, "Mirror the working tree to the remote validation host."),
            _cmd("python-deps", remote_prefix + "uv sync --extra dev'", "Refresh VPS deps."),
            _cmd(
                "release-native",
                remote_prefix
                + "uv tool run maturin develop --release "
                + "--manifest-path crates/wolfppt-py/Cargo.toml'",
                "Build the native binding in release mode for benchmark claims.",
            ),
            _cmd(
                "tool-gate",
                remote_prefix + RELEASE_TOOL_GATE + "'",
                "Fail fast if required claim-evidence tools are unavailable.",
            ),
            _cmd("release-full", remote_prefix + RELEASE_FULL_GATE + "'", "Run claim gate."),
        ],
        "notes": [
            "Prefer the detached launcher for normal use; the following SSH commands show the exact gate it runs.",
            "Use this only before updating public benchmark or release claims.",
            "Run real-corpus or sdk-comparison separately when the claim depends on them.",
        ],
    }


def render_validation_ladder_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# Validation Ladder: {plan['tier']}",
        "",
        f"- location: {plan['location']}",
        f"- purpose: {plan['purpose']}",
        "",
        "| Step | Command | Why |",
        "|---|---|---|",
    ]
    for command in plan["commands"]:
        lines.append(
            f"| {command['name']} | `{command['command']}` | {command['why']} |"
        )
    lines.append("")
    lines.append("## Notes")
    for note in plan["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def render_impacted_validation_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Impacted Validation",
        "",
        "## Changed Paths",
    ]
    if plan["changed_paths"]:
        for path in plan["changed_paths"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No changed paths detected.")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "| Step | Command | Why |",
            "|---|---|---|",
        ]
    )
    for command in plan["commands"]:
        lines.append(
            f"| {command['name']} | `{command['command']}` | {command['why']} |"
        )
    lines.extend(["", "## Notes"])
    for note in plan["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _cmd(name: str, command: str, why: str) -> dict[str, str]:
    return {"name": name, "command": command, "why": why}


def _git_changed_paths() -> list[str]:
    paths: list[str] = []
    for command in (
        ("git", "diff", "--name-only"),
        ("git", "diff", "--cached", "--name-only"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    ):
        result = subprocess.run(command, check=False, text=True, capture_output=True)
        if result.returncode == 0:
            paths.extend(line for line in result.stdout.splitlines() if line.strip())
    return paths


def _normalize_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw_path in paths:
        path = raw_path.strip().lstrip("./")
        if path and path not in seen:
            normalized.append(path)
            seen.add(path)
    return normalized


def _impacted_pytest_nodes(paths: list[str]) -> list[str]:
    nodes: set[str] = set()
    for path in paths:
        nodes.update(_nodes_for_path(path))
    return sorted(nodes)


def _nodes_for_path(path: str) -> set[str]:
    if path.startswith("tests/") and path.endswith(".py"):
        return {path}
    if path in {"src/wolfppt/validation_ladder.py"} or path.startswith("scripts/"):
        return {"tests/test_validation_ladder.py", "tests/test_cli.py"}
    if path.startswith("docs/") or path in {"AGENTS.md", "README.md"}:
        return {"tests/test_benchmark_docs.py", "tests/test_spec_and_matrix.py"}
    if "dropin_coverage" in path:
        return {"tests/test_dropin_coverage.py"}
    if "benchmark_profile" in path:
        return {
            "tests/test_benchmark_profiles.py",
            "tests/test_benchmark_profile_batch_selection.py",
            "tests/test_benchmark_profile_sdk_gates.py",
        }
    if path.startswith("src/wolfppt/adapters/"):
        return {"tests/test_adapters.py", "tests/test_toolchain_discovery.py"}
    if _contains_any(path, ("chart", "facade_chart_values")):
        return {
            "tests/parity/test_python_pptx_dropin_chart_data.py",
            "tests/parity/test_python_pptx_dropin_group_shape_adds.py",
            "tests/parity/test_python_pptx_dropin_slide_media_table.py",
            "tests/test_benchmark_dropin_chart.py",
            "tests/test_benchmark_dropin_shape_chart_add_chart.py",
            "tests/test_chart_axis_ids.py",
            "tests/test_chart_workbook.py",
            "tests/test_presentation_facade_chart.py",
        }
    if _contains_any(path, ("table",)):
        return {
            "tests/test_benchmark_dropin_table.py",
            "tests/test_presentation_facade_media_live.py",
        }
    if _contains_any(path, ("text", "paragraph")):
        return {
            "tests/test_benchmark_dropin_text_formatting.py",
            "tests/test_benchmark_dropin_text_frame.py",
            "tests/parity/test_python_pptx_dropin_text.py",
            "tests/parity/test_python_pptx_dropin_text_runs.py",
        }
    if _contains_any(path, ("connector",)):
        return {
            "tests/parity/test_python_pptx_dropin_text.py",
            "tests/test_benchmark_dropin_shape_chart.py",
            "tests/test_benchmark_dropin_shape_chart_add_chart.py",
            "tests/test_presentation_facade_live_roundtrip.py",
        }
    if _contains_any(path, ("shape", "group", "freeform", "connector")):
        return {
            "tests/test_benchmark_dropin_shape_format.py",
            "tests/test_presentation_facade_shape_style.py",
            "tests/parity/test_python_pptx_dropin_group_shape_adds.py",
        }
    if _contains_any(path, ("media", "image", "picture", "ole")):
        return {"tests/test_benchmark_dropin_media.py", "tests/test_native_media.py"}
    if path.startswith("src/wolfppt/corpus") or path.startswith("fixtures/"):
        return {"tests/test_corpus.py", "tests/test_extractor.py"}
    if path.startswith("src/wolfppt/native") or path.startswith("src/wolfppt/package"):
        return {"tests/test_native.py", "tests/test_package_diff.py"}
    if path.startswith("src/wolfppt/"):
        return {"tests/test_cli.py", "tests/test_file_line_budget.py"}
    return set()


def _impacted_rust_commands(paths: list[str]) -> list[str]:
    commands: list[str] = []
    if any(path.startswith("crates/wolfppt-core/") for path in paths):
        commands.append("cargo test -p wolfppt-core")
    if any(path.startswith("crates/wolfppt-cli/") for path in paths):
        commands.append("cargo test -p wolfppt-cli")
    if any(path.startswith("crates/wolfppt-py/") for path in paths):
        commands.append("cargo test -p wolfppt-py")
        commands.append(
            "uv run maturin develop --manifest-path crates/wolfppt-py/Cargo.toml"
        )
    return commands


def _touches_benchmark_runtime(paths: list[str]) -> bool:
    return any(
        path.startswith("src/wolfppt/benchmark")
        or path.startswith("src/wolfppt/dropin_coverage.py")
        for path in paths
    )


def _impacted_notes(paths: list[str], mapped: bool) -> list[str]:
    notes = [
        "This is an edit-feedback plan, not release or claim-grade evidence.",
        "Escalate to scripts/verify-vps.sh after several slices or before opening a PR.",
    ]
    if not paths:
        notes.insert(0, "No changed paths were detected; the default fast lane is safest.")
    elif not mapped:
        notes.insert(0, "No specific mapping matched; use the default fast lane.")
    if any(path.startswith("docs/compatibility/") for path in paths):
        notes.append(
            "If compatibility spec output changes, regenerate the matrix and keep KNOWN_GAPS.md in sync."
        )
    if any(path.startswith("crates/") for path in paths):
        notes.append("Native binding changes may need maturin develop before Python tests.")
    return notes


def _contains_any(path: str, fragments: tuple[str, ...]) -> bool:
    return any(fragment in path for fragment in fragments)
