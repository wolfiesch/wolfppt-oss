"""Source-bound PPTX encryption, write protection, and package signatures.

Encryption and decryption preserve admitted package bytes exactly.  Write
protection edits only the schema-defined ``p:modifyVerifier`` in
``ppt/presentation.xml`` and the standard ``ap:DocSecurity`` extended property;
all other source parts are copied unchanged.  Every mutable route uses a
private, mode-restricted verification staging, then copies the exact verified
byte stream into a descriptor-bound protected staging inode before hard-linking
the result without replacing an existing destination.

Credentials are named by environment variable and never appear in a request
report or log.  Encryption remains an optional, version-qualified dependency;
write protection uses only the standard library and is metadata, not
confidentiality or access control.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import secrets
import stat
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, BinaryIO, NamedTuple
from xml.etree import ElementTree as ET

from .package_limits import (
    PPTX_PACKAGE_LIMITS as PPTX_SECURITY_LIMITS,
)
from .package_limits import (
    PptxPackageLimits,
    _zip_envelope_refusal,
)
from .render_package import Package, PackageRefusal, read_package_bytes, resolve_target
from .shape_tree import (
    P_NS,
)

MSOFFCRYPTO_DISTRIBUTION = "msoffcrypto-tool"
"""The optional provider distribution this surface is qualified against."""

MSOFFCRYPTO_VERSION = "5.4.2+wolfoffice.1"
"""The exact qualified provider version; any other version is refused."""

ENCRYPTED_EXTRA = "encrypted"
"""The optional extra that installs the qualified provider."""

AGILE = "agile"
"""The one encryption scheme whose payload integrity this surface verifies."""

PRESENTATION_PART = "ppt/presentation.xml"
"""The PresentationML main part every admitted package must carry."""

ENCRYPTION_INFO_STREAM = "EncryptionInfo"
"""The CFB stream holding one container's encryption scheme header."""

ENCRYPTED_PACKAGE_STREAM = "EncryptedPackage"
"""The CFB stream holding the encrypted plaintext and its declared length."""

OPERATIONS = ("encrypt", "decrypt")
"""The two operations this surface exposes."""

SIGNATURE_OPERATIONS = ("signature-inspect", "signature-sign")
"""The two XMLDSIG package-signature operations this surface exposes."""

WRITE_PROTECTION_OPERATIONS = ("write-protection",)
"""The source-bound PresentationML modification-protection operation."""

_DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_OFFICE_DIGSIG_NS = "http://schemas.microsoft.com/office/2006/digsig"
_PACKAGE_DIGSIG_NS = "http://schemas.openxmlformats.org/package/2006/digital-signature"
_XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_SIGNATURE_ORIGIN_REL = "http://schemas.openxmlformats.org/package/2006/relationships/digital-signature/origin"
_SIGNATURE_REL = "http://schemas.openxmlformats.org/package/2006/relationships/digital-signature/signature"
_SIGNATURE_ORIGIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-package.digital-signature-origin"
)
_SIGNATURE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-package.digital-signature-xmlsignature+xml"
)
_INCLUSIVE_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_RELATIONSHIP_TRANSFORM = (
    "http://schemas.openxmlformats.org/package/2006/RelationshipTransform"
)
_DS_OBJECT_TYPE = "http://www.w3.org/2000/09/xmldsig#Object"
_XADES_SIGNED_PROPERTIES_TYPE = "http://uri.etsi.org/01903#SignedProperties"
_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
_SHA256_DIGEST = "http://www.w3.org/2001/04/xmlenc#sha256"
_SIGNATURE_PREFIX = "_xmlsignatures/"
_SIGNATURE_ORIGIN_PART = "_xmlsignatures/origin.sigs"
_SIGNATURE_ORIGIN_RELS = "_xmlsignatures/_rels/origin.sigs.rels"
_SIGNATURE_PART = "_xmlsignatures/sig1.xml"
_SIGNATURE_INPUT_LIMIT = 16 * 1024 * 1024
_SIGN_REQUEST_FIELDS = frozenset(
    {
        "source",
        "destination",
        "source_sha256",
        "certificate",
        "private_key",
        "private_key_password_env",
    }
)
_INSPECTION_REQUEST_FIELDS = frozenset({"source", "source_sha256"})

_PUBLISHED = "published"
_REFUSED = "refused"
_SHA256_LENGTH = 64
_PLAINTEXT_SIZE_HEADER_BYTES = 8
_DIGEST_CHUNK_BYTES = 1 << 20
_PRESENTATION_MAIN_CONTENT_TYPES = frozenset(
    {
        (
            "application/vnd.openxmlformats-officedocument.presentationml."
            "presentation.main+xml"
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml."
            "template.main+xml"
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml."
            "slideshow.main+xml"
        ),
        "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml",
        "application/vnd.ms-powerpoint.template.macroEnabled.main+xml",
        "application/vnd.ms-powerpoint.slideshow.macroEnabled.main+xml",
    }
)
_REQUEST_FIELDS = frozenset({"source", "destination", "source_sha256", "password_env"})
_WRITE_PROTECTION_REQUEST_FIELDS = frozenset(
    {
        "source",
        "destination",
        "source_sha256",
        "action",
        "password_env",
        "read_only_recommended",
    }
)
_WRITE_PROTECTION_ACTIONS = frozenset({"set", "remove"})
_EXTENDED_PROPERTIES_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
)
_EXTENDED_PROPERTIES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
_EXTENDED_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.extended-properties+xml"
)
_EXTENDED_PROPERTIES_PART = "docProps/app.xml"
_DOC_SECURITY_PASSWORD = 1
_DOC_SECURITY_READ_ONLY_RECOMMENDED = 2
_DOC_SECURITY_KNOWN_MASK = 15
_MODIFY_VERIFIER_SPIN_COUNT = 100_000
_MODIFY_VERIFIER_SALT_BYTES = 16
_MODIFY_VERIFIER_MAX_PASSWORD_CHARACTERS = 255
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SCHEME_BY_VERSION = {
    (2, 2): "standard",
    (3, 2): "standard",
    (4, 2): "standard",
    (3, 3): "extensible",
    (4, 3): "extensible",
    (4, 4): AGILE,
}

_CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
"""The OLE/CFB signature every encrypted ECMA-376 container starts with."""
_SCHEME_VERSION_BYTES = 4
"""The scheme version header bytes read from the EncryptionInfo stream."""

