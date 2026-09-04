"""Drop-in smoke benchmark profile batches."""

from __future__ import annotations

from .benchmark_profile_models import BenchmarkProfileBatch


def _adapter_pair(operation: str) -> tuple[str, str]:
    return (f"python-pptx-{operation}", f"wolfppt-facade-{operation}")


def build_dropin_smoke_batches(
    mixed_real_world_fixtures: tuple[str, ...],
) -> tuple[BenchmarkProfileBatch, ...]:
    return (
        BenchmarkProfileBatch(
            name="dropin-text-edit",
            description="Equivalent paragraph edit through python-pptx and the WolfPPT facade.",
            adapter_names=_adapter_pair("dropin-edit"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-file-like-edit",
            description="Equivalent paragraph edit through file-like input and output streams.",
            adapter_names=_adapter_pair("dropin-file-like-edit"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-table-edit",
            description="Equivalent table-cell edit through python-pptx and the WolfPPT facade.",
            adapter_names=_adapter_pair("dropin-table-cell-text-frame-edit"),
            fixture_ids=("tables/simple_table", *mixed_real_world_fixtures),
        ),
        BenchmarkProfileBatch(
            name="dropin-batched-table-edit",
            description="Dense repeated table-cell edits for batched mutation performance.",
            adapter_names=_adapter_pair("dropin-multi-edit"),
            fixture_ids=("workloads/multi_edit_table",),
        ),
        BenchmarkProfileBatch(
            name="dropin-mixed-real-world-edit",
            description=(
                "Mixed real-world deck edit covering text, table, chart, workbook, and notes."
            ),
            adapter_names=_adapter_pair("dropin-mixed-workload-edit"),
            fixture_ids=mixed_real_world_fixtures,
        ),
        BenchmarkProfileBatch(
            name="dropin-notes-text",
            description=(
                "Speaker-notes text edit isolated to the notes slide part, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-notes-text-edit"),
            fixture_ids=("notes/speaker_notes", *mixed_real_world_fixtures),
        ),
        BenchmarkProfileBatch(
            name="dropin-rich-text-formatting",
            description="Dense run-formatting edits for rich text workloads.",
            adapter_names=_adapter_pair("dropin-formatting-edit"),
            fixture_ids=("workloads/multi_format_runs",),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-style",
            description=(
                "Shape fill and line formatting through the public Python-compatible API."
            ),
            adapter_names=_adapter_pair("dropin-shape-style-edit"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-picture-crop",
            description="Existing picture crop edits on a media-bearing deck.",
            adapter_names=_adapter_pair("dropin-picture-crop-edit"),
            fixture_ids=("media/png_picture", "workloads/mixed_real_world_deck"),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-read",
            description="Chart metadata inspection through the public Python-compatible API.",
            adapter_names=_adapter_pair("dropin-chart-read"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-data",
            description=(
                "Simple CategoryChartData replacement for chart XML and workbook payloads."
            ),
            adapter_names=_adapter_pair("dropin-chart-data-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-sparse-category-data",
            description="Sparse CategoryChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-sparse-category-data-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-hierarchical-category-data",
            description="Hierarchical CategoryChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-hierarchical-category-data-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-plot-property",
            description="Chart plot spacing and vary-by-category edits.",
            adapter_names=_adapter_pair("dropin-chart-plot-property-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-data-label",
            description="Chart plot data-label edits.",
            adapter_names=_adapter_pair("dropin-chart-data-label-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-data-label-remove",
            description="Chart plot data-label removal.",
            adapter_names=_adapter_pair("dropin-chart-data-label-remove"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-point-data-label",
            description="Chart point data-label edits.",
            adapter_names=_adapter_pair("dropin-chart-point-data-label-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-style",
            description="Chart style edits.",
            adapter_names=_adapter_pair("dropin-chart-style-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-format",
            description=(
                "Series, point, and marker style/formatting through the public "
                "Python-compatible API."
            ),
            adapter_names=_adapter_pair("dropin-chart-format-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-picture",
            description=(
                "Picture insertion with explicit bounds through the public "
                "Python-compatible API."
            ),
            adapter_names=_adapter_pair("dropin-add-picture"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-picture-file-like",
            description="Picture insertion from a file-like object.",
            adapter_names=_adapter_pair("dropin-add-picture-file-like"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-replace-picture",
            description="Existing picture payload replacement with relationship preservation.",
            adapter_names=_adapter_pair("dropin-replace-picture"),
            fixture_ids=("media/png_picture",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-movie-file-like",
            description="Movie insertion from file-like movie and poster inputs.",
            adapter_names=_adapter_pair("dropin-add-movie-file-like"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-ole-object-file-like",
            description="OLE object insertion from file-like object and icon inputs.",
            adapter_names=_adapter_pair("dropin-add-ole-object-file-like"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-textbox",
            description="Text box insertion through the public Python-compatible API.",
            adapter_names=_adapter_pair("dropin-add-textbox"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-table",
            description="Table insertion through the public Python-compatible API.",
            adapter_names=_adapter_pair("dropin-add-table"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-slide",
            description="Slide insertion through the public Python-compatible API.",
            adapter_names=_adapter_pair("dropin-add-slide"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
    )
