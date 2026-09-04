# WolfPPT

[![CI](https://github.com/wolfiesch/wolfppt-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/wolfiesch/wolfppt-oss/actions/workflows/ci.yml)

WolfPPT is a Rust-native PowerPoint editing runtime for surgical, verified
edits to existing decks.

Generating a new deck from scratch is easy. Safely editing the 90-slide deck
a company already uses — without corrupting its charts, media, notes, links,
or unknown internals — is a different problem, and it is the problem WolfPPT
is built for.

- Lossless `.pptx` / `.pptm` package preservation: parts you did not edit,
  including parts WolfPPT has no schema for, stay byte-for-byte identical.
- Guarded text, shape, table, chart, and slide operations (edit, duplicate,
  delete, reorder) with mutation guards that refuse unsafe edits instead of
  writing them.
- Verification receipts, semantic diffs, and optional Open XML validation
  and render smoke, so every claimed edit is checked against the saved
  package, not assumed.

Those claims are not asserted; they are measured. The benchmark harness in
this repository is the evidence system that proves them, and it stays a
first-class part of the project.

## Quickstart

Install from source:

```bash
pip install wolfppt
```

PyPI wheels cover CPython 3.11-3.14 on Linux x86_64/aarch64 and macOS arm64. Add the `baseline` extra (`pip install wolfppt[baseline]`) for the `wolfppt-harness` command, which needs `python-pptx` for adapter comparison lanes.

Then run the built-in demo:

```bash
wolfppt demo
```

It builds a deterministic deck, applies four surgical edits, reopens the
saved package to verify every edit, and prints a verification receipt:

```text
requested edits: 4
verified edits: 4
unrelated package parts changed: 0
reopen: passed
open xml validation: skipped (Open XML validation is optional and is not run by the demo.)
```

Basic usage:

```python
from wolfppt import Presentation

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])
prs.save("output.pptx")
```

## Harness Shape

The harness is WolfPPT's evidence system. It generates a deterministic
fixture corpus, records the expected package semantics, and pushes every
adapter — including the native Rust engine behind the public API — through
validation, package diffing, semantic diffing, and render smoke. Results
append to an append-only evidence ledger and roll up into a generated
compatibility matrix:

```text
fixtures/*.pptx
   |
   v
semantic extractor -> expected/*.json
   |
   v
library adapters -> validation / package diff / semantic diff / render smoke
   |
   v
results/runs.jsonl -> generated compatibility matrix
```

## Benchmark Suite

`wolfppt-harness benchmark` runs repeatable adapter benchmarks across the checked-in
fixture manifest. It records latency separately from correctness checks, so
semantic diffs, package diffs, and optional Open XML validation do not inflate
the measured adapter time. The default suite compares the stdlib semantic
extractor, `python-pptx` summary/round-trip baselines, the official .NET Open XML
SDK, a PptxGenJS generation-only lane, Apache POI, Aspose.Slides, and
Spire.Presentation round-trip lanes when their toolchains are installed, a
licensed Syncfusion .NET round-trip lane, an opt-in external command round-trip
lane for other SDKs, the Rust CLI bridge, and the native Rust Python binding
when those tools are available. Use
`--validate-openxml` for release-grade output validation and `--write-results`
to append samples to `results/runs.jsonl`. The PptxGenJS lane is a generated-deck
baseline, not evidence of existing-deck preservation; Open XML validation may
surface schema differences separately from generation speed.

Drop-in edit benchmarks are opt-in because they target specific public API
workflows instead of the whole fixture corpus. Use them to compare equivalent
`python-pptx` and WolfPPT facade edits, such as paragraph and table-cell updates.
For performance claims against Python libraries, build the native module in
release mode first; debug editable builds are useful for development but slower.

Use `wolfppt-harness benchmark-profiles` to list curated benchmark suites and
`wolfppt-harness benchmark-profile <name>` to run one. Profiles keep drop-in
comparisons on valid adapter/fixture pairs and add a python-pptx vs WolfPPT
speedup table when both sides pass. Use `dev-smoke` for fast edit-loop
feedback; it is not claim-grade evidence. Useful profiles include `dev-smoke`,
`core-smoke`, `core-full`, `real-corpus`, `private-real-decks`,
`sdk-preservation`, `sdk-comparison`, `sdk-spire-reproducer`, `dropin-smoke`,
`dropin-full`, `release-smoke`, and `release-full`. Core and release profiles use built-in
preservation adapters only; Apache POI claim gates belong in
`sdk-preservation`, commercial SDKs and custom external commands belong in
`sdk-comparison`, stricter all-commercial setup proof belongs in
`sdk-comparison-strict`, and uncommitted local or VPS-only decks belong in
`private-real-decks` via `WOLFPPT_PRIVATE_DECKS_DIR`.
Release profiles omit the generation-only PptxGenJS lane so `--validate-openxml`
stays strict for existing-deck edit and round-trip lanes.
Add `--min-wolfppt-speedup 1.0` to turn passing python-pptx/WolfPPT pairs into a
performance gate for release evidence. The gate still reports every near miss,
but sub-threshold slowdowns of `0.100 ms` or less are treated as timing noise
rather than material failures.
Add `--require-adapter <name>` when a comparison lane must be present rather
than skipped, for example when recording commercial SDK evidence.
For visual-oracle corpus evidence, pair `run-corpus --include-powerpoint` with
`--require-lane powerpoint-render` so a missing or skipped PowerPoint export
fails the run instead of being treated as optional. Add
`--min-powerpoint-exported-slides <count>` to gate the actual slide PNG sample
count.

See the compatibility matrix under `docs/compatibility/` for the current
feature-coverage boundaries. As of the latest release-gate evidence,
`release-full` run `20260519T120111Z` passes the full checked-in release gate
with 483 passing rows, 0 skips, 0 failures, 29 distinct fixtures, and 5,040
Open XML validation samples, plus fixture gates for 110 slides, 290 shapes, 25
charts, 16 fixtures
with tables, 16 with charts, 14 with media, and 17 with embedded objects. This
release gate was refreshed after adding the procurement vendor-risk pack and
the one-pass grouped-connector connection, slide-level connector-to-new-shape,
and nested-group OLE insertion paths, then refreshed again after coalescing
grouped connector attachments to newly added group children. It includes connector attachment edits through
`begin_connect()` and
`end_connect()` for newly added, existing deck, and grouped child shapes, grouped-shape child
adjustment edits, grouped existing-shape and grouped existing-child lanes,
table row-height and column-width edits,
bar/line/pie chart-add lanes, packaged native chart templates, batched
chart-template-family insertion, coalesced nested-group auto-shape insertion,
speaker-notes text, text-frame, background, paragraph/run, placeholder-clone,
and slide-name metadata
lanes, and Linux
`fit_text` coverage through a discovered compatible font file.
The latest evidence-backed
`real-corpus` run `20260527T121753Z` passes 144/144 rows across sixteen
real-world-style fixtures, including the QoE diligence, customer success,
security compliance, revenue-operations forecast, product-launch readiness,
enterprise implementation, procurement vendor-risk, post-merger integration,
and earnings board appendix packs (`workloads/post_merger_integration_pack`
and `workloads/earnings_board_appendix_pack`), with 960 Open XML validation
samples and the 16-fixture gate plus slide, shape, table, chart, media, and
embedded-object complexity coverage. The report records Git metadata from the
remote launcher
environment for commit `3d6134b`, so the raw benchmark report and detached job
point at the same code. New launcher runs also record whether the VPS mirror was
freshly synced before benchmarking. Local
PowerPoint visual-oracle run `20260519T053625Z` passes the required
`powerpoint-render` lane across the current 29-fixture corpus and exports
110 slide PNGs. A redacted remote-host `private-real-decks` pressure run
`20260518T050715Z` passes on two distinct private decks with 16 slides, 135
shapes, 8 tables, 4 charts, 13 media parts, 120 Open XML validation samples,
and 0 raw-name/path leaks in the private report check. The latest remote-host
`sdk-preservation` run `20260519T034127Z` passes 56/56 rows across python-pptx,
Open XML SDK, Apache POI, and WolfPPT native with 840 Open XML validation
samples, 42 SDK preservation comparisons, and `2.006-561.911x` measured WolfPPT
speedups against those open-source baselines. These support checked-in corpus,
open-source SDK, and narrow private-pressure claims through those snapshots, but
not universal
"best in class" claims or first-of-kind claims.

## Python-Compatible Facade

WolfPPT exposes a first python-pptx-style API for existing-deck edits:

```python
from wolfppt import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.enum.text import MSO_AUTO_SIZE

prs = Presentation("deck.pptx")
prs.slides[0].shapes.title.text = "Updated title"
prs.slides[0].shapes[1].text = "Updated body"
prs.slides[0].shapes[1].left = 914400
prs.slides[0].shapes[1].text_frame.paragraphs[0].text = "Updated paragraph"
prs.slides[0].shapes[1].text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
prs.slides[0].shapes[1].text_frame.paragraphs[0].level = 1
prs.slides[0].shapes[1].text_frame.paragraphs[0].line_spacing = 1.25
prs.slides[0].shapes[1].text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].text = "Updated run"
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].font.bold = True
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].font.italic = True
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].font.underline = True
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].font.size = 304800
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].font.name = "Aptos"
prs.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].font.color.rgb = "123456"
prs.slides.add_slide(prs.slide_layouts[6])
prs.slides[0].shapes.add_textbox(914400, 2743200, 3657600, 914400).text = "New box"
prs.slides[0].shapes.add_shape(1, 914400, 3657600, 3657600, 914400).text = "New shape"
picture = prs.slides[0].shapes.add_picture("logo.png", 0, 0)
picture.crop_left = 0.125
prs.slides[0].shapes[0].table.cell(1, 1).text = "2"
prs.slides[0].shapes.add_table(2, 3, 0, 0, 2743200, 914400)
prs.save("updated.pptx")
```

The facade currently supports existing-deck open/save, slide and shape
iteration/indexing, common collection slicing, title placeholder lookup,
`slide.placeholders`, `slide.shapes.placeholders`, shape-tree helper flags, slide
layouts, read-only `.part` package metadata, read-only
`.element` XML inspection for common presentation, slide, layout, shape,
placeholder, and master objects, background fill reads and slide background
writes, existing notes slide/master reads,
`slides.add_slide(layout)`, `slides.move(...)`, `slides.duplicate(slide)` including chart, notes, OLE, comment, audio/video/media, and external-target relationship copy policies,
`slides.remove(slide)`, `del slides[index]`, and `del slides[start:stop:step]` for persisted and pending newly-added or duplicated slides,
`slide_layouts.remove(...)`,
`shapes.add_picture(...)` with explicit or inferred bounds,
picture crop reads/writes, `shapes.add_textbox(...)`, common `shapes.add_shape(...)`
preset shapes, table insertion, table cell text-frame/margin reads/writes, table row/column insert and remove, `shapes.remove(...)`, `group.shapes.remove(child)` including any-depth nested group children and whole sub-groups, chart insertion, chart type/series/title/legend/axis
reads, chart title, legend, and axis-title edits, category/XY/bubble chart data replacement, text reads, `shape.text` assignment, shape
name, type, geometry, rotation, adjustment, and line XML helper reads/writes, solid/gradient fill, line RGB, and line width writes, shadow inheritance, external hyperlink, and target-slide reads/writes, paragraph/run text
assignment, text-run external hyperlinks, text-frame margin, word-wrap, vertical-anchor, auto-size, and fit-text reads/writes, paragraph alignment, level, and spacing reads/writes, run bold/italic/underline reads/writes,
run size/name/color reads/writes, paragraph/run appends,
`shape.text_frame.clear()`, and `shape.text_frame.text` assignment. Edited
saves go through the native Rust mutation engine; no-op saves preserve the
source package.

## Commands

```bash
uv sync --extra dev
uv run pytest
uv run wolfppt-harness extract path/to/deck.pptx
uv run wolfppt-harness manifest path/to/deck.pptx
uv run wolfppt-harness diff before.pptx after.pptx
uv run --extra baseline wolfppt-harness python-pptx-summary path/to/deck.pptx
uv run --extra baseline wolfppt-harness python-pptx-roundtrip in.pptx out.pptx
uv run wolfppt-harness validate-openxml path/to/deck.pptx
uv run wolfppt-harness rust-inspect path/to/deck.pptx
uv run wolfppt-harness rust-roundtrip in.pptx out.pptx
uv run wolfppt-harness rust-add-slide in.pptx out.pptx 0
uv run wolfppt-harness rust-replace-text in.pptx out.pptx WolfPPT "WolfPPT Native"
uv run wolfppt-harness rust-replace-text in.pptx out.pptx WolfPPT "WolfPPT Native" --slide-index 0
uv run wolfppt-harness rust-replace-text-run in.pptx out.pptx 0 1 "Fast Native"
uv run wolfppt-harness rust-set-shape-text in.pptx out.pptx 0 1 "Fast Native"
uv run wolfppt-harness rust-set-paragraph-text in.pptx out.pptx 0 1 0 "Fast Native"
uv run wolfppt-harness rust-replace-image in.pptx out.pptx rId2 image.png
uv run wolfppt-harness rust-replace-image in.pptx out.pptx rId2 image.png --slide-index 0
uv run wolfppt-harness rust-add-image in.pptx out.pptx 0 image.png 0 0 914400 914400
uv run wolfppt-harness rust-replace-table-cell in.pptx out.pptx 0 0 1 1 "2"
uv run wolfppt-harness rust-add-table in.pptx out.pptx 0 2 3 0 0 2743200 914400
uv run wolfppt-harness native-inspect path/to/deck.pptx
uv run wolfppt-harness native-summary path/to/deck.pptx
uv run wolfppt-harness native-roundtrip in.pptx out.pptx
uv run wolfppt-harness native-add-slide in.pptx out.pptx 0
uv run wolfppt-harness native-replace-text in.pptx out.pptx WolfPPT "WolfPPT Native"
uv run wolfppt-harness native-replace-text in.pptx out.pptx WolfPPT "WolfPPT Native" --slide-index 0
uv run wolfppt-harness native-replace-text-run in.pptx out.pptx 0 1 "Fast Native"
uv run wolfppt-harness native-set-shape-text in.pptx out.pptx 0 1 "Fast Native"
uv run wolfppt-harness native-set-paragraph-text in.pptx out.pptx 0 1 0 "Fast Native"
uv run wolfppt-harness native-replace-image in.pptx out.pptx rId2 image.png
uv run wolfppt-harness native-replace-image in.pptx out.pptx rId2 image.png --slide-index 0
uv run wolfppt-harness native-add-image in.pptx out.pptx 0 image.png 0 0 914400 914400
uv run wolfppt-harness native-replace-table-cell in.pptx out.pptx 0 0 1 1 "2"
uv run wolfppt-harness native-add-table in.pptx out.pptx 0 2 3 0 0 2743200 914400
uv run wolfppt-harness render-libreoffice path/to/deck.pptx
uv run wolfppt-harness render-powerpoint path/to/deck.pptx
uv run --extra dev wolfppt-harness corpus
uv run wolfppt-harness python-api-surface --json --max-real-slides 999 --max-real-shapes 999 --min-fixtures 33 --min-representative-pairs 64 --min-real-pairs 1576 --write-report
uv run wolfppt-harness dropin-coverage --min-behaviors 149 --min-domains 9 --min-domain-behaviors charts=39,groups=31,media=16,notes=8,presentation=2 --min-domain-behaviors shapes=79,slides_layouts=18,tables=14,text=43 --min-fixture-scenarios 403 --min-adapter-fixture-rows 806
uv run wolfppt-harness run-corpus --write-report
uv run wolfppt-harness run-corpus --include-powerpoint --require-lane powerpoint-render --min-powerpoint-exported-slides 110 --write-report
npm install --prefix tools/pptxgenjs-generate
mvn -q -f tools/apache-poi-roundtrip/pom.xml -DskipTests compile
docker build -t wolfppt-aspose-slides:python3.11-bullseye examples/external-roundtrip/aspose-docker
uv run wolfppt-harness benchmark --iterations 5 --warmup 1 --write-report
uv run wolfppt-harness benchmark-profiles
scripts/verify-fast.sh tests/test_validation_ladder.py
scripts/verify-slice.sh tests/test_validation_ladder.py
scripts/verify-vps.sh --python-only -- tests/test_validation_ladder.py -q
scripts/verify-claims.sh
scripts/start-vps-claims.sh
scripts/start-vps-real-corpus.sh
scripts/start-vps-private-real-decks.sh --private-decks-dir /path/on/vps/private/decks
scripts/verify-sdk-comparison.sh
scripts/start-vps-sdk-comparison.sh
scripts/start-vps-sdk-comparison.sh --strict-commercial
scripts/vps-job-status.sh --active-only
uv run wolfppt-harness validate quick
uv run wolfppt-harness validate slice --json
uv run wolfppt-harness validate vps-pr
uv run wolfppt-harness validate real-corpus
uv run wolfppt-harness validate private-real-decks
uv run wolfppt-harness validate sdk-comparison
uv run wolfppt-harness validate sdk-comparison-strict
uv run wolfppt-harness validate release
uv run wolfppt-harness benchmark-profile dev-smoke --iterations 1 --warmup 0
uv run wolfppt-harness benchmark-profile release-smoke --iterations 5 --warmup 1 --validate-openxml --write-report
uv run wolfppt-harness benchmark-profile release-full --iterations 15 --warmup 2 --validate-openxml --progress --fail-fast --min-wolfppt-speedup 1.0 --min-distinct-fixtures 30 --min-fixture-total-slides 111 --min-fixture-total-shapes 291 --min-fixture-total-charts 26 --min-fixtures-with-tables 16 --min-fixtures-with-charts 16 --min-fixtures-with-media 14 --min-fixtures-with-embedded-objects 17 --min-openxml-samples 5010 --write-report
uv run wolfppt-harness benchmark-profile sdk-preservation --iterations 15 --warmup 2 --validate-openxml --min-native-roundtrip-speedup 1.0 --min-distinct-fixtures 16 --min-fixture-total-slides 106 --min-fixture-total-shapes 297 --min-fixture-total-tables 43 --min-fixture-total-charts 25 --min-fixture-total-media 15 --min-fixture-total-embedded-objects 36 --min-fixtures-with-tables 16 --min-fixtures-with-charts 16 --min-fixtures-with-media 15 --min-fixtures-with-embedded-objects 16 --min-sdk-preservation-rows 48 --min-openxml-samples 960 --require-adapter apache-poi-roundtrip --write-report
uv run wolfppt-harness benchmark-profile dropin-smoke --iterations 15 --warmup 2 --validate-openxml --min-wolfppt-speedup 1.0 --min-openxml-samples 20 --write-report
WOLFPPT_PRIVATE_DECKS_DIR=/path/to/private/decks uv run wolfppt-harness private-decks --json --min-count 5 --min-distinct-count 5 --min-total-slides 50 --min-total-shapes 100 --min-total-tables 1 --min-total-charts 1 --min-total-media 1 --min-total-embedded-objects 1 --min-decks-with-tables 1 --min-decks-with-charts 1 --min-decks-with-media 1 --min-decks-with-embedded-objects 1 --min-distinct-decks-with-tables 1 --min-distinct-decks-with-charts 1 --min-distinct-decks-with-media 1 --min-distinct-decks-with-embedded-objects 1 --min-slides-per-deck 3 --min-shapes-per-deck 10
WOLFPPT_PRIVATE_DECKS_DIR=/path/to/private/decks uv run wolfppt-harness benchmark-profile private-real-decks --iterations 15 --warmup 2 --min-private-decks 5 --min-distinct-private-decks 5 --min-private-total-slides 50 --min-private-total-shapes 100 --min-private-total-tables 1 --min-private-total-charts 1 --min-private-total-media 1 --min-private-total-embedded-objects 1 --min-private-decks-with-tables 1 --min-private-decks-with-charts 1 --min-private-decks-with-media 1 --min-private-decks-with-embedded-objects 1 --min-private-distinct-decks-with-tables 1 --min-private-distinct-decks-with-charts 1 --min-private-distinct-decks-with-media 1 --min-private-distinct-decks-with-embedded-objects 1 --min-private-slides-per-deck 3 --min-private-shapes-per-deck 10 --validate-openxml --progress --fail-fast --min-native-roundtrip-speedup 1.0 --min-distinct-fixtures 5 --min-openxml-samples 100 --write-report
WOLFPPT_PRIVATE_DECKS_DIR=/path/to/private/decks uv run wolfppt-harness private-report-check results/benchmarks/latest
SYNCFUSION_LICENSE_KEY='...' uv run wolfppt-harness benchmark --adapter syncfusion-roundtrip --fixture text_basic/title_body_bullets --validate-openxml --json
uv run wolfppt-harness benchmark --adapter aspose-docker-roundtrip --fixture text_basic/title_body_bullets --validate-openxml --json
uv run --with Spire.Presentation wolfppt-harness benchmark-profile sdk-spire-reproducer --iterations 3 --warmup 1 --validate-openxml --progress --write-report
uv run --with Spire.Presentation wolfppt-harness benchmark --adapter spire-presentation-roundtrip,native-rust-roundtrip --fixture workloads/mixed_real_world_deck --iterations 3 --warmup 1 --validate-openxml --write-report --json
WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_NAME='Vendor Slides' WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_VERSION='1.2.3' WOLFPPT_EXTERNAL_ROUNDTRIP_CMD='vendor-tool --input {input} --output {output}' uv run wolfppt-harness benchmark --adapter external-command-roundtrip --fixture text_basic/title_body_bullets --validate-openxml --json
WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_NAME='copy-example' WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_VERSION='0.0.0' WOLFPPT_EXTERNAL_ROUNDTRIP_CMD='python3 examples/external-roundtrip/external-command/copy_roundtrip.py --input {input} --output {output}' uv run wolfppt-harness benchmark --adapter external-command-roundtrip --fixture text_basic/title_body_bullets --validate-openxml --json
WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_NAME='Vendor Slides' WOLFPPT_EXTERNAL_ROUNDTRIP_SDK_VERSION='1.2.3' WOLFPPT_EXTERNAL_ROUNDTRIP_CMD='vendor-tool --input {input} --output {output}' uv run wolfppt-harness benchmark-profile sdk-comparison --require-adapter external-command-roundtrip --validate-openxml --progress --write-report
uv run wolfppt-harness benchmark --adapter python-pptx-roundtrip,openxml-sdk-roundtrip,pptxgenjs-generate,apache-poi-roundtrip,native-rust-roundtrip --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-edit,wolfppt-facade-dropin-edit --fixture text_basic/title_body_bullets,tables/simple_table --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-file-like-edit,wolfppt-facade-dropin-file-like-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-table-cell-text-frame-edit,wolfppt-facade-dropin-table-cell-text-frame-edit --fixture tables/simple_table --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-table-style-flags-edit,wolfppt-facade-dropin-table-style-flags-edit --fixture tables/simple_table --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-table-dimensions-edit,wolfppt-facade-dropin-table-dimensions-edit --fixture tables/simple_table --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-multi-edit,wolfppt-facade-dropin-multi-edit --fixture workloads/multi_edit_table --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-formatting-edit,wolfppt-facade-dropin-formatting-edit --fixture text_basic/title_body_bullets,workloads/multi_format_runs --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-run-formatting-edit,wolfppt-facade-dropin-add-run-formatting-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-paragraph-run-formatting-edit,wolfppt-facade-dropin-add-paragraph-run-formatting-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-replace-run-formatting-edit,wolfppt-facade-dropin-replace-run-formatting-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-paragraph-format-edit,wolfppt-facade-dropin-paragraph-format-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-paragraph-level-edit,wolfppt-facade-dropin-paragraph-level-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-paragraph-spacing-edit,wolfppt-facade-dropin-paragraph-spacing-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-paragraph-clear-edit,wolfppt-facade-dropin-paragraph-clear-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-paragraph-line-break-edit,wolfppt-facade-dropin-paragraph-line-break-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-paragraph-font-edit,wolfppt-facade-dropin-paragraph-font-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-paragraph-format-edit,wolfppt-facade-dropin-add-paragraph-format-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-picture,wolfppt-facade-dropin-add-picture --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-picture-auto-size,wolfppt-facade-dropin-add-picture-auto-size --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-picture-file-like,wolfppt-facade-dropin-add-picture-file-like --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-movie-file-like,wolfppt-facade-dropin-add-movie-file-like --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-ole-object-file-like,wolfppt-facade-dropin-add-ole-object-file-like --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-shape,wolfppt-facade-dropin-add-shape --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-textbox,wolfppt-facade-dropin-add-textbox --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-table,wolfppt-facade-dropin-add-table --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-slide,wolfppt-facade-dropin-add-slide --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-adjustment-edit,wolfppt-facade-dropin-shape-adjustment-edit --fixture text_basic/title_body_bullets --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-line-element-edit,wolfppt-facade-dropin-shape-line-element-edit --fixture text_basic/title_body_bullets --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-chart,wolfppt-facade-dropin-add-chart --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-bar-chart,wolfppt-facade-dropin-add-bar-chart --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-line-chart,wolfppt-facade-dropin-add-line-chart --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-pie-chart,wolfppt-facade-dropin-add-pie-chart --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-chart-template-family,wolfppt-facade-dropin-add-chart-template-family --fixture text_basic/title_body_bullets --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-add-connector,wolfppt-facade-dropin-add-connector --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-existing-connector-connection-edit,wolfppt-facade-dropin-existing-connector-connection-edit --fixture text_basic/title_body_bullets --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-connector-connection-edit,wolfppt-facade-dropin-connector-connection-edit --fixture text_basic/title_body_bullets --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-group-connector-connection-edit,wolfppt-facade-dropin-group-connector-connection-edit --fixture shapes/grouped_shapes --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-connector-line-style-edit,wolfppt-facade-dropin-connector-line-style-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-picture-crop-edit,wolfppt-facade-dropin-picture-crop-edit --fixture media/png_picture,workloads/mixed_real_world_deck --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-style-edit,wolfppt-facade-dropin-shape-style-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-theme-color-edit,wolfppt-facade-dropin-shape-theme-color-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-shadow-edit,wolfppt-facade-dropin-shape-shadow-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-hyperlink-edit,wolfppt-facade-dropin-shape-hyperlink-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-target-slide-edit,wolfppt-facade-dropin-shape-target-slide-edit --fixture slides/two_slide_text --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-target-new-slide-edit,wolfppt-facade-dropin-shape-target-new-slide-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-notes-text-edit,wolfppt-facade-dropin-notes-text-edit --fixture notes/speaker_notes --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-notes-background-edit,wolfppt-facade-dropin-notes-background-edit --fixture notes/speaker_notes --validate-openxml --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-text-run-hyperlink-edit,wolfppt-facade-dropin-text-run-hyperlink-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-fill-solid-edit,wolfppt-facade-dropin-shape-fill-solid-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-line-fill-background-edit,wolfppt-facade-dropin-shape-line-fill-background-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-patterned-fill-edit,wolfppt-facade-dropin-shape-patterned-fill-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-gradient-fill-edit,wolfppt-facade-dropin-shape-gradient-fill-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-rotation-edit,wolfppt-facade-dropin-shape-rotation-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-shape-name-edit,wolfppt-facade-dropin-shape-name-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-font-language-edit,wolfppt-facade-dropin-font-language-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-font-fill-edit,wolfppt-facade-dropin-font-fill-edit --fixture text_basic/title_body_bullets --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-text-frame-margin-edit,wolfppt-facade-dropin-text-frame-margin-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-text-frame-word-wrap-edit,wolfppt-facade-dropin-text-frame-word-wrap-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-text-frame-vertical-anchor-edit,wolfppt-facade-dropin-text-frame-vertical-anchor-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-text-frame-auto-size-edit,wolfppt-facade-dropin-text-frame-auto-size-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-text-frame-fit-text-edit,wolfppt-facade-dropin-text-frame-fit-text-edit --fixture text_basic/title_body_bullets,shapes/grouped_shapes --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-read,wolfppt-facade-dropin-chart-read --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-title-edit,wolfppt-facade-dropin-chart-title-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-legend-edit,wolfppt-facade-dropin-chart-legend-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-axis-title-edit,wolfppt-facade-dropin-chart-axis-title-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-axis-property-edit,wolfppt-facade-dropin-chart-axis-property-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-plot-property-edit,wolfppt-facade-dropin-chart-plot-property-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-data-label-edit,wolfppt-facade-dropin-chart-data-label-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-data-label-remove,wolfppt-facade-dropin-chart-data-label-remove --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-point-data-label-edit,wolfppt-facade-dropin-chart-point-data-label-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-style-edit,wolfppt-facade-dropin-chart-style-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-format-edit,wolfppt-facade-dropin-chart-format-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark --adapter python-pptx-dropin-chart-data-edit,wolfppt-facade-dropin-chart-data-edit --fixture charts/bar_chart --json
uv run wolfppt-harness benchmark-adapters
uv run wolfppt-harness matrix
uv run wolfppt-harness tools
cargo test
cargo run -p wolfppt-cli -- inspect fixtures/pptx/text_basic/title_body_bullets.pptx
cargo run -p wolfppt-cli -- summary fixtures/pptx/text_basic/title_body_bullets.pptx
cargo run -p wolfppt-cli -- roundtrip fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/title_body_bullets.pptx
cargo run -p wolfppt-cli -- add-slide fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/add_slide.pptx 0
cargo run -p wolfppt-cli -- replace-text fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/title_body_bullets.pptx WolfPPT "WolfPPT Native"
cargo run -p wolfppt-cli -- replace-text-in-slide fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/title_body_bullets.pptx 0 WolfPPT "WolfPPT Native"
cargo run -p wolfppt-cli -- replace-text-run fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/title_body_bullets.pptx 0 1 "Fast Native"
cargo run -p wolfppt-cli -- set-shape-text fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/title_body_bullets.pptx 0 1 "Fast Native"
cargo run -p wolfppt-cli -- set-paragraph-text fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/title_body_bullets.pptx 0 1 0 "Fast Native"
cargo run -p wolfppt-cli -- replace-image fixtures/pptx/media/png_picture.pptx /tmp/png_picture.pptx rId2 /tmp/image.png
cargo run -p wolfppt-cli -- replace-image-in-slide fixtures/pptx/media/png_picture.pptx /tmp/png_picture.pptx 0 rId2 /tmp/image.png
cargo run -p wolfppt-cli -- add-image fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/add_image.pptx 0 /tmp/image.png 0 0 914400 914400
cargo run -p wolfppt-cli -- replace-table-cell fixtures/pptx/tables/simple_table.pptx /tmp/simple_table.pptx 0 0 1 1 "2"
cargo run -p wolfppt-cli -- add-table fixtures/pptx/text_basic/title_body_bullets.pptx /tmp/add_table.pptx 0 2 3 0 0 2743200 914400
uv run maturin develop --manifest-path crates/wolfppt-py/Cargo.toml
uv run maturin develop --release --manifest-path crates/wolfppt-py/Cargo.toml
```

For performance claims involving `wolfppt_native`, rebuild the PyO3 module with
`uv run maturin develop --release --manifest-path crates/wolfppt-py/Cargo.toml`
before running benchmarks. Debug native builds are useful for development, but
their timings are not benchmark evidence.
For private corpora with source-invalid decks, add
`--min-source-invalid-preserved-samples N` to the `private-real-decks` profile
alongside `--validate-openxml` before claiming that WolfPPT preserves those exact
validator failures.

## Current Sprint

Built so far:

- compatibility spec source of truth in `docs/compatibility/_compat_spec.py`
- semantic extractor for PPTX package parts, relationships, slides, text, tables,
  pictures, charts, notes, and macro-package signals
- append-only result writer
- generated compatibility matrix renderer
- known-gaps sync tests
- deterministic Phase 1 fixture corpus generator using python-pptx-authored valid packages
- normalized package manifest and diff commands
- optional python-pptx baseline summary and round-trip commands
- Open XML SDK validator project and CLI wrapper
- LibreOffice PDF render smoke command
- corpus runner with semantic oracle, Open XML validation, optional python-pptx
  round-trip, optional LibreOffice render, Markdown/JSON reports, and append-only
  result rows
- repeatable benchmark runner with warmups, latency statistics, RSS snapshots,
  semantic/package correctness checks, JSON/Markdown reports, and append-only
  benchmark result rows
- Rust `wolfppt-core` package-inspection crate for listing OOXML parts and
  detecting VBA packages
- Rust `wolfppt-cli` bridge and Python adapter for invoking the Rust reader
  from the harness
- optional Microsoft PowerPoint PNG export adapter for the gold visual oracle
- optional `wolfppt_native` PyO3 binding for direct Python access to the Rust
  package reader and corpus-run lane
- typed Rust PresentationML summary for slide discovery, text runs, notes,
  tables, slide relationships, image/chart/comment/media/OLE relationship
  buckets, and transition/timing flags
- typed Rust and semantic-oracle extraction for shape trees, grouped shapes,
  child shapes, local transforms, and inherited effective transforms
- native Python access to the Rust typed presentation summary
- Rust-vs-Python semantic parity comparison for typed native summaries
- Rust CLI and native binding package round-trip lanes that prove part-level
  preservation with semantic and package diffs
- explicit OLE object fixture coverage for slide-level `oleObject`
  relationships and embedded binary preservation
- Rust CLI and native binding blank-slide append using either the first slide's
  layout relationship or a selected existing layout index, with editable
  placeholder materialization, corpus mutation lanes checking slide count,
  package delta, and Open XML validation when the validator is available
- Rust CLI and native binding exact slide-text replacement across all slides or
  scoped to a selected slide index, selected text-run replacement, and selected
  shape-level text setting with newline-separated text-frame paragraphs, plus
  selected paragraph text setting while preserving unrelated package parts
- Rust CLI and native binding replacement of an existing slide image
  relationship payload globally or scoped to a selected slide index while
  preserving package relationships, plus new PNG/JPEG/GIF picture-shape
  insertion with explicit EMU bounds
- Rust CLI and native binding basic empty-table insertion with explicit EMU
  bounds and table-cell text replacement by slide/table/row/column index while
  preserving unrelated package parts
- legacy comment fixture coverage with comment/comment-author parts preserved by
  Rust CLI/native round-trip package diffs
- chart fixture coverage with embedded workbook preservation verified by Rust
  CLI/native round-trip package diffs
- OLE object fixture coverage with embedded binary preservation verified by
  Rust CLI/native round-trip package diffs
- transition fixture coverage with Open XML validation and Rust CLI/native
  round-trip preservation
- animation timing-tree fixture coverage with Open XML validation and Rust
  CLI/native round-trip preservation
- grouped-shape fixture coverage with inherited transform semantics
- Rust-vs-Python semantic parity now compares shape tree facts, so grouped
  shape support is enforced in native summary corpus lanes
- public `wolfppt.Presentation` facade with python-pptx-style blank-deck
  construction, slide/shape iteration, and `shape.text` edits saved through the
  native Rust mutation path
- dynamic public-surface ratchet comparing common WolfPPT facade objects and
  all checked-in real-fixture shape objects against python-pptx public names
  and public read access, exposed as `uv run wolfppt-harness
  python-api-surface --json`; release-style runs can require minimum
  fixture/object-pair counts and write latest plus archived evidence under
  `results/api-surface/`
- read-only python-pptx-style `.part` metadata for presentations, slide
  collections, slides, slide layouts, shape/placeholder collections, shapes,
  actions, text objects, charts, and tables, including `partname`,
  `content_type`, `blob`, `part`, and `package`
- `Presentation.slide_width` and `Presentation.slide_height` reads/writes with
  python-pptx parity, package-delta checks, and a dedicated slide-size
  benchmark lane
- `Presentation.core_properties` reads/writes for common document metadata,
  including title, subject, author, keywords, comments, revision, timestamps,
  and status fields, with changes isolated to `docProps/core.xml` and covered
  by a dedicated benchmark lane
- `slide.slide_id`, `slide.slide_layout`, `slide.follow_master_background`,
  `slide.has_notes_slide`, `slides.get(...)`, and `slide.name` reads/writes
  with python-pptx parity, target-slide package-delta checks, and a dedicated
  drop-in slide-name benchmark lane
- existing `slide.notes_slide`, `notes_slide.notes_text_frame`, notes
  shapes/placeholders, and `Presentation.notes_master` reads with
  python-pptx parity for packages that already contain notes parts
- `notes_slide.notes_text_frame.text`, paragraph, and run edits with dedicated
  drop-in benchmarks that change only the target notes-slide XML part
- `notes_slide.clone_master_placeholders(...)` and
  `notes_slide.shapes.clone_placeholder(...)` coverage with notes-placeholder
  metadata parity and changes isolated to the target notes-slide XML part
- `slide.background`, layout/background, slide-master/background, and
  notes-master/background reads for element metadata and fill state, plus
  `slide.background.fill.solid()`, layout/master `.background.fill.solid()`,
  `.background()`, and foreground RGB/theme-color/brightness edits isolated to
  the target XML part
- `Presentation.slide_master`, `Presentation.slide_masters`, slide-master
  layout, shape, and placeholder metadata, and unused
  `Presentation.slide_layouts.remove(...)` for template cleanup workflows
- empty `shape.text = ""` and `shape.text_frame.clear()` keep python-pptx's
  one-empty-paragraph runtime semantics while saving through native Rust
- `slide.shapes.title`, `slide.placeholders`, and `placeholder_format`
  metadata backed by Rust placeholder extraction and a python-pptx parity probe
- `shape.left`, `shape.top`, `shape.width`, and `shape.height` reads/writes
  routed through native Rust with a python-pptx parity probe
- `shape.text_frame.paragraphs[index].text` routed through native Rust with a
  python-pptx parity probe for paragraph-level text edits
- `shape.text_frame.paragraphs[index].clear()` removes paragraph content while
  preserving empty-paragraph positions and paragraph properties
- `shape.text_frame.paragraphs[index].add_line_break()` inserts DrawingML line
  breaks while preserving python-pptx's `\v` paragraph text semantics
- `shape.text_frame.fit_text(...)` sets word-wrap, auto-size, and run font
  properties with python-pptx parity for stable font-file-backed cases
- `shape.text_frame.paragraphs[index].font` exposes paragraph default run
  properties for bold, italic, underline, size, name, RGB color, fill, and language
- paragraph alignment, level, and spacing reads/writes for existing and
  appended paragraphs with python-pptx parity probes and package-delta checks
- `shape.text_frame.paragraphs[index].runs[index].text`, `run.font.bold`,
  `run.font.italic`, `run.font.underline`, `run.font.size`,
  `run.font.name`, `run.font.color.rgb`, rich `run.font.fill`, and
  `run.font.language_id`
  reads/writes, including solid/background/patterned/gradient fill modes,
  paragraph appends, appended-paragraph run formatting, and run appends routed
  through native Rust plus slide XML patches with python-pptx parity probes
- `Presentation.slide_layouts` and `slides.add_slide(layout)` routed through
  native Rust with a python-pptx parity probe for blank-slide insertion
- `slide.shapes.add_textbox(...)` routed through native Rust with a python-pptx
  parity probe for text box insertion, immediate shape IDs, and immediate text edits
- `slide.shapes.add_shape(...)` for common preset autoshapes routed through
  native Rust with python-pptx parity probes for immediate shape IDs, preset
  geometry, pending style defaults, and text edits
- `shape.auto_shape_type` reads for supported preset autoshapes, matching
  python-pptx's non-autoshape error behavior
- `shape.adjustments` reads/writes for supported preset autoshapes at slide
  level and inside grouped shapes, including rounded-rectangle adjustment guide
  persistence with benchmark coverage
- `shape.ln` and `shape.get_or_add_ln()` line XML helpers for shape elements,
  matching python-pptx's low-level line-element surface
- `shape.shape_type` reads for text boxes and common shape classes, including
  python-pptx's TEXT_BOX vs AUTO_SHAPE distinction
- `shape.shadow.inherit` reads/writes for shape shadow inheritance toggles with
  python-pptx parity probes and package-delta checks
- `shape.click_action.hyperlink.address` reads/writes for external hyperlinks,
  changing only the target slide XML and slide relationship part
- `shape.click_action.target_slide` reads/writes for internal slide jumps,
  changing only the target slide XML and slide relationship part
- `run.hyperlink.address` reads/writes for external text-run hyperlinks,
  changing only the target slide XML and slide relationship part
- `slide.shapes.add_picture(...)` routed through native Rust with python-pptx
  parity probes for immediate shape IDs and explicit, native, or proportionally
  inferred picture bounds
- `slide.shapes.add_connector(...)` routed through native Rust with python-pptx
  parity probes for straight, elbow, and curve connector presets; connector
  `shape_id`, `begin_x`, `begin_y`, `end_x`, and `end_y` reads match
  python-pptx, and slide-level `begin_connect()` / `end_connect()` attachments
  persist for saved and newly added target shapes with benchmark coverage
- connector `line.color.rgb`, `line.width`, and `line.dash_style` reads/writes
  with python-pptx parity probes and package-delta checks
- picture `crop_left`, `crop_right`, `crop_top`, and `crop_bottom` reads/writes
  for existing picture elements with python-pptx parity probes and package-delta
  checks
- `shape.has_table`, `shape.table`, and `table.cell(...).text` routed through
  native Rust with a python-pptx parity probe for table cell edits
- `table.cell(...).text_frame` text, paragraphs, add/clear, wrapping, autosize,
  fit XML, cell margins, and vertical anchors with parity/package-delta checks
- `table.cell(...).fill` solid/background fills and foreground RGB with
  python-pptx parity probes and package-delta checks
- `table.cell(...).merge(...)`, `.split()`, and span metadata with python-pptx
  parity probes and package-delta checks
- table `first_row`, `first_col`, `last_row`, `last_col`, `horz_banding`,
  `vert_banding`, and `iter_cells()` with python-pptx parity probes
- `slide.shapes.add_table(...)` routed through native Rust with a python-pptx
  parity probe for basic table insertion and immediate cell edits
- `slide.shapes.add_chart(...)` and `group.shapes.add_chart(...)` add common
  category chart families, including column, bar, line, and pie variants, by
  transplanting packaged chart templates into the original package with
  python-pptx parity and package-delta checks, including no-series,
  empty-series, sparse category, hierarchical category, and XY/bubble data, without importing python-pptx
  at save time
- `shape.chart.element`, `chart.plots`, `chart.chart_style`, and
  `chart.chart_title.has_text_frame`, plus read-only chart/axis format,
  chart-font, major-gridline, tick-label, and category-axis type proxies with
  python-pptx parity and benchmark coverage
- `shape.chart.replace_data(CategoryChartData/XyChartData/BubbleChartData)` for
  category, XY scatter, and bubble charts, including series-count changes and
  sparse and hierarchical category data and uneven XY/bubble point counts, with python-pptx
  parity probes and package-delta checks
- `shape.chart.has_title` and `shape.chart.chart_title.text_frame.text` for
  chart title creation/removal with python-pptx parity probes and package-delta
  checks
- `shape.chart.has_legend`, `shape.chart.legend.position`, and
  `shape.chart.legend.include_in_layout` for chart legend creation/removal with
  python-pptx parity probes and package-delta checks
- `shape.chart.category_axis.axis_title.text_frame.text` and
  `shape.chart.value_axis.axis_title.text_frame.text` for chart axis title
  creation/removal with python-pptx parity probes and package-delta checks
- `shape.chart.category_axis` / `value_axis` visibility, gridline flags,
  tick marks, tick-label position, reverse-order, scale, and value-axis unit
  and crossing edits with python-pptx parity probes and package-delta checks
- `shape.chart` title, axis-title, plot/series data-label, and point-label
  paragraph/run font fills cover solid, background, patterned, and gradient
  modes with python-pptx parity probes and benchmark coverage
- `shape.fill.solid()`, `shape.fill.fore_color.rgb`, and
  `shape.fill.gradient()` / `shape.fill.gradient_angle` /
  `shape.fill.gradient_stops`, plus
  `shape.fill.background()` / `shape.fill.patterned()` /
  `shape.fill.pattern` / `shape.fill.back_color.rgb`, plus
  `shape.line.color.rgb` /
  `shape.line.fill.solid()` / `shape.line.fill.background()` /
  `shape.line.fill.patterned()` / `shape.line.fill.pattern` /
  `shape.line.fill.fore_color.rgb` / `shape.line.fill.back_color.rgb` /
  `shape.line.width` / `shape.line.dash_style` for existing shape elements
  with python-pptx parity probes and package-delta checks
- `shape.rotation` for existing shape elements with python-pptx parity probes,
  Open XML validation, and package-delta checks
- `shape.name` for template-oriented shape identification workflows with
  python-pptx parity probes, Open XML validation, and package-delta checks
- `shape.text_frame.margin_left/right/top/bottom` for text-box layout control
  with python-pptx parity probes, Open XML validation, and package-delta checks
- `shape.text_frame.word_wrap` for text-box layout control with python-pptx
  parity probes, Open XML validation, and package-delta checks
- `shape.text_frame.vertical_anchor` for text-box layout control with
  python-pptx parity probes, Open XML validation, and package-delta checks

Planned next:

See the [WolfPPT Roadmap](docs/roadmap.md) for the active dependency-ordered
epics (Epics 0 through 5), north star principles, and development protocol.

## Release readiness

Public releases are cut with the operator checklist in
[docs/release/PUBLISH_CHECKLIST.md](docs/release/PUBLISH_CHECKLIST.md):
freeze the candidate commit, produce the platform evidence card with
`wolfppt-harness release-candidate --strict`, gate on a green detached
claims job at the exact frozen head, and only then publish. The checklist
defines the full gate order and the evidence to record at each step.

## License

MIT — see [LICENSE](LICENSE).

## Security

See [SECURITY.md](SECURITY.md). WolfPPT makes no network requests and
collects no telemetry. Macro-enabled `.pptm` packages are supported: VBA
projects are preserved byte-for-byte as opaque data and are never authored,
interpreted, or executed.
