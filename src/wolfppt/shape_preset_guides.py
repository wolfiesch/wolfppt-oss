"""Typed preset adjustment handles and declared DrawingML adjust-guide names.

``PRESET_ADJUST_GUIDE_NAMES`` maps every ``ST_ShapeType`` value (187) to the ``a:gd/@name``
values of its default adjust list, in declaration order. It is generated, not curated, from the
ECMA-376 Part 1 preset shape definitions vendored in this repository:

    source:   engines/wolfrender/crates/wolfrender-geometry/data/presetShapeDefinitions.xml
    git blob: 4705e14015466c0b487c82209ce7845e1b113a61

The source declares ``upDownArrow`` twice and omits ``upArrow``; ``SOURCE_CORRECTIONS`` supplies
``upArrow`` (``adj1``, ``adj2``, as ECMA-376 and ``render_presets._up_arrow`` declare it) only when
the source lacks it. Regenerate the literal with::

    python -c "import pathlib, wolfppt.shape_preset_guides as m; \
print(m.render_table(m.preset_adjust_guide_names(pathlib.Path(\
'engines/wolfrender/crates/wolfrender-geometry/data/presetShapeDefinitions.xml').read_bytes())))"

``engines/wolfppt/tests/test_p4_census_ppt_shape_geometry_connectors.py`` re-runs the generator
against the source file and asserts it equals the table.

``preset_adjustment_handles(shape)`` returns typed, shape-bound handles in the source
``a:ahLst`` order. Each handle has an XY or polar ``kind`` and named ``axes``; each axis
exposes its guide name, X/Y/radius/angle kind, source bounds, and editable value.
``axis.raw_value`` uses integer DrawingML units. ``axis.ratio`` uses linear ratios
(100000 raw units = 1.0), while ``axis.degrees`` uses angles (60000 raw units = 1 degree).
The ratio's reference dimension is determined by the preset formula, not necessarily the
shape's width or height. Numeric edits truncate to integer raw units, like ``Shape.adjustments``.
Raw edits outside signed 64-bit guide units refuse before entering the native save queue.

The installed module embeds defaults and handle declarations generated from the same source,
plus the ``upArrow`` rows the source omits: defaults ``adj1``/``adj2`` of 50000 and the two XY
handles ECMA-376 declares, ``adj1`` on X at ``(x1, b)`` and ``adj2`` on Y (``0`` to ``maxAdj2``)
at ``(l, y2)``, mirroring ``downArrow`` exactly as ``preset_outline_geometry._up_arrow`` mirrors
its outline. It never reads the repository XML at runtime. A preset absent from the handle table
is refused with ``AdjustmentHandleError`` rather than inferred. Shape-bound access requires
a saved, live preset shape, and queued preset changes must be saved first. Custom geometry
uses its separate handle API. Bounds and positions may contain guide expressions: they are
reported, not evaluated or enforced here. Editing a guide does not imply renderer support for
its preset; unsupported renderers retain their own named refusals.

``preset_adjustment_metadata(definitions)`` regenerates the two metadata tables from XML
bytes, returning ``(defaults, handles)``; unlike the names table it applies no missing-source
correction. Source duplicate handling remains first-declaration-wins.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real
from typing import Any
from xml.etree import ElementTree as ET

__all__ = [
    "AdjustmentAxisKind",
    "AdjustmentHandleError",
    "AdjustmentHandleKind",
    "PRESET_ADJUST_GUIDE_NAMES",
    "PRESET_ADJUSTMENT_DEFAULTS",
    "PRESET_ADJUSTMENT_HANDLE_DEFINITIONS",
    "PresetAdjustmentAxis",
    "PresetAdjustmentHandle",
    "PresetHandleRow",
    "SOURCE_CORRECTIONS",
    "preset_adjust_guide_names",
    "preset_adjustment_handles",
    "preset_adjustment_metadata",
    "render_table",
]

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

SOURCE_CORRECTIONS: dict[str, tuple[str, ...]] = {"upArrow": ("adj1", "adj2")}


def preset_adjustment_metadata(
    definitions: bytes,
) -> tuple[
    dict[str, tuple[tuple[str, int], ...]],
    dict[str, tuple[PresetHandleRow, ...]],
]:
    """Generate default values and handle rows without guessing missing source data.

    Duplicate preset declarations use the first occurrence, like the names generator.
    Nonconstant defaults and undeclared handle references raise ``AdjustmentHandleError``.
    """
    root = ET.fromstring(definitions.removeprefix(b"\xef\xbb\xbf"))
    defaults: dict[str, tuple[tuple[str, int], ...]] = {}
    handles: dict[str, tuple[PresetHandleRow, ...]] = {}

    def operand(value: str | None) -> int | str | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return value

    for preset in root:
        if preset.tag in defaults:
            continue
        values: list[tuple[str, int]] = []
        for guide in preset.findall(f"{{{_A_NS}}}avLst/{{{_A_NS}}}gd"):
            name = guide.get("name")
            formula = guide.get("fmla", "")
            if not name or not formula.startswith("val "):
                raise AdjustmentHandleError(f"preset {preset.tag!r} lacks a constant default")
            try:
                values.append((name, int(formula[4:])))
            except ValueError as exc:
                raise AdjustmentHandleError(
                    f"preset {preset.tag!r} has an invalid default for {name!r}"
                ) from exc
        defaults[preset.tag] = tuple(values)
        declared = dict(values)
        rows: list[PresetHandleRow] = []
        adjust_list = preset.find(f"{{{_A_NS}}}ahLst")
        for handle in [] if adjust_list is None else adjust_list:
            if handle.tag == f"{{{_A_NS}}}ahXY":
                kind = "xy"
                attributes = (("x", "X"), ("y", "Y"))
            elif handle.tag == f"{{{_A_NS}}}ahPolar":
                kind = "polar"
                attributes = (("radius", "R"), ("angle", "Ang"))
            else:
                raise AdjustmentHandleError(f"preset {preset.tag!r} has an unknown handle")
            axes = []
            for axis, suffix in attributes:
                name = handle.get(f"gdRef{suffix}")
                if name is None:
                    continue
                if name not in declared:
                    raise AdjustmentHandleError(
                        f"preset {preset.tag!r} handle refers to undeclared guide {name!r}"
                    )
                axes.append(
                    (
                        axis,
                        name,
                        operand(handle.get(f"min{suffix}")),
                        operand(handle.get(f"max{suffix}")),
                    )
                )
            position = handle.find(f"{{{_A_NS}}}pos")
            if not axes or position is None:
                raise AdjustmentHandleError(f"preset {preset.tag!r} has an incomplete handle")
            x, y = operand(position.get("x")), operand(position.get("y"))
            if x is None or y is None:
                raise AdjustmentHandleError(f"preset {preset.tag!r} has no handle position")
            rows.append((kind, tuple(axes), (x, y)))
        handles[preset.tag] = tuple(rows)
    return dict(sorted(defaults.items())), dict(sorted(handles.items()))


def preset_adjust_guide_names(definitions: bytes) -> dict[str, tuple[str, ...]]:
    """Generate the preset -> adjust-guide-names table from presetShapeDefinitions.xml bytes."""
    root = ET.fromstring(definitions.removeprefix(b"\xef\xbb\xbf"))
    names: dict[str, tuple[str, ...]] = {}
    for preset in root:
        if preset.tag in names:
            continue
        adjust_list = preset.find(f"{{{_A_NS}}}avLst")
        names[preset.tag] = tuple(
            str(guide.get("name"))
            for guide in ([] if adjust_list is None else adjust_list)
            if guide.tag == f"{{{_A_NS}}}gd"
        )
    for preset, guides in SOURCE_CORRECTIONS.items():
        names.setdefault(preset, guides)
    return dict(sorted(names.items()))


def render_table(names: dict[str, tuple[str, ...]]) -> str:
    """Render ``names`` as the ``PRESET_ADJUST_GUIDE_NAMES`` literal below."""
    rows = "".join(f"    {preset!r}: {guides!r},\n" for preset, guides in sorted(names.items()))
    return "PRESET_ADJUST_GUIDE_NAMES: dict[str, tuple[str, ...]] = {\n" + rows + "}\n"


PRESET_ADJUST_GUIDE_NAMES: dict[str, tuple[str, ...]] = {
    "accentBorderCallout1": ("adj1", "adj2", "adj3", "adj4"),
    "accentBorderCallout2": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6"),
    "accentBorderCallout3": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6", "adj7", "adj8"),
    "accentCallout1": ("adj1", "adj2", "adj3", "adj4"),
    "accentCallout2": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6"),
    "accentCallout3": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6", "adj7", "adj8"),
    "actionButtonBackPrevious": (),
    "actionButtonBeginning": (),
    "actionButtonBlank": (),
    "actionButtonDocument": (),
    "actionButtonEnd": (),
    "actionButtonForwardNext": (),
    "actionButtonHelp": (),
    "actionButtonHome": (),
    "actionButtonInformation": (),
    "actionButtonMovie": (),
    "actionButtonReturn": (),
    "actionButtonSound": (),
    "arc": ("adj1", "adj2"),
    "bentArrow": ("adj1", "adj2", "adj3", "adj4"),
    "bentConnector2": (),
    "bentConnector3": ("adj1",),
    "bentConnector4": ("adj1", "adj2"),
    "bentConnector5": ("adj1", "adj2", "adj3"),
    "bentUpArrow": ("adj1", "adj2", "adj3"),
    "bevel": ("adj",),
    "blockArc": ("adj1", "adj2", "adj3"),
    "borderCallout1": ("adj1", "adj2", "adj3", "adj4"),
    "borderCallout2": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6"),
    "borderCallout3": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6", "adj7", "adj8"),
    "bracePair": ("adj",),
    "bracketPair": ("adj",),
    "callout1": ("adj1", "adj2", "adj3", "adj4"),
    "callout2": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6"),
    "callout3": ("adj1", "adj2", "adj3", "adj4", "adj5", "adj6", "adj7", "adj8"),
    "can": ("adj",),
    "chartPlus": (),
    "chartStar": (),
    "chartX": (),
    "chevron": ("adj",),
    "chord": ("adj1", "adj2"),
    "circularArrow": ("adj1", "adj2", "adj3", "adj4", "adj5"),
    "cloud": (),
    "cloudCallout": ("adj1", "adj2"),
    "corner": ("adj1", "adj2"),
    "cornerTabs": (),
    "cube": ("adj",),
    "curvedConnector2": (),
    "curvedConnector3": ("adj1",),
    "curvedConnector4": ("adj1", "adj2"),
    "curvedConnector5": ("adj1", "adj2", "adj3"),
    "curvedDownArrow": ("adj1", "adj2", "adj3"),
    "curvedLeftArrow": ("adj1", "adj2", "adj3"),
    "curvedRightArrow": ("adj1", "adj2", "adj3"),
    "curvedUpArrow": ("adj1", "adj2", "adj3"),
    "decagon": ("vf",),
    "diagStripe": ("adj",),
    "diamond": (),
    "dodecagon": (),
    "donut": ("adj",),
    "doubleWave": ("adj1", "adj2"),
    "downArrow": ("adj1", "adj2"),
    "downArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "ellipse": (),
    "ellipseRibbon": ("adj1", "adj2", "adj3"),
    "ellipseRibbon2": ("adj1", "adj2", "adj3"),
    "flowChartAlternateProcess": (),
    "flowChartCollate": (),
    "flowChartConnector": (),
    "flowChartDecision": (),
    "flowChartDelay": (),
    "flowChartDisplay": (),
    "flowChartDocument": (),
    "flowChartExtract": (),
    "flowChartInputOutput": (),
    "flowChartInternalStorage": (),
    "flowChartMagneticDisk": (),
    "flowChartMagneticDrum": (),
    "flowChartMagneticTape": (),
    "flowChartManualInput": (),
    "flowChartManualOperation": (),
    "flowChartMerge": (),
    "flowChartMultidocument": (),
    "flowChartOfflineStorage": (),
    "flowChartOffpageConnector": (),
    "flowChartOnlineStorage": (),
    "flowChartOr": (),
    "flowChartPredefinedProcess": (),
    "flowChartPreparation": (),
    "flowChartProcess": (),
    "flowChartPunchedCard": (),
    "flowChartPunchedTape": (),
    "flowChartSort": (),
    "flowChartSummingJunction": (),
    "flowChartTerminator": (),
    "foldedCorner": ("adj",),
    "frame": ("adj1",),
    "funnel": (),
    "gear6": ("adj1", "adj2"),
    "gear9": ("adj1", "adj2"),
    "halfFrame": ("adj1", "adj2"),
    "heart": (),
    "heptagon": ("hf", "vf"),
    "hexagon": ("adj", "vf"),
    "homePlate": ("adj",),
    "horizontalScroll": ("adj",),
    "irregularSeal1": (),
    "irregularSeal2": (),
    "leftArrow": ("adj1", "adj2"),
    "leftArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "leftBrace": ("adj1", "adj2"),
    "leftBracket": ("adj",),
    "leftCircularArrow": ("adj1", "adj2", "adj3", "adj4", "adj5"),
    "leftRightArrow": ("adj1", "adj2"),
    "leftRightArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "leftRightCircularArrow": ("adj1", "adj2", "adj3", "adj4", "adj5"),
    "leftRightRibbon": ("adj1", "adj2", "adj3"),
    "leftRightUpArrow": ("adj1", "adj2", "adj3"),
    "leftUpArrow": ("adj1", "adj2", "adj3"),
    "lightningBolt": (),
    "line": (),
    "lineInv": (),
    "mathDivide": ("adj1", "adj2", "adj3"),
    "mathEqual": ("adj1", "adj2"),
    "mathMinus": ("adj1",),
    "mathMultiply": ("adj1",),
    "mathNotEqual": ("adj1", "adj2", "adj3"),
    "mathPlus": ("adj1",),
    "moon": ("adj",),
    "noSmoking": ("adj",),
    "nonIsoscelesTrapezoid": ("adj1", "adj2"),
    "notchedRightArrow": ("adj1", "adj2"),
    "octagon": ("adj",),
    "parallelogram": ("adj",),
    "pentagon": ("hf", "vf"),
    "pie": ("adj1", "adj2"),
    "pieWedge": (),
    "plaque": ("adj",),
    "plaqueTabs": (),
    "plus": ("adj",),
    "quadArrow": ("adj1", "adj2", "adj3"),
    "quadArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "rect": (),
    "ribbon": ("adj1", "adj2"),
    "ribbon2": ("adj1", "adj2"),
    "rightArrow": ("adj1", "adj2"),
    "rightArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "rightBrace": ("adj1", "adj2"),
    "rightBracket": ("adj",),
    "round1Rect": ("adj",),
    "round2DiagRect": ("adj1", "adj2"),
    "round2SameRect": ("adj1", "adj2"),
    "roundRect": ("adj",),
    "rtTriangle": (),
    "smileyFace": ("adj",),
    "snip1Rect": ("adj",),
    "snip2DiagRect": ("adj1", "adj2"),
    "snip2SameRect": ("adj1", "adj2"),
    "snipRoundRect": ("adj1", "adj2"),
    "squareTabs": (),
    "star10": ("adj", "hf"),
    "star12": ("adj",),
    "star16": ("adj",),
    "star24": ("adj",),
    "star32": ("adj",),
    "star4": ("adj",),
    "star5": ("adj", "hf", "vf"),
    "star6": ("adj", "hf"),
    "star7": ("adj", "hf", "vf"),
    "star8": ("adj",),
    "straightConnector1": (),
    "stripedRightArrow": ("adj1", "adj2"),
    "sun": ("adj",),
    "swooshArrow": ("adj1", "adj2"),
    "teardrop": ("adj",),
    "trapezoid": ("adj",),
    "triangle": ("adj",),
    "upArrow": ("adj1", "adj2"),
    "upArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "upDownArrow": ("adj1", "adj2"),
    "upDownArrowCallout": ("adj1", "adj2", "adj3", "adj4"),
    "uturnArrow": ("adj1", "adj2", "adj3", "adj4", "adj5"),
    "verticalScroll": ("adj",),
    "wave": ("adj1", "adj2"),
    "wedgeEllipseCallout": ("adj1", "adj2"),
    "wedgeRectCallout": ("adj1", "adj2"),
    "wedgeRoundRectCallout": ("adj1", "adj2", "adj3"),
}


# Generated from the source blob documented above; no runtime data-file dependency.
PRESET_ADJUSTMENT_DEFAULTS: dict[str, tuple[tuple[str, int], ...]] = {
    "accentBorderCallout1": (("adj1", 18750), ("adj2", -8333), ("adj3", 112500), ("adj4", -38333)),
    "accentBorderCallout2": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 112500),
        ("adj6", -46667),
    ),
    "accentBorderCallout3": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 100000),
        ("adj6", -16667),
        ("adj7", 112963),
        ("adj8", -8333),
    ),
    "accentCallout1": (("adj1", 18750), ("adj2", -8333), ("adj3", 112500), ("adj4", -38333)),
    "accentCallout2": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 112500),
        ("adj6", -46667),
    ),
    "accentCallout3": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 100000),
        ("adj6", -16667),
        ("adj7", 112963),
        ("adj8", -8333),
    ),
    "actionButtonBackPrevious": (),
    "actionButtonBeginning": (),
    "actionButtonBlank": (),
    "actionButtonDocument": (),
    "actionButtonEnd": (),
    "actionButtonForwardNext": (),
    "actionButtonHelp": (),
    "actionButtonHome": (),
    "actionButtonInformation": (),
    "actionButtonMovie": (),
    "actionButtonReturn": (),
    "actionButtonSound": (),
    "arc": (("adj1", 16200000), ("adj2", 0)),
    "bentArrow": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 43750)),
    "bentConnector2": (),
    "bentConnector3": (("adj1", 50000),),
    "bentConnector4": (("adj1", 50000), ("adj2", 50000)),
    "bentConnector5": (("adj1", 50000), ("adj2", 50000), ("adj3", 50000)),
    "bentUpArrow": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000)),
    "bevel": (("adj", 12500),),
    "blockArc": (("adj1", 10800000), ("adj2", 0), ("adj3", 25000)),
    "borderCallout1": (("adj1", 18750), ("adj2", -8333), ("adj3", 112500), ("adj4", -38333)),
    "borderCallout2": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 112500),
        ("adj6", -46667),
    ),
    "borderCallout3": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 100000),
        ("adj6", -16667),
        ("adj7", 112963),
        ("adj8", -8333),
    ),
    "bracePair": (("adj", 8333),),
    "bracketPair": (("adj", 16667),),
    "callout1": (("adj1", 18750), ("adj2", -8333), ("adj3", 112500), ("adj4", -38333)),
    "callout2": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 112500),
        ("adj6", -46667),
    ),
    "callout3": (
        ("adj1", 18750),
        ("adj2", -8333),
        ("adj3", 18750),
        ("adj4", -16667),
        ("adj5", 100000),
        ("adj6", -16667),
        ("adj7", 112963),
        ("adj8", -8333),
    ),
    "can": (("adj", 25000),),
    "chartPlus": (),
    "chartStar": (),
    "chartX": (),
    "chevron": (("adj", 50000),),
    "chord": (("adj1", 2700000), ("adj2", 16200000)),
    "circularArrow": (
        ("adj1", 12500),
        ("adj2", 1142319),
        ("adj3", 20457681),
        ("adj4", 10800000),
        ("adj5", 12500),
    ),
    "cloud": (),
    "cloudCallout": (("adj1", -20833), ("adj2", 62500)),
    "corner": (("adj1", 50000), ("adj2", 50000)),
    "cornerTabs": (),
    "cube": (("adj", 25000),),
    "curvedConnector2": (),
    "curvedConnector3": (("adj1", 50000),),
    "curvedConnector4": (("adj1", 50000), ("adj2", 50000)),
    "curvedConnector5": (("adj1", 50000), ("adj2", 50000), ("adj3", 50000)),
    "curvedDownArrow": (("adj1", 25000), ("adj2", 50000), ("adj3", 25000)),
    "curvedLeftArrow": (("adj1", 25000), ("adj2", 50000), ("adj3", 25000)),
    "curvedRightArrow": (("adj1", 25000), ("adj2", 50000), ("adj3", 25000)),
    "curvedUpArrow": (("adj1", 25000), ("adj2", 50000), ("adj3", 25000)),
    "decagon": (("vf", 105146),),
    "diagStripe": (("adj", 50000),),
    "diamond": (),
    "dodecagon": (),
    "donut": (("adj", 25000),),
    "doubleWave": (("adj1", 6250), ("adj2", 0)),
    "downArrow": (("adj1", 50000), ("adj2", 50000)),
    "downArrowCallout": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 64977)),
    "ellipse": (),
    "ellipseRibbon": (("adj1", 25000), ("adj2", 50000), ("adj3", 12500)),
    "ellipseRibbon2": (("adj1", 25000), ("adj2", 50000), ("adj3", 12500)),
    "flowChartAlternateProcess": (),
    "flowChartCollate": (),
    "flowChartConnector": (),
    "flowChartDecision": (),
    "flowChartDelay": (),
    "flowChartDisplay": (),
    "flowChartDocument": (),
    "flowChartExtract": (),
    "flowChartInputOutput": (),
    "flowChartInternalStorage": (),
    "flowChartMagneticDisk": (),
    "flowChartMagneticDrum": (),
    "flowChartMagneticTape": (),
    "flowChartManualInput": (),
    "flowChartManualOperation": (),
    "flowChartMerge": (),
    "flowChartMultidocument": (),
    "flowChartOfflineStorage": (),
    "flowChartOffpageConnector": (),
    "flowChartOnlineStorage": (),
    "flowChartOr": (),
    "flowChartPredefinedProcess": (),
    "flowChartPreparation": (),
    "flowChartProcess": (),
    "flowChartPunchedCard": (),
    "flowChartPunchedTape": (),
    "flowChartSort": (),
    "flowChartSummingJunction": (),
    "flowChartTerminator": (),
    "foldedCorner": (("adj", 16667),),
    "frame": (("adj1", 12500),),
    "funnel": (),
    "gear6": (("adj1", 15000), ("adj2", 3526)),
    "gear9": (("adj1", 10000), ("adj2", 1763)),
    "halfFrame": (("adj1", 33333), ("adj2", 33333)),
    "heart": (),
    "heptagon": (("hf", 102572), ("vf", 105210)),
    "hexagon": (("adj", 25000), ("vf", 115470)),
    "homePlate": (("adj", 50000),),
    "horizontalScroll": (("adj", 12500),),
    "irregularSeal1": (),
    "irregularSeal2": (),
    "leftArrow": (("adj1", 50000), ("adj2", 50000)),
    "leftArrowCallout": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 64977)),
    "leftBrace": (("adj1", 8333), ("adj2", 50000)),
    "leftBracket": (("adj", 8333),),
    "leftCircularArrow": (
        ("adj1", 12500),
        ("adj2", -1142319),
        ("adj3", 1142319),
        ("adj4", 10800000),
        ("adj5", 12500),
    ),
    "leftRightArrow": (("adj1", 50000), ("adj2", 50000)),
    "leftRightArrowCallout": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 48123)),
    "leftRightCircularArrow": (
        ("adj1", 12500),
        ("adj2", 1142319),
        ("adj3", 20457681),
        ("adj4", 11942319),
        ("adj5", 12500),
    ),
    "leftRightRibbon": (("adj1", 50000), ("adj2", 50000), ("adj3", 16667)),
    "leftRightUpArrow": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000)),
    "leftUpArrow": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000)),
    "lightningBolt": (),
    "line": (),
    "lineInv": (),
    "mathDivide": (("adj1", 23520), ("adj2", 5880), ("adj3", 11760)),
    "mathEqual": (("adj1", 23520), ("adj2", 11760)),
    "mathMinus": (("adj1", 23520),),
    "mathMultiply": (("adj1", 23520),),
    "mathNotEqual": (("adj1", 23520), ("adj2", 6600000), ("adj3", 11760)),
    "mathPlus": (("adj1", 23520),),
    "moon": (("adj", 50000),),
    "noSmoking": (("adj", 18750),),
    "nonIsoscelesTrapezoid": (("adj1", 25000), ("adj2", 25000)),
    "notchedRightArrow": (("adj1", 50000), ("adj2", 50000)),
    "octagon": (("adj", 29289),),
    "parallelogram": (("adj", 25000),),
    "pentagon": (("hf", 105146), ("vf", 110557)),
    "pie": (("adj1", 0), ("adj2", 16200000)),
    "pieWedge": (),
    "plaque": (("adj", 16667),),
    "plaqueTabs": (),
    "plus": (("adj", 25000),),
    "quadArrow": (("adj1", 22500), ("adj2", 22500), ("adj3", 22500)),
    "quadArrowCallout": (("adj1", 18515), ("adj2", 18515), ("adj3", 18515), ("adj4", 48123)),
    "rect": (),
    "ribbon": (("adj1", 16667), ("adj2", 50000)),
    "ribbon2": (("adj1", 16667), ("adj2", 50000)),
    "rightArrow": (("adj1", 50000), ("adj2", 50000)),
    "rightArrowCallout": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 64977)),
    "rightBrace": (("adj1", 8333), ("adj2", 50000)),
    "rightBracket": (("adj", 8333),),
    "round1Rect": (("adj", 16667),),
    "round2DiagRect": (("adj1", 16667), ("adj2", 0)),
    "round2SameRect": (("adj1", 16667), ("adj2", 0)),
    "roundRect": (("adj", 16667),),
    "rtTriangle": (),
    "smileyFace": (("adj", 4653),),
    "snip1Rect": (("adj", 16667),),
    "snip2DiagRect": (("adj1", 0), ("adj2", 16667)),
    "snip2SameRect": (("adj1", 16667), ("adj2", 0)),
    "snipRoundRect": (("adj1", 16667), ("adj2", 16667)),
    "squareTabs": (),
    "star10": (("adj", 42533), ("hf", 105146)),
    "star12": (("adj", 37500),),
    "star16": (("adj", 37500),),
    "star24": (("adj", 37500),),
    "star32": (("adj", 37500),),
    "star4": (("adj", 12500),),
    "star5": (("adj", 19098), ("hf", 105146), ("vf", 110557)),
    "star6": (("adj", 28868), ("hf", 115470)),
    "star7": (("adj", 34601), ("hf", 102572), ("vf", 105210)),
    "star8": (("adj", 37500),),
    "straightConnector1": (),
    "stripedRightArrow": (("adj1", 50000), ("adj2", 50000)),
    "sun": (("adj", 25000),),
    "swooshArrow": (("adj1", 25000), ("adj2", 16667)),
    "teardrop": (("adj", 100000),),
    "trapezoid": (("adj", 25000),),
    "triangle": (("adj", 50000),),
    "upArrow": (("adj1", 50000), ("adj2", 50000)),
    "upArrowCallout": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 64977)),
    "upDownArrow": (("adj1", 50000), ("adj2", 50000)),
    "upDownArrowCallout": (("adj1", 25000), ("adj2", 25000), ("adj3", 25000), ("adj4", 48123)),
    "uturnArrow": (
        ("adj1", 25000),
        ("adj2", 25000),
        ("adj3", 25000),
        ("adj4", 43750),
        ("adj5", 75000),
    ),
    "verticalScroll": (("adj", 12500),),
    "wave": (("adj1", 12500), ("adj2", 0)),
    "wedgeEllipseCallout": (("adj1", -20833), ("adj2", 62500)),
    "wedgeRectCallout": (("adj1", -20833), ("adj2", 62500)),
    "wedgeRoundRectCallout": (("adj1", -20833), ("adj2", 62500), ("adj3", 16667)),
}

PresetHandleRow = tuple[
    str,
    tuple[tuple[str, str, int | str | None, int | str | None], ...],
    tuple[int | str, int | str],
]

PRESET_ADJUSTMENT_HANDLE_DEFINITIONS: dict[str, tuple[PresetHandleRow, ...]] = {
    "accentBorderCallout1": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
    ),
    "accentBorderCallout2": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
    ),
    "accentBorderCallout3": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
        (
            "xy",
            (("x", "adj8", -2147483647, 2147483647), ("y", "adj7", -2147483647, 2147483647)),
            ("x4", "y4"),
        ),
    ),
    "accentCallout1": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
    ),
    "accentCallout2": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
    ),
    "accentCallout3": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
        (
            "xy",
            (("x", "adj8", -2147483647, 2147483647), ("y", "adj7", -2147483647, 2147483647)),
            ("x4", "y4"),
        ),
    ),
    "actionButtonBackPrevious": (),
    "actionButtonBeginning": (),
    "actionButtonBlank": (),
    "actionButtonDocument": (),
    "actionButtonEnd": (),
    "actionButtonForwardNext": (),
    "actionButtonHelp": (),
    "actionButtonHome": (),
    "actionButtonInformation": (),
    "actionButtonMovie": (),
    "actionButtonReturn": (),
    "actionButtonSound": (),
    "arc": (
        ("polar", (("angle", "adj1", 0, 21599999),), ("x1", "y1")),
        ("polar", (("angle", "adj2", 0, 21599999),), ("x2", "y2")),
    ),
    "bentArrow": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("th", "b")),
        ("xy", (("y", "adj2", 0, 50000),), ("r", "y4")),
        ("xy", (("x", "adj3", 0, 50000),), ("x4", "t")),
        ("xy", (("x", "adj4", 0, "maxAdj4"),), ("bd", "t")),
    ),
    "bentConnector2": (),
    "bentConnector3": (("xy", (("x", "adj1", -2147483647, 2147483647),), ("x1", "vc")),),
    "bentConnector4": (
        ("xy", (("x", "adj1", -2147483647, 2147483647),), ("x1", "y1")),
        ("xy", (("y", "adj2", -2147483647, 2147483647),), ("x2", "y2")),
    ),
    "bentConnector5": (
        ("xy", (("x", "adj1", -2147483647, 2147483647),), ("x1", "y1")),
        ("xy", (("y", "adj2", -2147483647, 2147483647),), ("x2", "y2")),
        ("xy", (("x", "adj3", -2147483647, 2147483647),), ("x3", "y3")),
    ),
    "bentUpArrow": (
        ("xy", (("y", "adj1", 0, 50000),), ("l", "y2")),
        ("xy", (("x", "adj2", 0, 50000),), ("x1", "t")),
        ("xy", (("y", "adj3", 0, 50000),), ("x2", "y1")),
    ),
    "bevel": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "blockArc": (
        ("polar", (("angle", "adj1", 0, 21599999),), ("x1", "y1")),
        ("polar", (("radius", "adj3", 0, 50000), ("angle", "adj2", 0, 21599999)), ("x2", "y2")),
    ),
    "borderCallout1": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
    ),
    "borderCallout2": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
    ),
    "borderCallout3": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
        (
            "xy",
            (("x", "adj8", -2147483647, 2147483647), ("y", "adj7", -2147483647, 2147483647)),
            ("x4", "y4"),
        ),
    ),
    "bracePair": (("xy", (("y", "adj", 0, 25000),), ("l", "x1")),),
    "bracketPair": (("xy", (("y", "adj", 0, 50000),), ("l", "x1")),),
    "callout1": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
    ),
    "callout2": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
    ),
    "callout3": (
        (
            "xy",
            (("x", "adj2", -2147483647, 2147483647), ("y", "adj1", -2147483647, 2147483647)),
            ("x1", "y1"),
        ),
        (
            "xy",
            (("x", "adj4", -2147483647, 2147483647), ("y", "adj3", -2147483647, 2147483647)),
            ("x2", "y2"),
        ),
        (
            "xy",
            (("x", "adj6", -2147483647, 2147483647), ("y", "adj5", -2147483647, 2147483647)),
            ("x3", "y3"),
        ),
        (
            "xy",
            (("x", "adj8", -2147483647, 2147483647), ("y", "adj7", -2147483647, 2147483647)),
            ("x4", "y4"),
        ),
    ),
    "can": (("xy", (("y", "adj", 0, "maxAdj"),), ("hc", "y2")),),
    "chartPlus": (),
    "chartStar": (),
    "chartX": (),
    "chevron": (("xy", (("x", "adj", 0, "maxAdj"),), ("x2", "t")),),
    "chord": (
        ("polar", (("angle", "adj1", 0, 21599999),), ("x1", "y1")),
        ("polar", (("angle", "adj2", 0, 21599999),), ("x2", "y2")),
    ),
    "circularArrow": (
        ("polar", (("angle", "adj2", 0, "maxAng"),), ("xA", "yA")),
        ("polar", (("angle", "adj4", 0, 21599999),), ("xE", "yE")),
        ("polar", (("radius", "adj1", 0, "maxAdj1"), ("angle", "adj3", 0, 21599999)), ("xF", "yF")),
        ("polar", (("radius", "adj5", 0, 25000),), ("xB", "yB")),
    ),
    "cloud": (),
    "cloudCallout": (
        (
            "xy",
            (("x", "adj1", -2147483647, 2147483647), ("y", "adj2", -2147483647, 2147483647)),
            ("xPos", "yPos"),
        ),
    ),
    "corner": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("l", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "t")),
    ),
    "cornerTabs": (),
    "cube": (("xy", (("y", "adj", 0, 100000),), ("l", "y1")),),
    "curvedConnector2": (),
    "curvedConnector3": (("xy", (("x", "adj1", -2147483647, 2147483647),), ("x2", "vc")),),
    "curvedConnector4": (
        ("xy", (("x", "adj1", -2147483647, 2147483647),), ("x2", "y1")),
        ("xy", (("y", "adj2", -2147483647, 2147483647),), ("x3", "y4")),
    ),
    "curvedConnector5": (
        ("xy", (("x", "adj1", -2147483647, 2147483647),), ("x3", "y1")),
        ("xy", (("y", "adj2", -2147483647, 2147483647),), ("x1", "y4")),
        ("xy", (("x", "adj3", -2147483647, 2147483647),), ("x6", "y5")),
    ),
    "curvedDownArrow": (
        ("xy", (("x", "adj1", 0, "adj2"),), ("x7", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x4", "b")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "y1")),
    ),
    "curvedLeftArrow": (
        ("xy", (("y", "adj1", 0, "a2"),), ("x1", "y5")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("r", "y4")),
        ("xy", (("x", "adj3", 0, "maxAdj3"),), ("x1", "b")),
    ),
    "curvedRightArrow": (
        ("xy", (("y", "adj1", 0, "a2"),), ("x1", "y5")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("r", "y4")),
        ("xy", (("x", "adj3", 0, "maxAdj3"),), ("x1", "b")),
    ),
    "curvedUpArrow": (
        ("xy", (("x", "adj1", 0, "a2"),), ("x7", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x4", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "y1")),
    ),
    "decagon": (),
    "diagStripe": (("xy", (("y", "adj", 0, 100000),), ("l", "y2")),),
    "diamond": (),
    "dodecagon": (),
    "donut": (("polar", (("radius", "adj", 0, 50000),), ("dr", "vc")),),
    "doubleWave": (
        ("xy", (("y", "adj1", 0, 12500),), ("l", "y1")),
        ("xy", (("x", "adj2", -10000, 10000),), ("xAdj", "b")),
    ),
    "downArrow": (
        ("xy", (("x", "adj1", 0, 100000),), ("x1", "t")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("l", "y1")),
    ),
    "downArrowCallout": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("x2", "y3")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "b")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "y3")),
        ("xy", (("y", "adj4", 0, "maxAdj4"),), ("l", "y2")),
    ),
    "ellipse": (),
    "ellipseRibbon": (
        ("xy", (("y", "adj1", 0, 100000),), ("hc", "q1")),
        ("xy", (("x", "adj2", 25000, 75000),), ("x2", "b")),
        ("xy", (("y", "adj3", "minAdj3", "a1"),), ("l", "y8")),
    ),
    "ellipseRibbon2": (
        ("xy", (("y", "adj1", 0, 100000),), ("hc", "rh")),
        ("xy", (("x", "adj2", 25000, 100000),), ("x2", "t")),
        ("xy", (("y", "adj3", "minAdj3", "a1"),), ("l", "dy1")),
    ),
    "flowChartAlternateProcess": (),
    "flowChartCollate": (),
    "flowChartConnector": (),
    "flowChartDecision": (),
    "flowChartDelay": (),
    "flowChartDisplay": (),
    "flowChartDocument": (),
    "flowChartExtract": (),
    "flowChartInputOutput": (),
    "flowChartInternalStorage": (),
    "flowChartMagneticDisk": (),
    "flowChartMagneticDrum": (),
    "flowChartMagneticTape": (),
    "flowChartManualInput": (),
    "flowChartManualOperation": (),
    "flowChartMerge": (),
    "flowChartMultidocument": (),
    "flowChartOfflineStorage": (),
    "flowChartOffpageConnector": (),
    "flowChartOnlineStorage": (),
    "flowChartOr": (),
    "flowChartPredefinedProcess": (),
    "flowChartPreparation": (),
    "flowChartProcess": (),
    "flowChartPunchedCard": (),
    "flowChartPunchedTape": (),
    "flowChartSort": (),
    "flowChartSummingJunction": (),
    "flowChartTerminator": (),
    "foldedCorner": (("xy", (("x", "adj", 0, 50000),), ("x1", "b")),),
    "frame": (("xy", (("x", "adj1", 0, 50000),), ("x1", "t")),),
    "funnel": (),
    "gear6": (
        ("xy", (("y", "adj1", 0, 20000),), ("xD6", "yD6")),
        ("xy", (("x", "adj2", 0, 5358),), ("xA6", "yD6")),
    ),
    "gear9": (
        ("xy", (("y", "adj1", 0, 20000),), ("xD9", "yD9")),
        ("xy", (("x", "adj2", 0, 2679),), ("xA9", "yD9")),
    ),
    "halfFrame": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("l", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "t")),
    ),
    "heart": (),
    "heptagon": (),
    "hexagon": (("xy", (("x", "adj", 0, "maxAdj"),), ("x1", "t")),),
    "homePlate": (("xy", (("x", "adj", 0, "maxAdj"),), ("x1", "t")),),
    "horizontalScroll": (("xy", (("x", "adj", 0, 25000),), ("ch", "t")),),
    "irregularSeal1": (),
    "irregularSeal2": (),
    "leftArrow": (
        ("xy", (("y", "adj1", 0, 100000),), ("r", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x2", "t")),
    ),
    "leftArrowCallout": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("x1", "y2")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("l", "y1")),
        ("xy", (("x", "adj3", 0, "maxAdj3"),), ("x1", "t")),
        ("xy", (("x", "adj4", 0, "maxAdj4"),), ("x2", "b")),
    ),
    "leftBrace": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("hc", "y1")),
        ("xy", (("y", "adj2", 0, 100000),), ("l", "y3")),
    ),
    "leftBracket": (("xy", (("y", "adj", 0, "maxAdj"),), ("l", "y1")),),
    "leftCircularArrow": (
        ("polar", (("angle", "adj2", "minAng", 0),), ("xA", "yA")),
        ("polar", (("angle", "adj4", 0, 21599999),), ("xE", "yE")),
        ("polar", (("radius", "adj1", 0, "maxAdj1"), ("angle", "adj3", 0, 21599999)), ("xF", "yF")),
        ("polar", (("radius", "adj5", 0, 25000),), ("xB", "yB")),
    ),
    "leftRightArrow": (
        ("xy", (("y", "adj1", 0, 100000),), ("x3", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x2", "t")),
    ),
    "leftRightArrowCallout": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("x1", "y2")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("l", "y1")),
        ("xy", (("x", "adj3", 0, "maxAdj3"),), ("x1", "t")),
        ("xy", (("x", "adj4", 0, "maxAdj4"),), ("x2", "b")),
    ),
    "leftRightCircularArrow": (
        ("polar", (("angle", "adj2", 0, "maxAng"),), ("xA", "yA")),
        ("polar", (("angle", "adj4", 0, 21599999),), ("xE", "yE")),
        ("polar", (("radius", "adj1", 0, "maxAdj1"), ("angle", "adj3", 0, 21599999)), ("xF", "yF")),
        ("polar", (("radius", "adj5", 0, 25000),), ("xB", "yB")),
    ),
    "leftRightRibbon": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("x4", "ry2")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "t")),
        ("xy", (("y", "adj3", 0, 33333),), ("x3", "ry2")),
    ),
    "leftRightUpArrow": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("x3", "x1")),
        ("xy", (("x", "adj2", 0, 50000),), ("x2", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "x1")),
    ),
    "leftUpArrow": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("x3", "y3")),
        ("xy", (("x", "adj2", 0, 50000),), ("x2", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("x3", "x1")),
    ),
    "lightningBolt": (),
    "line": (),
    "lineInv": (),
    "mathDivide": (
        ("xy", (("y", "adj1", 1000, 36745),), ("l", "y3")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("r", "y2")),
        ("xy", (("x", "adj3", 1000, "maxAdj3"),), ("x2", "t")),
    ),
    "mathEqual": (
        ("xy", (("y", "adj1", 0, 36745),), ("l", "y1")),
        ("xy", (("y", "adj2", 0, "mAdj2"),), ("r", "y2")),
    ),
    "mathMinus": (("xy", (("y", "adj1", 0, 100000),), ("l", "y1")),),
    "mathMultiply": (("xy", (("y", "adj1", 0, 51965),), ("l", "th")),),
    "mathNotEqual": (
        ("xy", (("y", "adj1", 0, 50000),), ("l", "y1")),
        ("polar", (("angle", "adj2", 4200000, 6600000),), ("lx", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "y2")),
    ),
    "mathPlus": (("xy", (("y", "adj1", 0, 73490),), ("l", "y2")),),
    "moon": (("xy", (("x", "adj", 0, 87500),), ("g0w", "vc")),),
    "noSmoking": (("polar", (("radius", "adj", 0, 50000),), ("dr", "vc")),),
    "nonIsoscelesTrapezoid": (
        ("xy", (("x", "adj1", 0, "maxAdj"),), ("x2", "t")),
        ("xy", (("x", "adj2", 0, "maxAdj"),), ("x3", "t")),
    ),
    "notchedRightArrow": (
        ("xy", (("y", "adj1", 0, 100000),), ("r", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x2", "t")),
    ),
    "octagon": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "parallelogram": (("xy", (("x", "adj", 0, "maxAdj"),), ("x2", "t")),),
    "pentagon": (),
    "pie": (
        ("polar", (("angle", "adj1", 0, 21599999),), ("x1", "y1")),
        ("polar", (("angle", "adj2", 0, 21599999),), ("x2", "y2")),
    ),
    "pieWedge": (),
    "plaque": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "plaqueTabs": (),
    "plus": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "quadArrow": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("x3", "x1")),
        ("xy", (("x", "adj2", 0, 50000),), ("x2", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "x1")),
    ),
    "quadArrowCallout": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("x4", "ah")),
        ("xy", (("x", "adj2", 0, 50000),), ("x3", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "ah")),
        ("xy", (("y", "adj4", "a1", "maxAdj4"),), ("l", "y2")),
    ),
    "rect": (),
    "ribbon": (
        ("xy", (("y", "adj1", 0, 33333),), ("hc", "y2")),
        ("xy", (("x", "adj2", 25000, 75000),), ("x2", "t")),
    ),
    "ribbon2": (
        ("xy", (("y", "adj1", 0, 33333),), ("hc", "y2")),
        ("xy", (("x", "adj2", 25000, 75000),), ("x2", "b")),
    ),
    "rightArrow": (
        ("xy", (("y", "adj1", 0, 100000),), ("l", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "t")),
    ),
    "rightArrowCallout": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("x3", "y2")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("r", "y1")),
        ("xy", (("x", "adj3", 0, "maxAdj3"),), ("x3", "t")),
        ("xy", (("x", "adj4", 0, "maxAdj4"),), ("x2", "b")),
    ),
    "rightBrace": (
        ("xy", (("y", "adj1", 0, "maxAdj1"),), ("hc", "y1")),
        ("xy", (("y", "adj2", 0, 100000),), ("r", "y3")),
    ),
    "rightBracket": (("xy", (("y", "adj", 0, "maxAdj"),), ("r", "y1")),),
    "round1Rect": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "round2DiagRect": (
        ("xy", (("x", "adj1", 0, 50000),), ("x1", "t")),
        ("xy", (("x", "adj2", 0, 50000),), ("x2", "t")),
    ),
    "round2SameRect": (
        ("xy", (("x", "adj1", 0, 50000),), ("tx2", "t")),
        ("xy", (("x", "adj2", 0, 50000),), ("bx1", "b")),
    ),
    "roundRect": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "rtTriangle": (),
    "smileyFace": (("xy", (("y", "adj", -4653, 4653),), ("hc", "y4")),),
    "snip1Rect": (("xy", (("x", "adj", 0, 50000),), ("x1", "t")),),
    "snip2DiagRect": (
        ("xy", (("x", "adj1", 0, 50000),), ("lx1", "t")),
        ("xy", (("x", "adj2", 0, 50000),), ("rx2", "t")),
    ),
    "snip2SameRect": (
        ("xy", (("x", "adj1", 0, 50000),), ("tx2", "t")),
        ("xy", (("x", "adj2", 0, 50000),), ("bx1", "b")),
    ),
    "snipRoundRect": (
        ("xy", (("x", "adj1", 0, 50000),), ("x1", "t")),
        ("xy", (("x", "adj2", 0, 50000),), ("x2", "t")),
    ),
    "squareTabs": (),
    "star10": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star12": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star16": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star24": (("xy", (("y", "adj", 0, "ssd2"),), ("hc", "yAdj")),),
    "star32": (("xy", (("y", "adj", 0, "ssd2"),), ("hc", "yAdj")),),
    "star4": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star5": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star6": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star7": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "star8": (("xy", (("y", "adj", 0, 50000),), ("hc", "yAdj")),),
    "straightConnector1": (),
    "stripedRightArrow": (
        ("xy", (("y", "adj1", 0, 100000),), ("l", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x5", "t")),
    ),
    "sun": (("xy", (("x", "adj", 12500, 46875),), ("x19", "vc")),),
    "swooshArrow": (
        ("xy", (("y", "adj1", 1, 75000),), ("xF", "yF")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("xB", "yB")),
    ),
    "teardrop": (("xy", (("x", "adj", 0, 200000),), ("x1", "t")),),
    "trapezoid": (("xy", (("x", "adj", 0, "maxAdj"),), ("x2", "t")),),
    "triangle": (("xy", (("x", "adj", 0, 100000),), ("x2", "t")),),
    "upArrow": (
        ("xy", (("x", "adj1", 0, 100000),), ("x1", "b")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("l", "y2")),
    ),
    "upArrowCallout": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("x2", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "y1")),
        ("xy", (("y", "adj4", 0, "maxAdj4"),), ("l", "y2")),
    ),
    "upDownArrow": (
        ("xy", (("x", "adj1", 0, 100000),), ("x1", "y3")),
        ("xy", (("y", "adj2", 0, "maxAdj2"),), ("l", "y2")),
    ),
    "upDownArrowCallout": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("x2", "y1")),
        ("xy", (("x", "adj2", 0, "maxAdj2"),), ("x1", "t")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("r", "y1")),
        ("xy", (("y", "adj4", 0, "maxAdj4"),), ("l", "y2")),
    ),
    "uturnArrow": (
        ("xy", (("x", "adj1", 0, "maxAdj1"),), ("th", "b")),
        ("xy", (("x", "adj2", 0, 25000),), ("x6", "b")),
        ("xy", (("y", "adj3", 0, "maxAdj3"),), ("x6", "y4")),
        ("xy", (("x", "adj4", 0, "maxAdj4"),), ("bd", "t")),
        ("xy", (("y", "adj5", "minAdj5", 100000),), ("r", "y5")),
    ),
    "verticalScroll": (("xy", (("y", "adj", 0, 25000),), ("l", "ch")),),
    "wave": (
        ("xy", (("y", "adj1", 0, 20000),), ("l", "y1")),
        ("xy", (("x", "adj2", -10000, 10000),), ("xAdj", "b")),
    ),
    "wedgeEllipseCallout": (
        (
            "xy",
            (("x", "adj1", -2147483647, 2147483647), ("y", "adj2", -2147483647, 2147483647)),
            ("xPos", "yPos"),
        ),
    ),
    "wedgeRectCallout": (
        (
            "xy",
            (("x", "adj1", -2147483647, 2147483647), ("y", "adj2", -2147483647, 2147483647)),
            ("xPos", "yPos"),
        ),
    ),
    "wedgeRoundRectCallout": (
        (
            "xy",
            (("x", "adj1", -2147483647, 2147483647), ("y", "adj2", -2147483647, 2147483647)),
            ("xPos", "yPos"),
        ),
    ),
}


class AdjustmentHandleError(ValueError):
    """A preset handle cannot be inspected or edited without guessing its meaning."""


class AdjustmentHandleKind(StrEnum):
    XY = "xy"
    POLAR = "polar"


class AdjustmentAxisKind(StrEnum):
    X = "x"
    Y = "y"
    RADIUS = "radius"
    ANGLE = "angle"


def _preset_for_handles(shape: Any) -> str:
    from .shape_inspection import (
        _shape_auto_shape_preset_geometry,
        _shape_is_freeform,
        _shape_is_text_box,
    )

    payload = getattr(shape, "_payload", {})
    slide = getattr(shape, "_slide", None)
    if (
        not isinstance(payload, dict)
        or payload.get("kind") != "shape"
        or slide is None
        or _shape_is_text_box(shape)
        or _shape_is_freeform(shape)
    ):
        raise AdjustmentHandleError("preset adjustment handles require a preset auto shape")
    if (
        payload.get("_deleted")
        or payload.get("_stale")
        or getattr(shape, "_deleted", False)
        or getattr(slide, "_deleted", False)
    ):
        raise AdjustmentHandleError("cannot access preset handles of a deleted or stale shape")
    if (
        payload.get("id") is None
        or not getattr(slide, "partname", None)
        or slide._payload.get("_pending_creation")
        or payload.get("_pending_shape")
        or payload.get("_pending_group_child")
    ):
        raise AdjustmentHandleError("save the pending shape before accessing preset handles")
    presentation = slide._presentation
    slides = getattr(presentation, "_slides", None)
    shape_deletes = presentation._shape_deletes
    if (
        (slides is not None and slide not in slides)
        or slide.partname in getattr(presentation, "_slide_deletions", ())
        or (slide._index, shape._index) in shape_deletes
    ):
        raise AdjustmentHandleError("cannot access preset handles of a deleted shape or slide")
    if any(
        part == slide.partname and str(shape_id) == str(shape.shape_id)
        for part, shape_id in presentation._shape_preset_edits
    ):
        raise AdjustmentHandleError("save queued preset changes before accessing preset handles")
    try:
        preset = _shape_auto_shape_preset_geometry(shape)
    except (AttributeError, ValueError) as exc:
        raise AdjustmentHandleError("shape has no supported preset geometry") from exc
    if preset not in PRESET_ADJUSTMENT_HANDLE_DEFINITIONS:
        raise AdjustmentHandleError(f"preset {preset!r} has no source handle definitions")
    return preset


def _finite_handle_value(value: Real) -> Real:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise AdjustmentHandleError("adjustment handle value must be a finite real number")
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError) as exc:
        raise AdjustmentHandleError("adjustment handle value must be finite") from exc
    if not finite:
        raise AdjustmentHandleError("adjustment handle value must be finite")
    return value


class PresetAdjustmentAxis:
    """A named handle axis bound to a saved shape and its original preset.

    ``minimum`` and ``maximum`` are raw source operands, including unresolved guide names.
    Values are not clamped to these bounds: preset evaluation owns its pinning formulas.
    """

    __slots__ = ("_shape", "_preset", "_guide_name", "_kind", "_minimum", "_maximum")

    def __init__(
        self,
        shape: Any,
        preset: str,
        guide_name: str,
        kind: AdjustmentAxisKind,
        minimum: int | str | None,
        maximum: int | str | None,
    ) -> None:
        self._shape = shape
        self._preset = preset
        self._guide_name = guide_name
        self._kind = kind
        self._minimum = minimum
        self._maximum = maximum

    @property
    def guide_name(self) -> str:
        return self._guide_name

    @property
    def kind(self) -> AdjustmentAxisKind:
        return self._kind

    @property
    def minimum(self) -> int | str | None:
        return self._minimum

    @property
    def maximum(self) -> int | str | None:
        return self._maximum

    def _guide(self) -> tuple[int, int]:
        from .shape_inspection import _shape_adjustment_guides

        if _preset_for_handles(self._shape) != self._preset:
            raise AdjustmentHandleError("preset adjustment handle is stale after a preset change")
        for index, (name, value) in enumerate(_shape_adjustment_guides(self._shape)):
            if name == self.guide_name:
                return index, value
        raise AdjustmentHandleError(
            f"preset {self._preset!r} has no value for handle guide {self.guide_name!r}"
        )

    @property
    def raw_value(self) -> int:
        """Integer DrawingML guide units; angle guides use 60000 units per degree."""
        return self._guide()[1]

    @raw_value.setter
    def raw_value(self, value: Real) -> None:
        from .shape_edit_refs import shape_edit_ref
        from .shape_inspection import _shape_adjustment_guides

        raw = int(_finite_handle_value(value))
        if not -(2**63) <= raw < 2**63:
            raise AdjustmentHandleError(
                "adjustment handle value is outside signed 64-bit guide units"
            )
        index, current = self._guide()
        if raw == current:
            return
        guides = _shape_adjustment_guides(self._shape)
        guides[index] = (self.guide_name, raw)
        # The native queue takes integers; never transport raw units through a float ratio.
        self._shape._slide._presentation._queue_shape_adjustments(
            self._shape._slide._index, shape_edit_ref(self._shape), guides
        )
        self._shape._payload["adjustment_guides"] = list(guides)

    @property
    def ratio(self) -> float:
        """Linear ratio, with 100000 raw guide units per 1.0; not a length in EMUs."""
        if self.kind == AdjustmentAxisKind.ANGLE:
            raise AdjustmentHandleError("an angle handle has degrees, not a linear ratio")
        return self.raw_value / 100000.0

    @ratio.setter
    def ratio(self, value: Real) -> None:
        if self.kind == AdjustmentAxisKind.ANGLE:
            raise AdjustmentHandleError("an angle handle has degrees, not a linear ratio")
        self.raw_value = _finite_handle_value(_finite_handle_value(value) * 100000)

    @property
    def degrees(self) -> float:
        """Angle in degrees, with 60000 raw guide units per degree."""
        if self.kind != AdjustmentAxisKind.ANGLE:
            raise AdjustmentHandleError("a linear handle has a ratio, not degrees")
        return self.raw_value / 60000.0

    @degrees.setter
    def degrees(self, value: Real) -> None:
        if self.kind != AdjustmentAxisKind.ANGLE:
            raise AdjustmentHandleError("a linear handle has a ratio, not degrees")
        self.raw_value = _finite_handle_value(_finite_handle_value(value) * 60000)


@dataclass(frozen=True)
class PresetAdjustmentHandle:
    """One source handle with independently editable axes and an unresolved position."""

    kind: AdjustmentHandleKind
    axes: tuple[PresetAdjustmentAxis, ...]
    position: tuple[int | str, int | str]


def preset_adjustment_handles(shape: Any) -> tuple[PresetAdjustmentHandle, ...]:
    """Read typed XY/polar handle declarations for a saved, live preset auto shape.

    An admitted preset with no handles returns an empty tuple. A preset lacking source
    definitions, a non-preset shape, or an unsaved/stale shape raises
    :class:`AdjustmentHandleError`. Axis setters use the existing ``Shape.adjustments``
    queue, so saving the presentation persists all values together.
    """
    preset = _preset_for_handles(shape)
    return tuple(
        PresetAdjustmentHandle(
            AdjustmentHandleKind(kind),
            tuple(
                PresetAdjustmentAxis(
                    shape, preset, name, AdjustmentAxisKind(axis), minimum, maximum
                )
                for axis, name, minimum, maximum in axes
            ),
            position,
        )
        for kind, axes, position in PRESET_ADJUSTMENT_HANDLE_DEFINITIONS[preset]
    )
