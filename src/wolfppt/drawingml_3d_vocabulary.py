"""DrawingML 3-D schema vocabularies (ECMA-376 Part 1, 20.1.10).

Membership means a token is well-formed DrawingML, not that any renderer
admits it. The shape 3-D format editor validates against these sets, and the
renderer reads them to tell a malformed token from an unadmitted one.
"""

from __future__ import annotations

# 20.1.10.9 ST_BevelPresetType.
BEVEL_PRESETS = frozenset(
    ("relaxedInset", "circle", "slope", "cross", "angle", "softRound")
    + ("convex", "coolSlant", "divot", "riblet", "hardEdge", "artDeco")
)

# 20.1.10.30 ST_LightRigType.
LIGHT_RIG_PRESETS = frozenset(
    tuple(f"legacy{kind}{n}" for kind in ("Flat", "Normal", "Harsh") for n in "1234")
    + ("threePt", "balanced", "soft", "harsh", "flood", "contrasting", "morning")
    + ("sunrise", "sunset", "chilly", "freezing", "flat", "twoPt", "glow")
    + ("brightRoom",)
)

# 20.1.10.29 ST_LightRigDirection.
LIGHT_RIG_DIRECTIONS = frozenset(("t", "tr", "r", "br", "b", "bl", "l", "tl"))

# 20.1.10.50 ST_PresetMaterialType.
MATERIAL_PRESETS = frozenset(
    ("legacyMatte", "legacyPlastic", "legacyMetal", "legacyWireframe", "matte")
    + ("plastic", "metal", "warmMatte", "translucentPowder", "powder", "dkEdge")
    + ("softEdge", "clear", "flat", "softmetal")
)

# 20.1.10.47 ST_PresetCameraType.
_CAMERA_SIDES = ("TopLeft", "Top", "TopRight", "Left", "Front", "Right")
_CAMERA_SIDES += ("BottomLeft", "Bottom", "BottomRight")
CAMERA_PRESETS = frozenset(
    tuple(f"legacy{kind}{side}" for kind in ("Oblique", "Perspective") for side in _CAMERA_SIDES)
    + ("orthographicFront",)
    + tuple(
        f"isometric{side}{tilt}"
        for side in ("Top", "Bottom", "Left", "Right")
        for tilt in ("Up", "Down")
    )
    + tuple(f"isometricOffAxis{n}{side}" for n in (1, 2) for side in ("Left", "Right", "Top"))
    + tuple(f"isometricOffAxis{n}{side}" for n in (3, 4) for side in ("Left", "Right", "Bottom"))
    + tuple(f"oblique{side}" for side in _CAMERA_SIDES if side != "Front")
    + ("perspectiveFront", "perspectiveLeft", "perspectiveRight")
    + ("perspectiveAbove", "perspectiveBelow")
    + ("perspectiveAboveLeftFacing", "perspectiveAboveRightFacing")
    + ("perspectiveContrastingLeftFacing", "perspectiveContrastingRightFacing")
    + ("perspectiveHeroicLeftFacing", "perspectiveHeroicRightFacing")
    + ("perspectiveHeroicExtremeLeftFacing", "perspectiveHeroicExtremeRightFacing")
    + ("perspectiveRelaxed", "perspectiveRelaxedModerately")
)
