"""Package URI value semantics for the supported python-pptx import alias."""

from __future__ import annotations

import posixpath
import re


class PackURI(str):
    """Absolute OPC part name, including the package pseudo-part ``/``."""

    _filename_re = re.compile(r"([a-zA-Z]+)([0-9]+)?")

    def __new__(cls, pack_uri_str: str) -> PackURI:
        if not pack_uri_str.startswith("/"):
            raise ValueError(f"PackURI must begin with slash, got {pack_uri_str!r}")
        return super().__new__(cls, pack_uri_str)

    @staticmethod
    def from_rel_ref(baseURI: str, relative_ref: str) -> PackURI:
        return PackURI(posixpath.abspath(posixpath.join(baseURI, relative_ref)))

    @property
    def baseURI(self) -> str:
        return posixpath.dirname(self)

    @property
    def filename(self) -> str:
        return posixpath.basename(self)

    @property
    def ext(self) -> str:
        return posixpath.splitext(self)[1][1:]

    @property
    def idx(self) -> int | None:
        match = self._filename_re.match(posixpath.splitext(self.filename)[0])
        return int(match[2]) if match is not None and match[2] else None

    @property
    def membername(self) -> str:
        return self[1:]

    def relative_ref(self, baseURI: str) -> str:
        return self[1:] if baseURI == "/" else posixpath.relpath(self, baseURI)

    @property
    def rels_uri(self) -> PackURI:
        return PackURI(posixpath.join(self.baseURI, "_rels", self.filename + ".rels"))


PACKAGE_URI = PackURI("/")
CONTENT_TYPES_URI = PackURI("/[Content_Types].xml")
