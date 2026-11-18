"""Public CLI for native PPTX encryption, decryption, and XMLDSIG signing.

``wolfppt-harness encrypt --request FILE`` and ``wolfppt-harness decrypt
--request FILE`` run one strict, source-bound request over one presentation.
Their request file holds exactly ``source``, ``destination``, ``source_sha256``,
and ``password_env``; the credential itself is read from that named environment
variable only while the operation executes and never appears in the report.

``wolfppt-harness signature-inspect --request FILE`` returns success only for a
registered RSA/SHA-256 XMLDSIG that covers every non-signature package part.
``wolfppt-harness signature-sign --request FILE`` adds an RSA/X.509 ECMA-376
package signature. Its request names ``source``, ``destination``,
``source_sha256``, ``certificate``, ``private_key``, and an optional
``private_key_password_env``.

Exactly one JSON security report is printed to stdout, and the exit status
carries the outcome: ``0`` when inspection completed or verified output was
published, ``2`` when the operation refused and the destination was left alone.
A request that cannot be named, read, or parsed is the same refusal - one
content-safe report on stdout with ``{operation}_request_invalid`` and the same
``2`` - while the parser's own help and usage behavior is untouched.

Encryption produces a standard Agile-encrypted OLE/CFB container from the
admitted package bytes and decryption produces the admitted plaintext package;
both preserve those bytes exactly.  Signing preserves every ordinary package
part and publishes only after reopening and cryptographically re-verifying the
staged XMLDSIG. Publication is a private sibling staging file plus an atomic
``os.link`` no-replace commit, so an existing destination, a dangling symbolic
link, the source itself, and a destination created while the operation runs are
all refused instead of overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .security import (
    OPERATIONS,
    SIGNATURE_OPERATIONS,
    WRITE_PROTECTION_OPERATIONS,
    PptxSecurityReport,
    PptxSecurityRequest,
    PptxSignatureInspectionReport,
    PptxSignatureInspectionRequest,
    PptxSignatureReport,
    PptxSignatureRequest,
    PptxWriteProtectionRequest,
    decrypt_pptx,
    encrypt_pptx,
    inspect_pptx_signatures,
    load_pptx_security_request,
    load_pptx_signature_inspection_request,
    load_pptx_signature_request,
    load_pptx_write_protection_request,
    sign_pptx,
    write_protection_pptx,
)

_COMMAND_HELP = {
    "encrypt": (
        "encrypt one admitted PPTX package into an Agile-encrypted container "
        "(exit 0 published, 2 refused)"
    ),
    "decrypt": (
        "decrypt one Agile-encrypted container into its admitted PPTX package "
        "(exit 0 published, 2 refused)"
    ),
    "write-protection": (
        "set or remove PresentationML write protection and a read-only recommendation "
        "(exit 0 published, 2 refused)"
    ),
    "signature-inspect": (
        "verify registered OPC XMLDSIG package coverage and signer metadata "
        "(exit 0 verified, 2 unsigned, invalid, or refused)"
    ),
    "signature-sign": (
        "sign one admitted PPTX package with an RSA X.509 certificate "
        "(exit 0 published, 2 refused)"
    ),
}


def register_security_commands(sub: argparse._SubParsersAction[Any]) -> None:
    """Register source-bound encryption and XMLDSIG signature commands."""

    for operation in (*OPERATIONS, *WRITE_PROTECTION_OPERATIONS, *SIGNATURE_OPERATIONS):
        parser = sub.add_parser(
            operation,
            help=_COMMAND_HELP[operation],
            description=(
                f"Run one source-bound {operation} request and print exactly one "
                "JSON security report. The request names paths and a source SHA-256; "
                "a signing request also names certificate and private-key paths."
            ),
        )
        parser.add_argument(
            "--request",
            type=Path,
            help="JSON request file in the exact documented shape for this operation",
        )


def _run(
    operation: str,
    request: PptxSecurityRequest
    | PptxWriteProtectionRequest
    | PptxSignatureInspectionRequest
    | PptxSignatureRequest,
) -> PptxSecurityReport | PptxSignatureInspectionReport | PptxSignatureReport:
    if operation == "encrypt":
        return encrypt_pptx(request)  # type: ignore[arg-type]
    if operation == "decrypt":
        return decrypt_pptx(request)  # type: ignore[arg-type]
    if operation == "write-protection":
        return write_protection_pptx(request)  # type: ignore[arg-type]
    if operation == "signature-inspect":
        return inspect_pptx_signatures(request)  # type: ignore[arg-type]
    return sign_pptx(request)  # type: ignore[arg-type]


def _request_refusal(operation: str, recovery: str) -> dict[str, Any]:
    """Return the operation's report shape when its request cannot be read."""

    base: dict[str, Any] = {
        "schema_version": 1,
        "operation": operation,
        "passed": False,
        "status": "refused",
        "code": f"{operation}_request_invalid",
        "source_sha256": None,
        "recovery": recovery,
    }
    if operation in (*OPERATIONS, *WRITE_PROTECTION_OPERATIONS):
        return {
            **base,
            "password_env": None,
            "encryption_scheme": None,
            "destination_sha256": None,
        }
    if operation == "signature-inspect":
        return {**base, "signatures": []}
    return {**base, "destination_sha256": None, "signer": None}


def _print_report(payload: Mapping[str, Any]) -> None:
    """Print exactly one JSON security report on stdout."""

    print(json.dumps(payload, indent=2, sort_keys=True))


def handle_security_command(args: argparse.Namespace) -> int:
    """Run one encryption, decryption, or XMLDSIG request as JSON."""

    operation = getattr(args, "command", "")
    if operation not in (
        *OPERATIONS,
        *WRITE_PROTECTION_OPERATIONS,
        *SIGNATURE_OPERATIONS,
    ):
        print(
            f"security commands are {', '.join((*OPERATIONS, *WRITE_PROTECTION_OPERATIONS, *SIGNATURE_OPERATIONS))}",
            file=sys.stderr,
        )
        return 2
    request_path = getattr(args, "request", None)
    if request_path is None:
        _print_report(
            _request_refusal(
                operation,
                "Name the JSON request file with --request in the documented shape.",
            )
        )
        return 2
    loaders = {
        "encrypt": load_pptx_security_request,
        "decrypt": load_pptx_security_request,
        "write-protection": load_pptx_write_protection_request,
        "signature-inspect": load_pptx_signature_inspection_request,
        "signature-sign": load_pptx_signature_request,
    }
    try:
        request = loaders[operation](request_path)
    except (OSError, TypeError, ValueError):
        _print_report(
            _request_refusal(
                operation,
                "Supply a readable UTF-8 JSON request file in the documented shape.",
            )
        )
        return 2
    report = _run(operation, request)
    _print_report(report.to_dict())
    return 0 if report.passed else 2


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point so the commands run without the harness parser."""

    parser = argparse.ArgumentParser(
        prog="python -m wolfppt.cli_security",
        description=__doc__,
    )
    register_security_commands(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(argv)
    return handle_security_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
