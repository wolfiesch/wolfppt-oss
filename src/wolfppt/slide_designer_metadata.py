"""Read-only inspection of the designer ``p:extLst`` payload on a slide.

PowerPoint Designer stores its state as opaque ``p:ext`` entries below the slide's
``p:extLst``. This module only reads them from the source package. Saving never
rewrites them, so the original XML bytes are preserved by the package writer.
"""

from __future__ import annotations

from typing import Any

from .package_parts import XmlElementProxy

_NAMESPACES = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}


class DesignerMetadata(XmlElementProxy):
    """One payload element of a slide ``p:ext``, read-only.

    XML attributes read as Python attributes (``payload.marker``); ``attrib`` holds
    the full mapping when an attribute name collides with a property. ``uri`` is the
    owning ``p:ext`` URI.
    """

    def __init__(self, element: Any, uri: str) -> None:
        super().__init__(element._element)
        self._uri = uri

    @property
    def uri(self) -> str:
        return self._uri

    def __getattr__(self, name: str) -> str:
        if not name.startswith("_") and name in (attrib := self.attrib):
            return attrib[name]
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def __repr__(self) -> str:
        return f"<DesignerMetadata uri={self._uri!r} tag={self.tag!r}>"


def read_designer_metadata(slide: Any) -> tuple[DesignerMetadata, ...]:
    """Return every ``p:ext`` payload element of the slide, in document order."""
    try:
        root = slide.element
    except AttributeError:
        return ()
    return tuple(
        DesignerMetadata(payload, ext.get("uri", ""))
        for ext in root.findall("p:extLst/p:ext", _NAMESPACES)
        for payload in ext
    )
