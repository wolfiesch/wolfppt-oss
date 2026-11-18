"""Opt-in presentation printing through CUPS on Linux and macOS.

Only explicit discovery/submission calls contact a scheduler. Queue acceptance
is not physical completion. A submission timeout has an unknown outcome and
must not be retried automatically.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .editions import CommercialFeatureError, commercial_module

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PRINTER = re.compile(r"[^\s/#\\\x00-\x1f\x7f]{1,127}\Z")
_JOB = re.compile(r"^request id is (\S+) \(\d+ file\(s\)\)$", re.MULTILINE)
_SIDES = {
    "one_sided": "one-sided",
    "two_sided_long_edge": "two-sided-long-edge",
    "two_sided_short_edge": "two-sided-short-edge",
}
_DUPLEX = {
    "None": "one_sided",
    "DuplexNoTumble": "two_sided_long_edge",
    "DuplexTumble": "two_sided_short_edge",
}


@dataclass(frozen=True)
class PrintJobSettings:
    """One-based ascending slide selection, copies, layout and driver settings.

    ``slides=None`` selects all slides. Hidden slides remain excluded unless
    ``show_hidden_slides=True``. Media names must match the printer's PageSize
    choices. Only handouts accept ``slides_per_page`` and ``order``.
    """

    slides: tuple[int, ...] | None = None
    copies: int = 1
    layout: str = "slides"
    slides_per_page: int | None = None
    order: str | None = None
    show_hidden_slides: bool = False
    duplex: str | None = None
    media: str | None = None
    job_name: str = "WolfPPT presentation"


@dataclass(frozen=True)
class PrinterCapabilities:
    accepting: bool
    duplex_modes: frozenset[str] = field(default_factory=lambda: frozenset({"one_sided"}))
    media: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PrintSubmissionReport:
    """Submitted, refused, invalid_printer, backend_unavailable, or unknown.

    Only ``submitted`` carries a confirmed ``job_id``. ``unknown`` means the
    scheduler may have accepted a job; inspect its queue before any retry.
    """

    status: str
    code: str | None
    printer: str
    settings: PrintJobSettings
    job_id: str | None = None
    source_sha256: str | None = None
    document_sha256: str | None = None
    page_count: int = 0
    detail: str | None = None

    @property
    def submitted(self) -> bool:
        return self.status == "submitted"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PrintBackendError(Exception):
    """A typed platform, printer, or submission failure."""

    def __init__(self, status: str, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = _CONTROL.sub(" ", detail).strip()[:500] or None


def _valid_printer(printer: object) -> bool:
    return (
        isinstance(printer, str)
        and not printer.startswith("-")
        and _PRINTER.fullmatch(printer) is not None
    )


@dataclass(frozen=True)
class CupsPrintBackend:
    """Bounded, shell-free CUPS adapter, aligned with WolfDocx's backend.

    ``server=None`` uses the configured scheduler. An explicit ``server`` is
    passed to each client with ``-h``. No scheduler configuration is modified.
    """

    server: str | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.server is not None and (
            not isinstance(self.server, str)
            or not self.server
            or self.server.startswith("-")
            or _CONTROL.search(self.server)
        ):
            raise ValueError("print_server_invalid")
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, int | float)
            or not 0 < self.timeout <= 300
        ):
            raise ValueError("print_timeout_invalid")

    def _run(self, tool: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        command = [tool]
        if self.server is not None:
            command += ["-h", self.server]
        command += arguments
        submitting = tool == "lp"
        try:
            return subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout,
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise PrintBackendError(
                "unknown" if submitting else "backend_unavailable",
                "print_submission_unknown" if submitting else "print_backend_timeout",
                tool,
            ) from None
        except OSError as error:
            raise PrintBackendError(
                "backend_unavailable", "print_backend_missing", f"{tool}: {error.strerror}"
            ) from None

    def ensure_available(self) -> None:
        if sys.platform not in ("linux", "darwin"):
            raise PrintBackendError(
                "backend_unavailable", "print_platform_unsupported", sys.platform
            )
        for tool in ("lp", "lpstat", "lpoptions"):
            if shutil.which(tool) is None:
                raise PrintBackendError("backend_unavailable", "print_backend_missing", tool)
        result = self._run("lpstat", "-r")
        if result.returncode != 0 or result.stdout.strip() != "scheduler is running":
            raise PrintBackendError(
                "backend_unavailable", "print_scheduler_unavailable", result.stderr + result.stdout
            )

    def printers(self) -> tuple[str, ...]:
        """List configured destinations; raise PrintBackendError on discovery failure."""
        self.ensure_available()
        result = self._run("lpstat", "-e")
        if result.returncode:
            raise PrintBackendError(
                "backend_unavailable", "print_spooler_query_failed", result.stderr
            )
        names = result.stdout.splitlines()
        if any(not _valid_printer(name) for name in names):
            raise PrintBackendError("backend_unavailable", "print_spooler_response_unrecognized")
        return tuple(names)

    def printer_capabilities(self, printer: str) -> PrinterCapabilities:
        if not _valid_printer(printer):
            raise PrintBackendError("invalid_printer", "print_printer_name_invalid")
        result = self._run("lpstat", "-a", printer)
        if result.returncode:
            message = result.stderr + result.stdout
            missing = "Invalid destination name" in message or "does not exist" in message
            raise PrintBackendError(
                "invalid_printer" if missing else "backend_unavailable",
                "print_printer_not_found" if missing else "print_spooler_query_failed",
                message,
            )
        accepting = None
        for line in result.stdout.splitlines():
            name, _, state = line.partition(" ")
            if name.casefold() == printer.casefold():
                if state.startswith("accepting requests"):
                    accepting = True
                elif state.startswith("not accepting requests"):
                    accepting = False
        if accepting is None:
            raise PrintBackendError("backend_unavailable", "print_spooler_response_unrecognized")
        options = self._run("lpoptions", "-p", printer, "-l")
        duplex = {"one_sided"}
        media: set[str] = set()
        if options.returncode == 0:
            for line in options.stdout.splitlines():
                key, _, choices = line.partition(":")
                key = key.split("/", 1)[0].strip()
                values = [choice.lstrip("*").split("/", 1)[0] for choice in choices.split()]
                if key == "Duplex":
                    duplex.update(_DUPLEX[value] for value in values if value in _DUPLEX)
                elif key == "PageSize":
                    media.update(values)
        return PrinterCapabilities(accepting, frozenset(duplex), frozenset(media))

    def submit(self, document: Path, printer: str, settings: PrintJobSettings) -> str:
        arguments = ["-d", printer, "-n", str(settings.copies), "-t", settings.job_name]
        if settings.duplex is not None:
            arguments += ["-o", f"sides={_SIDES[settings.duplex]}"]
        if settings.media is not None:
            arguments += ["-o", f"media={settings.media}"]
        result = self._run("lp", *arguments, "--", str(document))
        if result.returncode:
            raise PrintBackendError(
                "refused", "print_spooler_rejected", result.stderr + result.stdout
            )
        match = _JOB.search(result.stdout)
        if match is None:
            raise PrintBackendError(
                "unknown", "print_submission_unknown", result.stdout + result.stderr
            )
        job_id = match.group(1)
        if not job_id.casefold().startswith(printer.casefold() + "-"):
            raise PrintBackendError("unknown", "print_submission_unknown", result.stdout)
        return job_id


def _settings_refusal(settings: PrintJobSettings) -> str | None:
    if type(settings.copies) is not int or not 1 <= settings.copies <= 999:
        return "print_copies_invalid"
    if settings.slides is not None and (
        not isinstance(settings.slides, tuple)
        or not settings.slides
        or any(type(slide) is not int or slide < 1 for slide in settings.slides)
        or tuple(sorted(set(settings.slides))) != settings.slides
    ):
        return "print_slides_invalid"
    if settings.layout not in ("slides", "notes", "handout"):
        return "print_layout_unsupported"
    if settings.layout == "handout":
        if settings.slides_per_page is not None and (
            type(settings.slides_per_page) is not int
            or settings.slides_per_page not in (1, 2, 3, 4, 6, 9)
        ):
            return "print_layout_unsupported"
        if settings.order not in (None, "horizontal", "vertical"):
            return "print_layout_unsupported"
        if settings.order == "vertical" and settings.slides_per_page not in (4, 6, 9):
            return "print_layout_unsupported"
    elif settings.slides_per_page is not None or settings.order is not None:
        return "print_layout_unsupported"
    if type(settings.show_hidden_slides) is not bool:
        return "print_hidden_slides_invalid"
    if settings.duplex is not None and settings.duplex not in _SIDES:
        return "print_duplex_invalid"
    if settings.media is not None and (
        not isinstance(settings.media, str)
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,127}", settings.media) is None
    ):
        return "print_media_invalid"
    if (
        not isinstance(settings.job_name, str)
        or not settings.job_name.strip()
        or len(settings.job_name) > 255
        or _CONTROL.search(settings.job_name)
    ):
        return "print_job_name_invalid"
    return None


def submit_print_job(
    source: Any,
    printer: str,
    *,
    fonts: tuple[str, ...],
    settings: PrintJobSettings | None = None,
    backend: CupsPrintBackend | None = None,
) -> PrintSubmissionReport:
    """Snapshot a saved presentation, render selected slides, and submit one PDF.

    Source package bytes are never written. Fonts use the existing native render
    ``Family[:style]=/path/font.ttf`` admission. All spooler errors are explicit
    reports; malformed settings are refused before contacting a scheduler.
    """
    settings = PrintJobSettings() if settings is None else settings
    backend = CupsPrintBackend() if backend is None else backend
    if not isinstance(settings, PrintJobSettings):
        raise TypeError("print_settings_invalid")
    values: dict[str, Any] = {}

    def report(status: str, code: str | None, **extra: Any) -> PrintSubmissionReport:
        return PrintSubmissionReport(status, code, printer, settings, **values, **extra)

    if not _valid_printer(printer):
        return report("invalid_printer", "print_printer_name_invalid")
    refusal = _settings_refusal(settings)
    if refusal:
        return report("refused", refusal)
    try:
        backend.ensure_available()
        capabilities = backend.printer_capabilities(printer)
        if not capabilities.accepting:
            return report("refused", "print_printer_not_accepting")
        if settings.duplex is not None and settings.duplex not in capabilities.duplex_modes:
            return report("refused", "print_duplex_unsupported")
        if settings.media is not None and settings.media not in capabilities.media:
            return report("refused", "print_media_unsupported")
        try:
            data = (
                source.read_bytes() if hasattr(source, "read_bytes") else Path(source).read_bytes()
            )
        except OSError:
            return report("refused", "print_source_unreadable")
        values["source_sha256"] = hashlib.sha256(data).hexdigest()
        try:
            renderer = commercial_module("native_render", "Printing a presentation")
        except CommercialFeatureError as error:
            return report("refused", "print_render_unavailable", detail=str(error))
        from .presentation import Presentation

        with tempfile.TemporaryDirectory(prefix="wolfppt-print-") as directory:
            root = Path(directory)
            snapshot = root / "source.pptx"
            snapshot.write_bytes(data)
            if settings.slides is not None:
                deck = Presentation(io.BytesIO(data), no_disk=True)
                try:
                    if settings.slides[-1] > len(deck.slides):
                        return report("refused", "print_slides_out_of_range")
                    snapshot = deck.split(
                        (tuple(slide - 1 for slide in settings.slides),), root / "selected"
                    )[0]
                finally:
                    deck.dispose()
            del data
            output = root / "render"
            common = dict(
                source=snapshot,
                output_dir=output,
                fonts=fonts,
                show_hidden_slides=settings.show_hidden_slides,
                title=settings.job_name,
            )
            try:
                if settings.layout == "slides":
                    receipt = renderer.render_deck_files(
                        renderer.RenderOptions(**common, formats=("pdf",))
                    )
                    document = output / "deck.pdf"
                    values["page_count"] = receipt["deck"]["rendered_slides"]
                else:
                    receipt = renderer.render_deck_handouts(
                        renderer.HandoutOptions(
                            **common,
                            slides_per_page=settings.slides_per_page or 3,
                            order=settings.order or "horizontal",
                            notes_pages=settings.layout == "notes",
                        )
                    )
                    document = output / renderer.HANDOUT_PDF_NAME
                    values["page_count"] = receipt["handout"]["pages"]
            except renderer.NativeRenderRefusal as error:
                return report("refused", "print_render_refused", detail=str(error)[:500])
            if values["page_count"] == 0:
                return report("refused", "print_no_visible_slides")
            values["document_sha256"] = hashlib.sha256(document.read_bytes()).hexdigest()
            job_id = backend.submit(document, printer, settings)
            return report("submitted", None, job_id=job_id)
    except PrintBackendError as error:
        return report(error.status, error.code, detail=error.detail)
