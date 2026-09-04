"""WolfPPT compatibility spec - source of truth.

Editing protocol:

1. Change ``ENTRIES`` here or the category-specific entry modules it imports.
2. Run ``wolfppt-harness matrix`` to regenerate
   ``docs/compatibility/compatibility-matrix.md``.
3. Keep ``tests/parity/KNOWN_GAPS.md`` aligned with entries whose status is
   ``partial`` or ``not_yet``.

Status values:

* ``supported``    implemented or harness-covered for the current phase
* ``partial``      intentionally incomplete; documented caveats
* ``not_yet``      planned but not implemented
* ``out_of_scope`` explicitly outside the current roadmap
"""

from __future__ import annotations

from _compat_python_api_entries import PYTHON_API_ENTRIES
from _compat_spec_types import CapabilityWorkflow, Category, Entry

STATUS_DISPLAY: dict[str, str] = {
    "supported": "[+] Supported",
    "partial": "[~] Partial",
    "not_yet": "[-] Not Yet",
    "out_of_scope": "[x] Out of Scope",
}


CATEGORIES: list[Category] = [
    {"id": "package", "title": "OPC package + preservation"},
    {"id": "presentation", "title": "Presentation + slides"},
    {"id": "shapes", "title": "Shapes + DrawingML"},
    {"id": "text", "title": "Text"},
    {"id": "tables", "title": "Tables"},
    {"id": "charts", "title": "Charts"},
    {"id": "media", "title": "Images + media"},
    {"id": "side_parts", "title": "Notes + comments + review parts"},
    {"id": "effects", "title": "Transitions + animations"},
    {"id": "python_api", "title": "Python-compatible API"},
    {"id": "rendering", "title": "Rendering oracles"},
]


