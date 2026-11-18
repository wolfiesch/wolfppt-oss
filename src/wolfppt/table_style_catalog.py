"""Built-in table style catalog: the 74 styles as first-party region data.

Listing and naming the built-in styles is part of editing a table's style, so
the catalog lives apart from the renderer that turns a style into drawing
instructions.
"""

from __future__ import annotations

#: Where the built-in region definitions below come from.  The receipt records
#: this string, so a reader can see that these are WolfPPT's own definitions of
#: a documented standard rather than a copy of an Office resource.
BUILT_IN_TABLE_STYLE_SOURCE = (
    "first-party region definitions for the 74 built-in table styles of "
    "[MS-OE376] Part 4 Section 5.1.6.10 (15 base styles plus the documented "
    "colour replacements); no Microsoft Office style-parity claim"
)

#: The colour transforms the built-in styles use inside a colour element.
_TINT = "tint"
_SHADE = "shade"
_ALPHA = "alpha"

#: The region keys of one style, in the order the OOXML model states them.
_TABLE_STYLE_REGIONS = (
    "wholeTbl",
    "band1H",
    "band2H",
    "band1V",
    "band2V",
    "lastCol",
    "firstCol",
    "lastRow",
    "firstRow",
    "seCell",
    "swCell",
    "neCell",
    "nwCell",
)

#: The cell edges one region may declare, in OOXML order.
_TABLE_EDGES = ("left", "right", "top", "bottom", "insideH", "insideV")


def _ref(idx: int, color: str, *transforms: tuple[str, int]) -> tuple[object, ...]:
    """A theme style reference (``a:lnRef``/``a:fillRef``) with its colour."""
    return ("ref", idx, color, transforms)


def _line(
    width: int, color: str, *transforms: tuple[str, int], compound: str = "sng"
) -> tuple[object, ...]:
    """A literal border line with its own width, colour, and compound style."""
    return ("line", width, color, transforms, compound)


def _solid(color: str, *transforms: tuple[str, int]) -> tuple[object, ...]:
    """A literal solid fill, with any colour transforms."""
    return ("solid", color, transforms)


def _sides(
    left: object = None,
    right: object = None,
    top: object = None,
    bottom: object = None,
    inside_h: object = None,
    inside_v: object = None,
) -> tuple[object, ...]:
    """The six border edges of one region, in OOXML order."""
    return (left, right, top, bottom, inside_h, inside_v)


