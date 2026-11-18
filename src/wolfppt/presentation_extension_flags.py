"""Read-only typed access to presentation-properties extension flags.

``SlideShowSettings`` inherits :class:`PresentationExtensionFlags` to expose
``p14:showMediaControls`` (inside ``p:showPr/p:extLst``) and
``p15:chartTrackingRefBased`` (inside ``p:presentationPr/p:extLst``), plus a
read-only snapshot of the stored ``presentationPr`` element.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import XmlElementProxy

_P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
_P15_NS = "http://schemas.microsoft.com/office/powerpoint/2012/main"


def extension_bool(owner: ET.Element | None, namespace: str, names: tuple[str, ...]) -> bool | None:
    """Return the ``val`` boolean of one ``p:ext`` child, None when absent.

    Raises ``LifecycleRefusal`` for a duplicated flag or a non-xsd:boolean value.
    """
    from .presentation_slides import _P_NS, _show_child
    from .presentation_tags import LifecycleRefusal
    from .xml_helpers import ooxml_path

    if owner is None:
        return None
    extensions = _show_child(owner, "extLst")
    if extensions is None:
        return None
    tags = {f"{{{namespace}}}{name}" for name in names}
    matches = [
        child
        for extension in extensions
        if extension.tag == ooxml_path(owner, f"{{{_P_NS}}}ext")
        for child in extension
        if child.tag in tags
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise LifecycleRefusal(f"ambiguous {names[0]} extension")
    raw = matches[0].get("val")
    if raw is not None:
        raw = raw.strip()
    if raw not in ("true", "false", "1", "0"):
        raise LifecycleRefusal(f"{names[0]} extension requires an xsd:boolean val")
    return raw in ("true", "1")


class PresentationExtensionFlags:
    """Mixin for ``SlideShowSettings``: stored extension flags, read only."""

    _presentation: Any

    def _show(self) -> ET.Element | None:
        raise NotImplementedError

    def _properties(self) -> ET.Element | None:
        """Stored ``p:presentationPr`` root, read from the source package."""
        from .package_parts import open_package_source
        from .presentation_slides import _presentation_partname, _resolve_pres_props

        presentation = self._presentation
        if presentation._disposed:
            raise RuntimeError("presentation is disposed")
        source = presentation._source_path
        with open_package_source(source) as package:
            _, root = _resolve_pres_props(
                package, _presentation_partname(source), {}, read_only=True
            )
        return root

    @property
    def show_media_controls(self) -> bool | None:
        """Stored media-control visibility (``p14:showMediaControls``); None when absent."""
        return extension_bool(self._show(), _P14_NS, ("showMediaCtrls", "showMediaControls"))

    @property
    def chart_tracking_ref_based(self) -> bool | None:
        """Stored ``p15:chartTrackingRefBased``; None when absent."""
        return extension_bool(self._properties(), _P15_NS, ("chartTrackingRefBased",))

    @property
    def pres_props_element(self) -> XmlElementProxy | None:
        """Read-only stored presentationPr snapshot, including unknown extensions."""
        root = self._properties()
        return None if root is None else XmlElementProxy(root)
