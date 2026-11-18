"""DrawingML paragraph bullet facade and validation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .image_inputs import image_source_for_queue as _image_source_for_queue

if TYPE_CHECKING:
    from .text_facade import TextParagraph

# Complete enumeration of ST_TextAutonumberScheme from ECMA-376 Part 1, 20.1.10.60
OOXML_AUTONUMBER_STYLES = frozenset(
    {
        "alphaLcParenBoth",
        "alphaLcParenR",
        "alphaLcPeriod",
        "alphaUcParenBoth",
        "alphaUcParenR",
        "alphaUcPeriod",
        "arabic1Minus",
        "arabic2Minus",
        "arabicDbPeriod",
        "arabicDbPlain",
        "arabicParenBoth",
        "arabicParenR",
        "arabicPeriod",
        "arabicPlain",
        "circleNumDbPlain",
        "circleNumWdBlackPlain",
        "circleNumWdWhitePlain",
        "ea1ChsPeriod",
        "ea1ChsPlain",
        "ea1ChtPeriod",
        "ea1ChtPlain",
        "ea1JpnChsDbPeriod",
        "ea1JpnKorPeriod",
        "ea1JpnKorPlain",
        "hebrew2Minus",
        "hindiAlpha1Period",
        "hindiAlphaPeriod",
        "hindiNumParenR",
        "hindiNumPeriod",
        "romanLcParenBoth",
        "romanLcParenR",
        "romanLcPeriod",
        "romanUcParenBoth",
        "romanUcParenR",
        "romanUcPeriod",
        "thaiAlphaPeriod",
        "thaiAlphaParenR",
        "thaiAlphaParenBoth",
        "thaiNumPeriod",
        "thaiNumParenR",
        "thaiNumParenBoth",
    }
)


def _validate_start_at(start_at: Any) -> int:
    """Validate OOXML startAt attribute (integer between 1 and 32767)."""
    if isinstance(start_at, bool):
        raise TypeError(f"start_at must be an integer >= 1, got {start_at!r}")
    try:
        val = int(start_at)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"start_at must be an integer >= 1, got {start_at!r}") from exc
    if val < 1 or val > 32767:
        raise ValueError(f"start_at must be between 1 and 32767, got {val}")
    return val


def _validate_auto_number_style(style: Any) -> str:
    """Validate OOXML auto-number style scheme name."""
    if not isinstance(style, str):
        raise TypeError(f"auto-number style must be a str, got {type(style).__name__}")
    if not style.strip():
        raise ValueError(f"auto-number style must be a non-empty string, got {style!r}")
    cleaned = style.strip()
    if cleaned not in OOXML_AUTONUMBER_STYLES:
        raise ValueError(
            f"unsupported auto-number style: {cleaned!r}. "
            f"Must be an explicitly enumerated OOXML style such as 'arabicPeriod', 'romanLcPeriod', etc."
        )
    return cleaned


def _validate_bullet_char(char: Any) -> str:
    """Validate character bullet character."""
    if not isinstance(char, str):
        raise TypeError(f"bullet character must be a str, got {type(char).__name__}")
    if len(char) == 0:
        raise ValueError(f"bullet character must be a non-empty string, got {char!r}")
    return char


def _validate_bullet_color(color: Any) -> str | None:
    """Validate bullet color as 6-character hex RGB."""
    if color is None:
        return None
    if not isinstance(color, str):
        raise TypeError(
            f"bullet color must be a hex RGB string, got {type(color).__name__}"
        )
    clean = color.strip().lstrip("#")
    if len(clean) != 6 or not all(c in "0123456789abcdefABCDEF" for c in clean):
        raise ValueError(
            f"bullet color must be a 6-character hex RGB string, got {color!r}"
        )
    return clean.upper()


def _validate_bullet_font(font: Any) -> str | None:
    """Validate bullet font typeface name."""
    if font is None:
        return None
    if not isinstance(font, str):
        raise TypeError(f"bullet font must be a str, got {type(font).__name__}")
    if not font.strip():
        raise ValueError(f"bullet font must be a non-empty string, got {font!r}")
    return font.strip()


class _AutoNumberCallable:
    """Helper descriptor callable that supports both method call and attribute inspection."""

    def __init__(self, bullet: BulletFormat) -> None:
        self._bullet = bullet

    def __call__(
        self,
        style: str = "arabicPeriod",
        start_at: int = 1,
        *,
        font: str | None = None,
        color: str | None = None,
    ) -> None:
        self._bullet.auto_number_set(
            style=style, start_at=start_at, font=font, color=color
        )

    @property
    def style(self) -> str | None:
        return self._bullet.auto_number_style

    @property
    def start_at(self) -> int | None:
        return self._bullet.start_at

    def __bool__(self) -> bool:
        return self._bullet.type == "auto_number"

    def __str__(self) -> str:
        return str(self._bullet.auto_number_style or "")

    def __repr__(self) -> str:
        if self._bullet.type == "auto_number":
            return (
                f"<AutoNumber style={self._bullet.auto_number_style!r} "
                f"start_at={self._bullet.start_at}>"
            )
        return "<AutoNumber (inactive)>"


class _AutoNumberDescriptor:
    def __get__(self, instance: BulletFormat | None, owner: Any = None) -> Any:
        if instance is None:
            return self
        return _AutoNumberCallable(instance)

    def __set__(self, instance: BulletFormat, value: Any) -> None:
        if isinstance(value, str):
            instance.auto_number_set(style=value)
        elif isinstance(value, dict):
            instance.auto_number_set(**value)
        else:
            raise TypeError(
                f"auto_number must be a style string or dict, got {type(value).__name__}"
            )


class BulletFormat:
    """Facade for managing paragraph bullet point properties in DrawingML (a:pPr)."""

    auto_number = _AutoNumberDescriptor()

    def __init__(self, paragraph: TextParagraph) -> None:
        self._paragraph = paragraph

    @property
    def _shape(self) -> Any:
        return self._paragraph._shape

    @property
    def _index(self) -> int:
        return self._paragraph._index

    def _get_payload(self) -> dict[str, Any] | None:
        from .text_facade_inspection import _shape_text_paragraph_bullet

        return _shape_text_paragraph_bullet(self._shape, self._index)

    def _set_payload_and_queue(self, payload: dict[str, Any] | None) -> None:
        from .text_facade_inspection import _set_shape_paragraph_bullet_payload
        from .text_facade_queue import _queue_paragraph_bullet_state

        _set_shape_paragraph_bullet_payload(self._shape, self._index, payload)
        _queue_paragraph_bullet_state(self._shape, self._index, payload)

    @property
    def type(self) -> str | None:
        """Return bullet type: 'char', 'auto_number', 'none', 'blip', or None if inherited."""
        payload = self._get_payload()
        if not payload:
            return None
        return payload.get("type")

    @property
    def char(self) -> str | None:
        """Return the bullet character if type is 'char', else None."""
        payload = self._get_payload()
        if not payload or payload.get("type") != "char":
            return None
        return payload.get("char")

    @char.setter
    def char(self, value: str | None) -> None:
        if value is None:
            self.clear()
            return
        validated = _validate_bullet_char(value)
        payload = self._get_payload()
        font = payload.get("font") if payload else None
        color = payload.get("color") if payload else None
        new_payload = {
            "type": "char",
            "char": validated,
            "font": font,
            "color": color,
        }
        self._set_payload_and_queue(new_payload)

    def character(
        self,
        char: str = "•",
        *,
        font: str | None = None,
        color: str | None = None,
    ) -> None:
        """Set a character bullet with optional custom font and color."""
        validated_char = _validate_bullet_char(char)
        validated_font = _validate_bullet_font(font)
        validated_color = _validate_bullet_color(color)
        payload = {
            "type": "char",
            "char": validated_char,
            "font": validated_font,
            "color": validated_color,
        }
        self._set_payload_and_queue(payload)

    def auto_number_set(
        self,
        style: str = "arabicPeriod",
        start_at: int = 1,
        *,
        font: str | None = None,
        color: str | None = None,
    ) -> None:
        """Configure an auto-numbered bullet."""
        validated_style = _validate_auto_number_style(style)
        validated_start = _validate_start_at(start_at)
        validated_font = _validate_bullet_font(font)
        validated_color = _validate_bullet_color(color)
        payload = {
            "type": "auto_number",
            "style": validated_style,
            "start_at": validated_start,
            "font": validated_font,
            "color": validated_color,
        }
        self._set_payload_and_queue(payload)

    def picture(self, image_file: Any) -> None:
        """Use an internally packaged image as this paragraph's bullet."""
        self._set_payload_and_queue(
            {"type": "blip", "image_source": _image_source_for_queue(image_file)}
        )

    @property
    def auto_number_style(self) -> str | None:
        """Return auto-number style name if type is 'auto_number', else None."""
        payload = self._get_payload()
        if not payload or payload.get("type") != "auto_number":
            return None
        return payload.get("style")

    @auto_number_style.setter
    def auto_number_style(self, value: str) -> None:
        validated = _validate_auto_number_style(value)
        payload = self._get_payload()
        start_at = payload.get("start_at", 1) if payload else 1
        font = payload.get("font") if payload else None
        color = payload.get("color") if payload else None
        new_payload = {
            "type": "auto_number",
            "style": validated,
            "start_at": start_at,
            "font": font,
            "color": color,
        }
        self._set_payload_and_queue(new_payload)

    @property
    def style(self) -> str | None:
        """Alias for auto_number_style."""
        return self.auto_number_style

    @style.setter
    def style(self, value: str) -> None:
        self.auto_number_style = value

    @property
    def start_at(self) -> int | None:
        """Return auto-number start value (>= 1) if type is 'auto_number', else None."""
        payload = self._get_payload()
        if not payload or payload.get("type") != "auto_number":
            return None
        return payload.get("start_at", 1)

    @start_at.setter
    def start_at(self, value: int) -> None:
        validated = _validate_start_at(value)
        payload = self._get_payload()
        style = payload.get("style", "arabicPeriod") if payload else "arabicPeriod"
        font = payload.get("font") if payload else None
        color = payload.get("color") if payload else None
        new_payload = {
            "type": "auto_number",
            "style": style,
            "start_at": validated,
            "font": font,
            "color": color,
        }
        self._set_payload_and_queue(new_payload)

    @property
    def font(self) -> str | None:
        """Return bullet font typeface name if custom, else None."""
        payload = self._get_payload()
        if not payload:
            return None
        return payload.get("font")

    @font.setter
    def font(self, value: str | None) -> None:
        validated = _validate_bullet_font(value)
        payload = self._get_payload()
        if payload is None or payload.get("type") is None:
            # Default to character bullet with this font
            new_payload = {
                "type": "char",
                "char": "•",
                "font": validated,
                "color": None,
            }
        else:
            new_payload = dict(payload)
            new_payload["font"] = validated
        self._set_payload_and_queue(new_payload)

    @property
    def color(self) -> str | None:
        """Return bullet color hex RGB string if custom, else None."""
        payload = self._get_payload()
        if not payload:
            return None
        return payload.get("color")

    @color.setter
    def color(self, value: str | None) -> None:
        validated = _validate_bullet_color(value)
        payload = self._get_payload()
        if payload is None or payload.get("type") is None:
            new_payload = {
                "type": "char",
                "char": "•",
                "font": None,
                "color": validated,
            }
        else:
            new_payload = dict(payload)
            new_payload["color"] = validated
        self._set_payload_and_queue(new_payload)

    def none(self) -> None:
        """Explicitly disable bullets (<a:buNone/>), overriding inherited bullets."""
        self._set_payload_and_queue({"type": "none"})

    def clear(self) -> None:
        """Remove all bullet elements (<a:bu*>), restoring inheritance from layout/master."""
        self._set_payload_and_queue(None)

    def __bool__(self) -> bool:
        """True if an explicit bullet definition exists on this paragraph."""
        return self.type is not None

    def __repr__(self) -> str:
        btype = self.type
        if btype == "char":
            return f"<BulletFormat char={self.char!r}>"
        if btype == "auto_number":
            return f"<BulletFormat auto_number={self.style!r} start_at={self.start_at}>"
        if btype == "none":
            return "<BulletFormat none>"
        return "<BulletFormat inherited>"