ENTRIES: list[Entry] = [
    {
        "id": "package.open.basic",
        "category": "package",
        "capability": "Open a .pptx package and enumerate parts",
        "priority": "P0",
        "status": "supported",
        "oracle": "zip package manifest",
        "notes": "Harness extractor records every package part.",
    },
    {
        "id": "package.relationships",
        "category": "package",
        "capability": "Read package and part relationships",
        "priority": "P0",
        "status": "supported",
        "oracle": "relationship manifest",
        "notes": "Harness extractor captures source, relationship id, type, target, and target mode.",
    },
    {
        "id": "package.roundtrip_parts",
        "category": "package",
        "capability": "Round-trip packages without part payload loss",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic diff + package diff",
        "notes": "Rust CLI and native round-trip lanes compare every part payload across the fixture corpus.",
    },
    {
        "id": "package.mixed_workload_preservation",
        "category": "package",
        "capability": "Preserve mixed real-world-style decks with text, media, tables, charts, and notes",
        "priority": "P1",
        "status": "supported",
        "oracle": "semantic diff + package diff + benchmark profile",
        "notes": "The checked-in mixed workload deck combines five slides with text, picture media, a table, a chart with embedded workbook, and speaker notes for core benchmark and corpus lanes.",
    },
    {
        "id": "package.macro_preservation",
        "category": "package",
        "capability": "Detect and preserve macro-enabled .pptm packages",
        "priority": "P0",
        "status": "supported",
        "oracle": "package manifest + content types",
        "notes": "Rust CLI and native round-trip lanes preserve the checked-in .pptm VBA package fixture with clean package diff.",
    },
    {
        "id": "package.ole_preservation",
        "category": "package",
        "capability": "Detect and preserve slide-level OLE object relationships and embedded binaries",
        "priority": "P1",
        "status": "supported",
        "oracle": "relationship manifest + package diff",
        "notes": "Checked-in OLE fixture carries a slide-level oleObject relationship plus an embedded binary package; Rust CLI/native round-trip lanes preserve both with clean package diffs.",
    },
    {
        "id": "presentation.slide_order",
        "category": "presentation",
        "capability": "Read slide order and slide part names",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic extractor",
        "notes": "Fallback natural sort is used when relationship ordering is incomplete.",
    },
    {
        "id": "presentation.slide_add_from_layout",
        "category": "presentation",
        "capability": "Add a slide from an existing layout",
        "priority": "P0",
        "status": "supported",
        "oracle": "PowerPoint repair check + package diff",
        "notes": "Rust CLI/native slide append can use the first slide's layout or a selected layout index, materializes editable placeholders without layout prompt text, and validates through Open XML SDK.",
    },
    {
        "id": "presentation.slide_reorder",
        "category": "presentation",
        "capability": "Reorder existing slides without changing their parts or relationships",
        "priority": "P0",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": "SlideCollection.move reorders p:sldId entries in the native edit batch while preserving slide ids, relationship ids, slide part names, and every non-presentation part payload.",
    },
    {
        "id": "presentation.slide_duplicate",
        "category": "presentation",
        "capability": "Duplicate an existing slide while preserving its owned relationships",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic extractor + package diff",
        "notes": "SlideCollection.duplicate appends a new slide part copied verbatim from the source, shares the source layout and image targets, and fails explicitly on relationship types without a copy policy.",
    },
    {
        "id": "presentation.slide_duplicate_chart",
        "category": "presentation",
        "capability": "Duplicate a slide that owns chart relationships including embedded workbooks",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic extractor + package diff + Open XML validation",
        "notes": "Chart parts, colors/style parts, and embedded xlsx workbooks are deep-copied to new part names with content types registered; the duplicated slide's relationship keeps the source r:id, so series edits on the duplicate never alias the source chart.",
    },
    {
        "id": "presentation.slide_duplicate_notes",
        "category": "presentation",
        "capability": "Duplicate a slide together with its notes slide",
        "priority": "P1",
        "status": "supported",
        "oracle": "semantic extractor + package diff",
        "notes": "The notesSlide part and its relationships are copied to a new part name; the copied notes slide's back-reference to the source slide is rewritten to the duplicate, and the notes master relationship stays shared.",
    },
    {
        "id": "presentation.slide_duplicate_ole",
        "category": "presentation",
        "capability": "Duplicate a slide that owns OLE object relationships and embedded binaries",
        "priority": "P1",
        "status": "supported",
        "oracle": "relationship manifest + package diff",
        "notes": "OLE relationship targets and their embedded binary packages are copied to new part names with the bin default content type registered, so the duplicate owns an independent embedded object.",
    },
    {
        "id": "presentation.slide_duplicate_comments",
        "category": "presentation",
        "capability": "Duplicate a slide that owns slide comments",
        "priority": "P2",
        "status": "supported",
        "oracle": "relationship manifest + package diff",
        "notes": "The slide-scoped comments part is copied to a new part name with its content type override registered; the presentation-scoped comment author part stays shared.",
    },
    {
        "id": "presentation.slide_delete",
        "category": "presentation",
        "capability": "Delete an existing slide and clean up owned package parts and relationships",
        "priority": "P0",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": (
            "Slide deletion removes the slide from presentation.xml and presentation.xml.rels, "
            "deletes the unreferenced slide part and slide relationships, and updates [Content_Types].xml."
        ),
    },
    {
        "id": "presentation.pending_slide_delete",
        "category": "presentation",
        "capability": "Delete pending newly-added or duplicated slides before save",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": (
            "SlideCollection.remove and del prs.slides[i] delete pending slides added via "
            "add_slide() or duplicate() before save, matching by creation identity token, "
            "unwinding slide_creations and slide_order queues, rebasing survivor indices, and "
            "ensuring zero package delta relative to an untouched save. "
            "Pending shape cancellation remains unsupported."
        ),
    },
    {
        "id": "presentation.slide_slice_delete",
        "category": "presentation",
        "capability": "Delete slides by slice across persisted and pending slides",
        "priority": "P2",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": (
            "wolfppt API completion beyond python-pptx (python-pptx raises TypeError on slice deletion); "
            "composes with persisted + pending removal via sequential remove(); all-slides deletion rejected "
            "before mutation; empty slice no-op; step + negative bounds supported."
        ),
    },
    {
        "id": "presentation.slide_duplicate_copy_policies",
        "category": "presentation",
        "capability": "Duplicate slides owning unhandled relationship types via explicit copy policies",
        "priority": "P1",
        "status": "supported",
        "oracle": "relationship manifest + package diff + Open XML validation",
        "notes": (
            "audio, video, and media relationships share immutable media assets under ppt/media/ "
            "with unchanged rIds and targets, covered by [Content_Types].xml Defaults; comments relationships "
            "are copied to a new owned ppt/comments/commentN.xml with Content-Type Override and remapped "
            "rel target while comment authors remain shared presentation-level assets; external and unhandled "
            "relationship types continue to fail fast with an explicit copy-policy error."
        ),
    },
    {
        "id": "presentation.slide_duplicate_external_targets",
        "category": "presentation",
        "capability": "Duplicate slides owning external-target relationships (e.g. hyperlinks)",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx behavior probe + semantic diff + package diff",
        "notes": (
            "external-target relationships (e.g. hyperlinks) pass through verbatim into the duplicate "
            "slide's rels — same rId, Type, Target, TargetMode; no package parts are created; unknown "
            "internal types still rejected; python-pptx element-level equivalence tests are the evidence."
        ),
    },
    {
        "id": "tables.row_column_mutation",
        "category": "tables",
        "capability": "Insert and delete table rows and columns",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx behavior probe + semantic diff + package diff",
        "notes": "table.rows and table.columns collections expose insert(index) and remove(index) through the native edit batch; inserted rows and columns carry empty cell text, merged-cell and sole-row/column deletions are rejected explicitly, and only the owning slide part changes.",
    },
    {
        "id": "shapes.iterate",
        "category": "shapes",
        "capability": "Iterate slide shape tree with ids, names, z-order, and transforms",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic extractor",
        "notes": "Python semantic oracles and Rust typed summaries expose the supported shape tree, including ids, names, kinds, text, tables, relationships, transforms, and children.",
    },
    {
        "id": "shapes.delete",
        "category": "shapes",
        "capability": "Delete an existing shape without disturbing unrelated slide content",
        "priority": "P0",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": "ShapeCollection.remove deletes one top-level shape in the native edit batch, updates live collections, and removes relationships owned only by that shape while preserving related package parts.",
    },
    {
        "id": "shapes.group_child_delete",
        "category": "shapes",
        "capability": "Delete a child shape inside a group shape without disturbing unrelated content",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": (
            "Group child deletion removes the shape element from the group shape tree "
            "while preserving sibling shapes and group transform bounds."
        ),
    },
    {
        "id": "shapes.nested_group_child_delete",
        "category": "shapes",
        "capability": "Delete a child shape inside a nested group shape without disturbing unrelated content",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx behavior probe + package diff + Open XML validation",
        "notes": (
            "GroupShapeCollection.remove supports any-depth child deletion and whole sub-group "
            "subtree removal with ownership-closure part cleanup, while retaining rejection of "
            "unsaved or pending targets."
        ),
    },
    {
        "id": "shapes.grouped",
        "category": "shapes",
        "capability": "Read grouped shapes and nested transforms",
        "priority": "P1",
        "status": "supported",
        "oracle": "semantic extractor + Rust typed summary + render diff",
        "notes": "Python semantic oracles and Rust typed summaries model group nodes, child shapes, local transforms, and inherited effective transforms with a checked-in grouped-shape fixture.",
    },
    {
        "id": "shapes.style_color",
        "category": "shapes",
        "capability": "Set solid, gradient, line RGB color, and line width on shape elements",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx parity + package diff + Open XML validation",
        "notes": "The Python facade supports shape.fill.solid(), shape.fill.gradient(), gradient angle/stop edits, shape.fill.fore_color.rgb, shape.line.color.rgb, and shape.line.width for existing shape elements, including direct children of top-level group shapes, while only changing the target slide XML.",
    },
    {
        "id": "text.extract",
        "category": "text",
        "capability": "Extract text from shapes, paragraphs, and runs",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic extractor",
    },
    {
        "id": "text.replace_preserve_formatting",
        "category": "text",
        "capability": "Replace text while preserving shape and run formatting",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic diff + package diff",
        "notes": "Exact-text, selected-run, and selected-paragraph operations preserve surrounding XML; shape-level text setting rewrites the target text body into newline-separated paragraphs while preserving unrelated package parts.",
    },
    {
        "id": "tables.extract",
        "category": "tables",
        "capability": "Extract table rows, cells, merges, and cell text",
        "priority": "P1",
        "status": "supported",
        "oracle": "semantic extractor",
    },
    {
        "id": "tables.write",
        "category": "tables",
        "capability": "Create and edit basic tables",
        "priority": "P1",
        "status": "supported",
        "oracle": "semantic diff + render diff",
        "notes": "Rust CLI/native table operations can add basic empty tables with explicit EMU bounds and replace existing table cell text by slide/table/row/column index while preserving unrelated package parts.",
    },
    {
        "id": "charts.detect",
        "category": "charts",
        "capability": "Detect charts and chart relationships",
        "priority": "P1",
        "status": "supported",
        "oracle": "relationship manifest",
        "notes": "Python and Rust semantic summaries bucket slide chart relationships.",
    },
    {
        "id": "charts.data_roundtrip",
        "category": "charts",
        "capability": "Preserve chart XML and embedded workbook data",
        "priority": "P1",
        "status": "supported",
        "oracle": "package diff + semantic extractor",
        "notes": "Checked-in chart fixture includes chart XML plus embedded workbook; Rust CLI/native round-trip lanes preserve both with clean package diff.",
    },
    {
        "id": "charts.data_edit",
        "category": "charts",
        "capability": "Replace simple category, XY, and bubble chart data",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx parity + package diff + Open XML validation",
        "notes": "The Python facade supports python-pptx-style CategoryChartData, XyChartData, and BubbleChartData replacement, including adding or removing series, date-category data, sparse/mismatched and hierarchical category chart data, and uneven XY/bubble point counts by cloning/removing chart series XML and updating the embedded workbook while only changing those two package parts. No-series replacement mirrors python-pptx parity, but zero-plot outputs can fail strict Open XML validation, so claim-grade benchmark lanes use Open XML-valid empty-series and sparse cases.",
    },
    {
        "id": "media.images",
        "category": "media",
        "capability": "Read image relationships and picture shapes",
        "priority": "P0",
        "status": "supported",
        "oracle": "semantic extractor",
        "notes": "Python and Rust semantic summaries bucket slide image relationships.",
    },
    {
        "id": "media.add_replace_image",
        "category": "media",
        "capability": "Add or replace pictures while preserving relationships",
        "priority": "P0",
        "status": "supported",
        "oracle": "package diff + PowerPoint repair check",
        "notes": "Rust CLI/native image operations can replace existing image payloads globally or by slide index and add new PNG/JPEG/GIF/BMP/TIFF picture shapes with explicit EMU bounds, python-pptx-style JPEG/TIFF part-extension canonicalization, and unrelated package-part preservation.",
    },
    {
        "id": "media.add_movie",
        "category": "media",
        "capability": "Add movie media parts with poster frames and slide relationships",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx parity probe + package diff + Open XML validation",
        "notes": "The native writer adds a video media part, PNG/JPEG/GIF/BMP/TIFF poster image part, media/video/image slide relationships, content-type defaults, movie picture XML, and timing markers while preserving unrelated package parts.",
    },
    {
        "id": "media.add_ole_object",
        "category": "media",
        "capability": "Add embedded OLE object parts with icon images and slide relationships",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx parity probe + package diff + Open XML validation",
        "notes": "The native writer adds an OLE embedding part, PNG/JPEG/GIF/BMP/TIFF icon image part, oleObject/image slide relationships, an OLE content-type override, and graphic-frame XML while preserving unrelated package parts.",
    },
    {
        "id": "side_parts.notes",
        "category": "side_parts",
        "capability": "Extract, create, and edit speaker notes text, text-run and placeholder click hyperlinks, paragraph/run font formatting, paragraph layout, and notes text-frame properties",
        "priority": "P1",
        "status": "supported",
        "oracle": "python-pptx parity + package diff",
        "notes": "The Python facade reads speaker notes, creates missing notes-slide package parts on first notes access, and can edit notes text-run hyperlinks, placeholder click hyperlinks, notes text, paragraph/run content, paragraph and run font formatting, paragraph alignment, level, spacing, placeholder clones, margins, word-wrap, vertical anchor, and auto-size while preserving visible slide content.",
    },
    {
        "id": "side_parts.comments",
        "category": "side_parts",
        "capability": "Preserve comments and review metadata",
        "priority": "P2",
        "status": "supported",
        "oracle": "package diff",
        "notes": "Checked-in legacy comment fixture validates cleanly; Python and Rust semantic summaries bucket slide comment relationships and Rust round-trip lanes preserve comment/comment-author parts with clean package diffs.",
    },
    {
        "id": "effects.transitions",
        "category": "effects",
        "capability": "Preserve slide transitions",
        "priority": "P2",
        "status": "supported",
        "oracle": "package diff",
        "notes": "Checked-in transition fixture validates cleanly; Python and Rust semantic summaries detect transition XML and Rust round-trip lanes preserve it with clean package diffs.",
    },
    {
        "id": "effects.animations",
        "category": "effects",
        "capability": "Preserve animation timing trees",
        "priority": "P2",
        "status": "supported",
        "oracle": "package diff",
        "notes": "Checked-in timing fixture validates cleanly; Python and Rust semantic summaries detect timing XML and Rust round-trip lanes preserve it with clean package diffs.",
    },
    *PYTHON_API_ENTRIES,
    {
        "id": "rendering.powerpoint_export",
        "category": "rendering",
        "capability": "Render through Microsoft PowerPoint as gold oracle",
        "priority": "P2",
        "status": "supported",
        "oracle": "PowerPoint PDF export + PNG conversion",
        "notes": "Optional corpus lane stages decks in Office TemporaryItems, disables macros for automation opens, exports PDF through Microsoft PowerPoint, and converts pages to PNGs for the gold visual oracle.",
    },
    {
        "id": "rendering.libreoffice_smoke",
        "category": "rendering",
        "capability": "Render through LibreOffice as non-authoritative smoke",
        "priority": "P2",
        "status": "supported",
        "oracle": "LibreOffice headless export",
        "notes": "Optional corpus lane exports all checked-in fixtures to PDF when LibreOffice is installed; this remains non-authoritative.",
    },
]


