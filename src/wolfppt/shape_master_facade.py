"""Master-shape facade objects."""

from __future__ import annotations

from typing import Any

from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
)
from .shape_action_facade import PlaceholderFormat
from .shape_inspection import _shape_type_value
from .shape_xml import _shape_xml_element
from .text_facade import TextFrame


class MasterShape:
    def __init__(
        self,
        master: Any,
        index: int,
        payload: dict[str, Any],
    ) -> None:
        self._master = master
        self._index = index
        self._payload = dict(payload)

    @property
    def shape_id(self) -> int | str | None:
        raw = self._payload.get("id")
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return raw

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @property
    def shape_type(self) -> Any:
        return _shape_type_value(self)

    @property
    def is_placeholder(self) -> bool:
        return bool(self._payload.get("is_placeholder"))

    @property
    def placeholder_format(self) -> "PlaceholderFormat":
        if not self.is_placeholder:
            raise ValueError("shape is not a placeholder")
        return PlaceholderFormat(self)

    @property
    def has_chart(self) -> bool:
        return False

    @property
    def has_table(self) -> bool:
        return False

    @property
    def has_text_frame(self) -> bool:
        return self._payload.get("kind") in {"shape", "freeform"}

    @property
    def part(self) -> PackagePart:
        return self._master.part

    @property
    def text(self) -> str:
        return str(self._payload.get("text") or "")

    @property
    def text_frame(self) -> "TextFrame":
        if not self.has_text_frame:
            raise AttributeError("shape does not have a text frame")
        return TextFrame(self)

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._master._presentation.path,
            self._master.partname,
        )
        return XmlElementProxy(_shape_xml_element(root._element, self._payload))

    @property
    def _element(self) -> XmlElementProxy:
        return self.element
