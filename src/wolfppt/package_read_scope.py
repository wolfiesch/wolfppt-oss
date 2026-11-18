"""Share ZIP handles and parsed XML parts across one read-only package pass."""

from __future__ import annotations

import os
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from xml.etree import ElementTree as ET


class _SharedPackageReads:
    """Open ZIP handles and parsed XML roots owned by one scope."""

    __slots__ = ("handles", "xml_roots")

    def __init__(self) -> None:
        self.handles: dict[Any, zipfile.ZipFile] = {}
        self.xml_roots: dict[int, dict[str, ET.Element]] = {}

    def close(self) -> None:
        for package in self.handles.values():
            package.close()
        self.handles.clear()
        self.xml_roots.clear()


_SHARED_PACKAGE_READS: ContextVar[_SharedPackageReads | None] = ContextVar(
    "wolfppt_shared_package_reads", default=None
)


class BorrowedPackage:
    """Context manager lending a scope-owned ZIP handle without closing it."""

    __slots__ = ("_package",)

    def __init__(self, package: zipfile.ZipFile) -> None:
        self._package = package

    def __enter__(self) -> zipfile.ZipFile:
        return self._package

    def __exit__(self, *exc: object) -> None:
        return None


@contextmanager
def shared_package_reads() -> Iterator[None]:
    """Share package reads across one read-only pass over unchanging sources.

    Inside the block, ``package_parts.open_package_source`` opens each source's
    central directory once and :func:`package_xml` parses each XML part once;
    both are released when the outermost block exits. Use it only where no code
    inside rewrites the sources it reads, and treat returned roots as read-only.
    Call :func:`release_shared_package` before deleting a source inside it.
    """

    if _SHARED_PACKAGE_READS.get() is not None:
        yield
        return
    shared = _SharedPackageReads()
    token = _SHARED_PACKAGE_READS.set(shared)
    try:
        yield
    finally:
        _SHARED_PACKAGE_READS.reset(token)
        shared.close()


def _source_key(source: Any) -> Any:
    return os.fspath(source) if isinstance(source, (str, os.PathLike)) else source


def borrow_shared_package(
    source: Any, open_source: Callable[[Any], zipfile.ZipFile]
) -> BorrowedPackage | None:
    """Return the scope's handle for *source*, opening it once; None outside a scope."""

    shared = _SHARED_PACKAGE_READS.get()
    if shared is None:
        return None
    key = _source_key(source)
    package = shared.handles.get(key)
    if package is None:
        package = open_source(source)
        shared.handles[key] = package
        shared.xml_roots[id(package)] = {}
    return BorrowedPackage(package)


def release_shared_package(source: Any) -> None:
    """Close the scope-owned handle of *source* before deleting or rewriting it."""

    shared = _SHARED_PACKAGE_READS.get()
    if shared is None:
        return
    package = shared.handles.pop(_source_key(source), None)
    if package is not None:
        shared.xml_roots.pop(id(package), None)
        package.close()


def package_xml(package: zipfile.ZipFile, partname: str) -> ET.Element:
    """Parse one package XML part; raises ``KeyError`` or ``ET.ParseError``.

    A scope-owned handle parses each part once and later callers receive the
    same read-only root; any other handle parses afresh on every call.
    """

    shared = _SHARED_PACKAGE_READS.get()
    roots = None if shared is None else shared.xml_roots.get(id(package))
    if roots is None:
        return ET.fromstring(package.read(partname))
    root = roots.get(partname)
    if root is None:
        root = ET.fromstring(package.read(partname))
        roots[partname] = root
    return root
