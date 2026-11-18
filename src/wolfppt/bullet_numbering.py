"""Automatic bullet numbering (``a:buAutoNum``) display text.

The renderer and text-build playback both draw numbered bullets, so they share
this one definition of the supported numbering schemes and their display text.
"""

from __future__ import annotations

AUTO_NUMBER_FORMATS = {
    "arabicPeriod": "{number}.",
    "arabicPlain": "{number}",
    "romanUcPeriod": "{number}.",
    "romanLcPeriod": "{number}.",
    "alphaUcPeriod": "{number}.",
    "alphaLcPeriod": "{number}.",
    "alphaUcParenR": "{number})",
    "alphaLcParenR": "{number})",
    "alphaUcParenBoth": "({number})",
    "alphaLcParenBoth": "({number})",
}


def auto_number_text(kind: str, value: int) -> str:
    """Return the display text of numbering scheme ``kind`` at ``value``.

    ``kind`` must be a key of :data:`AUTO_NUMBER_FORMATS`; callers refuse other
    schemes before asking for text.
    """
    if kind.startswith("roman"):
        number = _roman(value)
        if kind.startswith("romanLc"):
            number = number.lower()
    elif kind.startswith("alpha"):
        number = _alphabetic(value)
        if kind.startswith("alphaLc"):
            number = number.lower()
    else:
        number = str(value)
    return AUTO_NUMBER_FORMATS[kind].format(number=number)


def _roman(value: int) -> str:
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result: list[str] = []
    for amount, numeral in numerals:
        count, value = divmod(value, amount)
        result.append(numeral * count)
    return "".join(result)


def _alphabetic(value: int) -> str:
    result: list[str] = []
    while value:
        value, remainder = divmod(value - 1, 26)
        result.append(chr(ord("A") + remainder))
    return "".join(reversed(result))
