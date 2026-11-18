"""Validate and alias the native extension before importing the public facades."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from importlib import metadata as _metadata
from pathlib import Path

_NATIVE_MODULE = "wolfppt.wolfppt_native"


class NativeExtensionImportError(ImportError):
    """The WolfPPT native extension is missing, mismatched, or from another version.

    ``cause`` is one of ``"missing"``, ``"load_failed"``, ``"extension_mismatch"`` (the file
    differs from the installed distribution's RECORD: another CPython ABI build or another
    wolfppt version) or ``"version_skew"`` (the extension reports a version other than the
    installed distribution's). There is no fallback to a package without its extension.
    """

    # Keep the public exception identity stable after moving the bootstrap.
    __module__ = "wolfppt"

    def __init__(self, cause: str, message: str) -> None:
        super().__init__(message, name=_NATIVE_MODULE)
        self.cause = cause


def _record_mismatch(origin: Path) -> str | None:
    """Why ``origin`` differs from the installed distribution's RECORD hash, else ``None``.

    Runs before the extension is loaded: a build for another CPython ABI loads without error
    and is unsafe to call. Editable installs, source checkouts and any file the RECORD does not
    hash are not checkable and pass.
    """

    try:
        distribution = _metadata.distribution("wolfppt")
        files = distribution.files or []
    except _metadata.PackageNotFoundError:
        return None
    for entry in files:
        if entry.hash is None or entry.name != origin.name:
            continue
        if Path(distribution.locate_file(entry)).resolve() != origin:
            continue
        try:
            with origin.open("rb") as handle:
                digest = hashlib.file_digest(handle, entry.hash.mode).digest()
        except ValueError:
            return None
        actual = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        if actual != entry.hash.value:
            return (
                f"{origin.name} does not match the {entry.hash.mode} hash in the RECORD of the "
                f"installed wolfppt {distribution.version} distribution; it was built for "
                "another CPython ABI or from another wolfppt version"
            )
        return None
    return None


def _legacy_top_level_native() -> bool:
    """A top-level ``wolfppt_native`` (``maturin develop`` inside the crate) is accepted."""

    if "wolfppt_native" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("wolfppt_native") is not None
    except (ImportError, ValueError):
        return False


def _import_native():
    try:
        spec = importlib.util.find_spec(_NATIVE_MODULE)
    except (ImportError, ValueError):
        spec = None
    if spec is None or spec.origin is None:
        if _legacy_top_level_native():
            return None
        raise NativeExtensionImportError(
            "missing",
            f"the WolfPPT native extension {_NATIVE_MODULE} is missing from this installation; "
            "reinstall wolfppt (a wheel built for this CPython) or build it with maturin",
        )
    mismatch = _record_mismatch(Path(spec.origin).resolve())
    if mismatch is not None:
        raise NativeExtensionImportError(
            "extension_mismatch", f"the WolfPPT native extension {_NATIVE_MODULE}: {mismatch}"
        )
    try:
        from . import wolfppt_native as native  # type: ignore[attr-defined]
    except ImportError as exc:
        raise NativeExtensionImportError(
            "load_failed", f"the WolfPPT native extension {_NATIVE_MODULE} failed to load: {exc}"
        ) from exc
    try:
        expected = _metadata.version("wolfppt")
    except _metadata.PackageNotFoundError:
        return native
    build_info_json = getattr(native, "build_info_json", None)
    built = json.loads(build_info_json()).get("version") if build_info_json else None
    if built != expected:
        sys.modules.pop(_NATIVE_MODULE, None)
        raise NativeExtensionImportError(
            "version_skew",
            f"the WolfPPT native extension {_NATIVE_MODULE} reports version {built!r} but the "
            f"installed wolfppt distribution is {expected}",
        )
    return native


_native = _import_native()
if _native is not None:
    sys.modules.setdefault("wolfppt_native", _native)