#: The 15 base built-in table styles, keyed by GUID, as region definitions.
#: Each entry is ``(name, regions, tblBg)``; a region declares any of ``fill``
#: (``"none"``, a solid, or a style reference), ``borders``, ``text``, ``bold``
#: and ``italic``, and a channel a region does not declare stays absent so the
#: next region in the chain still decides it.
_BUILT_IN_BASES: dict[str, tuple[str, dict[str, dict[str, object]], object]] = {
    "2D5ABB26-0587-4C30-8999-92F81FD0307C": (
        "No Style, No Grid",
        {
            "wholeTbl": {
                "text": "tx1",
                "fill": "none",
                "borders": _sides("none", "none", "none", "none", "none", "none"),
            },
        },
        None,
    ),
    "3C2FFA5D-87B4-456A-9821-1D502468CF0F": (
        "Themed Style 1 - Accent 1",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": "none",
                "borders": _sides(*(_ref(1, "accent1"),) * 6),
            },
            "band1H": {"fill": _solid("accent1", (_ALPHA, 40000))},
            "band1V": {
                "fill": _solid("accent1", (_ALPHA, 40000)),
                "borders": _sides(None, None, _ref(1, "accent1"), _ref(1, "accent1")),
            },
            "lastCol": {
                "bold": True,
                "borders": _sides(
                    _ref(2, "accent1"),
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    "none",
                ),
            },
            "firstCol": {
                "bold": True,
                "borders": _sides(
                    _ref(1, "accent1"),
                    _ref(2, "accent1"),
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    "none",
                ),
            },
            "lastRow": {
                "bold": True,
                "fill": "none",
                "borders": _sides(
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    _ref(2, "accent1"),
                    _ref(2, "accent1"),
                    "none",
                    "none",
                ),
            },
            "firstRow": {
                "text": "lt1",
                "bold": True,
                "fill": _solid("accent1"),
                "borders": _sides(
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    _ref(1, "accent1"),
                    _ref(2, "lt1"),
                    "none",
                    "none",
                ),
            },
        },
        (2, "accent1", 1),
    ),
    "5940675A-B579-460E-94D1-54222C63F5DA": (
        "No Style, Table Grid",
        {
            "wholeTbl": {
                "text": "tx1",
                "fill": "none",
                "borders": _sides(*(_line(12700, "tx1"),) * 6),
            },
        },
        None,
    ),
    "D113A9D2-9D6B-4929-AA2D-F23B5EE8CBE7": (
        "Themed Style 2 - Accent 1",
        {
            "wholeTbl": {
                "text": "lt1",
                "fill": "none",
                "borders": _sides(
                    *(_ref(1, "accent1", (_TINT, 50000)),) * 4,
                    "none",
                    "none",
                ),
            },
            "band1H": {"fill": _solid("lt1", (_ALPHA, 20000))},
            "band1V": {"fill": _solid("lt1", (_ALPHA, 20000))},
            "lastCol": {"bold": True, "borders": _sides(_ref(2, "lt1"))},
            "firstCol": {"bold": True, "borders": _sides(None, _ref(2, "lt1"))},
            "lastRow": {
                "bold": True,
                "fill": "none",
                "borders": _sides(None, None, _ref(2, "lt1")),
            },
            "firstRow": {
                "bold": True,
                "fill": "none",
                "borders": _sides(None, None, None, _ref(3, "lt1")),
            },
            "seCell": {"borders": _sides("none", None, "none")},
            "swCell": {"borders": _sides(None, "none", "none")},
            "neCell": {"borders": _sides(None, None, None, "none")},
        },
        (3, "accent1", 3),
    ),
    "9D7B26C5-4107-4FEC-AEDC-1716B250A1EF": (
        "Light Style 1",
        {
            "wholeTbl": {
                "text": "tx1",
                "fill": "none",
                "borders": _sides(
                    "none",
                    "none",
                    _line(12700, "tx1"),
                    _line(12700, "tx1"),
                    "none",
                    "none",
                ),
            },
            "band1H": {"fill": _solid("tx1", (_ALPHA, 20000))},
            "band1V": {"fill": _solid("tx1", (_ALPHA, 20000))},
            "lastCol": {"bold": True},
            "firstCol": {"bold": True},
            "lastRow": {
                "bold": True,
                "borders": _sides(None, None, _line(12700, "tx1")),
            },
            "firstRow": {
                "bold": True,
                "borders": _sides(None, None, None, _line(12700, "tx1")),
            },
        },
        None,
    ),
    "7E9639D4-E3E2-4D34-9284-5A2195B3D0D7": (
        "Light Style 2",
        {
            "wholeTbl": {
                "text": "tx1",
                "fill": "none",
                "borders": _sides(*(_ref(1, "tx1"),) * 4, "none", "none"),
            },
            "band1H": {"borders": _sides(None, None, _ref(1, "tx1"), _ref(1, "tx1"))},
            "band1V": {"borders": _sides(_ref(1, "tx1"), _ref(1, "tx1"))},
            "band2V": {"borders": _sides(_ref(1, "tx1"), _ref(1, "tx1"))},
            "lastCol": {"bold": True},
            "firstCol": {"bold": True},
            "lastRow": {
                "bold": True,
                "borders": _sides(None, None, _line(50800, "tx1", compound="dbl")),
            },
            "firstRow": {"text": "bg1", "bold": True},
        },
        None,
    ),
    "616DA210-FB5B-4158-B5E0-FEB733F419BA": (
        "Light Style 3",
        {
            "wholeTbl": {
                "text": "tx1",
                "fill": "none",
                "borders": _sides(*(_line(12700, "tx1"),) * 6),
            },
            "band1H": {"fill": _solid("tx1", (_ALPHA, 20000))},
            "band1V": {"fill": _solid("tx1", (_ALPHA, 20000))},
            "lastCol": {"bold": True},
            "firstCol": {"bold": True},
            "lastRow": {
                "bold": True,
                "fill": "none",
                "borders": _sides(None, None, _line(50800, "tx1", compound="dbl")),
            },
            "firstRow": {
                "bold": True,
                "fill": "none",
                "borders": _sides(None, None, None, _line(25400, "tx1")),
            },
        },
        None,
    ),
    "793D81CF-94F2-401A-BA57-92F5A7B2D0C5": (
        "Medium Style 1",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": _solid("lt1"),
                "borders": _sides(
                    _line(12700, "dk1"),
                    _line(12700, "dk1"),
                    _line(12700, "dk1"),
                    _line(12700, "dk1"),
                    _line(12700, "dk1"),
                    "none",
                ),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 20000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 20000))},
            "lastCol": {"bold": True},
            "firstCol": {"bold": True},
            "lastRow": {
                "bold": True,
                "fill": _solid("lt1"),
                "borders": _sides(None, None, _line(50800, "dk1", compound="dbl")),
            },
            "firstRow": {"text": "lt1", "bold": True, "fill": _solid("dk1")},
        },
        None,
    ),
    "073A0DAA-6AF3-43AB-8588-CEC1D06C72B9": (
        "Medium Style 2",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": _solid("dk1", (_TINT, 20000)),
                "borders": _sides(*(_line(12700, "lt1"),) * 6),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 40000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 40000))},
            "lastCol": {"text": "lt1", "bold": True, "fill": _solid("dk1")},
            "firstCol": {"text": "lt1", "bold": True, "fill": _solid("dk1")},
            "lastRow": {
                "text": "lt1",
                "bold": True,
                "fill": _solid("dk1"),
                "borders": _sides(None, None, _line(38100, "lt1")),
            },
            "firstRow": {
                "text": "lt1",
                "bold": True,
                "fill": _solid("dk1"),
                "borders": _sides(None, None, None, _line(38100, "lt1")),
            },
        },
        None,
    ),
    "8EC20E35-A176-4012-BC5E-935CFFF8708E": (
        "Medium Style 3",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": _solid("lt1"),
                "borders": _sides(
                    "none",
                    "none",
                    _line(25400, "dk1"),
                    _line(25400, "dk1"),
                    "none",
                    "none",
                ),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 20000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 20000))},
            "lastCol": {"text": "lt1", "bold": True, "fill": _solid("dk1")},
            "firstCol": {"text": "lt1", "bold": True, "fill": _solid("dk1")},
            "lastRow": {
                "bold": True,
                "fill": _solid("lt1"),
                "borders": _sides(None, None, _line(50800, "dk1", compound="dbl")),
            },
            "firstRow": {
                "text": "lt1",
                "bold": True,
                "fill": _solid("dk1"),
                "borders": _sides(None, None, None, _line(25400, "dk1")),
            },
            "seCell": {"text": "dk1", "bold": True},
            "swCell": {"text": "dk1", "bold": True},
        },
        None,
    ),
    "6E25E649-3F16-4E02-A733-19D2CDBF48F0": (
        "Medium Style 3 - Accent 1",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": _solid("lt1"),
                "borders": _sides(
                    "none",
                    "none",
                    _line(25400, "dk1"),
                    _line(25400, "dk1"),
                    "none",
                    "none",
                ),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 20000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 20000))},
            "lastCol": {"text": "lt1", "bold": True, "fill": _solid("accent1")},
            "firstCol": {"text": "lt1", "bold": True, "fill": _solid("accent1")},
            "lastRow": {
                "bold": True,
                "fill": _solid("lt1"),
                "borders": _sides(None, None, _line(50800, "dk1", compound="dbl")),
            },
            "firstRow": {
                "text": "lt1",
                "bold": True,
                "fill": _solid("accent1"),
                "borders": _sides(None, None, None, _line(25400, "dk1")),
            },
            "seCell": {"text": "dk1", "bold": True},
            "swCell": {"text": "dk1", "bold": True},
        },
        None,
    ),
    "D7AC3CCA-C797-4891-BE02-D94E43425B78": (
        "Medium Style 4",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": _solid("dk1", (_TINT, 20000)),
                "borders": _sides(*(_line(12700, "dk1"),) * 6),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 40000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 40000))},
            "lastCol": {"bold": True},
            "firstCol": {"bold": True},
            "lastRow": {
                "bold": True,
                "fill": _solid("dk1", (_TINT, 20000)),
                "borders": _sides(None, None, _line(25400, "dk1")),
            },
            "firstRow": {
                "bold": True,
                "fill": _solid("dk1", (_TINT, 20000)),
            },
        },
        None,
    ),
    "E8034E78-7F5D-4C2E-B375-FC64B27BC917": (
        "Dark Style 1",
        {
            "wholeTbl": {
                "text": "lt1",
                "fill": _solid("dk1", (_TINT, 20000)),
                "borders": _sides("none", "none", "none", "none", "none", "none"),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 40000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 40000))},
            "lastCol": {
                "bold": True,
                "fill": _solid("dk1", (_TINT, 60000)),
                "borders": _sides(_line(25400, "lt1")),
            },
            "firstCol": {
                "bold": True,
                "fill": _solid("dk1", (_TINT, 60000)),
                "borders": _sides(None, _line(25400, "lt1")),
            },
            "lastRow": {
                "bold": True,
                "fill": _solid("dk1", (_TINT, 60000)),
                "borders": _sides(None, None, _line(25400, "lt1")),
            },
            "firstRow": {
                "bold": True,
                "fill": _solid("dk1"),
                "borders": _sides(None, None, None, _line(25400, "lt1")),
            },
            "seCell": {"borders": _sides("none")},
            "swCell": {"borders": _sides(None, "none")},
            "neCell": {"borders": _sides("none")},
            "nwCell": {"borders": _sides(None, "none")},
        },
        None,
    ),
    "125E5076-3810-47DD-B79F-674D7AD40C01": (
        "Dark Style 1 - Accent 1",
        {
            "wholeTbl": {
                "text": "lt1",
                "fill": _solid("accent1"),
                "borders": _sides("none", "none", "none", "none", "none", "none"),
            },
            "band1H": {"fill": _solid("accent1", (_SHADE, 60000))},
            "band1V": {"fill": _solid("accent1", (_SHADE, 60000))},
            "lastCol": {
                "bold": True,
                "fill": _solid("accent1", (_SHADE, 60000)),
                "borders": _sides(_line(25400, "lt1")),
            },
            "firstCol": {
                "bold": True,
                "fill": _solid("accent1", (_SHADE, 60000)),
                "borders": _sides(None, _line(25400, "lt1")),
            },
            "lastRow": {
                "bold": True,
                "fill": _solid("accent1", (_SHADE, 40000)),
                "borders": _sides(None, None, _line(25400, "lt1")),
            },
            "firstRow": {
                "bold": True,
                "fill": _solid("dk1"),
                "borders": _sides(None, None, None, _line(25400, "lt1")),
            },
            "seCell": {"borders": _sides("none")},
            "swCell": {"borders": _sides(None, "none")},
            "neCell": {"borders": _sides("none")},
            "nwCell": {"borders": _sides(None, "none")},
        },
        None,
    ),
    "5202B0CA-FC54-4496-8BCA-5EF66A818D29": (
        "Dark Style 2",
        {
            "wholeTbl": {
                "text": "dk1",
                "fill": _solid("dk1", (_TINT, 20000)),
                "borders": _sides("none", "none", "none", "none", "none", "none"),
            },
            "band1H": {"fill": _solid("dk1", (_TINT, 40000))},
            "band1V": {"fill": _solid("dk1", (_TINT, 40000))},
            "lastCol": {"bold": True},
            "firstCol": {"bold": True},
            "lastRow": {
                "bold": True,
                "fill": _solid("dk1", (_TINT, 20000)),
                "borders": _sides(None, None, _line(50800, "dk1", compound="dbl")),
            },
            "firstRow": {"text": "lt1", "bold": True, "fill": _solid("dk1")},
        },
        None,
    ),
}