_MISSING_DEPENDENCY_RECOVERY = (
    f'Install the "{ENCRYPTED_EXTRA}" extra to add the qualified provider: '
    f'pip install "wolfppt[{ENCRYPTED_EXTRA}]".'
)
_UNQUALIFIED_DEPENDENCY_RECOVERY = (
    f"Remove the unqualified provider and install the qualified artifact "
    f"{MSOFFCRYPTO_DISTRIBUTION}=={MSOFFCRYPTO_VERSION}, for example through "
    f'pip install "wolfppt[{ENCRYPTED_EXTRA}]".'
)
_MISSING_CREDENTIAL_RECOVERY = (
    "Export the named environment variable with the presentation password in the "
    "environment that runs this operation."
)
_BLANK_CREDENTIAL_RECOVERY = (
    "The named environment variable is empty; set it to the presentation password or "
    "name a different variable."
)
_INVALID_CREDENTIAL_NAME_RECOVERY = (
    f"Name an environment variable that matches {_ENVIRONMENT_NAME.pattern} in the "
    "request's password_env."
)
_NOT_ENCRYPTED_RECOVERY = (
    "The source is an unencrypted package; encrypt it first or name an "
    "Agile-encrypted container."
)
_SCHEME_RECOVERY = (
    "Only the Agile scheme carries verifiable payload integrity; re-encrypt this "
    "presentation as Agile."
)
_PASSWORD_RECOVERY = (
    "The named environment variable does not hold this presentation's password; use "
    "the password the container was encrypted with."
)
_INTEGRITY_RECOVERY = (
    "The ciphertext failed payload integrity verification; restore the original "
    "container from a trusted copy."
)
_PUBLICATION_RECOVERIES = {
    "staging_unavailable": (
        "The destination directory refused this surface's private staging file, so "
        "nothing was written; check that the directory exists, is writable, and has "
        "free space, then retry."
    ),
    "verification": (
        "The staged output could not be re-read for verification, so nothing was "
        "published; retry against a destination the process can read and write."
    ),
    "publication_unavailable": (
        "The filesystem could not hard-link the verified staged file into place; "
        "this surface never falls back to a replacing rename, so publish to a "
        "destination on a filesystem that supports hard links."
    ),
}


@dataclass(frozen=True)
class PptxSecurityRequest:
    source: Path
    destination: Path
    source_sha256: str
    password_env: str | None


@dataclass(frozen=True)
class PptxSecurityReport:
    operation: str
    status: str
    code: str | None
    source_sha256: str
    password_env: str | None
    destination_sha256: str | None = None
    encryption_scheme: str | None = None
    recovery: str | None = None

    @property
    def passed(self) -> bool:
        """Return whether the operation published its verified output."""
        return self.status == _PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        """Return the machine-readable report in one stable key order."""
        return {
            "schema_version": 1,
            "operation": self.operation,
            "passed": self.passed,
            "status": self.status,
            "code": self.code,
            "source_sha256": self.source_sha256,
            "password_env": self.password_env,
            "encryption_scheme": self.encryption_scheme,
            "destination_sha256": self.destination_sha256,
            "recovery": self.recovery,
        }


@dataclass(frozen=True)
class PptxWriteProtectionRequest(PptxSecurityRequest):
    action: str
    read_only_recommended: bool | None


@dataclass(frozen=True)
class PptxSignatureInspectionRequest:
    source: Path
    source_sha256: str


@dataclass(frozen=True)
class PptxSignatureRequest:
    source: Path
    destination: Path
    source_sha256: str
    certificate: Path
    private_key: Path
    private_key_password_env: str | None


@dataclass(frozen=True)
class PptxDigitalSignature:
    part: str
    signer: str | None
    timestamp: str | None
    valid: bool | None
    code: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "part": self.part,
            "signer": self.signer,
            "timestamp": self.timestamp,
            "valid": self.valid,
            "code": self.code,
        }


@dataclass(frozen=True)
class PptxSignatureInspectionReport:
    status: str
    code: str | None
    source_sha256: str | None
    signatures: tuple[PptxDigitalSignature, ...]
    recovery: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.status == "inspected"
            and self.code is None
            and any(signature.valid is True for signature in self.signatures)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation": "signature-inspect",
            "passed": self.passed,
            "status": self.status,
            "code": self.code,
            "source_sha256": self.source_sha256,
            "signatures": [signature.to_dict() for signature in self.signatures],
            "recovery": self.recovery,
        }


@dataclass(frozen=True)
class PptxSignatureReport:
    status: str
    code: str | None
    source_sha256: str
    destination_sha256: str | None
    signer: str | None
    recovery: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == _PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation": "signature-sign",
            "passed": self.passed,
            "status": self.status,
            "code": self.code,
            "source_sha256": self.source_sha256,
            "destination_sha256": self.destination_sha256,
            "signer": self.signer,
            "recovery": self.recovery,
        }


class _Provider(NamedTuple):
    ole: Any
    ooxml_file: Any
    invalid_key_error: type[BaseException]
    decryption_error: type[BaseException]


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or any(character not in _HEX_DIGITS for character in value)
    ):
        raise ValueError(f"{label}_invalid")
    return value.lower()


def _require_environment_name(value: Any) -> str:
    if not isinstance(value, str) or _ENVIRONMENT_NAME.fullmatch(value) is None:
        raise ValueError("pptx_security_password_env_invalid")
    return value


def parse_pptx_security_request(value: Any) -> PptxSecurityRequest:
    if not isinstance(value, Mapping):
        raise TypeError("pptx_security_request_invalid")
    if set(value) != _REQUEST_FIELDS:
        raise ValueError("pptx_security_request_fields_invalid")
    source = value["source"]
    destination = value["destination"]
    if not isinstance(source, str) or not source:
        raise ValueError("pptx_security_source_invalid")
    if not isinstance(destination, str) or not destination:
        raise ValueError("pptx_security_destination_invalid")
    return PptxSecurityRequest(
        source=Path(source),
        destination=Path(destination),
        source_sha256=_require_sha256(
            value["source_sha256"], "pptx_security_source_sha256"
        ),
        password_env=_require_environment_name(value["password_env"]),
    )


def load_pptx_security_request(path: str | Path) -> PptxSecurityRequest:
    with Path(path).open(encoding="utf-8") as stream:
        return parse_pptx_security_request(json.load(stream))


def parse_pptx_write_protection_request(value: Any) -> PptxWriteProtectionRequest:
    if not isinstance(value, Mapping):
        raise TypeError("pptx_write_protection_request_invalid")
    if set(value) != _WRITE_PROTECTION_REQUEST_FIELDS:
        raise ValueError("pptx_write_protection_request_fields_invalid")
    source, destination, action = value["source"], value["destination"], value["action"]
    if not isinstance(source, str) or not source:
        raise ValueError("pptx_write_protection_source_invalid")
    if not isinstance(destination, str) or not destination:
        raise ValueError("pptx_write_protection_destination_invalid")
    if action not in _WRITE_PROTECTION_ACTIONS:
        raise ValueError("pptx_write_protection_action_invalid")
    password_env = value["password_env"]
    if password_env is not None:
        password_env = _require_environment_name(password_env)
    recommended = value["read_only_recommended"]
    if recommended is not None and not isinstance(recommended, bool):
        raise ValueError("pptx_write_protection_read_only_recommended_invalid")
    if action == "remove" and (password_env is not None or recommended is not None):
        raise ValueError("pptx_write_protection_remove_configuration_invalid")
    if action == "set" and password_env is None and recommended is None:
        raise ValueError("pptx_write_protection_set_configuration_missing")
    return PptxWriteProtectionRequest(
        source=Path(source),
        destination=Path(destination),
        source_sha256=_require_sha256(
            value["source_sha256"], "pptx_write_protection_source_sha256"
        ),
        password_env=password_env,
        action=action,
        read_only_recommended=recommended,
    )


