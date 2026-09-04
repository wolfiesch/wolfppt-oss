"""Full drop-in benchmark batch definitions."""

from __future__ import annotations

from .benchmark_profile_dropin_full_text import build_dropin_full_text_batches
from .benchmark_profile_models import BenchmarkProfileBatch


def _adapter_pair(operation: str) -> tuple[str, str]:
    return (f"python-pptx-{operation}", f"wolfppt-facade-{operation}")


def build_dropin_full_batches(
    mixed_real_world_fixtures: tuple[str, ...],
    grouped_real_world_fixtures: tuple[str, ...],
) -> tuple[BenchmarkProfileBatch, ...]:
    MIXED_REAL_WORLD_FIXTURES = mixed_real_world_fixtures
    GROUPED_REAL_WORLD_FIXTURES = grouped_real_world_fixtures

    DROPIN_FULL_BATCHES = (
        *build_dropin_full_text_batches(MIXED_REAL_WORLD_FIXTURES),
        BenchmarkProfileBatch(
            name="dropin-add-picture",
            description="Add a picture with explicit dimensions, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-picture"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-picture",
            description="Add a picture inside an existing grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-group-picture"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-picture",
            description="Add a picture inside a nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-picture"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-picture",
            description="Add a picture inside a deeper nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-picture"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-picture-auto-size",
            description=(
                "Add a picture with inferred image dimensions, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-picture-auto-size"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-picture-file-like",
            description=(
                "Add a picture from a file-like input, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-picture-file-like"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-picture-image-inspection",
            description="Read existing picture image blob and metadata without mutating the package.",
            adapter_names=_adapter_pair("dropin-picture-image-inspection"),
            fixture_ids=(
                "media/png_picture",
                "workloads/mixed_real_world_deck",
                "workloads/customer_success_review_pack",
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-replace-picture",
            description=(
                "Replace an existing picture payload while preserving placement "
                "and relationships, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-replace-picture"),
            fixture_ids=(
                "media/png_picture",
                "workloads/mixed_real_world_deck",
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-movie",
            description=(
                "Add a movie shape with poster media, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-movie"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-movie-file-like",
            description=(
                "Add a movie shape from file-like movie and poster inputs, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-movie-file-like"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-ole-object",
            description=(
                "Add an embedded OLE object with icon media, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-ole-object"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-ole-object",
            description="Add an embedded OLE object inside an existing grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-group-ole-object"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-ole-object",
            description="Add an embedded OLE object inside a nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-ole-object"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-ole-object",
            description="Add an embedded OLE object inside a deeper nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-ole-object"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-ole-object-file-like",
            description=(
                "Add an embedded OLE object from file-like object and icon inputs, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-ole-object-file-like"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-shape",
            description="Add a preset shape, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-shape"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-textbox",
            description="Add a text box, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-textbox"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-table",
            description="Add a table and edit a cell, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-table"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-slide",
            description=(
                "Add a blank slide from an existing layout, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-slide"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-title-slide",
            description=(
                "Add a title/content slide and edit materialized placeholders, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-title-slide"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-adjustment",
            description=(
                "Add a rounded rectangle and set its adjustment handle, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-shape-adjustment-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-geometry",
            description="Move and resize an existing shape, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-shape-geometry-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-child-geometry",
            description=(
                "Move and resize an existing direct child of a grouped shape, "
                "including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-group-child-geometry-edit"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-child-adjustment",
            description=(
                "Add and adjust a rounded rectangle inside a grouped shape, "
                "including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-group-child-adjustment-edit"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-line-element",
            description=(
                "Create a low-level shape line XML element, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-shape-line-element-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-shape",
            description="Add an empty group shape, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-group-shape"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-existing-shapes",
            description=(
                "Group existing slide shapes with explicit argument order, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-group-existing-shapes"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-shape",
            description="Add an empty nested group shape inside an existing grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-shape"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-shape",
            description="Add an empty group shape inside an existing nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-shape"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-textbox",
            description="Add a text box inside a deeper nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-textbox"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-auto-shape",
            description="Add an auto-shape inside a deeper nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-auto-shape"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-chart",
            description="Add a category chart inside a deeper nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-chart"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-deeper-nested-group-connector",
            description="Add a connector inside a deeper nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-deeper-nested-group-connector"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-existing-children",
            description="Group existing direct children inside an existing grouped shape.",
            adapter_names=_adapter_pair("dropin-group-existing-children"),
            fixture_ids=("workloads/customer_success_review_pack",),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-existing-nested-children",
            description=(
                "Group existing direct children inside a nested grouped shape, "
                "including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-group-existing-nested-children"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-existing-deeper-nested-children",
            description=(
                "Group existing direct children inside a deeper nested grouped "
                "shape, including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-group-existing-deeper-nested-children"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-auto-shape",
            description="Add an auto-shape inside a nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-auto-shape"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-chart",
            description="Add a category chart inside a nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-chart"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-connector",
            description="Add a connector inside a nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-connector"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-nested-group-textbox",
            description="Add a text box inside a nested grouped shape, including grouped real-world decks.",
            adapter_names=_adapter_pair("dropin-add-nested-group-textbox"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-textbox",
            description=(
                "Add a text box inside an existing grouped shape, including "
                "grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-group-textbox"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-auto-shape",
            description=(
                "Add an auto-shape inside an existing grouped shape, including "
                "grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-group-auto-shape"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-chart",
            description=(
                "Add a chart inside an existing grouped shape, including grouped "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-group-chart"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-group-connector",
            description=(
                "Add a connector inside an existing grouped shape, including "
                "grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-group-connector"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-build-freeform",
            description="Build a freeform custom-geometry shape, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-build-freeform"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-build-group-freeform",
            description=(
                "Build a freeform custom-geometry shape inside an existing grouped "
                "shape, including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-build-group-freeform"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-build-nested-group-freeform",
            description=(
                "Build a freeform custom-geometry shape inside a nested grouped "
                "shape, including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-build-nested-group-freeform"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-build-deeper-nested-group-freeform",
            description=(
                "Build a freeform custom-geometry shape inside a deeper nested "
                "grouped shape, including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-build-deeper-nested-group-freeform"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-clone-layout-placeholders",
            description="Clone editable layout placeholders onto a slide.",
            adapter_names=_adapter_pair("dropin-clone-layout-placeholders"),
            fixture_ids=("text_basic/title_body_bullets",),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-chart",
            description="Add a chart, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-hierarchical-chart",
            description=(
                "Add a three-level hierarchical category chart, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-hierarchical-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-bar-chart",
            description="Add a horizontal bar chart, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-bar-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-line-chart",
            description="Add a line chart with markers, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-line-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-pie-chart",
            description="Add a pie chart, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-pie-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-xy-scatter-chart",
            description="Add an XY scatter chart, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-xy-scatter-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-bubble-chart",
            description="Add a bubble chart, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-bubble-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-bubble-3d-chart",
            description="Add a 3D bubble chart, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-bubble-3d-chart"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-chart-template-family",
            description=(
                "Add every packaged category chart template in one deck, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-chart-template-family"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-xy-scatter-template-family",
            description=(
                "Add every packaged XY scatter chart template in one deck, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-add-xy-scatter-template-family"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-add-connector",
            description="Add a connector shape, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-add-connector"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-connector-connection",
            description=(
                "Attach connector begin/end points to newly added shapes, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-connector-connection-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-group-connector-connection",
            description=(
                "Attach grouped connector begin/end points to newly added grouped "
                "shapes, including grouped real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-group-connector-connection-edit"),
            fixture_ids=("shapes/grouped_shapes", *GROUPED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-existing-connector-connection",
            description=(
                "Attach connector begin/end points to existing deck shapes, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-existing-connector-connection-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-connector-line-style",
            description="Connector line formatting, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-connector-line-style-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-picture-crop",
            description="Existing picture crop edits, including a mixed real-world deck.",
            adapter_names=_adapter_pair("dropin-picture-crop-edit"),
            fixture_ids=("media/png_picture", "workloads/mixed_real_world_deck"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-style",
            description="Shape fill and line style edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-style-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-theme-color",
            description="Shape theme color and brightness edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-theme-color-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-shadow",
            description="Shape shadow inheritance edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-shadow-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-hyperlink",
            description="External shape hyperlink edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-hyperlink-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-target-slide",
            description="Internal target-slide hyperlink edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-shape-target-slide-edit"),
            fixture_ids=("slides/two_slide_text", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-target-new-slide",
            description=(
                "Internal hyperlinks to slides added in the same session, including "
                "mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-shape-target-new-slide-edit"),
            fixture_ids=("text_basic/title_body_bullets", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-text-run-hyperlink",
            description="External run hyperlink edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-text-run-hyperlink-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-fill-solid",
            description="Shape solid-fill edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-fill-solid-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-line-fill-background",
            description="Shape line background-fill edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-line-fill-background-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-patterned-fill",
            description="Shape patterned-fill edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-patterned-fill-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-gradient-fill",
            description="Shape gradient-fill edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-shape-gradient-fill-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-rotation",
            description="Shape rotation edits.",
            adapter_names=_adapter_pair("dropin-shape-rotation-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-shape-name",
            description="Shape name edits.",
            adapter_names=_adapter_pair("dropin-shape-name-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-text-frame-margin",
            description="Text-frame margin edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-text-frame-margin-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-text-frame-word-wrap",
            description="Text-frame word-wrap edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-text-frame-word-wrap-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-text-frame-vertical-anchor",
            description="Text-frame vertical-anchor edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-text-frame-vertical-anchor-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-text-frame-auto-size",
            description="Text-frame auto-size edits, including grouped-shape children.",
            adapter_names=_adapter_pair("dropin-text-frame-auto-size-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-text-frame-fit-text",
            description=(
                "Text-frame fit_text edits, including grouped-shape children, when a "
                "compatible font file is available."
            ),
            adapter_names=_adapter_pair("dropin-text-frame-fit-text-edit"),
            fixture_ids=("text_basic/title_body_bullets", "shapes/grouped_shapes"),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-read",
            description="Chart metadata inspection.",
            adapter_names=_adapter_pair("dropin-chart-read"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-title",
            description="Chart title edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-title-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-title-remove",
            description="Chart title removal, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-title-remove"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-legend",
            description="Chart legend edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-legend-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-axis-title",
            description="Chart axis-title edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-axis-title-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-axis-title-remove",
            description="Chart axis-title removal, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-axis-title-remove"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-title-text-frame",
            description=(
                "Chart and axis title text-frame paragraph and run formatting edits, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-title-text-frame-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-title-text-frame-flow",
            description=(
                "Chart and axis title text-frame margins, wrap, anchor, and auto-size "
                "edits, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-title-text-frame-flow-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-title-paragraph-format",
            description=(
                "Chart and axis title paragraph alignment, level, and spacing edits, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-title-paragraph-format-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-title-paragraph-font",
            description=(
                "Chart and axis title paragraph default-font edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-title-paragraph-font-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-axis-property",
            description="Chart axis property edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-axis-property-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-plot-property",
            description=(
                "Chart plot spacing and vary-by-category edits, including mixed "
                "real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-plot-property-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-data-label",
            description="Chart plot data-label edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-data-label-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-data-label-remove",
            description="Chart plot data-label removal, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-data-label-remove"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-point-data-label",
            description="Chart point data-label edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-point-data-label-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-style",
            description="Chart style edits, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-style-edit"),
            fixture_ids=("charts/bar_chart", *MIXED_REAL_WORLD_FIXTURES),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-format",
            description=(
                "Chart series, point, marker style, and marker formatting edits, "
                "including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-format-edit"),
            fixture_ids=(
                "charts/bar_chart",
                "charts/multi_series_chart",
                "charts/pie_chart",
                *MIXED_REAL_WORLD_FIXTURES,
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-data",
            description="Simple CategoryChartData replacement, including mixed real-world decks.",
            adapter_names=_adapter_pair("dropin-chart-data-edit"),
            fixture_ids=(
                "charts/bar_chart",
                "charts/multi_series_chart",
                "charts/pie_chart",
                *MIXED_REAL_WORLD_FIXTURES,
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-sparse-category-data",
            description=(
                "Sparse CategoryChartData replacement with mismatched category/value "
                "counts, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-sparse-category-data-edit"),
            fixture_ids=(
                "charts/bar_chart",
                "charts/multi_series_chart",
                *MIXED_REAL_WORLD_FIXTURES,
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-hierarchical-category-data",
            description=(
                "Hierarchical CategoryChartData replacement with multi-level category "
                "labels, including mixed real-world decks."
            ),
            adapter_names=_adapter_pair("dropin-chart-hierarchical-category-data-edit"),
            fixture_ids=(
                "charts/bar_chart",
                "charts/multi_series_chart",
                *MIXED_REAL_WORLD_FIXTURES,
            ),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-empty-category-data",
            description="Empty-series CategoryChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-empty-category-data-edit"),
            fixture_ids=("charts/bar_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-xy-data",
            description="Simple XyChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-xy-data-edit"),
            fixture_ids=("charts/xy_scatter_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-empty-xy-data",
            description="Empty-series XyChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-empty-xy-data-edit"),
            fixture_ids=("charts/xy_scatter_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-bubble-data",
            description="Simple BubbleChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-bubble-data-edit"),
            fixture_ids=("charts/bubble_chart",),
        ),
        BenchmarkProfileBatch(
            name="dropin-chart-empty-bubble-data",
            description="Empty-series BubbleChartData replacement.",
            adapter_names=_adapter_pair("dropin-chart-empty-bubble-data-edit"),
            fixture_ids=("charts/bubble_chart",),
        ),
    )
    return DROPIN_FULL_BATCHES