#: The 59 derived built-in styles, keyed by GUID: ``(base, name, rule)``.  The
#: rule maps a region (or ``"*"``) to the colour replacements that section
#: documents; a region listed in the entry's fourth member keeps its borders.
_BUILT_IN_DERIVED: dict[
    str, tuple[str, str, dict[str, dict[str, str]], tuple[str, ...]]
] = {}


def _derive(
    guid: str,
    base: str,
    name: str,
    rule: dict[str, dict[str, str]],
    protected: tuple[str, ...] = (),
) -> None:
    _BUILT_IN_DERIVED[guid] = (base, name, rule, protected)


def _accent_family(
    prefix: str,
    base: str,
    source: str,
    first: int = 1,
    last: int = 6,
) -> None:
    """Register one accent family whose rule replaces one colour."""
    for index in range(first, last + 1):
        _derive(
            _ACCENT_GUIDS[(prefix, index)],
            base,
            f"{prefix} - Accent {index}",
            {"*": {source: f"accent{index}"}},
        )


#: The GUID of every derived style of an accent family, by family and accent.
_ACCENT_GUIDS: dict[tuple[str, int], str] = {
    ("Themed Style 1", 2): "284E427A-3D55-4303-BF80-6455036E1DE7",
    ("Themed Style 1", 3): "69C7853C-536D-4A76-A0AE-DD22124D55A5",
    ("Themed Style 1", 4): "775DCB02-9BB8-47FD-8907-85C794F793BA",
    ("Themed Style 1", 5): "35758FB7-9AC5-4552-8A53-C91805E547FA",
    ("Themed Style 1", 6): "08FB837D-C827-4EFA-A057-4D05807E0F7C",
    ("Themed Style 2", 2): "18603FDC-E32A-4AB5-989C-0864C3EAD2B8",
    ("Themed Style 2", 3): "306799F8-075E-4A3A-A7F6-7FBC6576F1A4",
    ("Themed Style 2", 4): "E269D01E-BC32-4049-B463-5C60D7B0CCD2",
    ("Themed Style 2", 5): "327F97BB-C833-4FB7-BDE5-3F7075034690",
    ("Themed Style 2", 6): "638B1855-1B75-4FBE-930C-398BA8C253C6",
    ("Light Style 1", 1): "3B4B98B0-60AC-42C2-AFA5-B58CD77FA1E5",
    ("Light Style 1", 2): "0E3FDE45-AF77-4B5C-9715-49D594BDF05E",
    ("Light Style 1", 3): "C083E6E3-FA7D-4D7B-A595-EF9225AFEA82",
    ("Light Style 1", 4): "D27102A9-8310-4765-A935-A1911B00CA55",
    ("Light Style 1", 5): "5FD0F851-EC5A-4D38-B0AD-8093EC10F338",
    ("Light Style 1", 6): "68D230F3-CF80-4859-8CE7-A43EE81993B5",
    ("Light Style 2", 1): "69012ECD-51FC-41F1-AA8D-1B2483CD663E",
    ("Light Style 2", 2): "72833802-FEF1-4C79-8D5D-14CF1EAF98D9",
    ("Light Style 2", 3): "F2DE63D5-997A-4646-A377-4702673A728D",
    ("Light Style 2", 4): "17292A2E-F333-43FB-9621-5CBBE7FDCDCB",
    ("Light Style 2", 5): "5A111915-BE36-4E01-A7E5-04B1672EAD32",
    ("Light Style 2", 6): "912C8C85-51F0-491E-9774-3900AFEF0FD7",
    ("Light Style 3", 1): "BC89EF96-8CEA-46FF-86C4-4CE0E7609802",
    ("Light Style 3", 2): "5DA37D80-6434-44D0-A028-1B22A696006F",
    ("Light Style 3", 3): "8799B23B-EC83-4686-B30A-512413B5E67A",
    ("Light Style 3", 4): "ED083AE6-46FA-4A59-8FB0-9F97EB10719F",
    ("Light Style 3", 5): "BDBED569-4797-4DF1-A0F4-6AAB3CD982D8",
    ("Light Style 3", 6): "E8B1032C-EA38-4F05-BA0D-38AFFFC7BED3",
    ("Medium Style 1", 1): "B301B821-A1FF-4177-AEE7-76D212191A09",
    ("Medium Style 1", 2): "9DCAF9ED-07DC-4A11-8D7F-57B35C25682E",
    ("Medium Style 1", 3): "1FECB4D8-DB02-4DC6-A0A2-4F2EBAE1DC90",
    ("Medium Style 1", 4): "1E171933-4619-4E11-9A3F-F7608DF75F80",
    ("Medium Style 1", 5): "FABFCF23-3B69-468F-B69F-88F6DE6A72F2",
    ("Medium Style 1", 6): "10A1B5D5-9B99-4C35-A422-299274C87663",
    ("Medium Style 2", 1): "5C22544A-7EE6-4342-B048-85BDC9FD1C3A",
    ("Medium Style 2", 2): "21E4AEA4-8DFA-4A89-87EB-49C32662AFE0",
    ("Medium Style 2", 3): "F5AB1C69-6EDB-4FF4-983F-18BD219EF322",
    ("Medium Style 2", 4): "00A15C55-8517-42AA-B614-E9B94910E393",
    ("Medium Style 2", 5): "7DF18680-E054-41AD-8BC1-D1AEF772440D",
    ("Medium Style 2", 6): "93296810-A885-4BE3-A3E7-6D5BEEA58F35",
    ("Medium Style 3", 2): "85BE263C-DBD7-4A20-BB59-AAB30ACAA65A",
    ("Medium Style 3", 3): "EB344D84-9AFB-497E-A393-DC336BA19D2E",
    ("Medium Style 3", 4): "EB9631B5-78F2-41C9-869B-9F39066F8104",
    ("Medium Style 3", 5): "74C1A8A3-306A-4EB7-A6B1-4F7E0EB9C5D6",
    ("Medium Style 3", 6): "2A488322-F2BA-4B5B-9748-0D474271808F",
    ("Medium Style 4", 1): "69CF1AB2-1976-4502-BF36-3FF5EA218861",
    ("Medium Style 4", 2): "8A107856-5554-42FB-B03E-39F5DBC370BA",
    ("Medium Style 4", 3): "0505E3EF-67EA-436B-97B2-0124C06EBD24",
    ("Medium Style 4", 4): "C4B1156A-380E-4F78-BDF5-A606A8083BF9",
    ("Medium Style 4", 5): "22838BEF-8BB2-4498-84A7-C5851F593DF1",
    ("Medium Style 4", 6): "16D9F66E-5EB9-4882-86FB-DCBF35E3C3E4",
    ("Dark Style 1", 2): "37CE84F3-28C3-443E-9E96-99CF82512B78",
    ("Dark Style 1", 3): "D03447BB-5D67-496B-8E87-E561075AD55C",
    ("Dark Style 1", 4): "E929F9F4-4A8F-4326-A1B4-22849713DDAB",
    ("Dark Style 1", 5): "8FD4443E-F989-4FC4-A0C8-D5A2AF1F390B",
    ("Dark Style 1", 6): "AF606853-7671-496A-8E4F-DF71F8EC918B",
}