def load_pptx_write_protection_request(path: str | Path) -> PptxWriteProtectionRequest:
    with Path(path).open(encoding="utf-8") as stream:
        return parse_pptx_write_protection_request(json.load(stream))


def parse_pptx_signature_inspection_request(
    value: Any,
) -> PptxSignatureInspectionRequest:
    if not isinstance(value, Mapping):
        raise TypeError("pptx_signature_inspection_request_invalid")
    if set(value) != _INSPECTION_REQUEST_FIELDS:
        raise ValueError("pptx_signature_inspection_request_fields_invalid")
    source = value["source"]
    if not isinstance(source, str) or not source:
        raise ValueError("pptx_signature_inspection_source_invalid")
    return PptxSignatureInspectionRequest(
        source=Path(source),
        source_sha256=_require_sha256(
            value["source_sha256"], "pptx_signature_inspection_source_sha256"
        ),
    )


def load_pptx_signature_inspection_request(
    path: str | Path,
) -> PptxSignatureInspectionRequest:
    with Path(path).open(encoding="utf-8") as stream:
        return parse_pptx_signature_inspection_request(json.load(stream))


def parse_pptx_signature_request(value: Any) -> PptxSignatureRequest:
    if not isinstance(value, Mapping):
        raise TypeError("pptx_signature_request_invalid")
    if set(value) != _SIGN_REQUEST_FIELDS:
        raise ValueError("pptx_signature_request_fields_invalid")
    source = value["source"]
    destination = value["destination"]
    certificate = value["certificate"]
    private_key = value["private_key"]
    if not isinstance(source, str) or not source:
        raise ValueError("pptx_signature_source_invalid")
    if not isinstance(destination, str) or not destination:
        raise ValueError("pptx_signature_destination_invalid")
    if not isinstance(certificate, str) or not certificate:
        raise ValueError("pptx_signature_certificate_invalid")
    if not isinstance(private_key, str) or not private_key:
        raise ValueError("pptx_signature_private_key_invalid")
    password_env = value["private_key_password_env"]
    if password_env is not None:
        password_env = _require_environment_name(password_env)
    return PptxSignatureRequest(
        source=Path(source),
        destination=Path(destination),
        source_sha256=_require_sha256(
            value["source_sha256"], "pptx_signature_source_sha256"
        ),
        certificate=Path(certificate),
        private_key=Path(private_key),
        private_key_password_env=password_env,
    )


def load_pptx_signature_request(path: str | Path) -> PptxSignatureRequest:
    with Path(path).open(encoding="utf-8") as stream:
        return parse_pptx_signature_request(json.load(stream))


def _refusal(
    operation: str,
    request: PptxSecurityRequest,
    code: str,
    *,
    recovery: str | None = None,
    scheme: str | None = None,
) -> PptxSecurityReport:
    return PptxSecurityReport(
        operation=operation,
        status=_REFUSED,
        code=code,
        source_sha256=request.source_sha256,
        password_env=request.password_env,
        recovery=recovery,
        encryption_scheme=scheme,
    )


def _published(
    operation: str,
    request: PptxSecurityRequest,
    destination_sha256: str,
    scheme: str | None,
) -> PptxSecurityReport:
    return PptxSecurityReport(
        operation=operation,
        status=_PUBLISHED,
        code=None,
        source_sha256=request.source_sha256,
        password_env=request.password_env,
        destination_sha256=destination_sha256,
        encryption_scheme=scheme,
    )


def _qualified_provider(
    operation: str, request: PptxSecurityRequest
) -> _Provider | PptxSecurityReport:
    try:
        installed = version(MSOFFCRYPTO_DISTRIBUTION)
    except PackageNotFoundError:
        return _refusal(
            operation,
            request,
            f"{operation}_dependency_missing",
            recovery=_MISSING_DEPENDENCY_RECOVERY,
        )
    if installed != MSOFFCRYPTO_VERSION:
        return _refusal(
            operation,
            request,
            f"{operation}_dependency_unqualified",
            recovery=_UNQUALIFIED_DEPENDENCY_RECOVERY,
        )
    try:
        import olefile
        from msoffcrypto import exceptions
        from msoffcrypto.format.ooxml import OOXMLFile
    except ImportError:
        return _refusal(
            operation,
            request,
            f"{operation}_dependency_missing",
            recovery=_MISSING_DEPENDENCY_RECOVERY,
        )
    return _Provider(
        ole=olefile,
        ooxml_file=OOXMLFile,
        invalid_key_error=exceptions.InvalidKeyError,
        decryption_error=exceptions.DecryptionError,
    )


def _resolve_password(
    operation: str, request: PptxSecurityRequest
) -> str | PptxSecurityReport:
    if _ENVIRONMENT_NAME.fullmatch(request.password_env) is None:
        return _refusal(
            operation,
            request,
            f"{operation}_password_env_invalid",
            recovery=_INVALID_CREDENTIAL_NAME_RECOVERY,
        )
    value = os.environ.get(request.password_env)
    if value is None:
        return _refusal(
            operation,
            request,
            f"{operation}_password_env_missing",
            recovery=_MISSING_CREDENTIAL_RECOVERY,
        )
    if not value:
        return _refusal(
            operation,
            request,
            f"{operation}_password_env_blank",
            recovery=_BLANK_CREDENTIAL_RECOVERY,
        )
    return value


def _source_guard(
    operation: str, request: PptxSecurityRequest
) -> tuple[Path, Path] | PptxSecurityReport:
    source = request.source.resolve()
    destination = request.destination
    if source == destination.resolve():
        return _refusal(operation, request, f"{operation}_source_destination_same")
    if not source.is_file():
        return _refusal(operation, request, f"{operation}_source_missing")
    if not destination.parent.is_dir():
        return _refusal(operation, request, f"{operation}_destination_parent_missing")
    return source, destination


