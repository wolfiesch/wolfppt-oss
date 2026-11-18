"""Format-aware merge through existing loaders, assembly and export transactions.

Package output uses an admitted presentation suffix. Render output uses the
native export directory contract, including its omission receipt, selected by
``render_options``. No format converter or render backend is implemented here.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .editions import commercial_module
from .presentation_formats import (
    BINARY_PPT_SUFFIXES,
    has_cfbf_signature,
    inspect_presentation_format,
    is_odp_package,
)

_OOXML_SUFFIXES = frozenset({".pptx", ".pptm", ".ppsx", ".ppsm", ".potx", ".potm"})
_PACKAGE_SUFFIXES = _OOXML_SUFFIXES | BINARY_PPT_SUFFIXES | {".odp"}


class MergeFormatRefusal(ValueError):
    """A merge format or control combination refused before output publication."""


def merge_presentations(
    decks: Sequence[Any],
    output: Any,
    *,
    save_options: Mapping[str, Any] | None = None,
    render_options: Mapping[str, Any] | None = None,
) -> Path:
    """Normalize admitted inputs, assemble privately, export, then publish once.

    ``save_options`` contains keyword arguments accepted by ``Presentation.save``.
    Package controls are admitted only for PresentationML, never applied to a
    binary or OpenDocument file. ``render_options`` instead contains keyword
    arguments accepted by ``RenderOptions`` other than ``source``/``output_dir``;
    pass ``fonts`` explicitly and choose ``formats`` as in the native exporter.
    ``output`` is then a new directory containing all exports and their receipt.
    Save and render options cannot be combined. Format-specific refusals from
    loaders, save exporters and renderers propagate unchanged.
    """
    from .presentation import Presentation

    assembly = commercial_module("assembly", "Merging presentations")
    paths = [Path(deck) for deck in decks]
    target = Path(output)
    if len(paths) < 2:
        raise ValueError("merge needs a destination deck and at least one source")
    for options in (save_options, render_options):
        if options is not None and not isinstance(options, Mapping):
            raise MergeFormatRefusal("merge options must be keyword mappings")
    if render_options is not None and save_options is not None:
        raise MergeFormatRefusal("save_options and render_options cannot be combined")
    suffix = target.suffix.casefold()
    if render_options is None:
        if suffix not in _PACKAGE_SUFFIXES:
            raise MergeFormatRefusal(
                f"unsupported merge output suffix {suffix!r}; use a presentation suffix "
                "or render_options with a new export directory"
            )
        if save_options and suffix not in _OOXML_SUFFIXES:
            raise MergeFormatRefusal("package save controls require PresentationML output")
    elif {"source", "output_dir"} & render_options.keys():
        raise MergeFormatRefusal("merge owns the render source and output_dir")
    if not target.parent.is_dir():
        raise assembly.AssemblyRefusal("output parent directory does not exist")
    if any(path.resolve() == target.resolve() for path in paths):
        raise assembly.AssemblyRefusal("output must not overwrite an input presentation")
    if any(path.resolve() == paths[0].resolve() for path in paths[1:]):
        raise assembly.AssemblyRefusal("a source must not be the destination presentation")
    if any(not path.is_file() for path in paths):
        raise assembly.AssemblyRefusal("input presentation does not exist")

    hashes = [_digest(path) for path in paths]
    with ExitStack() as stack:
        directory = Path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix="wolfppt-merge-", dir=target.parent)
            )
        )
        normalized = []
        for path in paths:
            if has_cfbf_signature(path) or is_odp_package(path):
                presentation = Presentation(path)
                stack.callback(presentation.dispose)
                normalized.append(presentation.path)
            else:
                # Preserve the established byte-copy and closure semantics for OPC.
                normalized.append(path)
        destination = assembly.discover_assembly_targets(normalized[0])
        sources = []
        for path in normalized[1:]:
            targets = assembly.discover_assembly_targets(path)
            sources.append(
                {
                    "path": str(path),
                    "source_sha256": targets["source_sha256"],
                    "slide_indexes": [slide["slide_index"] for slide in targets["slides"]],
                    "expected_slide_ids": [slide["slide_id"] for slide in targets["slides"]],
                }
            )
        assembled = directory / "assembled.pptx"
        assembly.assemble_presentations(
            {
                "destination_sha256": destination["source_sha256"],
                "insertion_index": len(destination["slides"]),
                "sources": sources,
            },
            normalized[0],
            assembled,
        )
        if render_options is not None:
            renderer = commercial_module("native_render", "Rendering merged presentations")
            options = dict(render_options)
            callback = options.pop("progress_callback", None)
            options.setdefault("fonts", ())
            if callback is not None and not callable(callback):
                raise MergeFormatRefusal("progress_callback must be callable")

            def progress(fraction: float) -> None:
                # Completion belongs to the caller-visible publication, not staging.
                if callback is not None and fraction < 1:
                    callback(fraction)

            rendered = directory / "rendered"
            renderer.render_deck_files(
                renderer.RenderOptions(
                    source=assembled, output_dir=rendered, progress_callback=progress, **options
                )
            )
            _check_sources(paths, hashes, assembly.AssemblyRefusal)
            renderer._rename_no_replace(rendered, target)
            renderer._fsync_directory(target.parent)
            if callback is not None:
                callback(1.0)
        else:
            # Save once with the real suffix before applying controls: controlled
            # saves serialize through a stream, which has no suffix for retargeting.
            if suffix in _OOXML_SUFFIXES:
                source_format = inspect_presentation_format(assembled).format.value
                if source_format.endswith("m") != suffix.endswith("m"):
                    raise MergeFormatRefusal("merge output cannot change the package macro state")
            presentation = Presentation(assembled)
            stack.callback(presentation.dispose)
            candidate = directory / ("output" + suffix)
            presentation.save(candidate)
            if save_options:
                presentation.save(candidate, **save_options)
            _check_sources(paths, hashes, assembly.AssemblyRefusal)
            os.replace(candidate, target)
    return target


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _check_sources(paths: list[Path], hashes: list[str], refusal: type[ValueError]) -> None:
    for path, expected in zip(paths, hashes, strict=True):
        try:
            actual = _digest(path)
        except OSError as exc:
            raise refusal("an input disappeared during merge; nothing was published") from exc
        if actual != expected:
            raise refusal("an input changed during merge; nothing was published")