_accent_family("Themed Style 1", "3C2FFA5D-87B4-456A-9821-1D502468CF0F", "accent1", 2)
_accent_family("Themed Style 2", "D113A9D2-9D6B-4929-AA2D-F23B5EE8CBE7", "accent1", 2)
_accent_family("Light Style 1", "9D7B26C5-4107-4FEC-AEDC-1716B250A1EF", "tx1")
_accent_family("Light Style 2", "7E9639D4-E3E2-4D34-9284-5A2195B3D0D7", "tx1")
_accent_family("Light Style 3", "616DA210-FB5B-4158-B5E0-FEB733F419BA", "tx1")
_accent_family("Medium Style 1", "793D81CF-94F2-401A-BA57-92F5A7B2D0C5", "dk1")
_accent_family("Medium Style 2", "073A0DAA-6AF3-43AB-8588-CEC1D06C72B9", "dk1")
_accent_family("Medium Style 3", "6E25E649-3F16-4E02-A733-19D2CDBF48F0", "accent1", 2)
_accent_family("Medium Style 4", "D7AC3CCA-C797-4891-BE02-D94E43425B78", "dk1")
_accent_family("Dark Style 1", "125E5076-3810-47DD-B79F-674D7AD40C01", "accent1", 2)

#: Dark Style 2 carries two accents at once: its header row takes the even
#: accent and every other row the odd one, and the last row keeps the colour of
#: its top border, which is the one border the standard leaves alone.
_derive(
    "0660B408-B3CF-4A94-85FC-2B1E0A45F4A2",
    "5202B0CA-FC54-4496-8BCA-5EF66A818D29",
    "Dark Style 2 - Accent 1/Accent 2",
    {"*": {"dk1": "accent1"}, "firstRow": {"dk1": "accent2"}},
    ("lastRow",),
)
_derive(
    "91EBBBCC-DAD2-459C-BE2E-F6DE35CF9A28",
    "5202B0CA-FC54-4496-8BCA-5EF66A818D29",
    "Dark Style 2 - Accent 3/Accent 4",
    {"*": {"dk1": "accent3"}, "firstRow": {"dk1": "accent4"}},
    ("lastRow",),
)
_derive(
    "46F890A9-2807-4EBB-B81D-B2AA78EC7F39",
    "5202B0CA-FC54-4496-8BCA-5EF66A818D29",
    "Dark Style 2 - Accent 5/Accent 6",
    {"*": {"dk1": "accent5"}, "firstRow": {"dk1": "accent6"}},
    ("lastRow",),
)


def built_in_table_styles() -> dict[str, str]:
    """Return ``{style id: style name}`` for every built-in table style."""
    names = {f"{{{guid}}}": base[0] for guid, base in _BUILT_IN_BASES.items()}
    names.update(
        {f"{{{guid}}}": derived[1] for guid, derived in _BUILT_IN_DERIVED.items()}
    )
    return names