def _snapshot(
    operation: str,
    request: PptxSecurityRequest,
    source: Path,
    limits: PptxPackageLimits,
) -> bytes | PptxSecurityReport:
    limit = limits.max_archive_size
    try:
        with source.open("rb") as stream:
            snapshot = stream.read(limit + 1)
    except OSError:
        return _refusal(operation, request, f"{operation}_source_unreadable")
    if len(snapshot) > limit:
        return _refusal(
            operation,
            request,
            f"{operation}_source_size_limit",
            recovery=(
                f"The source holds more than the {limit} byte package archive limit "
                f"this surface admits; the bound stopped the snapshot after "
                f"{len(snapshot)} bytes.  Use a smaller source package."
            ),
        )
    return snapshot


def _presentation_refusal(package: Package) -> str | None:

    payload = package.parts.get(PRESENTATION_PART)
    if payload is None:
        return "presentation_part_missing"
    roots = [
        relationship
        for relationship in package.part_rels("")
        if relationship.kind == "officeDocument" and not relationship.external
    ]
    if len(roots) != 1:
        return "presentation_relationship_mismatch"
    if resolve_target("", roots[0].target) != PRESENTATION_PART:
        return "presentation_relationship_mismatch"
    if package.content_type(PRESENTATION_PART) not in _PRESENTATION_MAIN_CONTENT_TYPES:
        return "presentation_content_type_invalid"
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return "presentation_part_malformed"
    if root.tag != f"{{{P_NS}}}presentation":
        return "presentation_part_root_invalid"
    return None


def _admitted_package(
    operation: str, source: Path, snapshot: bytes, digest: str
) -> Package | str:

    try:
        package = read_package_bytes(source, snapshot)
    except PackageRefusal:
        return f"{operation}_source_package_invalid"
    if package.digest != digest:
        return f"{operation}_source_hash_changed"
    reason = _presentation_refusal(package)
    if reason is not None:
        return f"{operation}_source_{reason}"
    return package


def _staged_plaintext_refusal(
    staged: Path, expected_sha256: str, limits: PptxPackageLimits
) -> str | None:

    try:
        with staged.open("rb") as stream:
            payload = stream.read(limits.max_archive_size + 1)
    except OSError:
        return "decrypt_staged_verification_failed"
    if len(payload) > limits.max_archive_size:
        return "decrypt_staged_verification_failed"
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        return "decrypt_staged_verification_failed"
    envelope = _zip_envelope_refusal(payload, limits)
    if envelope is not None:
        return f"decrypt_plaintext_{envelope.code}"
    try:
        package = read_package_bytes(staged, payload)
    except PackageRefusal:
        return "decrypt_plaintext_package_invalid"
    if package.digest != expected_sha256:
        return "decrypt_staged_verification_failed"
    reason = _presentation_refusal(package)
    if reason is not None:
        return f"decrypt_plaintext_{reason}"
    return None


def _reopened_plaintext(provider: _Provider, path: Path, password: str) -> bytes | None:
    try:
        with path.open("rb") as stream:
            office = provider.ooxml_file(stream)
            if not office.is_encrypted() or office.type != AGILE:
                return None
            office.load_key(password=password, verify_password=True)
            plaintext = io.BytesIO()
            office.decrypt(plaintext, verify_integrity=True)
    except Exception:  # noqa: BLE001 - an unverified staged container is a refusal
        return None
    return plaintext.getvalue()


def _provider_error_recovery(operation: str) -> str:
    return (
        f"The encryption provider failed while the {operation} operation used it; a "
        "provider message may quote the credential or the package contents, so this "
        "engine never repeats one.  Re-install the qualified encrypted extra and "
        "retry with a fresh copy of the file."
    )


def sha256_file(path: Path) -> str:

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_DIGEST_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _secure_directory_descriptor(
    directory: Path | str, *, parent_descriptor: int | None = None
) -> int | None:
    """Open one directory without following its final path component."""

    required_flags = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    if any(not hasattr(os, flag) for flag in required_flags):
        return None
    try:
        descriptor = os.open(
            directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_descriptor,
        )
    except OSError:
        return None
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            return None
    except OSError:
        os.close(descriptor)
        return None
    return descriptor


def _fsync_directory_descriptor(descriptor: int) -> None:
    try:
        os.fsync(descriptor)
    except OSError:
        pass


def _copy_verified_payload(
    source: Path, target_descriptor: int
) -> tuple[str, os.stat_result]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open("payload", flags, 0o600, dir_fd=target_descriptor)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            while chunk := input_stream.read(_DIGEST_CHUNK_BYTES):
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
            payload_stat = os.fstat(output.fileno())
    finally:
        if descriptor != -1:
            os.close(descriptor)
    return digest.hexdigest(), payload_stat