TIER_A_WORKFLOWS: list[CapabilityWorkflow] = [
    {
        "id": "tier-a.slides.reorder",
        "tier": "A",
        "domain": "slides",
        "rank": 10,
        "status": "verified",
        "capability_id": "presentation.slide_reorder",
        "capability": "Reorder existing slides without changing their parts or relationships",
        "python_pptx_probe": (
            "The parity probe moves the existing python-pptx p:sldId entry and "
            "confirms the same presentation-only package delta and slide-id order."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_reorder_shape_delete.py::"
            "test_slide_move_preserves_identity_and_only_rewrites_presentation_part",
            "tests/test_slide_reorder_shape_delete.py::"
            "test_mixed_structural_save_targets_original_slide_identity",
            "tests/parity/test_python_pptx_structural_edits.py::"
            "test_slide_reorder_matches_python_pptx_package_delta",
        ],
        "rust_nodes": [
            "reorders_slides_without_changing_slide_parts_or_relationships",
            "applies_slide_local_edits_before_delete_and_reorder",
        ],
        "expected_changed_parts": ["ppt/presentation.xml"],
        "mutation_route": (
            "SlideCollection.move -> EditOperation::ReorderSlides -> apply_edit_batch"
        ),
        "notes": (
            "The live collection moves immediately; save retains the same slide "
            "objects and rebases indices after the single native batch transaction."
        ),
    },
    {
        "id": "tier-a.slides.duplicate",
        "tier": "A",
        "domain": "slides",
        "rank": 20,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate",
        "capability": "Duplicate an existing slide while preserving its owned relationships",
        "python_pptx_probe": (
            "python-pptx exposes no duplicate operation; the probe records that "
            "gap and pins the defined semantic: verbatim slide copy, shared "
            "layout and image targets, explicit rejection of other relationships."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::"
            "test_slide_duplicate_appends_independent_live_slide_and_composes_edits",
            "tests/test_slide_duplication.py::"
            "test_slide_duplicate_uses_source_identity_after_reorder",
            "tests/test_slide_duplication.py::"
            "test_slide_duplicate_shares_image_media_and_layout_parts",
        ],
        "rust_nodes": [
            "duplicates_slide_sharing_layout_and_image_parts",
            "rejects_unknown_source_slide_part_for_duplication",
            "rejects_unsupported_relationships_without_copy_policy",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> _slide_creations queue -> "
            "native duplicate_slide"
        ),
        "notes": (
            "The duplicate appends a new slide part copied verbatim from the "
            "source; layout and image targets are shared, chart, notes, OLE, "
            "and comments relationships follow their copy policies, and any "
            "remaining relationship type fails with an explicit copy-policy error."
        ),
    },
    {
        "id": "tier-a.slides.duplicate-chart",
        "tier": "A",
        "domain": "slides",
        "rank": 21,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate_chart",
        "capability": "Duplicate a slide that owns chart relationships including embedded workbooks",
        "python_pptx_probe": (
            "python-pptx has no duplicate API; the probe copies the chart-bearing "
            "slide through package-level part cloning and pins the expected part "
            "additions: chart XML, colors, style, and the embedded xlsx workbook."
        ),
        "fixture": "fixtures/pptx/charts/styled_bar_chart.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::"
            "test_slide_duplicate_copies_chart_and_embedded_data_parts",
            "tests/test_slide_duplication.py::"
            "test_slide_duplicate_copies_chart_style_and_color_parts",
        ],
        "rust_nodes": [
            "duplicates_slide_with_chart_and_embedded_data",
            "duplicates_slide_with_chart_style_and_color_parts",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> _slide_creations queue -> "
            "native duplicate_slide with chart copy policy"
        ),
        "notes": (
            "Chart, colors, style, and embedded workbook parts are deep-copied "
            "so series edits on the duplicate never alias the source chart; the "
            "duplicated package passes strict Open XML validation when the "
            ".NET validator is available."
        ),
    },
    {
        "id": "tier-a.slides.duplicate-notes",
        "tier": "A",
        "domain": "slides",
        "rank": 22,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate_notes",
        "capability": "Duplicate a slide together with its notes slide",
        "python_pptx_probe": (
            "python-pptx has no duplicate API; the probe clones the notes slide "
            "part and pins that notes text edits stay slide-scoped."
        ),
        "fixture": "fixtures/pptx/notes/speaker_notes.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::"
            "test_slide_duplicate_copies_notes_slide_and_rewrites_back_reference",
        ],
        "rust_nodes": [
            "duplicates_slide_with_notes_slide_and_rewrites_back_reference",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> _slide_creations queue -> "
            "native duplicate_slide with notes copy policy"
        ),
        "notes": (
            "Notes edits remain part-scoped per the notes mutation watchpoint."
        ),
    },
    {
        "id": "tier-a.slides.duplicate-ole",
        "tier": "A",
        "domain": "slides",
        "rank": 23,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate_ole",
        "capability": "Duplicate a slide that owns OLE object relationships and embedded binaries",
        "python_pptx_probe": (
            "python-pptx has no duplicate API; the probe clones the OLE "
            "relationship and embedded binary and pins preservation."
        ),
        "fixture": "fixtures/pptx/package/ole_object.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::test_slide_duplicate_copies_ole_object_part",
        ],
        "rust_nodes": [
            "duplicates_slide_with_ole_object",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> _slide_creations queue -> "
            "native duplicate_slide with OLE copy policy"
        ),
        "notes": "Preservation-first: unknown embedded binaries must never be dropped.",
    },
    {
        "id": "tier-a.slides.duplicate-comments",
        "tier": "A",
        "domain": "slides",
        "rank": 24,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate_comments",
        "capability": "Duplicate a slide that owns slide comments",
        "python_pptx_probe": (
            "python-pptx has no duplicate API; the probe copies the "
            "slide-scoped comments part and shares the author part."
        ),
        "fixture": "fixtures/pptx/side_parts/legacy_comments.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::test_slide_duplicate_copies_legacy_comment_part",
        ],
        "rust_nodes": [
            "duplicates_slide_with_legacy_comments",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> _slide_creations queue -> "
            "native duplicate_slide with comments copy policy"
        ),
        "notes": "Comment author parts are presentation-scoped and stay shared.",
    },
    {
        "id": "tier-a.slides.delete",
        "tier": "A",
        "domain": "slides",
        "rank": 25,
        "status": "verified",
        "capability_id": "presentation.slide_delete",
        "capability": "Delete an existing slide and clean up owned package parts and relationships",
        "python_pptx_probe": (
            "python-pptx has no public slide delete API; the probe mutates the underlying "
            "presentation slide list and drops the unreferenced slide part and relationships."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_deletion.py::test_slide_delete_first_preserves_survivor_and_edits",
            "tests/test_slide_deletion.py::test_slide_delete_second_via_remove",
            "tests/parity/test_python_pptx_structural_edits.py::test_slide_delete_matches_python_pptx_package_delta",
        ],
        "rust_nodes": [
            "crates/wolfppt-core/src/tests_slide_delete.inc.rs::deletes_first_slide_and_preserves_survivor_and_package_integrity",
            "crates/wolfppt-core/src/tests_slide_delete.inc.rs::deletes_second_slide_and_preserves_first_slide",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.remove / del prs.slides[i] -> native delete_slides batch mutation"
        ),
        "notes": (
            "Slide deletion removes slide part and slide relationships from the package while "
            "performing ownership-closure cleanup for owned child parts (unreferenced charts, "
            "workbooks, and OLE objects) and preserving shared targets (media, layouts, macros, "
            "and unreferenced unknown parts). Pending queue compositions (reorders, edits, additions) "
            "are rebased across survivor slide indices."
        ),
    },
    {
        "id": "tier-a.slides.pending-delete",
        "tier": "A",
        "domain": "slides",
        "rank": 26,
        "status": "verified",
        "capability_id": "presentation.pending_slide_delete",
        "capability": "Delete pending newly-added or duplicated slides before save",
        "python_pptx_probe": (
            "The parity probe removes pending slides added via add_slide() or duplicate() "
            "before save and verifies in-memory collection and package delta consistency."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_deletion.py::test_slide_delete_remove_add_slide_pending",
            "tests/test_slide_deletion.py::test_slide_delete_remove_duplicate_pending",
            "tests/test_slide_deletion.py::test_slide_delete_pending_slide_with_queued_edits",
            "tests/test_slide_deletion.py::test_slide_delete_save_equivalence_untouched_deck",
            "tests/test_slide_deletion.py::test_slide_delete_add_remove_add",
            "tests/test_slide_deletion.py::test_slide_delete_duplicate_remove_duplicate",
            "tests/test_slide_deletion.py::test_slide_delete_remove_pending_then_persisted",
            "tests/test_slide_deletion.py::test_slide_delete_remove_persisted_then_pending",
            "tests/test_slide_deletion.py::test_slide_delete_move_and_pending_removal",
            "tests/test_slide_deletion.py::test_slide_delete_delitem_pending_slide",
            "tests/test_slide_deletion.py::test_slide_delete_move_reorders_pending_slides_then_remove_targets_correct_creation",
            "tests/parity/test_python_pptx_structural_edits.py::test_pending_slide_delete_matches_python_pptx_target_state",
        ],
        "rust_nodes": [],
        "expected_changed_parts": [],
        "mutation_route": (
            "SlideCollection.remove -> cancel pending slide creation queue by identity token -> rebase survivor indices"
        ),
        "notes": (
            "Identity-based creation cancellation, queue unwind + survivor rebase, zero-delta save equivalence; "
            "pending shape deletion remains unsupported."
        ),
    },
    {
        "id": "tier-a.slides.slice-delete",
        "tier": "A",
        "domain": "slides",
        "rank": 27,
        "status": "verified",
        "capability_id": "presentation.slide_slice_delete",
        "capability": "Delete slides by slice across persisted and pending slides",
        "python_pptx_probe": (
            "python-pptx raises TypeError on slice deletion; the wolfppt probe verifies "
            "del prs.slides[start:stop:step] correctly removes mixed persisted and pending slides."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_deletion.py::test_slide_delete_slice_contiguous_persisted",
            "tests/test_slide_deletion.py::test_slide_delete_slice_with_step",
            "tests/test_slide_deletion.py::test_slide_delete_slice_negative_bounds",
            "tests/test_slide_deletion.py::test_slide_delete_slice_mixed_persisted_and_pending",
            "tests/test_slide_deletion.py::test_slide_delete_slice_leaves_exactly_one_slide",
            "tests/test_slide_deletion.py::test_slide_delete_slice_all_slides_rejected",
            "tests/test_slide_deletion.py::test_slide_delete_slice_empty_noop",
            "tests/test_slide_deletion.py::test_slide_delete_slice_after_move",
            "tests/test_slide_deletion.py::test_slide_delete_slice_survivors_retain_prior_queued_edits",
            "tests/test_slide_deletion.py::test_slide_delete_slice_equivalence_with_individual_deletions",
            "tests/test_slide_deletion.py::test_slide_delete_slice_propagates_remove_errors",
        ],
        "rust_nodes": [],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.__delitem__(slice) -> SlideCollection.remove -> native delete_slides batch mutation"
        ),
        "notes": (
            "wolfppt API completion beyond python-pptx (python-pptx raises TypeError on slice deletion); "
            "composes with persisted + pending removal via sequential remove(); all-slides deletion rejected "
            "before mutation; empty slice no-op; step + negative bounds supported. Equivalence tests verify "
            "del prs.slides[a:b] produces package and semantic extraction delta equal to sequential one-by-one deletions."
        ),
    },
    {
        "id": "tier-a.slides.duplicate-copy-policies",
        "tier": "A",
        "domain": "slides",
        "rank": 28,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate_copy_policies",
        "capability": "Duplicate slides owning unhandled relationship types via explicit copy policies",
        "python_pptx_probe": (
            "python-pptx has no duplicate API; the probe duplicates slides owning unhandled "
            "relationship types (audio, video, comments and related) and verifies copy policy enforcement."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::test_slide_duplicate_shares_video_and_partnered_media_relationships",
            "tests/test_slide_duplication.py::test_slide_duplicate_shares_audio_relationship",
            "tests/test_slide_duplication.py::test_slide_duplicate_copies_synthetic_comment_relationship",
            "tests/test_slide_duplication.py::test_slide_duplicate_mixed_deck_video_image_notes",
            "tests/test_slide_duplication.py::test_slide_duplicate_rejects_relationships_without_copy_policy",
        ],
        "rust_nodes": [
            "duplicates_slide_with_video_and_partnered_media_relationships",
            "duplicates_slide_with_audio_relationship",
            "duplicates_slide_with_singular_comment_relationship",
            "rejects_unsupported_relationships_without_copy_policy",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> native duplicate_slide batch mutation with explicit copy policies"
        ),
        "notes": (
            "Explicit copy policies: audio, video, and generic media targets under ppt/media/ are SHARED "
            "immutable binary assets (unchanged rIds/targets, covered by [Content_Types].xml Defaults); "
            "comments relationships and parts are COPIED to a new owned ppt/comments/commentN.xml with "
            "Content-Type Override and remapped rel target while comment authors remain shared presentation-level "
            "assets; unhandled internal relationship targets continue to be explicitly rejected."
        ),
    },
    {
        "id": "tier-a.slides.duplicate-external-rels",
        "tier": "A",
        "domain": "slides",
        "rank": 29,
        "status": "verified",
        "capability_id": "presentation.slide_duplicate_external_targets",
        "capability": "Duplicate slides owning external-target relationships (e.g. hyperlinks)",
        "python_pptx_probe": (
            "python-pptx has no duplicate API; the probe duplicates slides owning external-target "
            "relationships (such as hyperlinks) and verifies identical rel pass-through, rId consistency, "
            "hyperlink address resolution, and package part diffs."
        ),
        "fixture": "fixtures/pptx/slides/two_slide_text.pptx",
        "pytest_nodes": [
            "tests/test_slide_duplication.py::test_slide_duplicate_preserves_external_hyperlink_relationship",
            "tests/test_slide_duplication.py::test_slide_duplicate_mixed_deck_external_image_comments",
        ],
        "rust_nodes": [
            "duplicates_slide_with_external_hyperlink_relationship",
            "duplicates_slide_with_mixed_external_image_and_comment_relationships",
        ],
        "expected_changed_parts": [
            "[Content_Types].xml",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
        ],
        "mutation_route": (
            "SlideCollection.duplicate -> native duplicate_slide batch mutation with external relationship pass-through"
        ),
        "notes": (
            "External-target relationships (e.g. hyperlinks) pass through verbatim into the duplicate "
            "slide's rels — same rId, Type, Target, TargetMode; no package parts are created; unknown "
            "internal types still rejected; python-pptx element-level equivalence tests are the evidence."
        ),
    },
    {
        "id": "tier-a.shapes.delete",
        "tier": "A",
        "domain": "shapes",
        "rank": 30,
        "status": "verified",
        "capability_id": "shapes.delete",
        "capability": "Delete an existing shape without disturbing unrelated slide content",
        "python_pptx_probe": (
            "The parity probe removes the same python-pptx shape element and "
            "confirms the same slide-only package delta and survivor shape ids."
        ),
        "fixture": "fixtures/pptx/text_basic/title_body_bullets.pptx",
        "pytest_nodes": [
            "tests/test_slide_reorder_shape_delete.py::"
            "test_shape_remove_updates_live_state_and_preserves_unrelated_content",
            "tests/test_slide_reorder_shape_delete.py::"
            "test_shape_remove_cleans_orphan_relationship_but_preserves_media_part",
            "tests/parity/test_python_pptx_structural_edits.py::"
            "test_shape_delete_matches_python_pptx_package_delta",
        ],
        "rust_nodes": [
            "deletes_one_shape_without_changing_unrelated_package_parts",
            "removes_a_deleted_picture_relationship_but_preserves_its_media_part",
        ],
        "expected_changed_parts": ["ppt/slides/slide1.xml"],
        "mutation_route": (
            "ShapeCollection.remove -> EditOperation::DeleteShape -> apply_edit_batch"
        ),
        "notes": (
            "Deletion is limited to saved top-level shapes; grouped-child deletion "
            "is rejected explicitly and shared relationships remain intact."
        ),
    },
    {
        "id": "tier-a.shapes.group-child-delete",
        "tier": "A",
        "domain": "shapes",
        "rank": 31,
        "status": "verified",
        "capability_id": "shapes.group_child_delete",
        "capability": "Delete a child shape inside a group shape without disturbing unrelated content",
        "python_pptx_probe": (
            "The parity probe removes the group child shape element and verifies "
            "only the target slide XML changes."
        ),
        "fixture": "fixtures/pptx/shapes/grouped_shapes.pptx",
        "pytest_nodes": [
            "tests/parity/test_python_pptx_structural_edits.py::test_group_child_shape_delete_matches_python_pptx_package_delta",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_via_group_shapes",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_middle_child_preserves_order",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_sequential_deletes_target_stable_ids",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_composed_with_top_level_shape_delete",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_rejects_nested_groups_and_preserves_state",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_rejects_foreign_and_unsaved",
            "tests/test_group_shape_child_delete.py::test_group_child_shape_remove_cleans_orphan_relationship_but_preserves_media_part",
        ],
        "rust_nodes": [
            "crates/wolfppt-core/src/tests_group_shape_child_edits.inc.rs::deletes_existing_group_child_shape_without_losing_package_parts",
            "crates/wolfppt-core/src/tests_group_shape_child_edits.inc.rs::deletes_group_child_from_multi_child_group_preserving_siblings",
            "crates/wolfppt-core/src/tests_group_shape_child_edits.inc.rs::deletes_group_child_picture_cleans_relationship_but_preserves_media_part",
        ],
        "expected_changed_parts": [
            "ppt/slides/slide1.xml",
        ],
        "mutation_route": (
            "GroupShapes.remove / ShapeCollection.remove -> native group child delete mutation"
        ),
        "notes": (
            "Only the owning slide XML part is modified when removing a child shape from a group."
        ),
    },
    {
        "id": "tier-a.shapes.nested-group-child-delete",
        "tier": "A",
        "domain": "shapes",
        "rank": 32,
        "status": "verified",
        "capability_id": "shapes.nested_group_child_delete",
        "capability": "Delete a child shape inside a nested group shape without disturbing unrelated content",
        "python_pptx_probe": (
            "The parity probe removes nested group child shapes or whole sub-groups and verifies "
            "surviving shape IDs/order, slide-only package delta, relationship-entry removal, "
            "and shared-media preservation."
        ),
        "fixture": "fixtures/pptx/shapes/grouped_shapes.pptx",
        "pytest_nodes": [
            "tests/test_group_shape_child_delete.py::test_delete_nested_group_child_from_two_level_group",
            "tests/test_group_shape_child_delete.py::test_delete_deeply_nested_group_child_from_three_level_group",
            "tests/test_group_shape_child_delete.py::test_delete_entire_nested_subgroup_removes_full_subtree_and_cleans_relationships",
            "tests/test_group_shape_child_delete.py::test_delete_nested_group_child_with_picture_cleans_relationship_preserves_shared_media",
            "tests/test_group_shape_child_delete.py::test_nested_group_child_delete_python_pptx_element_parity",
        ],
        "rust_nodes": [
            "crates/wolfppt-core/src/tests_group_shape_child_edits.inc.rs::deletes_child_shape_in_nested_group_preserving_siblings",
            "crates/wolfppt-core/src/tests_group_shape_child_edits.inc.rs::deletes_entire_nested_subgroup_from_outer_group",
            "crates/wolfppt-core/src/tests_group_shape_child_edits.inc.rs::deletes_nested_group_child_picture_cleans_relationship",
        ],
        "expected_changed_parts": [
            "ppt/slides/slide1.xml",
        ],
        "mutation_route": (
            "GroupShapes.remove / ShapeCollection.remove -> native nested group child delete mutation"
        ),
        "notes": (
            "Any-depth child deletion + whole sub-group subtree removal, ownership-closure part cleanup, "
            "unsaved/pending-target rejection retained."
        ),
    },
    {
        "id": "tier-a.tables.row-column-mutation",
        "tier": "A",
        "domain": "tables",
        "rank": 35,
        "status": "verified",
        "capability_id": "tables.row_column_mutation",
        "capability": "Insert and delete table rows and columns",
        "python_pptx_probe": (
            "python-pptx exposes no first-class insert or delete API; the probe "
            "mirrors the common tbl XML workaround and pins the expected "
            "grid, row, and cell deltas."
        ),
        "fixture": "fixtures/pptx/tables/simple_table.pptx",
        "pytest_nodes": [
            "tests/test_table_row_column_mutation.py::"
            "test_table_row_insert_at_start",
            "tests/test_table_row_column_mutation.py::"
            "test_table_row_delete_merged_cell_raises",
            "tests/test_table_row_column_mutation.py::"
            "test_table_column_insert_in_middle",
            "tests/test_table_row_column_mutation.py::"
            "test_table_column_delete_sole_column_raises",
            "tests/test_table_row_column_mutation.py::"
            "test_table_mutations_persist_across_save_reload",
        ],
        "rust_nodes": [
            "test_table_row_insert_start_middle_end",
            "test_table_row_delete_single_and_multiple",
            "test_table_column_insert_start_middle_end",
            "test_table_column_delete_single_and_multiple",
            "test_table_delete_with_merged_cells_rejected",
            "test_table_delete_sole_row_or_col_rejected",
        ],
        "expected_changed_parts": ["ppt/slides/slide1.xml"],
        "mutation_route": (
            "table row/column ops -> EditOperation batch -> apply_edit_batch"
        ),
        "notes": (
            "Row and column mutation must keep gridCol counts, tr counts, and "
            "per-cell text aligned; the slide part is the only changed part."
        ),
    },
    {
        "id": "tier-a.text.shape-text",
        "tier": "A",
        "domain": "text",
        "rank": 100,
        "status": "verified",
        "capability_id": "python_api.shape_text_setter",
        "capability": "Set shape.text through the native batch mutation route",
        "python_pptx_probe": (
            "Compare direct shape.text assignment with python-pptx, then use the "
            "drop-in parity node when the native extension is installed."
        ),
        "fixture": "fixtures/pptx/text_basic/title_body_bullets.pptx",
        "pytest_nodes": [
            "tests/test_presentation_facade_queue.py::"
            "test_shape_text_assignment_queues_native_save"
        ],
        "rust_nodes": [
            "applies_text_edit_batch_without_rewriting_package_parts_repeatedly"
        ],
        "expected_changed_parts": ["ppt/slides/slide1.xml"],
        "mutation_route": (
            "Presentation.shape.text -> EditOperation::SetShapeText -> "
            "apply_edit_batch"
        ),
        "notes": (
            "The focused facade and Rust batch tests are runnable locally; the "
            "python-pptx parity lane remains available when the native extension is installed."
        ),
    },
]


def entries_by_status(status: str) -> list[Entry]:
    return [entry for entry in ENTRIES if entry.get("status") == status]
