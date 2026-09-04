"""Fixture manifest definitions for deterministic corpus generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureSpec:
    id: str
    path: str
    description: str
    tags: list[str]


FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec(
        id="text_basic/title_body_bullets",
        path="text_basic/title_body_bullets.pptx",
        description="Title and body text with multiple paragraphs.",
        tags=["P0", "text", "shapes"],
    ),
    FixtureSpec(
        id="slides/two_slide_text",
        path="slides/two_slide_text.pptx",
        description="Two-slide deck for internal slide hyperlink and navigation probes.",
        tags=["P0", "slides", "relationships", "text"],
    ),
    FixtureSpec(
        id="tables/simple_table",
        path="tables/simple_table.pptx",
        description="A two-by-two table with stable cell text.",
        tags=["P1", "tables"],
    ),
    FixtureSpec(
        id="workloads/multi_edit_table",
        path="workloads/multi_edit_table.pptx",
        description="Dense table workload for batched table-cell edit benchmarks.",
        tags=["P1", "tables", "benchmark"],
    ),
    FixtureSpec(
        id="workloads/multi_format_runs",
        path="workloads/multi_format_runs.pptx",
        description="Dense text-run workload for batched rich-formatting edit benchmarks.",
        tags=["P1", "text", "benchmark"],
    ),
    FixtureSpec(
        id="workloads/mixed_real_world_deck",
        path="workloads/mixed_real_world_deck.pptx",
        description=(
            "Multi-slide mixed deck with text, picture, table, chart, and notes "
            "for real-world preservation benchmarks."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "tables",
            "charts",
            "media",
            "notes",
        ],
    ),
    FixtureSpec(
        id="workloads/mixed_deal_review_deck",
        path="workloads/mixed_deal_review_deck.pptx",
        description=(
            "Deal-review style mixed deck with KPI table, chart, risks, actions, "
            "and notes for real-world edit benchmarks."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "tables",
            "charts",
            "notes",
            "deals",
        ],
    ),
    FixtureSpec(
        id="workloads/large_real_world_deck",
        path="workloads/large_real_world_deck.pptx",
        description=(
            "Larger board-style deck with repeated section, table, chart, "
            "media, and notes patterns for real-world corpus benchmarks."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "large",
            "tables",
            "charts",
            "media",
            "notes",
        ],
    ),
    FixtureSpec(
        id="workloads/portfolio_ops_review_deck",
        path="workloads/portfolio_ops_review_deck.pptx",
        description=(
            "Portfolio operations review deck with KPI tables, charts, notes, "
            "comments, media, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "portfolio",
            "tables",
            "charts",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/management_reporting_deck",
        path="workloads/management_reporting_deck.pptx",
        description=(
            "Management reporting pack with dashboard tables, grouped shapes, "
            "grouped charts, notes, comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "management",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/finance_board_pack",
        path="workloads/finance_board_pack.pptx",
        description=(
            "Finance board pack with close status, covenant tracking, cash bridge, "
            "grouped KPI dashboard, notes, comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "finance",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/investor_update_pack",
        path="workloads/investor_update_pack.pptx",
        description=(
            "Investor update pack with cohort metrics, runway planning, grouped "
            "milestones, notes, comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "investor",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/qoe_diligence_pack",
        path="workloads/qoe_diligence_pack.pptx",
        description=(
            "Quality-of-earnings diligence pack with EBITDA adjustments, revenue "
            "quality, working-capital scenarios, grouped findings, notes, comments, "
            "and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "qoe",
            "deals",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/customer_success_review_pack",
        path="workloads/customer_success_review_pack.pptx",
        description=(
            "Customer success quarterly review pack with renewal forecast, "
            "adoption metrics, account risks, grouped action tiles, notes, "
            "comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "customer-success",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/security_compliance_review_pack",
        path="workloads/security_compliance_review_pack.pptx",
        description=(
            "Security and compliance review pack with control readiness, "
            "vendor risk, remediation actions, notes, comments, and embedded "
            "side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "security",
            "compliance",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/revenue_ops_forecast_pack",
        path="workloads/revenue_ops_forecast_pack.pptx",
        description=(
            "Revenue operations forecast pack with pipeline coverage, commit "
            "quality, forecast risk, grouped owner actions, notes, comments, "
            "and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "revenue-ops",
            "forecasting",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/product_launch_readiness_pack",
        path="workloads/product_launch_readiness_pack.pptx",
        description=(
            "Product launch readiness pack with milestone tracking, demand "
            "signals, launch risks, grouped owner actions, notes, comments, "
            "and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "product",
            "launch",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/enterprise_implementation_pack",
        path="workloads/enterprise_implementation_pack.pptx",
        description=(
            "Enterprise implementation pack with data migration, integration "
            "workplan, go-live risks, grouped owner actions, notes, comments, "
            "and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "implementation",
            "enterprise",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/procurement_vendor_risk_pack",
        path="workloads/procurement_vendor_risk_pack.pptx",
        description=(
            "Procurement vendor risk pack with supplier exposure, contract "
            "renewals, spend concentration, grouped owner actions, notes, "
            "comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "procurement",
            "vendor-risk",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/post_merger_integration_pack",
        path="workloads/post_merger_integration_pack.pptx",
        description=(
            "Post-merger integration pack with Day 1 readiness, synergy "
            "tracking, systems cutover, grouped owner actions, notes, "
            "comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "post-merger",
            "integration",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="workloads/earnings_board_appendix_pack",
        path="workloads/earnings_board_appendix_pack.pptx",
        description=(
            "Earnings board appendix pack with KPI scorecard, guidance "
            "bridge, segment risk table, grouped disclosure actions, notes, "
            "comments, and embedded side parts."
        ),
        tags=[
            "P1",
            "benchmark",
            "mixed",
            "real-world",
            "earnings",
            "board",
            "tables",
            "charts",
            "groups",
            "media",
            "notes",
            "comments",
            "ole",
        ],
    ),
    FixtureSpec(
        id="shapes/grouped_shapes",
        path="shapes/grouped_shapes.pptx",
        description="Grouped shape with inherited child transform coordinates.",
        tags=["P1", "shapes", "groups"],
    ),
    FixtureSpec(
        id="notes/speaker_notes",
        path="notes/speaker_notes.pptx",
        description="Slide text plus speaker notes relationship.",
        tags=["P1", "notes"],
    ),
    FixtureSpec(
        id="side_parts/legacy_comments",
        path="side_parts/legacy_comments.pptx",
        description="Slide with legacy comment and comment-author parts.",
        tags=["P2", "comments", "relationships"],
    ),
    FixtureSpec(
        id="media/png_picture",
        path="media/png_picture.pptx",
        description="Picture shape with an image relationship.",
        tags=["P0", "media", "relationships"],
    ),
    FixtureSpec(
        id="media/image_formats",
        path="media/image_formats.pptx",
        description="Picture shapes covering JPEG-family, BMP, and TIFF image parts.",
        tags=["P1", "media", "relationships", "image-formats"],
    ),
    FixtureSpec(
        id="charts/bar_chart",
        path="charts/bar_chart.pptx",
        description="Bar chart with chart XML and embedded workbook parts.",
        tags=["P1", "charts", "relationships", "embeddings"],
    ),
    FixtureSpec(
        id="charts/styled_bar_chart",
        path="charts/styled_bar_chart.pptx",
        description="Bar chart with chart style and color style side parts beside the embedded workbook.",
        tags=["P1", "charts", "relationships", "embeddings", "side-parts"],
    ),
    FixtureSpec(
        id="charts/multi_series_chart",
        path="charts/multi_series_chart.pptx",
        description="Clustered column chart with two category series and an embedded workbook.",
        tags=["P1", "charts", "relationships", "embeddings", "multi-series"],
    ),
    FixtureSpec(
        id="charts/pie_chart",
        path="charts/pie_chart.pptx",
        description="Pie chart with category data and an embedded workbook.",
        tags=["P1", "charts", "relationships", "embeddings", "pie"],
    ),
    FixtureSpec(
        id="charts/xy_scatter_chart",
        path="charts/xy_scatter_chart.pptx",
        description="XY scatter chart with x/y numeric data and an embedded workbook.",
        tags=["P1", "charts", "relationships", "embeddings", "xy"],
    ),
    FixtureSpec(
        id="charts/bubble_chart",
        path="charts/bubble_chart.pptx",
        description="Bubble chart with x/y/size numeric data and an embedded workbook.",
        tags=["P1", "charts", "relationships", "embeddings", "bubble"],
    ),
    FixtureSpec(
        id="package/ole_object",
        path="package/ole_object.pptx",
        description="Slide-level OLE object relationship with an embedded binary package.",
        tags=["P1", "ole", "embeddings", "relationships"],
    ),
    FixtureSpec(
        id="effects/simple_transition",
        path="effects/simple_transition.pptx",
        description="Slide with a minimal transition element.",
        tags=["P2", "effects", "transitions"],
    ),
    FixtureSpec(
        id="effects/simple_timing",
        path="effects/simple_timing.pptx",
        description="Slide with a minimal animation timing tree.",
        tags=["P2", "effects", "animations"],
    ),
    FixtureSpec(
        id="package/macro_preservation",
        path="package/macro_preservation.pptm",
        description="Macro-enabled package marker with vbaProject.bin.",
        tags=["P0", "pptm", "macros"],
    ),
)
