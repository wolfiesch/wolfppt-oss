# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