def _publish_staged(
    output: Path,
    write: Callable[[BinaryIO], str | None],
    verify: Callable[[Path], str | None],
    *,
    staging_code: str,
    verification_code: str,
    exists_code: str,
    unavailable_code: str,
) -> tuple[str | None, str | None]:
    """Publish the exact verified bytes through private descriptor-bound staging."""

    if not all(
        (
            os.open in os.supports_dir_fd,
            os.stat in os.supports_dir_fd,
            os.link in os.supports_dir_fd,
            os.unlink in os.supports_dir_fd,
            os.rmdir in os.supports_dir_fd,
        )
    ):
        return unavailable_code, None
    destination_descriptor = _secure_directory_descriptor(output.parent)
    if destination_descriptor is None:
        return unavailable_code, None
    stage_descriptor = -1
    stage_name: str | None = None
    stage_stat: os.stat_result | None = None
    try:
        try:
            os.stat(output.name, dir_fd=destination_descriptor, follow_symlinks=False)
            return exists_code, None
        except FileNotFoundError:
            pass
        except OSError:
            return unavailable_code, None

        try:
            verification_context = tempfile.TemporaryDirectory(
                prefix="wolfppt-security-"
            )
        except OSError:
            return staging_code, None
        with verification_context as directory:
            verification_directory = Path(directory)
            try:
                os.chmod(verification_directory, 0o700)
            except OSError:
                return staging_code, None
            staged = verification_directory / "payload"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
            descriptor = -1
            try:
                descriptor = os.open(staged, flags, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    descriptor = -1
                    if (code := write(stream)) is not None:
                        return code, None
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError:
                return staging_code, None
            finally:
                if descriptor != -1:
                    os.close(descriptor)

            try:
                staged_stat = staged.stat(follow_symlinks=False)
                if not stat.S_ISREG(staged_stat.st_mode):
                    return verification_code, None
                if (code := verify(staged)) is not None:
                    return code, None
                current_stat = staged.stat(follow_symlinks=False)
                if not _same_inode(staged_stat, current_stat):
                    return verification_code, None
            except OSError:
                return verification_code, None

            for _ in range(4):
                candidate = f".{output.name}.{secrets.token_hex(16)}.tmp"
                try:
                    os.mkdir(candidate, 0o700, dir_fd=destination_descriptor)
                    stage_name = candidate
                    break
                except FileExistsError:
                    continue
                except OSError:
                    return staging_code, None
            if stage_name is None:
                return staging_code, None
            stage_descriptor = _secure_directory_descriptor(
                stage_name, parent_descriptor=destination_descriptor
            )
            if stage_descriptor is None:
                return staging_code, None
            try:
                stage_stat = os.fstat(stage_descriptor)
                if not stat.S_ISDIR(stage_stat.st_mode):
                    return staging_code, None
                digest, written_stat = _copy_verified_payload(staged, stage_descriptor)
                payload_stat = os.stat(
                    "payload", dir_fd=stage_descriptor, follow_symlinks=False
                )
                if not stat.S_ISREG(payload_stat.st_mode) or not _same_inode(
                    written_stat, payload_stat
                ):
                    return unavailable_code, None
                try:
                    if (code := verify(staged)) is not None:
                        return code, None
                except OSError:
                    return verification_code, None
                try:
                    os.link(
                        "payload",
                        output.name,
                        src_dir_fd=stage_descriptor,
                        dst_dir_fd=destination_descriptor,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    return exists_code, None
                except (AttributeError, NotImplementedError, OSError):
                    return unavailable_code, None
                _fsync_directory_descriptor(destination_descriptor)
                return None, digest
            except OSError:
                return unavailable_code, None
    finally:
        if stage_descriptor != -1:
            try:
                os.unlink("payload", dir_fd=stage_descriptor)
            except FileNotFoundError:
                pass
            except OSError:
                pass
            os.close(stage_descriptor)
        if stage_name is not None and stage_stat is not None:
            try:
                current = os.stat(
                    stage_name, dir_fd=destination_descriptor, follow_symlinks=False
                )
                if _same_inode(stage_stat, current):
                    os.rmdir(stage_name, dir_fd=destination_descriptor)
            except OSError:
                pass
        os.close(destination_descriptor)


def _container_facts(snapshot: bytes, provider: _Provider) -> tuple[str, int] | None:

    try:
        with provider.ole.OleFileIO(io.BytesIO(snapshot)) as archive:
            with archive.openstream(ENCRYPTION_INFO_STREAM) as stream:
                version = stream.read(_SCHEME_VERSION_BYTES)
            with archive.openstream(ENCRYPTED_PACKAGE_STREAM) as stream:
                header = stream.read(_PLAINTEXT_SIZE_HEADER_BYTES)
    except Exception:  # noqa: BLE001 - untrusted container bytes are a refusal
        return None
    if len(version) != _SCHEME_VERSION_BYTES:
        return None
    if len(header) != _PLAINTEXT_SIZE_HEADER_BYTES:
        return None
    major = int.from_bytes(version[:2], "little")
    minor = int.from_bytes(version[2:4], "little")
    scheme = _SCHEME_BY_VERSION.get((major, minor), f"unrecognized {major}.{minor}")
    return scheme, int.from_bytes(header, "little")


def encrypt_pptx(request: PptxSecurityRequest) -> PptxSecurityReport:

    provider = _qualified_provider("encrypt", request)
    if not isinstance(provider, _Provider):
        return provider
    guarded = _source_guard("encrypt", request)
    if not isinstance(guarded, tuple):
        return guarded
    source, destination = guarded
    limits = PptxPackageLimits()
    snapshot = _snapshot("encrypt", request, source, limits)
    if not isinstance(snapshot, bytes):
        return snapshot
    digest = hashlib.sha256(snapshot).hexdigest()
    if digest != request.source_sha256:
        return _refusal("encrypt", request, "encrypt_source_hash_mismatch")
    envelope = _zip_envelope_refusal(snapshot, limits)
    if envelope is not None:
        return _refusal(
            "encrypt",
            request,
            f"encrypt_source_{envelope.code}",
            recovery=envelope.recovery,
        )
    admission = _admitted_package("encrypt", source, snapshot, digest)
    if isinstance(admission, str):
        return _refusal("encrypt", request, admission)
    password = _resolve_password("encrypt", request)
    if not isinstance(password, str):
        return password

    def write(stream: BinaryIO) -> str | None:
        try:
            provider.ooxml_file(io.BytesIO(snapshot)).encrypt(password, stream)
        except OSError:
            # Writing the container failed - a full disk, a closed stream - so the
            # staging step is what refused, not the provider.
            return "encrypt_staging_unavailable"
        except Exception:  # noqa: BLE001 - the provider only fails with a refusal here
            return "encrypt_provider_error"
        return None

    # The staged size that is measured during verification, reported in the
    # refusal it triggers.
    staged_size: int | None = None

    def verify(staged: Path) -> str | None:
        # The paired operation admits an encrypted container under the same
        # archive limit, so a container this engine could not itself decrypt is
        # never published.
        nonlocal staged_size
        staged_size = staged.stat().st_size
        if staged_size > limits.max_archive_size:
            return "encrypt_staged_size_limit"
        facts = _container_facts(staged.read_bytes(), provider)
        if facts is None:
            return "encrypt_staged_verification_failed"
        scheme, declared = facts
        if scheme != AGILE or declared != len(snapshot):
            return "encrypt_staged_verification_failed"
        if _reopened_plaintext(provider, staged, password) != snapshot:
            return "encrypt_staged_verification_failed"
        # Re-checked last, so the originality guard sits as close to the
        # no-replace publication as the staging protocol allows.
        try:
            current = sha256_file(source)
        except OSError:
            return "encrypt_source_missing"
        if current != request.source_sha256:
            return "encrypt_source_changed"
        return None

    code, output_digest = _publish_staged(
        destination,
        write,
        verify,
        staging_code="encrypt_staging_unavailable",
        verification_code="encrypt_staged_verification_failed",
        exists_code="encrypt_destination_invalid",
        unavailable_code="encrypt_publication_unavailable",
    )
    if code is not None:
        recovery = (
            f"The staged container measures {staged_size} bytes, above the "
            f"{limits.max_archive_size} byte package archive limit that bounds "
            "every container this engine admits, so the paired decryption could "
            "not accept it.  Encrypt a smaller source presentation."
            if code == "encrypt_staged_size_limit"
            else _PUBLICATION_RECOVERIES.get(code.removeprefix("encrypt_"))
        )
        return _refusal("encrypt", request, code, recovery=recovery)
    assert output_digest is not None
    return _published("encrypt", request, output_digest, AGILE)


def decrypt_pptx(request: PptxSecurityRequest) -> PptxSecurityReport:

    provider = _qualified_provider("decrypt", request)
    if not isinstance(provider, _Provider):
        return provider
    guarded = _source_guard("decrypt", request)
    if not isinstance(guarded, tuple):
        return guarded
    source, destination = guarded
    limits = PptxPackageLimits()
    snapshot = _snapshot("decrypt", request, source, limits)
    if not isinstance(snapshot, bytes):
        return snapshot
    if hashlib.sha256(snapshot).hexdigest() != request.source_sha256:
        return _refusal("decrypt", request, "decrypt_source_hash_mismatch")
    if zipfile.is_zipfile(io.BytesIO(snapshot)):
        return _refusal(
            "decrypt",
            request,
            "decrypt_source_not_encrypted",
            recovery=_NOT_ENCRYPTED_RECOVERY,
        )
    if snapshot[:8] != _CFB_MAGIC:
        return _refusal("decrypt", request, "decrypt_container_invalid")
    facts = _container_facts(snapshot, provider)
    if facts is None:
        return _refusal("decrypt", request, "decrypt_container_invalid")
    scheme, declared = facts
    if scheme != AGILE:
        return _refusal(
            "decrypt",
            request,
            "decrypt_encryption_scheme_unsupported",
            recovery=_SCHEME_RECOVERY,
            scheme=scheme,
        )
    if declared > limits.max_archive_size:
        return _refusal(
            "decrypt",
            request,
            "decrypt_plaintext_size_limit",
            recovery=(
                f"The container declares a {declared} byte recovered archive, above "
                f"the {limits.max_archive_size} byte package archive bound this "
                "surface admits.  Use a container whose recovered package fits that "
                "bound."
            ),
        )
    password = _resolve_password("decrypt", request)
    if not isinstance(password, str):
        return password
    try:
        office = provider.ooxml_file(io.BytesIO(snapshot))
    except Exception:  # noqa: BLE001 - untrusted container bytes are a refusal
        return _refusal("decrypt", request, "decrypt_container_invalid")
    if not office.is_encrypted():
        return _refusal(
            "decrypt",
            request,
            "decrypt_source_not_encrypted",
            recovery=_NOT_ENCRYPTED_RECOVERY,
        )
    if office.type != AGILE:
        # This surface read the same scheme out of the container itself; a
        # provider that disagrees is looking at a container that is not coherent.
        return _refusal("decrypt", request, "decrypt_container_invalid")
    try:
        office.load_key(password=password, verify_password=True)
    except provider.invalid_key_error:
        return _refusal(
            "decrypt", request, "decrypt_password_rejected", recovery=_PASSWORD_RECOVERY
        )
    except Exception:  # noqa: BLE001 - a provider message may quote the credential
        return _refusal(
            "decrypt",
            request,
            "decrypt_provider_error",
            recovery=_provider_error_recovery("decrypt"),
        )
    plaintext = io.BytesIO()
    try:
        office.decrypt(plaintext, verify_integrity=True)
    except provider.invalid_key_error:
        # The provider verifies the payload HMAC before it writes the plaintext
        # and probes the recovered package after writing it, so an empty buffer
        # here is an integrity failure and a written buffer is a package whose
        # admission this engine decides itself.
        if plaintext.getvalue():
            return _refusal("decrypt", request, "decrypt_plaintext_package_invalid")
        return _refusal(
            "decrypt", request, "decrypt_integrity_failed", recovery=_INTEGRITY_RECOVERY
        )
    except Exception:  # noqa: BLE001 - a provider message may quote the credential
        return _refusal(
            "decrypt",
            request,
            "decrypt_provider_error",
            recovery=_provider_error_recovery("decrypt"),
        )
    recovered = plaintext.getvalue()
    envelope = _zip_envelope_refusal(recovered, limits)
    if envelope is not None:
        return _refusal(
            "decrypt",
            request,
            f"decrypt_plaintext_{envelope.code}",
            recovery=envelope.recovery,
        )
    recovered_sha256 = hashlib.sha256(recovered).hexdigest()

    def write(stream: BinaryIO) -> str | None:
        stream.write(recovered)
        return None

    def verify(staged: Path) -> str | None:
        if (
            code := _staged_plaintext_refusal(staged, recovered_sha256, limits)
        ) is not None:
            return code
        # Re-checked last, so the originality guard sits as close to the
        # no-replace publication as the staging protocol allows.
        try:
            current = sha256_file(source)
        except OSError:
            return "decrypt_source_missing"
        if current != request.source_sha256:
            return "decrypt_source_changed"
        return None

    code, output_digest = _publish_staged(
        destination,
        write,
        verify,
        staging_code="decrypt_staging_unavailable",
        verification_code="decrypt_staged_verification_failed",
        exists_code="decrypt_destination_invalid",
        unavailable_code="decrypt_publication_unavailable",
    )
    if code is not None:
        return _refusal(
            "decrypt",
            request,
            code,
            recovery=_PUBLICATION_RECOVERIES.get(code.removeprefix("decrypt_")),
        )
    assert output_digest is not None
    return _published("decrypt", request, output_digest, scheme)


def _modify_verifier_hash(password: str, salt: bytes) -> bytes:
    value = hashlib.sha512(
        salt + password[:_MODIFY_VERIFIER_MAX_PASSWORD_CHARACTERS].encode("utf-16le")
    ).digest()
    for count in range(_MODIFY_VERIFIER_SPIN_COUNT):
        value = hashlib.sha512(value + count.to_bytes(4, "little")).digest()
    return value


def _write_protection_archive(
    snapshot: bytes, request: PptxWriteProtectionRequest, password: str | None
) -> bytes:
    with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
        infos = archive.infolist()
        parts = {
            info.filename: archive.read(info) for info in infos if not info.is_dir()
        }
    presentation = _xml_root(parts[PRESENTATION_PART])
    verifier_name = f"{{{P_NS}}}modifyVerifier"
    verifiers = [child for child in presentation if child.tag == verifier_name]
    if len(verifiers) > 1:
        raise ValueError("presentation_verifier_unsupported")
    if request.action == "remove":
        if verifiers:
            presentation.remove(verifiers[0])
    elif password is not None:
        if verifiers:
            presentation.remove(verifiers[0])
        salt = os.urandom(_MODIFY_VERIFIER_SALT_BYTES)
        verifier = ET.Element(
            verifier_name,
            {
                "cryptProviderType": "rsaAES",
                "cryptAlgorithmClass": "hash",
                "cryptAlgorithmType": "typeAny",
                "cryptAlgorithmSid": "14",
                "spinCount": str(_MODIFY_VERIFIER_SPIN_COUNT),
                "saltData": base64.b64encode(salt).decode("ascii"),
                "hashData": base64.b64encode(
                    _modify_verifier_hash(password, salt)
                ).decode("ascii"),
            },
        )
        position = next(
            (
                index
                for index, child in enumerate(presentation)
                if child.tag == f"{{{P_NS}}}extLst"
            ),
            len(presentation),
        )
        presentation.insert(position, verifier)
    parts[PRESENTATION_PART] = ET.tostring(
        presentation, encoding="utf-8", xml_declaration=True
    )

    app_root: ET.Element | None = None
    current = 0
    if _EXTENDED_PROPERTIES_PART in parts:
        app_root = _xml_root(parts[_EXTENDED_PROPERTIES_PART])
        if app_root.tag != f"{{{_EXTENDED_PROPERTIES_NS}}}Properties":
            raise ValueError("extended_properties_unsupported")
        entries = [
            child
            for child in app_root
            if child.tag == f"{{{_EXTENDED_PROPERTIES_NS}}}DocSecurity"
        ]
        if len(entries) > 1:
            raise ValueError("extended_properties_unsupported")
        if entries:
            try:
                current = int(entries[0].text or "")
            except ValueError as error:
                raise ValueError("extended_properties_unsupported") from error
            if not 0 <= current <= _DOC_SECURITY_KNOWN_MASK:
                raise ValueError("extended_properties_unsupported")
    target = current & ~(_DOC_SECURITY_PASSWORD | _DOC_SECURITY_READ_ONLY_RECOMMENDED)
    if request.action == "set":
        target |= (
            _DOC_SECURITY_PASSWORD
            if password is not None
            else current & _DOC_SECURITY_PASSWORD
        )
        if request.read_only_recommended is None:
            target |= current & _DOC_SECURITY_READ_ONLY_RECOMMENDED
        elif request.read_only_recommended:
            target |= _DOC_SECURITY_READ_ONLY_RECOMMENDED
    if target != current:
        if app_root is None:
            app_root = ET.Element(f"{{{_EXTENDED_PROPERTIES_NS}}}Properties")
        existing = app_root.find(f"{{{_EXTENDED_PROPERTIES_NS}}}DocSecurity")
        if target:
            if existing is None:
                existing = ET.SubElement(
                    app_root, f"{{{_EXTENDED_PROPERTIES_NS}}}DocSecurity"
                )
            existing.text = str(target)
        elif existing is not None:
            app_root.remove(existing)
        parts[_EXTENDED_PROPERTIES_PART] = ET.tostring(
            app_root, encoding="utf-8", xml_declaration=True
        )
        content_types = _xml_root(parts["[Content_Types].xml"])
        relationships = _xml_root(parts["_rels/.rels"])
        overrides = [
            child
            for child in content_types
            if child.attrib.get("PartName") == f"/{_EXTENDED_PROPERTIES_PART}"
        ]
        if len(overrides) > 1 or (
            overrides
            and overrides[0].attrib.get("ContentType")
            != _EXTENDED_PROPERTIES_CONTENT_TYPE
        ):
            raise ValueError("extended_properties_unsupported")
        if not overrides:
            ET.SubElement(
                content_types,
                f"{{{_CT_NS}}}Override",
                PartName=f"/{_EXTENDED_PROPERTIES_PART}",
                ContentType=_EXTENDED_PROPERTIES_CONTENT_TYPE,
            )
        properties_rels = [
            child
            for child in relationships
            if child.attrib.get("Type") == _EXTENDED_PROPERTIES_REL
        ]
        if len(properties_rels) > 1 or (
            properties_rels
            and (
                properties_rels[0].attrib.get("TargetMode") == "External"
                or resolve_target("", properties_rels[0].attrib.get("Target", ""))
                != _EXTENDED_PROPERTIES_PART
            )
        ):
            raise ValueError("extended_properties_unsupported")
        if not properties_rels:
            ET.SubElement(
                relationships,
                f"{{{_REL_NS}}}Relationship",
                Id=_next_relationship_id(relationships),
                Type=_EXTENDED_PROPERTIES_REL,
                Target=_EXTENDED_PROPERTIES_PART,
            )
        parts["[Content_Types].xml"] = (
            ET.tostring(content_types, encoding="utf-8", xml_declaration=True)
            .replace(
                b'xmlns:ns0="' + _CT_NS.encode("ascii") + b'"',
                b'xmlns="' + _CT_NS.encode("ascii") + b'"',
                1,
            )
            .replace(b"ns0:", b"")
        )
        parts["_rels/.rels"] = ET.tostring(
            relationships, encoding="utf-8", xml_declaration=True
        )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as rewritten:
        known: set[str] = set()
        for info in infos:
            if info.is_dir() or info.filename not in parts:
                continue
            copied = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            copied.compress_type, copied.comment = info.compress_type, info.comment
            copied.external_attr, copied.create_system = (
                info.external_attr,
                info.create_system,
            )
            rewritten.writestr(copied, parts[info.filename])
            known.add(info.filename)
        for name in sorted(set(parts) - known):
            rewritten.writestr(name, parts[name], compress_type=zipfile.ZIP_DEFLATED)
    return output.getvalue()


def write_protection_pptx(
    request: PptxWriteProtectionRequest,
) -> PptxSecurityReport:
    operation = "write_protection"
    guarded = _source_guard(operation, request)
    if not isinstance(guarded, tuple):
        return guarded
    source, destination = guarded
    snapshot = _snapshot(operation, request, source, PptxPackageLimits())
    if not isinstance(snapshot, bytes):
        return snapshot
    digest = hashlib.sha256(snapshot).hexdigest()
    if digest != request.source_sha256:
        return _refusal(operation, request, f"{operation}_source_hash_mismatch")
    envelope = _zip_envelope_refusal(snapshot, PptxPackageLimits())
    if envelope is not None:
        return _refusal(operation, request, f"{operation}_source_{envelope.code}")
    if isinstance(_admitted_package(operation, source, snapshot, digest), str):
        return _refusal(operation, request, f"{operation}_source_package_invalid")
    password: str | None = None
    if request.password_env is not None:
        password = _resolve_password(operation, request)
        if not isinstance(password, str):
            return password
    try:
        output = _write_protection_archive(snapshot, request, password)
    except UnicodeEncodeError:
        return _refusal(operation, request, f"{operation}_password_unsupported")
    except (KeyError, ValueError, ET.ParseError, zipfile.BadZipFile):
        return _refusal(operation, request, f"{operation}_source_metadata_unsupported")
    output_digest = hashlib.sha256(output).hexdigest()

    def write(stream: BinaryIO) -> str | None:
        stream.write(output)
        return None

    def verify(staged: Path) -> str | None:
        try:
            payload = staged.read_bytes()
            if hashlib.sha256(payload).hexdigest() != output_digest:
                return f"{operation}_staged_verification_failed"
            if _zip_envelope_refusal(payload, PptxPackageLimits()) is not None:
                return f"{operation}_staged_verification_failed"
            staged_package = read_package_bytes(staged, payload)
            if _presentation_refusal(staged_package) is not None:
                return f"{operation}_staged_verification_failed"
            return (
                None
                if sha256_file(source) == request.source_sha256
                else f"{operation}_source_changed"
            )
        except (OSError, PackageRefusal):
            return f"{operation}_staged_verification_failed"

    code, published_digest = _publish_staged(
        destination,
        write,
        verify,
        staging_code=f"{operation}_staging_unavailable",
        verification_code=f"{operation}_staged_verification_failed",
        exists_code=f"{operation}_destination_invalid",
        unavailable_code=f"{operation}_publication_unavailable",
    )
    if code is not None:
        return _refusal(operation, request, code)
    assert published_digest is not None
    return _published("write-protection", request, published_digest, None)


def inspect_pptx_signatures(
    request: PptxSignatureInspectionRequest,
) -> PptxSignatureInspectionReport:
    source = request.source.resolve()
    if not source.is_file():
        return _signature_inspection_refusal(
            request, "signature_inspect_source_missing"
        )
    snapshot = _signature_snapshot(source, request.source_sha256)
    if isinstance(snapshot, str):
        return _signature_inspection_refusal(request, f"signature_inspect_{snapshot}")
    payload, package = snapshot
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            parts = {
                info.filename: archive.read(info)
                for info in archive.infolist()
                if not info.is_dir()
            }
    except (OSError, zipfile.BadZipFile):
        return _signature_inspection_refusal(
            request, "signature_inspect_package_malformed"
        )
    candidates = _signature_candidates(parts)
    if not candidates:
        code = (
            "signature_inspect_registry_malformed"
            if _signature_part_marker(parts)
            else "signature_inspect_unsigned"
        )
        return PptxSignatureInspectionReport(_REFUSED, code, request.source_sha256, ())
    signatures = tuple(
        _signature_from_payload(part, parts[part], parts, package)
        for part in candidates
    )
    registered = _registered_signature_parts(parts, candidates, package)
    if isinstance(registered, str):
        return PptxSignatureInspectionReport(
            _REFUSED,
            f"signature_inspect_{registered}",
            request.source_sha256,
            signatures,
        )
    if any(
        signature.part in registered and signature.valid is True
        for signature in signatures
    ):
        return PptxSignatureInspectionReport(
            "inspected", None, request.source_sha256, signatures
        )
    return PptxSignatureInspectionReport(
        _REFUSED,
        "signature_inspect_no_valid_signature",
        request.source_sha256,
        signatures,
    )


def sign_pptx(request: PptxSignatureRequest) -> PptxSignatureReport:
    source = request.source.resolve()
    destination = request.destination
    if source == destination.resolve():
        return _signature_refusal(request, "signature_sign_source_destination_same")
    if not source.is_file():
        return _signature_refusal(request, "signature_sign_source_missing")
    if not destination.parent.is_dir():
        return _signature_refusal(request, "signature_sign_destination_parent_missing")
    snapshot = _signature_snapshot(source, request.source_sha256)
    if isinstance(snapshot, str):
        return _signature_refusal(request, f"signature_sign_{snapshot}")
    payload, package = snapshot
    if _signature_part_marker(package.parts):
        return _signature_refusal(request, "signature_sign_source_already_signed")
    dependency = _signature_dependency()
    if dependency is None:
        return _signature_refusal(
            request,
            "signature_sign_dependency_missing",
            (
                "Install the cryptography and lxml dependencies required for X.509 "
                "XMLDSIG signing."
            ),
        )
    credentials = _load_signature_credentials(request, dependency)
    if isinstance(credentials, str):
        return _signature_refusal(request, f"signature_sign_{credentials}")
    certificate, key, signer = credentials
    try:
        signed_archive = _signature_archive(
            payload, package, certificate, key, dependency
        )
    except (ET.ParseError, ValueError, zipfile.BadZipFile, OSError):
        return _signature_refusal(request, "signature_sign_source_package_malformed")

    def write(stream: BinaryIO) -> str | None:
        stream.write(signed_archive)
        return None

    def verify(staged: Path) -> str | None:
        try:
            digest = sha256_file(staged)
            inspection = inspect_pptx_signatures(
                PptxSignatureInspectionRequest(staged, digest)
            )
        except OSError:
            return "signature_sign_staged_verification_failed"
        if (
            not inspection.passed
            or len(inspection.signatures) != 1
            or inspection.signatures[0].valid is not True
        ):
            return "signature_sign_staged_verification_failed"
        return None

    code, output_digest = _publish_staged(
        destination,
        write,
        verify,
        staging_code="signature_sign_staging_unavailable",
        verification_code="signature_sign_staged_verification_failed",
        exists_code="signature_sign_destination_invalid",
        unavailable_code="signature_sign_publication_unavailable",
    )
    if code is not None:
        return _signature_refusal(
            request,
            code,
            _PUBLICATION_RECOVERIES.get(code.removeprefix("signature_sign_")),
        )
    assert output_digest is not None
    return PptxSignatureReport(
        status=_PUBLISHED,
        code=None,
        source_sha256=request.source_sha256,
        destination_sha256=output_digest,
        signer=signer,
    )


__all__ = [
    "AGILE",
    "ENCRYPTED_EXTRA",
    "ENCRYPTED_PACKAGE_STREAM",
    "ENCRYPTION_INFO_STREAM",
    "MSOFFCRYPTO_DISTRIBUTION",
    "MSOFFCRYPTO_VERSION",
    "PPTX_SECURITY_LIMITS",
    "PRESENTATION_PART",
    "SIGNATURE_OPERATIONS",
    "PptxDigitalSignature",
    "PptxPackageLimits",
    "PptxSecurityReport",
    "PptxSecurityRequest",
    "PptxSignatureInspectionReport",
    "PptxSignatureInspectionRequest",
    "PptxSignatureReport",
    "PptxSignatureRequest",
    "decrypt_pptx",
    "encrypt_pptx",
    "inspect_pptx_signatures",
    "load_pptx_security_request",
    "load_pptx_signature_inspection_request",
    "load_pptx_signature_request",
    "parse_pptx_security_request",
    "parse_pptx_signature_inspection_request",
    "parse_pptx_signature_request",
    "sha256_file",
    "sign_pptx",
]


# Re-exported so existing ``security.<name>`` imports keep working.
# isort: split
from .security_signatures import (
    _add_digest_reference,  # noqa: F401
    _canonical_xml,  # noqa: F401
    _load_signature_credentials,
    _next_relationship_id,
    _reference_digest_code,  # noqa: F401
    _reference_uri,  # noqa: F401
    _registered_signature_parts,
    _signature_archive,
    _signature_candidates,
    _signature_content_types,  # noqa: F401
    _signature_dependency,
    _signature_from_payload,
    _signature_inspection_refusal,
    _signature_part_marker,
    _signature_refusal,
    _signature_root_relationships,  # noqa: F401
    _signature_snapshot,
    _signature_xml,  # noqa: F401
    _xml_root,
)
# isort: split
