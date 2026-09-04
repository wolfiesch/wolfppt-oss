"""Text and document batches for the full drop-in benchmark profile."""

from __future__ import annotations

from .benchmark_profile_models import BenchmarkProfileBatch


def _adapter_pair(operation: str) -> tuple[str, str]:
    return (f"python-pptx-{operation}", f"wolfppt-facade-{operation}")


def build_dropin_full_text_batches(
    mixed_real_world_fixtures: tuple[str, ...],
) -> tuple[BenchmarkProfileBatch, ...]:
    MIXED_REAL_WORLD_FIXTURES = mixed_real_world_fixtures
    return (
        BenchmarkProfileBatch(
            name="dropin-basic-edit",
            description=(
                "Basic text and table-cell edits through equivalent public API calls, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-edit"),
            fixture_ids=(
                "text_basic/title_body_bullets",
                "tables/simple_table",
                *MIXED_REAL_WORLD_FIXTURES,
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-file-like-edit",
            description=(
                "Basic text edit through file-like input and output streams, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-file-like-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-text-frame",
            description=(
                "Table-cell text-frame, margin, and vertical-anchor edits, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-text-frame-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-text-frame-flow",
            description=(
                "Table-cell paragraph, word-wrap, and auto-size edits, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-text-frame-flow-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-paragraph-runs",
            description=(
                "Table-cell paragraph run text and append edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-paragraph-runs-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-paragraph-line-break",
            description=(
                "Table-cell paragraph line-break insertion, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-paragraph-line-break-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-run-font",
            description=(
                "Table-cell paragraph run font formatting edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-run-font-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-run-hyperlink",
            description=(
                "Table-cell paragraph run hyperlink edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-run-hyperlink-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-paragraph-font",
            description=(
                "Table-cell paragraph default-font formatting edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-paragraph-font-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-fill",
            description=(
                "Table-cell solid, gradient, and background fill edits, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-cell-fill-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-cell-merge",
            description="Table-cell merge edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-table-cell-merge-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-dimensions",
            description=(
                "Table row-height and column-width edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-table-dimensions-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-style-flags",
            description="Table style flag edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-table-style-flags-edit"),
            fixture_ids=("tables/simple_table", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-multi-edit",
            description="Multi-edit workloads for text, table, and dense table fixtures.",
            adapter_names=_adapter_pair("dropin-multi-edit"),
            fixture_ids=(
                "text_basic/title_body_bullets",
                "tables/simple_table",
                "workloads/multi_edit_table",
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-mixed-real-world-edit",
            description="Mixed edit across a board-style deck with notes and chart data.",
            adapter_names=_adapter_pair("dropin-mixed-workload-edit"),
            fixture_ids=MIXED_REAL_WORLD_FIXTURES,
        ),
        BenchmarkProfileBatch(
            name="dropin-slide-name",
            description=(
                "Slide name metadata edit isolated to the target slide part, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-slide-name-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-slide-size",
            description=(
                "Presentation slide-size edit isolated to the presentation part, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-slide-size-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-slide-layout-remove",
            description="Remove an unused slide layout while preserving slide layout bindings.",
            adapter_names=_adapter_pair("dropin-slide-layout-remove"),
            fixture_ids=("slides/two_slide_text",),
        ),
        BenchmarkProfileBatch(
            name="dropin-slide-background",
            description=(
                "Slide background solid-fill edits isolated to the target slide part, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-slide-background-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-template-background",
            description=(
                "Slide layout and master background solid-fill edits isolated to "
                "template parts, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-template-background-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-core-properties",
            description=(
                "Presentation document metadata edit isolated to the core properties part, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-core-properties-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-text",
            description=(
                "Speaker-notes text edit isolated to the notes slide part, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-text-edit"),
            fixture_ids=("notes/speaker_notes", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-text-frame-flow",
            description=(
                "Speaker-notes text-frame margins, wrap, anchor, and auto-size edits "
                "isolated to the notes slide part, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-text-frame-flow-edit"),
            fixture_ids=("notes/speaker_notes", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-background",
            description=(
                "Speaker-notes background fill edits isolated to the notes slide part, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-background-edit"),
            fixture_ids=("notes/speaker_notes", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-hyperlink",
            description=(
                "Speaker-notes placeholder and text-run hyperlink edits isolated to "
                "notes-slide relationships, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-hyperlink-edit"),
            fixture_ids=("notes/speaker_notes", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-create-notes-slide",
            description="Create a missing speaker-notes slide while preserving visible slide content.",
            adapter_names=_adapter_pair("dropin-create-notes-slide"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-paragraph-run",
            description=(
                "Speaker-notes paragraph layout, paragraph font, and run/font edits "
                "isolated to the notes slide part, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-paragraph-run-edit"),
            fixture_ids=("notes/speaker_notes", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-placeholder-clone",
            description=(
                "Notes placeholder clone edits isolated to the notes slide part, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-placeholder-clone"),
            fixture_ids=("notes/speaker_notes", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-formatting",
            description="Run-formatting workloads for small, dense, and grouped text fixtures.",
            adapter_names=_adapter_pair("dropin-formatting-edit"),
            fixture_ids=(
                "text_basic/title_body_bullets",
                "workloads/multi_format_runs",
                "shapes/grouped_shapes",
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-font-language",
            description="Run language metadata edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-font-language-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-font-fill",
            description="Run font fill edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-font-fill-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-run-formatting",
            description=(
                "Append and format a run in an existing paragraph, including "
                "grouped-shape children."
            ),
            adapter_names=_adapter_pair("dropin-add-run-formatting-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-paragraph-run-formatting",
            description="Append a paragraph and formatted run, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-add-paragraph-run-formatting-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-replace-run-formatting",
            description=(
                "Replace run text and formatting together, including grouped-shape "
                "children."
            ),
            adapter_names=_adapter_pair("dropin-replace-run-formatting-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-paragraph-format",
            description="Paragraph alignment formatting, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-paragraph-format-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-paragraph-level",
            description="Paragraph list-level edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-paragraph-level-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-paragraph-spacing",
            description="Paragraph line and spacing edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-paragraph-spacing-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-paragraph-clear",
            description="Text-frame paragraph clearing, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-paragraph-clear-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-paragraph-line-break",
            description="Paragraph line-break insertion, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-paragraph-line-break-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-paragraph-font",
            description="Paragraph default font edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-paragraph-font-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-paragraph-format",
            description=(
                "Append a paragraph and set paragraph formatting, including "
                "grouped-shape children."
            ),
            adapter_names=_adapter_pair("dropin-add-paragraph-format-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
    )
