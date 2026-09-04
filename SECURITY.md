# Security Policy

## Scope

WolfPPT reads, edits, and writes PowerPoint Open XML packages (`.pptx`,
`.pptm`). Parsing and mutation run on untrusted input by design, so the
following are in scope for security reports:

- Memory-safety or panic issues in the Rust core triggered by malformed
  packages.
- Corruption or silent data loss of unrelated package parts during a
  requested edit or save.
- Zip-bomb and decompression-bomb handling during package reads.
- Path traversal or arbitrary file write outside the requested destination
  during save or render helpers.
- Command injection through harness subprocess lanes.

Out of scope:

- Executing embedded VBA macros. WolfPPT preserves `.pptm` macro parts
  byte-for-byte as opaque data; it never authors, interprets, or executes
  macro code.
- Rendering fidelity bugs that do not corrupt the package.
- Denial of service through pathologically large but structurally valid
  decks on under-provisioned hardware.

## Telemetry

WolfPPT makes no network requests and collects no telemetry. Optional
external tool lanes (Open XML SDK validation, LibreOffice rendering,
commercial SDK comparisons) invoke locally installed binaries only.

## Reporting a vulnerability

Report privately via GitHub security advisories
(`https://github.com/wolfiesch/wolfppt/security/advisories/new`) or email
`security@wolfie.gg`. Include a minimal reproducing package where possible.
Please do not open public issues for suspected corrupt-output or
security-sensitive behavior. Reports are acknowledged within 7 days.
