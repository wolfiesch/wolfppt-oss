"""Curated benchmark profile catalog definitions."""

from __future__ import annotations

from .benchmark_profile_dropin_full import build_dropin_full_batches
from .benchmark_profile_dropin_smoke import build_dropin_smoke_batches
from .benchmark_profile_models import BenchmarkProfile, BenchmarkProfileBatch
from .private_decks import PRIVATE_DECKS_SENTINEL

CORE_SMOKE_FIXTURES = (
    "text_basic/title_body_bullets",
    "tables/simple_table",
    "charts/bar_chart",
    "media/png_picture",
    "workloads/multi_edit_table",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)

MIXED_REAL_WORLD_FIXTURES = (
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
GROUPED_REAL_WORLD_FIXTURES = (
    "workloads/management_reporting_deck",
    "workloads/customer_success_review_pack",
)

REAL_CORPUS_FIXTURES = (
    *MIXED_REAL_WORLD_FIXTURES,
    "workloads/large_real_world_deck",
    "workloads/portfolio_ops_review_deck",
    "workloads/management_reporting_deck",
    "workloads/finance_board_pack",
    "workloads/investor_update_pack",
    "workloads/qoe_diligence_pack",
    "workloads/customer_success_review_pack",
    "workloads/security_compliance_review_pack",
    "workloads/revenue_ops_forecast_pack",
    "workloads/product_launch_readiness_pack",
    "workloads/enterprise_implementation_pack",
    "workloads/procurement_vendor_risk_pack",
    "workloads/post_merger_integration_pack",
    "workloads/earnings_board_appendix_pack",
)

CORE_PRESERVATION_ADAPTERS = (
    "semantic-oracle",
    "python-pptx-summary",
    "python-pptx-roundtrip",
    "openxml-sdk-roundtrip",
    "rust-core-inspect",
    "rust-core-roundtrip",
    "native-rust-package",
    "native-rust-summary",
    "native-rust-roundtrip",
)

SDK_COMPARISON_ADAPTERS = (
    "python-pptx-roundtrip",
    "openxml-sdk-roundtrip",
    "apache-poi-roundtrip",
    "aspose-slides-roundtrip",
    "aspose-docker-roundtrip",
    "spire-presentation-roundtrip",
    "syncfusion-roundtrip",
    "external-command-roundtrip",
    "native-rust-roundtrip",
)

SDK_SMOKE_FIXTURES = ("workloads/mixed_real_world_deck",)

SDK_PRESERVATION_ADAPTERS = (
    "python-pptx-roundtrip",
    "openxml-sdk-roundtrip",
    "apache-poi-roundtrip",
    "native-rust-roundtrip",
)

SDK_SPIRE_REPRODUCER_ADAPTERS = (
    "spire-presentation-roundtrip",
    "native-rust-roundtrip",
)

RELEASE_CORE_ADAPTERS = CORE_PRESERVATION_ADAPTERS


def _adapter_pair(operation: str) -> tuple[str, str]:
    return (f"python-pptx-{operation}", f"wolfppt-facade-{operation}")


DEV_SMOKE_BATCHES = (
    BenchmarkProfileBatch(
        name="dev-core-roundtrip",
        description=(
            "Tiny preservation check against python-pptx and WolfPPT native for edit-loop "
            "feedback; use claim profiles for evidence."
        ),
        adapter_names=("python-pptx-roundtrip", "native-rust-roundtrip"),
        fixture_ids=("text_basic/title_body_bullets",),
    ),
    BenchmarkProfileBatch(
        name="dev-table-add",
        description="Fast table insertion comparison for table writer changes.",
        adapter_names=_adapter_pair("dropin-add-table"),
        fixture_ids=("text_basic/title_body_bullets",),
    ),
    BenchmarkProfileBatch(
        name="dev-nested-group-chart-add",
        description="Fast nested-group chart insertion comparison for current floor work.",
        adapter_names=_adapter_pair("dropin-add-nested-group-chart"),
        fixture_ids=("shapes/grouped_shapes",),
    ),
    BenchmarkProfileBatch(
        name="dev-mixed-workload-edit",
        description="Small real-world-style mixed edit comparison for facade regressions.",
        adapter_names=_adapter_pair("dropin-mixed-workload-edit"),
        fixture_ids=("workloads/mixed_real_world_deck",),
    ),
    BenchmarkProfileBatch(
        name="dev-real-world-table-chart-edits",
        description=(
            "Small real-world-style table and chart edit comparisons for scoped "
            "package-change regressions."
        ),
        adapter_names=(
            *_adapter_pair("dropin-table-cell-text-frame-edit"),
            *_adapter_pair("dropin-chart-data-edit"),
            *_adapter_pair("dropin-chart-title-edit"),
        ),
        fixture_ids=MIXED_REAL_WORLD_FIXTURES,
    ),
)


DROPIN_SMOKE_BATCHES = build_dropin_smoke_batches(MIXED_REAL_WORLD_FIXTURES)


DROPIN_FULL_BATCHES = build_dropin_full_batches(
    MIXED_REAL_WORLD_FIXTURES,
    GROUPED_REAL_WORLD_FIXTURES,
)

RELEASE_SMOKE_DROPIN_BATCH_NAMES = {
    "dropin-text-edit",
    "dropin-table-edit",
    "dropin-mixed-real-world-edit",
    "dropin-chart-data",
    "dropin-add-picture",
    "dropin-add-table",
    "dropin-add-slide",
}
RELEASE_SMOKE_BATCHES = (
    BenchmarkProfileBatch(
        name="core-smoke",
        description=(
            "Default existing-deck adapters across representative fixture categories."
        ),
        adapter_names=RELEASE_CORE_ADAPTERS,
        fixture_ids=CORE_SMOKE_FIXTURES,
    ),
    *(
        batch
        for batch in DROPIN_SMOKE_BATCHES
        if batch.name in RELEASE_SMOKE_DROPIN_BATCH_NAMES
    ),
)


BENCHMARK_PROFILES = (
    BenchmarkProfile(
        name="dev-smoke",
        description=(
            "Tiny edit-loop profile for quick local or VPS feedback. It is intentionally "
            "not claim-grade evidence; use release-full, real-corpus, sdk-preservation, "
            "or private-real-decks before making benchmark claims."
        ),
        batches=DEV_SMOKE_BATCHES,
    ),
    BenchmarkProfile(
        name="core-smoke",
        description=(
            "Representative preservation/read benchmark across text, table, chart, media, "
            "and dense-table fixtures using built-in preservation adapters."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="core-smoke",
                description=(
                    "Built-in preservation adapters across representative fixture categories."
                ),
                adapter_names=CORE_PRESERVATION_ADAPTERS,
                fixture_ids=CORE_SMOKE_FIXTURES,
            ),
        ),
    ),
    BenchmarkProfile(
        name="core-full",
        description=(
            "Built-in preservation/read adapter set across the full checked-in fixture manifest."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="core-full",
                description="Built-in preservation adapters across every checked-in corpus fixture.",
                adapter_names=CORE_PRESERVATION_ADAPTERS,
                fixture_ids=None,
            ),
        ),
    ),
    BenchmarkProfile(
        name="real-corpus",
        description=(
            "Real-world-style preservation lane across mixed workload decks, including "
            "larger board, finance, investor-update, and QoE corpus sentinels."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="real-corpus",
                description=(
                    "Existing-deck adapters across mixed real-world corpus fixtures."
                ),
                adapter_names=CORE_PRESERVATION_ADAPTERS,
                fixture_ids=REAL_CORPUS_FIXTURES,
            ),
        ),
    ),
    BenchmarkProfile(
        name="private-real-decks",
        description=(
            "Opt-in preservation lane for user-supplied private .pptx/.pptm decks. "
            "Deck names and paths are redacted in benchmark reports."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="private-real-decks",
                description=(
                    "Built-in preservation adapters across private real-world decks "
                    "discovered from WOLFPPT_PRIVATE_DECKS_DIR."
                ),
                adapter_names=CORE_PRESERVATION_ADAPTERS,
                fixture_ids=(PRIVATE_DECKS_SENTINEL,),
            ),
        ),
    ),
    BenchmarkProfile(
        name="sdk-comparison",
        description=(
            "Explicit third-party SDK comparison lane across real-world corpus fixtures. "
            "Commercial and external adapters may fail or skip; use this profile for "
            "claim-boundary evidence, not the default release gate."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="sdk-comparison",
                description=(
                    "Round-trip comparison across python-pptx, Open XML SDK, "
                    "Apache POI, commercial SDKs, external commands, and WolfPPT native."
                ),
                adapter_names=SDK_COMPARISON_ADAPTERS,
                fixture_ids=REAL_CORPUS_FIXTURES,
            ),
        ),
    ),
    BenchmarkProfile(
        name="sdk-smoke",
        description=(
            "Small third-party SDK setup and correctness smoke on one mixed "
            "real-world-style deck. Use for adapter triage before sdk-comparison; "
            "it is not broad commercial-SDK claim evidence."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="sdk-smoke",
                description=(
                    "Round-trip comparison across SDK adapters on the mixed "
                    "real-world workload fixture."
                ),
                adapter_names=SDK_COMPARISON_ADAPTERS,
                fixture_ids=SDK_SMOKE_FIXTURES,
            ),
        ),
    ),
    BenchmarkProfile(
        name="sdk-preservation",
        description=(
            "Claim-grade passing preservation comparison against popular open-source "
            "round-trip baselines that currently produce valid real-corpus outputs. "
            "Commercial SDK failure evidence stays in sdk-comparison."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="sdk-preservation",
                description=(
                    "Round-trip preservation comparison across python-pptx, "
                    "Open XML SDK, Apache POI, and WolfPPT native."
                ),
                adapter_names=SDK_PRESERVATION_ADAPTERS,
                fixture_ids=REAL_CORPUS_FIXTURES,
            ),
        ),
    ),
    BenchmarkProfile(
        name="sdk-spire-reproducer",
        description=(
            "Narrow Spire.Presentation versus WolfPPT native reproducer on a "
            "chart-bearing real-world-style deck. Use for SDK setup and correctness "
            "triage, not broad speed claims."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="sdk-spire-reproducer",
                description=(
                    "Spire.Presentation and WolfPPT native round-trip comparison on "
                    "the mixed real-world workload fixture."
                ),
                adapter_names=SDK_SPIRE_REPRODUCER_ADAPTERS,
                fixture_ids=("workloads/mixed_real_world_deck",),
            ),
        ),
    ),
    BenchmarkProfile(
        name="dropin-smoke",
        description=(
            "Representative python-pptx vs WolfPPT facade edits with only valid "
            "adapter/fixture combinations."
        ),
        batches=DROPIN_SMOKE_BATCHES,
    ),
    BenchmarkProfile(
        name="dropin-full",
        description=(
            "Full curated python-pptx vs WolfPPT facade suite for supported drop-in "
            "editing workflows."
        ),
        batches=DROPIN_FULL_BATCHES,
    ),
    BenchmarkProfile(
        name="release-smoke",
        description=(
            "A combined smoke suite for release evidence: representative core preservation "
            "plus a small set of representative drop-in API edits. The generation-only "
            "PptxGenJS lane is omitted so --validate-openxml is strict for existing-deck lanes."
        ),
        batches=RELEASE_SMOKE_BATCHES,
    ),
    BenchmarkProfile(
        name="release-full",
        description=(
            "An exhaustive release evidence suite: full existing-deck corpus preservation "
            "plus the full curated drop-in API benchmark matrix. The generation-only "
            "PptxGenJS lane is omitted so --validate-openxml is strict for existing-deck "
            "lanes."
        ),
        batches=(
            BenchmarkProfileBatch(
                name="core-full",
                description=(
                    "Default existing-deck adapters across every checked-in corpus fixture."
                ),
                adapter_names=RELEASE_CORE_ADAPTERS,
                fixture_ids=None,
            ),
            *DROPIN_FULL_BATCHES,
        ),
    ),
)
