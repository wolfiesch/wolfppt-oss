# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.2] - 2026-10-02

### Fixed
- Index `paragraph.runs` like python-pptx: every `a:r` is a run, including runs with empty text, and `a:fld` fields are not runs. Run text edits on paragraphs that start with an empty run or contain fields now land on the run python-pptx edits, and field text is kept.
- `chart.replace_data(...)` writes the new values into the chart's existing embedded workbook instead of swapping in a generated one, so the workbook keeps its parts, theme, styles, column widths and sheet view, its cells agree with the chart caches, and cells the chart no longer reads are cleared.

## [0.1.1] - 2026-09-30

### Changed
- Lead the README and PyPI description with editing existing decks, a verified example, and a python-pptx comparison.
- Point the PyPI Homepage and Repository links at wolfppt.com and the public repository.

### Fixed
- Include LICENSE in the source distribution, so the sdist publishes alongside the wheels.

## [0.1.0] - 2026-09-04

### Added
- Support slide duplication with configurable copy policies for media, comments, charts, notes, OLE objects, and external relationships.
- Support slide deletion across single slide parts, slide slices, and pending creations before save.
- Support nested group shape child deletion with native batch coalescing.
- Expose row and column mutation on table facades and presentation save pipelines.
- Expose slide reorder and shape deletion operations.
- Add packaging and build readiness with Maturin PEP 517 build backend and native PyO3 wheel distribution.
- Add MIT license, security policy, and runtime package positioning.
- Add `wolfppt demo` surgical-edit demo with verification receipt and refused-commit path.
- Add `wolfppt-harness release-candidate` evidence card aggregating build, test, corpus, demo, and audit rows.
- Add `scripts/build-release-artifacts.sh` producing verified platform wheels with the native PyO3 module.
- Reposition the README for the editing-runtime product and add the release publish checklist.

### Changed
- Harden mutation guards for slide duplication and table modifications.
- Tighten guard errors and drop unused helpers across native mutation paths.
- Upgrade PyO3 dependency to 0.29.
- Bump Pillow dependency to 12.3.0.
- Coalesce notes slide edit passes and cache notes XML and text formatting property inspection.
- Collect benchmark cycles between samples for latency evidence.
