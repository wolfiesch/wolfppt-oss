"""The resolved scene model shared by the built-in renderer's emitters.

Scene geometry is expressed in EMU on the slide's own coordinate system, with
the origin at the slide's top-left corner and y increasing downwards.  Every
drawable object is reduced to the same small set of primitives, so the SVG,
PNG, and PDF emitters consume one resolved scene and cannot disagree about what
a slide contains.  A primitive carries an :class:`Affine` that maps its local
coordinates onto the slide, which is how shape rotation, flipping, and nested
group scaling are represented without duplicating geometry.  It also carries a
:class:`SourceRef` naming the object it draws, so rendered output can be mapped
back to the source object an edit would address.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .render_theme import LinearGradientPaint, PathGradientPaint, PatternPaint, ResolvedColor

_EMU_PER_INCH = 914400


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in EMU."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass(frozen=True)
class Affine:
    """A 2D affine transform: ``x' = a*x + c*y + e``, ``y' = b*x + d*y + f``."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def then(self, outer: Affine) -> Affine:
        """Return the transform that applies ``self`` and then ``outer``."""
        return Affine(
            a=outer.a * self.a + outer.c * self.b,
            b=outer.b * self.a + outer.d * self.b,
            c=outer.a * self.c + outer.c * self.d,
            d=outer.b * self.c + outer.d * self.d,
            e=outer.a * self.e + outer.c * self.f + outer.e,
            f=outer.b * self.e + outer.d * self.f + outer.f,
        )

    def is_identity(self) -> bool:
        return (
            self.a == 1.0
            and self.b == 0.0
            and self.c == 0.0
            and self.d == 1.0
            and self.e == 0.0
            and self.f == 0.0
        )

    @property
    def flips(self) -> bool:
        return (self.a * self.d - self.b * self.c) < 0

    @property
    def rotation_degrees(self) -> float:
        """Clockwise rotation in degrees [0, 360)."""
        deg = math.degrees(math.atan2(self.b, self.a)) % 360.0
        return round(deg, 4)

    @staticmethod
    def translation(dx: float, dy: float) -> Affine:
        return Affine(e=dx, f=dy)

    @staticmethod
    def rotation_about(center_x: float, center_y: float, degrees: float) -> Affine:
        """Return a clockwise rotation about a point (y grows downwards)."""
        radians = math.radians(degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        return Affine(
            a=cosine,
            b=sine,
            c=-sine,
            d=cosine,
            e=center_x - cosine * center_x + sine * center_y,
            f=center_y - sine * center_x - cosine * center_y,
        )

    @staticmethod
    def box_map(
        child_rect: Rect,
        parent_rect: Rect,
        *,
        flip_h: bool,
        flip_v: bool,
    ) -> Affine:
        """Map a group child's coordinate box onto the group's own box."""
        if child_rect.width == 0 or child_rect.height == 0:
            raise ValueError("group child extent must be non-zero")
        scale_x = parent_rect.width / child_rect.width
        scale_y = parent_rect.height / child_rect.height
        if flip_h:
            scale_x = -scale_x
        if flip_v:
            scale_y = -scale_y
        origin_x = parent_rect.x - scale_x * (child_rect.right if flip_h else child_rect.x)
        origin_y = parent_rect.y - scale_y * (child_rect.bottom if flip_v else child_rect.y)
        return Affine(a=scale_x, d=scale_y, e=origin_x, f=origin_y)


PRESET_DASH_PATTERNS: dict[str, tuple[float, ...]] = {
    "solid": (),
    "dot": (1.0, 3.0),
    "dash": (4.0, 3.0),
    "lgDash": (8.0, 3.0),
    "dashDot": (4.0, 3.0, 1.0, 3.0),
    "lgDashDot": (8.0, 3.0, 1.0, 3.0),
    "lgDashDotDot": (8.0, 3.0, 1.0, 3.0, 1.0, 3.0),
    "sysDash": (2.0, 2.0),
    "sysDot": (1.0, 1.0),
    "sysDashDot": (2.0, 2.0, 1.0, 2.0),
    "sysDashDotDot": (2.0, 2.0, 1.0, 2.0, 1.0, 2.0),
}


@dataclass(frozen=True)
class Stroke:
    """A resolved outline paint, width in EMU, and preset dash style."""

    color: ResolvedColor | LinearGradientPaint
    width_emu: int
    dash_style: str = "solid"
    cap: str = "flat"


@dataclass(frozen=True)
class SourceRef:
    """Where one drawable object is authored in the source package.

    ``(role, part, shape_id, occurrence)`` is the object's key.  The part says
    which package part authors the object -- the slide itself, the slide layout
    it reads, or the slide master above that -- and ``shape_id`` is the object's
    own ``p:cNvPr/@id``, which survives an edit that renames it.  PowerPoint
    tolerates a part that lists the same id twice, so ``occurrence`` counts the
    objects of that part carrying that id in document order and makes the
    duplicate names of a real deck addressable one by one.

    ``name`` is carried for reporting only: a name is display metadata a caller
    may rewrite, so it is never identity.  ``structure_sha256`` digests the
    object's own source subtree, so a caller holding a target can tell whether
    the object it addressed is still the object it inspected.
    """

    part: str
    role: str
    shape_id: str | None = None
    occurrence: int = 0
    name: str = ""
    structure_sha256: str = ""

    @property
    def selector(self) -> str:
        """The object's stable selector: ``role/part#id+occurrence``."""
        identifier = "none" if self.shape_id is None else self.shape_id
        return f"{self.role}/{self.part}#{identifier}+{self.occurrence}"


@dataclass(frozen=True)
class ChartRef:
    """Semantic chart membership independent of the editable shape ``source``.

    Series indices are chart-part document-order ordinals, global across combo
    plots; ``series_ids`` retains authored ``c:idx`` values (None when absent).
    Category indices retain original cache point indices, including gaps.
    Connecting geometry lists every contributing series/category, not one
    guessed owner. Empty memberships mark fixed chart adornments. A named
    ``refusal`` means this renderer cannot qualify staged chart playback.
    """

    part: str = ""
    plot_type: str = ""
    series_indices: tuple[int, ...] = ()
    category_indices: tuple[int, ...] = ()
    series_ids: tuple[int | None, ...] = ()
    refusal: str | None = None


_DEFAULT_SHADOW_COLOR = ResolvedColor("000000", 1.0)


@dataclass(frozen=True)
class OuterShadowScene:
    """Resolved outer shadow with anchored affine mask geometry and back layers."""

    blur_radius_emu: int = 0
    distance_emu: int = 0
    direction: float = 0.0  # degrees [0.0, 360.0), clockwise from +X axis
    alignment: str = "b"
    rotate_with_shape: bool = True
    color: ResolvedColor = _DEFAULT_SHADOW_COLOR
    scale_x: float = 1.0
    scale_y: float = 1.0
    skew_x: float = 0.0
    skew_y: float = 0.0
    additional_layers: tuple[OuterShadowScene, ...] = field(default=(), kw_only=True)

    @property
    def dx_emu(self) -> float:
        """Horizontal offset in EMU."""
        angle_rad = math.radians(self.direction)
        return self.distance_emu * math.cos(angle_rad)

    @property
    def dy_emu(self) -> float:
        """Vertical offset in EMU."""
        angle_rad = math.radians(self.direction)
        return self.distance_emu * math.sin(angle_rad)

    @property
    def blur_radius_pt(self) -> float:
        """Blur radius in PostScript points."""
        return emu_to_points(self.blur_radius_emu)

    @property
    def distance_pt(self) -> float:
        """Distance in PostScript points."""
        return emu_to_points(self.distance_emu)

    @property
    def std_deviation_pt(self) -> float:
        """Gaussian standard deviation in points for SVG/Pillow filters."""
        if self.blur_radius_emu <= 0:
            return 0.0
        return self.blur_radius_pt / 2.0

    def offset_emu(self, shape_rotation_degrees: float = 0.0) -> tuple[float, float]:
        """Return (dx, dy) in local EMU taking rotate_with_shape into account."""
        if self.rotate_with_shape:
            angle = self.direction
        else:
            angle = self.direction - shape_rotation_degrees
        rad = math.radians(angle % 360.0)
        return (self.distance_emu * math.cos(rad), self.distance_emu * math.sin(rad))

    def offset_points(self, shape_rotation_degrees: float = 0.0) -> tuple[float, float]:
        """Return (dx, dy) in points taking rotate_with_shape into account."""
        dx, dy = self.offset_emu(shape_rotation_degrees)
        return (emu_to_points(dx), emu_to_points(dy))


@dataclass(frozen=True)
class GlowScene:
    """Resolved glow effect parameters for a 2-D primitive."""

    radius_emu: int = 0
    color: ResolvedColor = _DEFAULT_SHADOW_COLOR

    @property
    def radius_pt(self) -> float:
        """Glow radius in PostScript points."""
        return emu_to_points(self.radius_emu)

    @property
    def std_deviation_pt(self) -> float:
        """Gaussian standard deviation in points for SVG/Pillow filters."""
        if self.radius_emu <= 0:
            return 0.0
        return self.radius_pt / 2.0


@dataclass(frozen=True)
class InnerShadowScene:
    """Resolved inset shadow parameters for a filled 2-D primitive."""

    blur_radius_emu: int = 0
    distance_emu: int = 0
    direction: float = 0.0
    color: ResolvedColor = _DEFAULT_SHADOW_COLOR
    rotate_with_shape: bool = True

    @property
    def std_deviation_pt(self) -> float:
        return emu_to_points(self.blur_radius_emu) / 2.0

    def offset_emu(self, shape_rotation_degrees: float = 0.0) -> tuple[float, float]:
        angle = (
            self.direction if self.rotate_with_shape else self.direction - shape_rotation_degrees
        )
        radians = math.radians(angle % 360.0)
        return (
            self.distance_emu * math.cos(radians),
            self.distance_emu * math.sin(radians),
        )


@dataclass(frozen=True)
class SoftEdgeScene:
    """Resolved DrawingML soft-edge radius for a filled 2-D primitive.

    ``a:softEdge`` blurs the shape's own edges without painting outside it:
    the shape alpha is eroded by half the radius and blurred with a standard
    deviation of a quarter of it, so opacity falls from about 1 at ``rad``
    inside the outline to about 0 at the outline.
    """

    radius_emu: int = 0

    @property
    def inset_emu(self) -> float:
        return self.radius_emu / 2.0

    @property
    def std_deviation_emu(self) -> float:
        return self.radius_emu / 4.0


@dataclass(frozen=True)
class ReflectionScene:
    """Resolved vertical reflection parameters for a filled 2-D primitive."""

    blur_radius_emu: int = 0
    distance_emu: int = 0
    direction: float = 90.0
    start_alpha: float = 0.5
    end_alpha: float = 0.0
    start_position: float = 0.0
    end_position: float = 1.0
    rotate_with_shape: bool = True

    @property
    def std_deviation_pt(self) -> float:
        return emu_to_points(self.blur_radius_emu) / 2.0

    def offset_emu(self, shape_rotation_degrees: float = 0.0) -> tuple[float, float]:
        angle = (
            self.direction if self.rotate_with_shape else self.direction - shape_rotation_degrees
        )
        radians = math.radians(angle % 360.0)
        return (
            self.distance_emu * math.cos(radians),
            self.distance_emu * math.sin(radians),
        )


@dataclass(frozen=True)
class TiledPicturePaint:
    """A cropped bitmap painted inside one shape or slide background.

    Tile dimensions are local EMU after ``a:tile`` scale and source cropping.
    Alignment and offsets place the grid; ``flip`` reflects alternate grid
    columns/rows without changing its origin. With ``stretch=True`` the cropped
    source fills the original paint bounds once, with edge pixels clamped.
    """

    data: bytes
    image_format: str
    pixel_width: int
    pixel_height: int
    tile_width_emu: float
    tile_height_emu: float
    offset_x_emu: float
    offset_y_emu: float
    alignment: str = "tl"
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float = 0.0
    crop_bottom: float = 0.0
    alpha: float = 1.0
    flip: str = "none"
    stretch: bool = False


FillPaint = (
    ResolvedColor | LinearGradientPaint | PathGradientPaint | PatternPaint | TiledPicturePaint
)


@dataclass(frozen=True)
class BlurScene:
    """Resolved Gaussian surface blur; sigma is half the radius.

    ``grow=False`` clips to the original rectangular body bounds, not its silhouette.
    """

    radius_emu: int = 0
    grow: bool = True


@dataclass(frozen=True)
class FillOverlayScene:
    """Resolved surface overlay retaining its blend mode and full paint opacity."""

    blend: str
    color: FillPaint


@dataclass(frozen=True)
class Primitive:
    """Base class for the drawable primitives of a resolved scene."""

    transform: Affine = Affine()
    object_name: str = ""
    #: The source object this primitive draws.  One source object may resolve
    #: to many primitives -- a compound geometry, a table's cells and borders,
    #: a chart's bars -- and all of them carry the same reference, so a caller
    #: maps rendered output back to exactly one editable object.
    source: SourceRef | None = None
    shadow: OuterShadowScene | None = None
    glow: GlowScene | None = None
    inner_shadow: InnerShadowScene | None = None
    soft_edge: SoftEdgeScene | None = None
    reflection: ReflectionScene | None = None
    hyperlink: str | None = None
    #: Direct surface effects are rendered on admitted 2-D shape bodies.
    #: Generated outline bands retain named refusals until grouped effects exist.
    blur: BlurScene | None = field(default=None, kw_only=True)
    fill_overlay: FillOverlayScene | None = field(default=None, kw_only=True)
    chart_ref: ChartRef | None = field(default=None, kw_only=True)
    #: Authored table row, column, row span and column span, independent of paint order.
    table_cell: tuple[int, int, int, int] | None = field(default=None, kw_only=True)
    #: Resolved theme slots and mapped aliases for animation color evaluation.
    theme_colors: tuple[tuple[str, ResolvedColor], ...] = field(default=(), kw_only=True)


@dataclass(frozen=True)
class RectPrimitive(Primitive):
    """A filled/stroked rectangle, optionally with rounded corners."""

    rect: Rect = Rect(0, 0, 0, 0)
    fill: FillPaint | None = None
    stroke: Stroke | None = None
    corner_radius_emu: int = 0


@dataclass(frozen=True)
class EllipsePrimitive(Primitive):
    """A filled/stroked ellipse inscribed in ``rect``."""

    rect: Rect = Rect(0, 0, 0, 0)
    fill: FillPaint | None = None
    stroke: Stroke | None = None


@dataclass(frozen=True)
class PolygonPrimitive(Primitive):
    """A filled/stroked polygon whose points are in local EMU."""

    points: tuple[tuple[float, float], ...] = ()
    fill: FillPaint | None = None
    stroke: Stroke | None = None


@dataclass(frozen=True)
class PathPrimitive(Primitive):
    """A filled/stroked sequence of straight segments and quadratic curves.

    ``subpaths`` retains compound DrawingML geometry.  An even-odd fill rule
    expresses path-reversal holes consistently in SVG, PDF, and raster output.
    """

    start: tuple[float, float] = (0.0, 0.0)
    segments: tuple[tuple[str, tuple[tuple[float, float], ...]], ...] = ()
    closed: bool = False
    subpaths: tuple[
        tuple[
            tuple[float, float],
            tuple[tuple[str, tuple[tuple[float, float], ...]], ...],
            bool,
        ],
        ...,
    ] = ()
    fill_rule: str = "nonzero"
    fill: FillPaint | None = None
    stroke: Stroke | None = None


@dataclass(frozen=True)
class LinePrimitive(Primitive):
    """A single straight stroked segment in local EMU."""

    start: tuple[float, float] = (0.0, 0.0)
    end: tuple[float, float] = (0.0, 0.0)
    stroke: Stroke | None = None


@dataclass(frozen=True)
class PicturePrimitive(Primitive):
    """A bitmap placed in ``rect`` with normalised source cropping.

    ``crop_*`` are the fractions of the source image removed from each edge
    (DrawingML ``a:srcRect``), and ``alpha`` is the uniform opacity applied to
    the whole picture (DrawingML ``a:alphaModFix``).
    """

    rect: Rect = Rect(0, 0, 0, 0)
    part: str = ""
    data: bytes = b""
    pixel_width: int = 0
    pixel_height: int = 0
    image_format: str = "png"
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float = 0.0
    crop_bottom: float = 0.0
    alpha: float = 1.0


# How a run's text effects are blurred, as factors of the DrawingML lengths:
# an outer shadow is a Gaussian of standard deviation
# ``TEXT_SHADOW_SIGMA_PER_BLUR * blurRad``; a glow grows the glyph outline by
# ``TEXT_GLOW_GROW_PER_RADIUS * rad`` and then blurs it with a standard
# deviation of ``TEXT_GLOW_SIGMA_PER_RADIUS * rad``.  One mapping serves every
# emitter (raster, SVG, and PDF through the raster layer).  The factors are
# the PowerPoint 16.113 measurements ``crates/wolfppt-render`` draws shape
# effects with (``lower/effects.rs``: ``SIGMA_PER_BLUR``, ``GLOW_DILATE`` and
# ``GLOW_SIGMA_BLUR``); ``tests/test_text_effects.py`` holds the text drawn
# with them to PowerPoint's own export of a 12-slide fixture.
TEXT_SHADOW_SIGMA_PER_BLUR = 1.0 / 3.0
TEXT_GLOW_GROW_PER_RADIUS = 0.44
TEXT_GLOW_SIGMA_PER_RADIUS = 0.16


@dataclass(frozen=True)
class TextSegmentScene:
    """One laid-out text segment in the text frame's local EMU."""

    x_emu: int
    text: str
    family: str
    bold: bool
    italic: bool
    size_emu: int
    color: ResolvedColor
    underline: bool = False
    strike: str = "noStrike"
    baseline_offset_emu: int = 0
    character_spacing_emu: int = 0
    highlight: ResolvedColor | None = None
    hyperlink: str | None = None
    #: Each glyph's advance in EMU (character spacing included, except after
    #: the last glyph), from the native PowerPoint 16.113 per-glyph model;
    #: ``None`` (chart labels) places glyphs by the font's own widths.
    advances_emu: tuple[int, ...] | None = None
    #: The run's text drop shadow (``a:rPr/a:effectLst/a:outerShdw``), drawn
    #: beneath the glyphs from their own coverage.
    shadow: OuterShadowScene | None = None
    #: The run's text glow (``a:rPr/a:effectLst/a:glow``), drawn beneath the
    #: glyphs from their own coverage.
    glow: GlowScene | None = None


@dataclass(frozen=True)
class TextLineScene:
    """One laid-out line: its segments and baseline in the frame's local EMU."""

    segments: tuple[TextSegmentScene, ...]
    baseline_emu: int


@dataclass(frozen=True)
class TextPrimitive(Primitive):
    """A laid-out text body anchored at ``origin`` in the parent's EMU."""

    origin: tuple[int, int] = (0, 0)
    lines: tuple[TextLineScene, ...] = ()
    #: The text frame the body was laid out in, in the same local EMU as
    #: ``lines``.  It is the frame's own placement, which is what a caller
    #: needs to bound the object; text that exceeds it is reported as overflow
    #: rather than folded into these bounds.
    frame: Rect | None = None
    #: The authored auto-fit mode the layout honoured: ``"none"``, ``"shape"``,
    #: or ``"normal"``.
    autofit: str = "none"
    #: The uniform scale the body's text is drawn at: the ``fontScale`` the
    #: deck stores, the shrink the renderer computed for a ``normAutofit`` body
    #: that stores none, or ``1.0`` when the text is drawn at its authored size.
    applied_font_scale: float = 1.0
    #: Where :attr:`applied_font_scale` comes from: ``"authored"`` (the text is
    #: drawn at the size the source resolves to), ``"stored"`` (the deck's own
    #: ``fontScale`` was applied in full), or ``"computed"`` (the body stores
    #: none, so the renderer computed the shrink).
    font_scale_source: str = "authored"
    #: How far the laid-out text exceeds ``frame``, in EMU (``0`` when it fits).
    #: This is the layout's own measurement, never a re-measurement.
    overflow_emu: int = 0
    #: The renderer's own note for a frame whose text does not fit, exactly as
    #: the resolved slide reports it.  Empty when the text fits.
    overflow_note: str = ""


@dataclass(frozen=True)
class SlideScene:
    """One resolved slide: its size, background, and drawable primitives."""

    number: int
    part: str
    width_emu: int
    height_emu: int
    background: FillPaint | PicturePrimitive
    primitives: tuple[Primitive, ...]
    layout_part: str
    master_part: str
    #: Content the renderer could not draw exactly.  The slide's primitives are
    #: still the whole of what it draws.
    omissions: tuple[str, ...] = ()
    #: What the drawing rests on: a value the slide renders from a stored cache,
    #: or a text fit the renderer computed itself, rather than from the source
    #: as authored.  Nothing here is missing from the slide, so it is kept
    #: apart from the omissions.
    provenance: tuple[str, ...] = ()

    def counts(self) -> dict[str, int]:
        """Return how many primitives of each kind the slide holds."""
        counts: dict[str, int] = {}
        for primitive in self.primitives:
            key = type(primitive).__name__
            counts[key] = counts.get(key, 0) + 1
        return counts


@dataclass(frozen=True)
class DeckScene:
    """Every resolved slide of one deck, plus its package identity."""

    source: str
    source_digest: str
    slide_width_emu: int
    slide_height_emu: int
    slides: tuple[SlideScene, ...]
    theme_part: str


def emu_to_points(value: int) -> float:
    """Convert EMU to PostScript points (1/72 inch)."""
    return value * 72.0 / _EMU_PER_INCH


def emu_to_inches(value: int) -> float:
    """Convert EMU to inches."""
    return value / _EMU_PER_INCH
