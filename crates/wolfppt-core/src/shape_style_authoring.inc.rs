// Shape style authoring: fill, line, line ends, preset geometry, anchors,
// connector connections, and slide or master backgrounds, plus the style
// summaries behind the FFI `shape_styles` and `masters` queries. Values are
// reported as stored in the part, with null where the element or attribute is
// absent; colours also carry their base sRGB value before transforms.

chart_token_enum!(
    /// ST_LineCap.
    StyleLineCap { Round => "rnd", Square => "sq", Flat => "flat" }
);
chart_token_enum!(
    /// ST_PresetLineDashVal.
    StyleLineDash {
        Solid => "solid",
        Dot => "dot",
        Dash => "dash",
        LargeDash => "lgDash",
        DashDot => "dashDot",
        LargeDashDot => "lgDashDot",
        LargeDashDotDot => "lgDashDotDot",
        SystemDash => "sysDash",
        SystemDot => "sysDot",
        SystemDashDot => "sysDashDot",
        SystemDashDotDot => "sysDashDotDot",
    }
);
chart_token_enum!(
    /// ST_LineEndType.
    StyleLineEndType {
        None => "none",
        Triangle => "triangle",
        Stealth => "stealth",
        Diamond => "diamond",
        Oval => "oval",
        Arrow => "arrow",
    }
);
chart_token_enum!(
    /// ST_LineEndWidth and ST_LineEndLength.
    StyleLineEndSize { Small => "sm", Medium => "med", Large => "lg" }
);

/// Present-and-null clears, present-with-value sets, absent leaves untouched.
fn style_tri<'de, D, T>(deserializer: D) -> Result<Option<Option<T>>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: serde::Deserialize<'de>,
{
    <Option<T> as serde::Deserialize>::deserialize(deserializer).map(Some)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StyleColorKind {
    Srgb,
    Scheme,
    Preset,
    System,
    Hsl,
}

/// One colour transform child (`a:lumMod val="50000"`). `comp`, `inv`,
/// `gray`, `gamma`, and `invGamma` take no value.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StyleColorTransform {
    pub name: String,
    #[serde(default)]
    pub val: Option<i64>,
}

/// A DrawingML colour choice. `value` is the hex digits (`srgb`), the
/// ST_SchemeColorVal, ST_PresetColorVal, or ST_SystemColorVal token;
/// `last_color` is the system colour's cached hex; `hsl` uses `hue` (60000ths
/// of a degree), `sat`, and `lum` (1000ths of a percent).
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StyleColor {
    pub kind: StyleColorKind,
    #[serde(default)]
    pub value: Option<String>,
    #[serde(default)]
    pub last_color: Option<String>,
    #[serde(default)]
    pub hue: Option<i64>,
    #[serde(default)]
    pub sat: Option<i64>,
    #[serde(default)]
    pub lum: Option<i64>,
    #[serde(default)]
    pub transforms: Vec<StyleColorTransform>,
}

/// Creates the line end element when absent, then applies the given fields.
#[derive(Debug, Clone, Default, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StyleLineEndEdit {
    #[serde(default, rename = "type", deserialize_with = "style_tri")]
    pub end_type: Option<Option<StyleLineEndType>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub width: Option<Option<StyleLineEndSize>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub length: Option<Option<StyleLineEndSize>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StyleAnchorEdit {
    pub x: i64,
    pub y: i64,
    pub cx: u64,
    pub cy: u64,
}

/// A connector end glued to connection site `site` of shape `shape_id`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StyleConnectionEdit {
    pub shape_id: u64,
    pub site: u32,
}

/// Restyles shape `shape_id` (its `cNvPr` id, at any group depth) on slide
/// `slide_index`. Absent fields stay untouched. A null `fill` or
/// `line_color` writes `a:noFill`; a null or zero `line_width_emu` removes the
/// width; null `line_cap` or `line_dash` removes them. Any line field creates
/// `a:ln`. `child_anchor` applies to groups only; connections to connectors
/// only; line fields and `preset_geometry` are refused on groups.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ShapeStyleEdit {
    pub slide_index: usize,
    pub shape_id: u64,
    #[serde(default)]
    pub preset_geometry: Option<String>,
    #[serde(default)]
    pub anchor: Option<StyleAnchorEdit>,
    #[serde(default)]
    pub child_anchor: Option<StyleAnchorEdit>,
    #[serde(default, deserialize_with = "style_tri")]
    pub fill: Option<Option<StyleColor>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub line_width_emu: Option<Option<u64>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub line_cap: Option<Option<StyleLineCap>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub line_dash: Option<Option<StyleLineDash>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub line_color: Option<Option<StyleColor>>,
    #[serde(default)]
    pub head_end: Option<StyleLineEndEdit>,
    #[serde(default)]
    pub tail_end: Option<StyleLineEndEdit>,
    #[serde(default, deserialize_with = "style_tri")]
    pub connection_start: Option<Option<StyleConnectionEdit>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub connection_end: Option<Option<StyleConnectionEdit>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BackgroundTarget {
    Slide,
    Master,
}

/// Sets the background of slide or master `index` to a solid colour, or to
/// `a:noFill` when `color` is null. A theme background reference (`p:bgRef`)
/// is replaced by background properties.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BackgroundFillEdit {
    pub target: BackgroundTarget,
    pub index: usize,
    #[serde(default)]
    pub color: Option<StyleColor>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ShapeStyleEditSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct BackgroundEditSummary {
    pub path: PathBuf,
    pub target: BackgroundTarget,
    pub index: usize,
    pub part: String,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleColorTransformSummary {
    pub name: String,
    pub val: Option<i64>,
    /// `val` in percent (ST_Percentage stores 1000ths of a percent).
    pub percent: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleColorSummary {
    /// `srgb`, `scheme`, `preset`, `system`, `hsl`, or `scrgb`.
    pub kind: &'static str,
    pub value: Option<String>,
    pub last_color: Option<String>,
    pub hue: Option<i64>,
    pub sat: Option<i64>,
    pub lum: Option<i64>,
    pub transforms: Vec<StyleColorTransformSummary>,
    /// The colour before transforms as six uppercase hex digits: preset and
    /// system tokens use their default sRGB, scheme colours resolve through
    /// the colour map and theme. Null when unresolvable.
    pub base_rgb: Option<String>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleFillSummary {
    /// `no_fill`, `solid`, `gradient`, `blip`, `pattern`, or `group`.
    pub kind: &'static str,
    pub color: Option<StyleColorSummary>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StyleLineEndSummary {
    #[serde(rename = "type")]
    pub end_type: Option<String>,
    pub width: Option<String>,
    pub length: Option<String>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleLineSummary {
    pub width_emu: Option<i64>,
    pub cap: Option<String>,
    pub compound: Option<String>,
    pub dash: Option<String>,
    pub fill: Option<StyleFillSummary>,
    pub head_end: Option<StyleLineEndSummary>,
    pub tail_end: Option<StyleLineEndSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleOuterShadowSummary {
    pub blur_radius_emu: Option<i64>,
    pub distance_emu: Option<i64>,
    pub direction: Option<i64>,
    pub alignment: Option<String>,
    pub rotate_with_shape: Option<bool>,
    pub color: Option<StyleColorSummary>,
}

/// An `a:effectLst`.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleEffectsSummary {
    pub effects: Vec<String>,
    pub outer_shadow: Option<StyleOuterShadowSummary>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StylePathCommand {
    /// `move_to`, `line_to`, `quad_bezier_to`, `cubic_bezier_to`, `arc_to`,
    /// or `close`.
    pub op: &'static str,
    /// Point coordinates as stored: an integer or a guide name.
    pub points: Vec<[String; 2]>,
    /// `wR`, `hR`, `stAng`, `swAng` of an `arc_to`.
    pub arc: Option<[String; 4]>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StylePathSummary {
    pub w: Option<i64>,
    pub h: Option<i64>,
    pub commands: Vec<StylePathCommand>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StyleCustomGeometrySummary {
    pub paths: Vec<StylePathSummary>,
    /// The `a:custGeom` element as stored.
    pub xml: String,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StyleAnchorSummary {
    pub x: Option<i64>,
    pub y: Option<i64>,
    pub cx: Option<i64>,
    pub cy: Option<i64>,
    pub child_x: Option<i64>,
    pub child_y: Option<i64>,
    pub child_cx: Option<i64>,
    pub child_cy: Option<i64>,
    pub rotation: Option<i64>,
    pub flip_h: bool,
    pub flip_v: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StyleConnectionSummary {
    pub shape_id: Option<u64>,
    pub site: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ShapeStyleSummary {
    pub id: Option<u64>,
    pub name: Option<String>,
    /// The shape element: `sp`, `cxnSp`, `grpSp`, `pic`, `graphicFrame`, or
    /// `contentPart`.
    pub kind: String,
    pub text_box: bool,
    pub anchor: Option<StyleAnchorSummary>,
    pub preset_geometry: Option<String>,
    pub custom_geometry: Option<StyleCustomGeometrySummary>,
    pub fill: Option<StyleFillSummary>,
    pub line: Option<StyleLineSummary>,
    pub effects: Option<StyleEffectsSummary>,
    pub connection_start: Option<StyleConnectionSummary>,
    pub connection_end: Option<StyleConnectionSummary>,
    /// Group children in document order.
    pub children: Vec<ShapeStyleSummary>,
}

/// A `p:bg`: background properties (`fill`) or a theme reference.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StyleBackgroundSummary {
    pub fill: Option<StyleFillSummary>,
    pub reference_index: Option<u64>,
    pub reference_color: Option<StyleColorSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct SlideStylesSummary {
    pub index: usize,
    pub part: String,
    pub background: Option<StyleBackgroundSummary>,
    pub shapes: Vec<ShapeStyleSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct MasterStylesSummary {
    pub index: usize,
    pub part: String,
    pub theme_part: Option<String>,
    pub background: Option<StyleBackgroundSummary>,
    /// Theme colour scheme slots (`dk1`, `lt1`, `accent1`, ...).
    pub color_scheme: BTreeMap<String, StyleColorSummary>,
    /// Theme `a:effectStyleLst` entries; null for an `a:effectDag` style.
    pub effect_styles: Option<Vec<Option<StyleEffectsSummary>>>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ShapeStylesSummary {
    pub slides: Vec<SlideStylesSummary>,
    pub masters: Vec<MasterStylesSummary>,
}

const STYLE_SHAPE_KINDS: &[&str] = &["sp", "cxnSp", "grpSp", "pic", "graphicFrame", "contentPart"];
const STYLE_FILL_NAMES: &[&str] = &[
    "noFill",
    "solidFill",
    "gradFill",
    "blipFill",
    "pattFill",
    "grpFill",
];
const STYLE_LINE_FILL_NAMES: &[&str] = &["noFill", "solidFill", "gradFill", "pattFill"];
const STYLE_SP_PR_ORDER: &[&str] = &[
    "xfrm",
    "custGeom|prstGeom",
    "noFill|solidFill|gradFill|blipFill|pattFill|grpFill",
    "ln",
    "effectLst|effectDag",
    "scene3d",
    "sp3d",
    "extLst",
];
const STYLE_GRP_SP_PR_ORDER: &[&str] = &[
    "xfrm",
    "noFill|solidFill|gradFill|blipFill|pattFill|grpFill",
    "effectLst|effectDag",
    "scene3d",
    "extLst",
];
const STYLE_BG_PR_ORDER: &[&str] = &[
    "noFill|solidFill|gradFill|blipFill|pattFill|grpFill",
    "effectLst|effectDag",
    "extLst",
];
const STYLE_LN_ORDER: &[&str] = &[
    "noFill|solidFill|gradFill|pattFill",
    "prstDash|custDash",
    "round|bevel|miter",
    "headEnd",
    "tailEnd",
    "extLst",
];
const STYLE_XFRM_ORDER: &[&str] = &["off", "ext", "chOff", "chExt"];
const STYLE_CSLD_ORDER: &[&str] = &["bg", "spTree", "custDataLst", "controls", "extLst"];
const STYLE_BG_ORDER: &[&str] = &["bgPr|bgRef"];
const STYLE_CNV_CXN_SP_PR_ORDER: &[&str] = &["cxnSpLocks", "stCxn", "endCxn", "extLst"];
const STYLE_SHAPE_ORDER: &[&str] = &[
    "nvSpPr|nvCxnSpPr|nvPicPr|nvGrpSpPr",
    "blipFill",
    "spPr|grpSpPr",
    "style",
    "txBody",
    "extLst",
];
/// ST_ShapeType connector geometries; every other preset is an auto shape
/// geometry `auto_shape_display_name` accepts.
const STYLE_CONNECTOR_PRESETS: &[&str] = &[
    "line",
    "straightConnector1",
    "bentConnector2",
    "bentConnector3",
    "bentConnector4",
    "bentConnector5",
    "curvedConnector2",
    "curvedConnector3",
    "curvedConnector4",
    "curvedConnector5",
];
const STYLE_SCHEME_COLORS: &[&str] = &[
    "bg1", "tx1", "bg2", "tx2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
    "hlink", "folHlink", "phClr", "dk1", "lt1", "dk2", "lt2",
];
const STYLE_COLOR_TRANSFORMS: &[&str] = &[
    "tint", "shade", "comp", "inv", "gray", "alpha", "alphaOff", "alphaMod", "hue", "hueOff",
    "hueMod", "sat", "satOff", "satMod", "lum", "lumOff", "lumMod", "red", "redOff", "redMod",
    "green", "greenOff", "greenMod", "blue", "blueOff", "blueMod", "gamma", "invGamma",
];
const STYLE_VALUELESS_TRANSFORMS: &[&str] = &["comp", "inv", "gray", "gamma", "invGamma"];
/// ST_LineWidth upper bound in EMU.
const STYLE_MAX_LINE_WIDTH_EMU: u64 = 20_116_800;

/// Default sRGB of the ST_PresetColorVal and ST_SystemColorVal tokens, sorted
/// by token. System colours are the Windows defaults.
const STYLE_DEFAULT_COLORS: [(&str, u32); 170] = [
    ("3dDkShadow", 0x000000),
    ("3dLight", 0xE3E3E3),
    ("activeBorder", 0xB4B4B4),
    ("activeCaption", 0x99B4D1),
    ("aliceBlue", 0xF0F8FF),
    ("antiqueWhite", 0xFAEBD7),
    ("appWorkspace", 0xABABAB),
    ("aqua", 0x00FFFF),
    ("aquamarine", 0x7FFFD4),
    ("azure", 0xF0FFFF),
    ("background", 0x000000),
    ("beige", 0xF5F5DC),
    ("bisque", 0xFFE4C4),
    ("black", 0x000000),
    ("blanchedAlmond", 0xFFEBCD),
    ("blue", 0x0000FF),
    ("blueViolet", 0x8A2BE2),
    ("brown", 0xA52A2A),
    ("btnFace", 0xF0F0F0),
    ("btnHighlight", 0xE3E3E3),
    ("btnShadow", 0x696969),
    ("btnText", 0x000000),
    ("burlyWood", 0xDEB887),
    ("cadetBlue", 0x5F9EA0),
    ("captionText", 0x000000),
    ("chartreuse", 0x7FFF00),
    ("chocolate", 0xD2691E),
    ("coral", 0xFF7F50),
    ("cornflowerBlue", 0x6495ED),
    ("cornsilk", 0xFFF8DC),
    ("crimson", 0xDC143C),
    ("cyan", 0x00FFFF),
    ("deepPink", 0xFF1493),
    ("deepSkyBlue", 0x00BFFF),
    ("dimGray", 0x696969),
    ("dkBlue", 0x00008B),
    ("dkCyan", 0x008B8B),
    ("dkGoldenrod", 0xB8860B),
    ("dkGray", 0xA9A9A9),
    ("dkGreen", 0x006400),
    ("dkKhaki", 0xBDB76B),
    ("dkMagenta", 0x8B008B),
    ("dkOliveGreen", 0x556B2F),
    ("dkOrange", 0xFF8C00),
    ("dkOrchid", 0x9932CC),
    ("dkRed", 0x8B0000),
    ("dkSalmon", 0xE9967A),
    ("dkSeaGreen", 0x8FBC8B),
    ("dkSlateBlue", 0x483D8B),
    ("dkSlateGray", 0x2F4F4F),
    ("dkTurquoise", 0x00CED1),
    ("dkViolet", 0x9400D3),
    ("dodgerBlue", 0x1E90FF),
    ("firebrick", 0xB22222),
    ("floralWhite", 0xFFFAF0),
    ("forestGreen", 0x228B22),
    ("fuchsia", 0xFF00FF),
    ("gainsboro", 0xDCDCDC),
    ("ghostWhite", 0xF8F8FF),
    ("gold", 0xFFD700),
    ("goldenrod", 0xDAA520),
    ("gradientActiveCaption", 0xB9D1EA),
    ("gradientInactiveCaption", 0xD7E4F2),
    ("gray", 0x808080),
    ("grayText", 0x6D6D6D),
    ("green", 0x008000),
    ("greenYellow", 0xADFF2F),
    ("highlight", 0x3399FF),
    ("highlightText", 0xFFFFFF),
    ("honeydew", 0xF0FFF0),
    ("hotLight", 0x0066CC),
    ("hotPink", 0xFF69B4),
    ("inactiveBorder", 0xF4F7FC),
    ("inactiveCaption", 0xBFCDDB),
    ("inactiveCaptionText", 0x000000),
    ("indianRed", 0xCD5C5C),
    ("indigo", 0x4B0082),
    ("infoBk", 0xFFFFE1),
    ("infoText", 0x000000),
    ("ivory", 0xFFFFF0),
    ("khaki", 0xF0E68C),
    ("lavender", 0xE6E6FA),
    ("lavenderBlush", 0xFFF0F5),
    ("lawnGreen", 0x7CFC00),
    ("lemonChiffon", 0xFFFACD),
    ("lime", 0x00FF00),
    ("limeGreen", 0x32CD32),
    ("linen", 0xFAF0E6),
    ("ltBlue", 0xADD8E6),
    ("ltCoral", 0xF08080),
    ("ltCyan", 0xE0FFFF),
    ("ltGoldenrodYellow", 0xFAFA78),
    ("ltGray", 0xD3D3D3),
    ("ltGreen", 0x90EE90),
    ("ltPink", 0xFFB6C1),
    ("ltSalmon", 0xFFA07A),
    ("ltSeaGreen", 0x20B2AA),
    ("ltSkyBlue", 0x87CEFA),
    ("ltSlateGray", 0x778899),
    ("ltSteelBlue", 0xB0C4DE),
    ("ltYellow", 0xFFFFE0),
    ("magenta", 0xFF00FF),
    ("maroon", 0x800000),
    ("medAquamarine", 0x66CDAA),
    ("medBlue", 0x0000CD),
    ("medOrchid", 0xBA55D3),
    ("medPurple", 0x9370DB),
    ("medSeaGreen", 0x3CB371),
    ("medSlateBlue", 0x7B68EE),
    ("medSpringGreen", 0x00FA9A),
    ("medTurquoise", 0x48D1CC),
    ("medVioletRed", 0xC71585),
    ("menu", 0xF0F0F0),
    ("menuBar", 0xF0F0F0),
    ("menuHighlight", 0x3399FF),
    ("menuText", 0x000000),
    ("midnightBlue", 0x191970),
    ("mintCream", 0xF5FFFA),
    ("mistyRose", 0xFFE4E1),
    ("moccasin", 0xFFE4B5),
    ("navajoWhite", 0xFFDEAD),
    ("navy", 0x000080),
    ("oldLace", 0xFDF5E6),
    ("olive", 0x808000),
    ("oliveDrab", 0x6B8E23),
    ("orange", 0xFFA500),
    ("orangeRed", 0xFF4500),
    ("orchid", 0xDA70D6),
    ("paleGoldenrod", 0xEEE8AA),
    ("paleGreen", 0x98FB98),
    ("paleTurquoise", 0xAFEEEE),
    ("paleVioletRed", 0xDB7093),
    ("papayaWhip", 0xFFEFD5),
    ("peachPuff", 0xFFDAB9),
    ("peru", 0xCD853F),
    ("pink", 0xFFC0CB),
    ("plum", 0xDDA0DD),
    ("powderBlue", 0xB0E0E6),
    ("purple", 0x800080),
    ("red", 0xFF0000),
    ("rosyBrown", 0xBC8F8F),
    ("royalBlue", 0x4169E1),
    ("saddleBrown", 0x8B4513),
    ("salmon", 0xFA8072),
    ("sandyBrown", 0xF4A460),
    ("scrollBar", 0xC8C8C8),
    ("seaGreen", 0x2E8B57),
    ("seaShell", 0xFFF5EE),
    ("sienna", 0xA0522D),
    ("silver", 0xC0C0C0),
    ("skyBlue", 0x87CEEB),
    ("slateBlue", 0x6A5ACD),
    ("slateGray", 0x708090),
    ("snow", 0xFFFAFA),
    ("springGreen", 0x00FF7F),
    ("steelBlue", 0x4682B4),
    ("tan", 0xD2B48C),
    ("teal", 0x008080),
    ("thistle", 0xD8BFD8),
    ("tomato", 0xFF6347),
    ("turquoise", 0x40E0D0),
    ("violet", 0xEE82EE),
    ("wheat", 0xF5DEB3),
    ("white", 0xFFFFFF),
    ("whiteSmoke", 0xF5F5F5),
    ("window", 0xFFFFFF),
    ("windowFrame", 0x646464),
    ("windowText", 0x000000),
    ("yellow", 0xFFFF00),
    ("yellowGreen", 0x9ACD32),
];

fn style_invalid(message: impl Into<String>) -> WolfPptError {
    WolfPptError::InvalidInput(message.into())
}

fn style_default_color(token: &str) -> Option<String> {
    STYLE_DEFAULT_COLORS
        .binary_search_by(|(name, _)| (*name).cmp(token))
        .ok()
        .map(|index| format!("{:06X}", STYLE_DEFAULT_COLORS[index].1))
}

fn style_hex(value: &str) -> Option<String> {
    uppercase_hex6(value).map(|hex| String::from_utf8_lossy(&hex).into_owned())
}

/// HSL (hue in 60000ths of a degree, saturation and luminance in 1000ths of a
/// percent) to sRGB hex.
fn style_hsl_hex(hue: i64, sat: i64, lum: i64) -> String {
    let h = (hue as f64 / 60000.0).rem_euclid(360.0) / 360.0;
    let s = (sat as f64 / 100_000.0).clamp(0.0, 1.0);
    let l = (lum as f64 / 100_000.0).clamp(0.0, 1.0);
    let q = if l < 0.5 {
        l * (1.0 + s)
    } else {
        l + s - s * l
    };
    let p = 2.0 * l - q;
    let channel = |t: f64| {
        let t = if t < 0.0 {
            t + 1.0
        } else if t > 1.0 {
            t - 1.0
        } else {
            t
        };
        let value = if 6.0 * t < 1.0 {
            p + (q - p) * 6.0 * t
        } else if 2.0 * t < 1.0 {
            q
        } else if 3.0 * t < 2.0 {
            p + (q - p) * 6.0 * (2.0 / 3.0 - t)
        } else {
            p
        };
        (value.clamp(0.0, 1.0) * 255.0 + 0.5) as u8
    };
    format!(
        "{:02X}{:02X}{:02X}",
        channel(h + 1.0 / 3.0),
        channel(h),
        channel(h - 1.0 / 3.0)
    )
}

fn style_valid_preset_geometry(preset: &str) -> bool {
    STYLE_CONNECTOR_PRESETS.contains(&preset) || auto_shape_display_name(preset).is_ok()
}

fn style_number<T: std::str::FromStr>(element: &ChartXmlElement, name: &str) -> Option<T> {
    element
        .attribute(name)
        .and_then(|value| value.trim().parse().ok())
}

fn style_bool(element: &ChartXmlElement, name: &str) -> Option<bool> {
    element
        .attribute(name)
        .map(|value| value == "1" || value == "true")
}

fn style_remove_attribute(element: &mut ChartXmlElement, name: &str) {
    element.attributes.retain(|(key, _)| key != name);
}

/// Like `ensure_child`, but creates the element under the given qualified
/// name (a DrawingML child of a PresentationML element has another prefix).
fn style_ensure<'e>(
    parent: &'e mut ChartXmlElement,
    name: &str,
    order: &[&str],
) -> &'e mut ChartXmlElement {
    let local = name.rsplit_once(':').map_or(name, |(_, local)| local);
    let existing = parent.children.iter().position(
        |node| matches!(node, ChartXmlNode::Element(element) if element.local() == local),
    );
    let position = match existing {
        Some(position) => position,
        None => {
            let position = parent.insert_position(local, order);
            parent.children.insert(
                position,
                ChartXmlNode::Element(ChartXmlElement::new(name.to_string())),
            );
            position
        }
    };
    match &mut parent.children[position] {
        ChartXmlNode::Element(element) => element,
        _ => unreachable!("position selects an element"),
    }
}

/// Removes every child named in `names` and inserts `replacement` at the first
/// removed position, else at its schema position.
fn style_replace_choice(
    parent: &mut ChartXmlElement,
    names: &[&str],
    replacement: Option<ChartXmlElement>,
    order: &[&str],
) {
    let is_choice = |node: &ChartXmlNode| matches!(node, ChartXmlNode::Element(element) if names.contains(&element.local()));
    let first = parent.children.iter().position(is_choice);
    parent.children.retain(|node| !is_choice(node));
    if let Some(element) = replacement {
        let position = first.unwrap_or_else(|| parent.insert_position(element.local(), order));
        parent
            .children
            .insert(position, ChartXmlNode::Element(element));
    }
}

/// The prefix the part binds to the DrawingML main namespace, else `a`.
fn style_drawing_prefix(root: &ChartXmlElement) -> String {
    root.attributes
        .iter()
        .find_map(|(name, value)| {
            let prefix = name.strip_prefix("xmlns:")?;
            let uri = chart_xml_unescape(value);
            (uri.as_bytes() == DRAWINGML_MAIN_NS || uri.as_bytes() == STRICT_DRAWINGML_MAIN_NS)
                .then(|| prefix.to_string())
        })
        .unwrap_or_else(|| "a".to_string())
}

fn style_color_element(a: &str, color: &StyleColor) -> Result<ChartXmlElement, WolfPptError> {
    let hsl = color.kind == StyleColorKind::Hsl;
    if !hsl && (color.hue.is_some() || color.sat.is_some() || color.lum.is_some()) {
        return Err(style_invalid("hue, sat, and lum apply to hsl colours only"));
    }
    if color.kind != StyleColorKind::System && color.last_color.is_some() {
        return Err(style_invalid("last_color applies to system colours only"));
    }
    let value = || {
        color
            .value
            .as_deref()
            .ok_or_else(|| style_invalid("the colour needs a value"))
    };
    let mut element = match color.kind {
        StyleColorKind::Srgb => {
            let value = value()?;
            let hex = style_hex(value).ok_or_else(|| {
                style_invalid(format!(
                    "srgb colour value must be six hex digits, got {value:?}"
                ))
            })?;
            ChartXmlElement::new(format!("{a}:srgbClr")).with_val(&hex)
        }
        StyleColorKind::Scheme => {
            let value = value()?;
            if !STYLE_SCHEME_COLORS.contains(&value) {
                return Err(style_invalid(format!(
                    "scheme colour value must be an ST_SchemeColorVal token, got {value:?}"
                )));
            }
            ChartXmlElement::new(format!("{a}:schemeClr")).with_val(value)
        }
        StyleColorKind::Preset => {
            let value = value()?;
            if !PRESET_COLOR_TOKENS.contains(&value) {
                return Err(style_invalid(format!(
                    "preset colour value must be an ST_PresetColorVal token, got {value:?}"
                )));
            }
            ChartXmlElement::new(format!("{a}:prstClr")).with_val(value)
        }
        StyleColorKind::System => {
            let value = value()?;
            if !SYSTEM_COLOR_TOKENS.contains(&value) {
                return Err(style_invalid(format!(
                    "system colour value must be an ST_SystemColorVal token, got {value:?}"
                )));
            }
            let mut element = ChartXmlElement::new(format!("{a}:sysClr")).with_val(value);
            if let Some(last) = &color.last_color {
                let hex = style_hex(last).ok_or_else(|| {
                    style_invalid(format!(
                        "system colour last_color must be six hex digits, got {last:?}"
                    ))
                })?;
                element.set_attribute("lastClr", &hex);
            }
            element
        }
        StyleColorKind::Hsl => {
            if color.value.is_some() {
                return Err(style_invalid(
                    "hsl colours take hue, sat, and lum, not value",
                ));
            }
            let (Some(hue), Some(sat), Some(lum)) = (color.hue, color.sat, color.lum) else {
                return Err(style_invalid("hsl colours need hue, sat, and lum"));
            };
            if !(0..21_600_000).contains(&hue) {
                return Err(style_invalid(format!(
                    "hsl hue must be in [0, 21600000), got {hue}"
                )));
            }
            let mut element = ChartXmlElement::new(format!("{a}:hslClr"));
            element.set_attribute("hue", &hue.to_string());
            element.set_attribute("sat", &sat.to_string());
            element.set_attribute("lum", &lum.to_string());
            element
        }
    };
    for transform in &color.transforms {
        let name = transform.name.as_str();
        if !STYLE_COLOR_TRANSFORMS.contains(&name) {
            return Err(style_invalid(format!(
                "colour transform must be a DrawingML colour transform element, got {name:?}"
            )));
        }
        let mut child = ChartXmlElement::new(format!("{a}:{name}"));
        match (STYLE_VALUELESS_TRANSFORMS.contains(&name), transform.val) {
            (true, None) => {}
            (true, Some(_)) => {
                return Err(style_invalid(format!(
                    "colour transform {name} takes no val"
                )))
            }
            (false, Some(val)) => child.set_attribute("val", &val.to_string()),
            (false, None) => {
                return Err(style_invalid(format!(
                    "colour transform {name} needs a val"
                )))
            }
        }
        element.push(child);
    }
    Ok(element)
}

fn style_fill_element(
    a: &str,
    color: Option<&StyleColor>,
) -> Result<ChartXmlElement, WolfPptError> {
    Ok(match color {
        None => ChartXmlElement::new(format!("{a}:noFill")),
        Some(color) => {
            let mut fill = ChartXmlElement::new(format!("{a}:solidFill"));
            fill.push(style_color_element(a, color)?);
            fill
        }
    })
}

/// Colour resolution context: the theme colour scheme and the colour map
/// (`bg1` -> `lt1`, ...) of the slide or master.
struct StyleTheme {
    slots: BTreeMap<String, StyleColorSummary>,
    map: BTreeMap<String, String>,
}

impl StyleTheme {
    fn resolve(&self, token: &str) -> Option<String> {
        let slot = self.map.get(token).map_or(token, String::as_str);
        self.slots
            .get(slot)
            .and_then(|color| color.base_rgb.clone())
    }
}

fn style_color_summary(
    element: &ChartXmlElement,
    theme: Option<&StyleTheme>,
) -> Option<StyleColorSummary> {
    let kind = match element.local() {
        "srgbClr" => "srgb",
        "schemeClr" => "scheme",
        "prstClr" => "preset",
        "sysClr" => "system",
        "hslClr" => "hsl",
        "scrgbClr" => "scrgb",
        _ => return None,
    };
    let transforms = element
        .elements()
        .filter(|child| STYLE_COLOR_TRANSFORMS.contains(&child.local()))
        .map(|child| {
            let val = style_number::<i64>(child, "val");
            StyleColorTransformSummary {
                name: child.local().to_string(),
                val,
                percent: val.map(|val| val as f64 / 1000.0),
            }
        })
        .collect();
    let value = match kind {
        "hsl" | "scrgb" => None,
        _ => element.attribute("val"),
    };
    let last_color = (kind == "system")
        .then(|| element.attribute("lastClr"))
        .flatten();
    let (hue, sat, lum) = if kind == "hsl" {
        (
            style_number(element, "hue"),
            style_number(element, "sat"),
            style_number(element, "lum"),
        )
    } else {
        (None, None, None)
    };
    let base_rgb = match kind {
        "srgb" => value.as_deref().and_then(style_hex),
        "preset" => value.as_deref().and_then(style_default_color),
        "system" => last_color
            .as_deref()
            .and_then(style_hex)
            .or_else(|| value.as_deref().and_then(style_default_color)),
        "hsl" => match (hue, sat, lum) {
            (Some(hue), Some(sat), Some(lum)) => Some(style_hsl_hex(hue, sat, lum)),
            _ => None,
        },
        "scheme" => theme
            .zip(value.as_deref())
            .and_then(|(theme, token)| theme.resolve(token)),
        _ => None,
    };
    Some(StyleColorSummary {
        kind,
        value,
        last_color,
        hue,
        sat,
        lum,
        transforms,
        base_rgb,
    })
}

fn style_first_color(
    element: &ChartXmlElement,
    theme: Option<&StyleTheme>,
) -> Option<StyleColorSummary> {
    element
        .elements()
        .find_map(|child| style_color_summary(child, theme))
}

fn style_fill_summary(
    properties: &ChartXmlElement,
    theme: Option<&StyleTheme>,
) -> Option<StyleFillSummary> {
    properties.elements().find_map(|child| {
        let kind = match child.local() {
            "noFill" => "no_fill",
            "solidFill" => "solid",
            "gradFill" => "gradient",
            "blipFill" => "blip",
            "pattFill" => "pattern",
            "grpFill" => "group",
            _ => return None,
        };
        Some(StyleFillSummary {
            kind,
            color: (kind == "solid")
                .then(|| style_first_color(child, theme))
                .flatten(),
        })
    })
}

fn style_line_end_summary(element: &ChartXmlElement) -> StyleLineEndSummary {
    StyleLineEndSummary {
        end_type: element.attribute("type"),
        width: element.attribute("w"),
        length: element.attribute("len"),
    }
}

fn style_line_summary(line: &ChartXmlElement, theme: Option<&StyleTheme>) -> StyleLineSummary {
    StyleLineSummary {
        width_emu: style_number(line, "w"),
        cap: line.attribute("cap"),
        compound: line.attribute("cmpd"),
        dash: line.child_val("prstDash"),
        fill: style_fill_summary(line, theme),
        head_end: line.child("headEnd").map(style_line_end_summary),
        tail_end: line.child("tailEnd").map(style_line_end_summary),
    }
}

fn style_effects_summary(
    effects: &ChartXmlElement,
    theme: Option<&StyleTheme>,
) -> StyleEffectsSummary {
    StyleEffectsSummary {
        effects: effects
            .elements()
            .map(|effect| effect.local().to_string())
            .collect(),
        outer_shadow: effects
            .child("outerShdw")
            .map(|shadow| StyleOuterShadowSummary {
                blur_radius_emu: style_number(shadow, "blurRad"),
                distance_emu: style_number(shadow, "dist"),
                direction: style_number(shadow, "dir"),
                alignment: shadow.attribute("algn"),
                rotate_with_shape: style_bool(shadow, "rotWithShape"),
                color: style_first_color(shadow, theme),
            }),
    }
}

fn style_point(point: &ChartXmlElement) -> [String; 2] {
    [
        point.attribute("x").unwrap_or_default(),
        point.attribute("y").unwrap_or_default(),
    ]
}

fn style_custom_geometry_summary(geometry: &ChartXmlElement) -> StyleCustomGeometrySummary {
    let paths = geometry
        .child("pathLst")
        .map(|list| {
            list.elements()
                .filter(|path| path.local() == "path")
                .map(|path| StylePathSummary {
                    w: style_number(path, "w"),
                    h: style_number(path, "h"),
                    commands: path
                        .elements()
                        .filter_map(|command| {
                            let op = match command.local() {
                                "moveTo" => "move_to",
                                "lnTo" => "line_to",
                                "quadBezTo" => "quad_bezier_to",
                                "cubicBezTo" => "cubic_bezier_to",
                                "arcTo" => "arc_to",
                                "close" => "close",
                                _ => return None,
                            };
                            let arc = (op == "arc_to").then(|| {
                                ["wR", "hR", "stAng", "swAng"]
                                    .map(|name| command.attribute(name).unwrap_or_default())
                            });
                            Some(StylePathCommand {
                                op,
                                points: command
                                    .elements()
                                    .filter(|point| point.local() == "pt")
                                    .map(style_point)
                                    .collect(),
                                arc,
                            })
                        })
                        .collect(),
                })
                .collect()
        })
        .unwrap_or_default();
    let mut xml = String::new();
    geometry.write(&mut xml);
    StyleCustomGeometrySummary { paths, xml }
}

fn style_anchor_summary(xfrm: &ChartXmlElement) -> StyleAnchorSummary {
    let pair = |local: &str, first: &str, second: &str| {
        xfrm.child(local).map_or((None, None), |element| {
            (style_number(element, first), style_number(element, second))
        })
    };
    let (x, y) = pair("off", "x", "y");
    let (cx, cy) = pair("ext", "cx", "cy");
    let (child_x, child_y) = pair("chOff", "x", "y");
    let (child_cx, child_cy) = pair("chExt", "cx", "cy");
    StyleAnchorSummary {
        x,
        y,
        cx,
        cy,
        child_x,
        child_y,
        child_cx,
        child_cy,
        rotation: style_number(xfrm, "rot"),
        flip_h: style_bool(xfrm, "flipH").unwrap_or(false),
        flip_v: style_bool(xfrm, "flipV").unwrap_or(false),
    }
}

fn style_non_visual(shape: &ChartXmlElement) -> Option<&ChartXmlElement> {
    shape
        .elements()
        .find(|element| element.local().starts_with("nv"))
}

fn style_shape_id(shape: &ChartXmlElement) -> Option<u64> {
    style_non_visual(shape)
        .and_then(|nv| nv.child("cNvPr"))
        .and_then(|properties| style_number(properties, "id"))
}

fn style_shape_summary(shape: &ChartXmlElement, theme: Option<&StyleTheme>) -> ShapeStyleSummary {
    let kind = shape.local();
    let non_visual = style_non_visual(shape);
    let c_nv_pr = non_visual.and_then(|nv| nv.child("cNvPr"));
    let properties = shape.child(if kind == "grpSp" { "grpSpPr" } else { "spPr" });
    let xfrm = properties
        .and_then(|properties| properties.child("xfrm"))
        .or_else(|| shape.child("xfrm"));
    let connection = |local: &str| {
        non_visual
            .and_then(|nv| nv.child("cNvCxnSpPr"))
            .and_then(|properties| properties.child(local))
            .map(|connection| StyleConnectionSummary {
                shape_id: style_number(connection, "id"),
                site: style_number(connection, "idx"),
            })
    };
    ShapeStyleSummary {
        id: c_nv_pr.and_then(|properties| style_number(properties, "id")),
        name: c_nv_pr.and_then(|properties| properties.attribute("name")),
        kind: kind.to_string(),
        text_box: non_visual
            .and_then(|nv| nv.child("cNvSpPr"))
            .and_then(|properties| style_bool(properties, "txBox"))
            .unwrap_or(false),
        anchor: xfrm.map(style_anchor_summary),
        preset_geometry: properties
            .and_then(|properties| properties.child("prstGeom"))
            .and_then(|geometry| geometry.attribute("prst")),
        custom_geometry: properties
            .and_then(|properties| properties.child("custGeom"))
            .map(style_custom_geometry_summary),
        fill: properties.and_then(|properties| style_fill_summary(properties, theme)),
        line: properties
            .and_then(|properties| properties.child("ln"))
            .map(|line| style_line_summary(line, theme)),
        effects: properties
            .and_then(|properties| properties.child("effectLst"))
            .map(|effects| style_effects_summary(effects, theme)),
        connection_start: connection("stCxn"),
        connection_end: connection("endCxn"),
        children: if kind == "grpSp" {
            style_shape_summaries(shape, theme)
        } else {
            Vec::new()
        },
    }
}

fn style_shape_summaries(
    container: &ChartXmlElement,
    theme: Option<&StyleTheme>,
) -> Vec<ShapeStyleSummary> {
    container
        .elements()
        .filter(|element| STYLE_SHAPE_KINDS.contains(&element.local()))
        .map(|shape| style_shape_summary(shape, theme))
        .collect()
}

fn style_background_summary(
    common: &ChartXmlElement,
    theme: Option<&StyleTheme>,
) -> Option<StyleBackgroundSummary> {
    let background = common.child("bg")?;
    let reference = background.child("bgRef");
    Some(StyleBackgroundSummary {
        fill: background
            .child("bgPr")
            .and_then(|properties| style_fill_summary(properties, theme)),
        reference_index: reference.and_then(|reference| style_number(reference, "idx")),
        reference_color: reference.and_then(|reference| style_first_color(reference, theme)),
    })
}

fn style_color_map(element: Option<&ChartXmlElement>) -> BTreeMap<String, String> {
    element
        .map(|map| {
            map.attributes
                .iter()
                .filter(|(name, _)| !name.contains(':'))
                .map(|(name, value)| (name.clone(), chart_xml_unescape(value)))
                .collect()
        })
        .unwrap_or_default()
}

fn style_read_root<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    part: &str,
) -> Result<Option<ChartXmlElement>, WolfPptError> {
    match read_archive_text(archive, part)? {
        Some(xml) => Ok(Some(chart_xml_parse(&xml)?.root)),
        None => Ok(None),
    }
}

fn style_related_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    part: &str,
    relationship_suffix: &str,
) -> Result<Option<String>, WolfPptError> {
    Ok(read_relationships(archive, part)?
        .into_iter()
        .find(|relationship| {
            relationship
                .relationship_type
                .ends_with(relationship_suffix)
        })
        .map(|relationship| resolve_target(part, &relationship.target)))
}

/// Slide master parts in `p:sldMasterIdLst` order.
fn style_master_parts<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
) -> Result<Vec<String>, WolfPptError> {
    const PRESENTATION: &str = "ppt/presentation.xml";
    let Some(root) = style_read_root(archive, PRESENTATION)? else {
        return Ok(Vec::new());
    };
    let relationships = read_relationships(archive, PRESENTATION)?;
    let mut parts = Vec::new();
    for entry in root
        .child("sldMasterIdLst")
        .into_iter()
        .flat_map(|list| list.elements())
    {
        let relationship_id = entry
            .attributes
            .iter()
            .find(|(name, _)| name.ends_with(":id"))
            .map(|(_, value)| chart_xml_unescape(value));
        if let Some(relationship) = relationship_id.and_then(|id| {
            relationships
                .iter()
                .find(|relationship| relationship.id == id)
        }) {
            parts.push(resolve_target(PRESENTATION, &relationship.target));
        }
    }
    Ok(parts)
}

/// A master's colour map, theme part name, and theme root.
type StyleMasterTheme = (
    BTreeMap<String, String>,
    Option<String>,
    Option<ChartXmlElement>,
);

/// Reads a master's colour map, theme part, and theme root.
fn style_master_theme<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    master_part: &str,
    master: &ChartXmlElement,
) -> Result<StyleMasterTheme, WolfPptError> {
    let map = style_color_map(master.child("clrMap"));
    let theme_part = style_related_part(archive, master_part, "/theme")?;
    let theme = match &theme_part {
        Some(part) => style_read_root(archive, part)?,
        None => None,
    };
    Ok((map, theme_part, theme))
}

fn style_theme_slots(theme: Option<&ChartXmlElement>) -> BTreeMap<String, StyleColorSummary> {
    theme
        .and_then(|theme| theme.child("themeElements"))
        .and_then(|elements| elements.child("clrScheme"))
        .map(|scheme| {
            scheme
                .elements()
                .filter_map(|slot| {
                    style_first_color(slot, None).map(|color| (slot.local().to_string(), color))
                })
                .collect()
        })
        .unwrap_or_default()
}

/// Style summaries of every slide (shapes and background) and master
/// (background, theme colour scheme, and theme effect styles).
pub fn summarize_shape_styles_bytes(bytes: &[u8]) -> Result<ShapeStylesSummary, WolfPptError> {
    let mut archive = ZipArchive::new(Cursor::new(bytes))?;
    let mut masters = Vec::new();
    for (index, part) in style_master_parts(&mut archive)?.into_iter().enumerate() {
        let Some(master) = style_read_root(&mut archive, &part)? else {
            continue;
        };
        let (map, theme_part, theme_root) = style_master_theme(&mut archive, &part, &master)?;
        let theme = StyleTheme {
            slots: style_theme_slots(theme_root.as_ref()),
            map,
        };
        let effect_styles = theme_root
            .as_ref()
            .and_then(|theme| theme.child("themeElements"))
            .and_then(|elements| elements.child("fmtScheme"))
            .and_then(|scheme| scheme.child("effectStyleLst"))
            .map(|list| {
                list.elements()
                    .filter(|style| style.local() == "effectStyle")
                    .map(|style| {
                        style
                            .child("effectLst")
                            .map(|effects| style_effects_summary(effects, Some(&theme)))
                    })
                    .collect()
            });
        masters.push(MasterStylesSummary {
            index,
            background: master
                .child("cSld")
                .and_then(|common| style_background_summary(common, Some(&theme))),
            part,
            theme_part,
            color_scheme: theme.slots,
            effect_styles,
        });
    }
    let mut slides = Vec::new();
    for (index, part) in slide_parts(&mut archive)?.into_iter().enumerate() {
        let Some(slide) = style_read_root(&mut archive, &part)? else {
            continue;
        };
        let master_part = match style_related_part(&mut archive, &part, "/slideLayout")? {
            Some(layout) => style_related_part(&mut archive, &layout, "/slideMaster")?,
            None => None,
        };
        let master = match &master_part {
            Some(master_part) => style_read_root(&mut archive, master_part)?,
            None => None,
        };
        let theme = match (&master_part, &master) {
            (Some(master_part), Some(master)) => {
                let (map, _, theme_root) = style_master_theme(&mut archive, master_part, master)?;
                let map = match slide
                    .child("clrMapOvr")
                    .and_then(|over| over.child("overrideClrMapping"))
                {
                    Some(over) => style_color_map(Some(over)),
                    None => map,
                };
                Some(StyleTheme {
                    slots: style_theme_slots(theme_root.as_ref()),
                    map,
                })
            }
            _ => None,
        };
        let common = slide.child("cSld");
        slides.push(SlideStylesSummary {
            index,
            part,
            background: common.and_then(|common| style_background_summary(common, theme.as_ref())),
            shapes: common
                .and_then(|common| common.child("spTree"))
                .map(|tree| style_shape_summaries(tree, theme.as_ref()))
                .unwrap_or_default(),
        });
    }
    Ok(ShapeStylesSummary { slides, masters })
}

/// Rewrites one XML part chosen by `select` with `edit`, copying every other
/// part unchanged. Returns the part name, part count, and VBA flag.
fn style_rewrite_part(
    input_path: &Path,
    output_path: &Path,
    select: impl FnOnce(&mut ZipArchive<File>) -> Result<String, WolfPptError>,
    edit: impl FnOnce(&mut ChartXmlElement) -> Result<(), WolfPptError>,
) -> Result<(String, usize, bool), WolfPptError> {
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let mut archive = ZipArchive::new(File::open(input_path)?)?;
    let part = select(&mut archive)?;
    let xml = read_archive_text(&mut archive, &part)?
        .ok_or_else(|| style_invalid(format!("part {part} was not found")))?;
    let mut document = chart_xml_parse(&xml)?;
    edit(&mut document.root)?;
    let payload = chart_xml_serialize(&document);
    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &part, payload.as_bytes())?;
    Ok((part, part_count, has_vba))
}

fn style_slide_part(
    archive: &mut ZipArchive<File>,
    slide_index: usize,
) -> Result<String, WolfPptError> {
    slide_part_at_index(archive, slide_index)?
        .ok_or_else(|| style_invalid(format!("slide index {slide_index} was not found")))
}

fn style_shape_mut(container: &mut ChartXmlElement, shape_id: u64) -> Option<&mut ChartXmlElement> {
    for element in container.elements_mut() {
        if !STYLE_SHAPE_KINDS.contains(&element.local()) {
            continue;
        }
        if style_shape_id(element) == Some(shape_id) {
            return Some(element);
        }
        if element.local() == "grpSp" {
            if let Some(found) = style_shape_mut(element, shape_id) {
                return Some(found);
            }
        }
    }
    None
}

fn style_collect_ids(container: &ChartXmlElement, ids: &mut std::collections::BTreeSet<u64>) {
    for element in container.elements() {
        if !STYLE_SHAPE_KINDS.contains(&element.local()) {
            continue;
        }
        if let Some(id) = style_shape_id(element) {
            ids.insert(id);
        }
        if element.local() == "grpSp" {
            style_collect_ids(element, ids);
        }
    }
}

fn style_set_line_end(a: &str, line: &mut ChartXmlElement, local: &str, edit: &StyleLineEndEdit) {
    let end = style_ensure(line, &format!("{a}:{local}"), STYLE_LN_ORDER);
    let mut apply = |name: &str, token: Option<Option<&'static str>>| match token {
        Some(Some(token)) => end.set_attribute(name, token),
        Some(None) => style_remove_attribute(end, name),
        None => {}
    };
    apply(
        "type",
        edit.end_type
            .map(|value| value.map(StyleLineEndType::token)),
    );
    apply(
        "w",
        edit.width.map(|value| value.map(StyleLineEndSize::token)),
    );
    apply(
        "len",
        edit.length.map(|value| value.map(StyleLineEndSize::token)),
    );
}

fn style_set_anchor(a: &str, xfrm: &mut ChartXmlElement, anchor: StyleAnchorEdit, child: bool) {
    let (offset, extent) = if child {
        ("chOff", "chExt")
    } else {
        ("off", "ext")
    };
    let element = style_ensure(xfrm, &format!("{a}:{offset}"), STYLE_XFRM_ORDER);
    element.set_attribute("x", &anchor.x.to_string());
    element.set_attribute("y", &anchor.y.to_string());
    let element = style_ensure(xfrm, &format!("{a}:{extent}"), STYLE_XFRM_ORDER);
    element.set_attribute("cx", &anchor.cx.to_string());
    element.set_attribute("cy", &anchor.cy.to_string());
}

fn style_apply_shape_edit(
    a: &str,
    shape: &mut ChartXmlElement,
    edit: &ShapeStyleEdit,
    ids: &std::collections::BTreeSet<u64>,
) -> Result<(), WolfPptError> {
    let kind = shape.local().to_string();
    let id = edit.shape_id;
    if !matches!(kind.as_str(), "sp" | "cxnSp" | "pic" | "grpSp") {
        return Err(style_invalid(format!(
            "shape {id} is a {kind}; style edits address sp, cxnSp, pic, and grpSp shapes"
        )));
    }
    let group = kind == "grpSp";
    let refuse = |field: &str| {
        Err(style_invalid(format!(
            "{field} does not apply to {kind} shape {id}"
        )))
    };
    let line_edit = edit.line_width_emu.is_some()
        || edit.line_cap.is_some()
        || edit.line_dash.is_some()
        || edit.line_color.is_some()
        || edit.head_end.is_some()
        || edit.tail_end.is_some();
    if group && line_edit {
        return refuse("line properties");
    }
    if group && edit.preset_geometry.is_some() {
        return refuse("preset_geometry");
    }
    if !group && edit.child_anchor.is_some() {
        return refuse("child_anchor");
    }
    if kind != "cxnSp" && (edit.connection_start.is_some() || edit.connection_end.is_some()) {
        return refuse("connections");
    }
    if let Some(Some(width)) = edit.line_width_emu {
        if width > STYLE_MAX_LINE_WIDTH_EMU {
            return Err(style_invalid(format!(
                "line_width_emu must be at most {STYLE_MAX_LINE_WIDTH_EMU}, got {width}"
            )));
        }
    }
    let preset = match &edit.preset_geometry {
        Some(preset) if !style_valid_preset_geometry(preset) => {
            return Err(style_invalid(format!(
                "preset_geometry must be an ST_ShapeType token, got {preset:?}"
            )))
        }
        preset => preset.as_deref(),
    };
    let mut connections = Vec::new();
    for (local, connection) in [
        ("stCxn", edit.connection_start),
        ("endCxn", edit.connection_end),
    ] {
        if let Some(Some(target)) = connection {
            if target.shape_id == id || !ids.contains(&target.shape_id) {
                return Err(style_invalid(format!(
                    "connection target shape {} was not found on the slide",
                    target.shape_id
                )));
            }
        }
        if let Some(connection) = connection {
            connections.push((local, connection));
        }
    }
    let fill = match &edit.fill {
        Some(color) => Some(style_fill_element(a, color.as_ref())?),
        None => None,
    };
    let line_fill = match &edit.line_color {
        Some(color) => Some(style_fill_element(a, color.as_ref())?),
        None => None,
    };

    if !connections.is_empty() {
        let non_visual = shape
            .child_mut("nvCxnSpPr")
            .ok_or_else(|| style_invalid(format!("connector {id} has no p:nvCxnSpPr")))?;
        let name = non_visual.qualified("cNvCxnSpPr");
        let properties = style_ensure(non_visual, &name, &["cNvPr", "cNvCxnSpPr", "nvPr"]);
        for (local, connection) in connections {
            let element = connection.map(|target| {
                let mut element = ChartXmlElement::new(format!("{a}:{local}"));
                element.set_attribute("id", &target.shape_id.to_string());
                element.set_attribute("idx", &target.site.to_string());
                element
            });
            style_replace_choice(properties, &[local], element, STYLE_CNV_CXN_SP_PR_ORDER);
        }
    }

    let properties_name = shape.qualified(if group { "grpSpPr" } else { "spPr" });
    let order = if group {
        STYLE_GRP_SP_PR_ORDER
    } else {
        STYLE_SP_PR_ORDER
    };
    let properties = style_ensure(shape, &properties_name, STYLE_SHAPE_ORDER);
    if let Some(preset) = preset {
        properties.remove_children("custGeom");
        let geometry = style_ensure(properties, &format!("{a}:prstGeom"), order);
        geometry.set_attribute("prst", preset);
        if geometry.child("avLst").is_none() {
            geometry.push(ChartXmlElement::new(format!("{a}:avLst")));
        }
    }
    if edit.anchor.is_some() || edit.child_anchor.is_some() {
        let xfrm = style_ensure(properties, &format!("{a}:xfrm"), order);
        if let Some(anchor) = edit.anchor {
            style_set_anchor(a, xfrm, anchor, false);
        }
        if let Some(anchor) = edit.child_anchor {
            style_set_anchor(a, xfrm, anchor, true);
        }
    }
    if let Some(fill) = fill {
        style_replace_choice(properties, STYLE_FILL_NAMES, Some(fill), order);
    }
    if line_edit {
        let line = style_ensure(properties, &format!("{a}:ln"), order);
        match edit.line_width_emu {
            Some(Some(width)) if width > 0 => line.set_attribute("w", &width.to_string()),
            Some(_) => style_remove_attribute(line, "w"),
            None => {}
        }
        match edit.line_cap {
            Some(Some(cap)) => line.set_attribute("cap", cap.token()),
            Some(None) => style_remove_attribute(line, "cap"),
            None => {}
        }
        if let Some(dash) = edit.line_dash {
            let element = dash
                .map(|dash| ChartXmlElement::new(format!("{a}:prstDash")).with_val(dash.token()));
            style_replace_choice(line, &["prstDash", "custDash"], element, STYLE_LN_ORDER);
        }
        if let Some(fill) = line_fill {
            style_replace_choice(line, STYLE_LINE_FILL_NAMES, Some(fill), STYLE_LN_ORDER);
        }
        if let Some(end) = &edit.head_end {
            style_set_line_end(a, line, "headEnd", end);
        }
        if let Some(end) = &edit.tail_end {
            style_set_line_end(a, line, "tailEnd", end);
        }
    }
    Ok(())
}

pub fn set_slide_shape_style(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &ShapeStyleEdit,
) -> Result<ShapeStyleEditSummary, WolfPptError> {
    let output_path = output_path.as_ref();
    let (slide_part, part_count, has_vba) = style_rewrite_part(
        input_path.as_ref(),
        output_path,
        |archive| style_slide_part(archive, edit.slide_index),
        |root| {
            let a = style_drawing_prefix(root);
            let tree = root
                .child_mut("cSld")
                .and_then(|common| common.child_mut("spTree"))
                .ok_or_else(|| style_invalid("slide has no p:cSld/p:spTree"))?;
            let mut ids = std::collections::BTreeSet::new();
            style_collect_ids(tree, &mut ids);
            let shape = style_shape_mut(tree, edit.shape_id).ok_or_else(|| {
                style_invalid(format!(
                    "shape {} was not found on slide {}",
                    edit.shape_id, edit.slide_index
                ))
            })?;
            style_apply_shape_edit(&a, shape, edit, &ids)
        },
    )?;
    Ok(ShapeStyleEditSummary {
        path: output_path.to_path_buf(),
        slide_index: edit.slide_index,
        slide_part,
        shape_id: edit.shape_id,
        part_count,
        has_vba,
    })
}

pub fn set_background_fill(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &BackgroundFillEdit,
) -> Result<BackgroundEditSummary, WolfPptError> {
    let output_path = output_path.as_ref();
    let (part, part_count, has_vba) = style_rewrite_part(
        input_path.as_ref(),
        output_path,
        |archive| match edit.target {
            BackgroundTarget::Slide => style_slide_part(archive, edit.index),
            BackgroundTarget::Master => style_master_parts(archive)?
                .into_iter()
                .nth(edit.index)
                .ok_or_else(|| style_invalid(format!("master index {} was not found", edit.index))),
        },
        |root| {
            let a = style_drawing_prefix(root);
            let fill = style_fill_element(&a, edit.color.as_ref())?;
            let common = root
                .child_mut("cSld")
                .ok_or_else(|| style_invalid("part has no p:cSld"))?;
            let background_name = common.qualified("bg");
            let properties_name = common.qualified("bgPr");
            let background = style_ensure(common, &background_name, STYLE_CSLD_ORDER);
            background.remove_children("bgRef");
            let properties = style_ensure(background, &properties_name, STYLE_BG_ORDER);
            style_replace_choice(properties, STYLE_FILL_NAMES, Some(fill), STYLE_BG_PR_ORDER);
            if properties.child("effectLst").is_none() && properties.child("effectDag").is_none() {
                style_ensure(properties, &format!("{a}:effectLst"), STYLE_BG_PR_ORDER);
            }
            Ok(())
        },
    )?;
    Ok(BackgroundEditSummary {
        path: output_path.to_path_buf(),
        target: edit.target,
        index: edit.index,
        part,
        part_count,
        has_vba,
    })
}

/// Adds a freeform shape from a path in absolute slide EMU coordinates. The
/// anchor is the bounding box of every path point (control points included);
/// the path is stored relative to it with `w`/`h` equal to its size.
pub fn add_slide_freeform_path(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    operations: &[FreeformPathOperation],
) -> Result<FreeformShapeAddSummary, WolfPptError> {
    use FreeformPathOperation as Op;
    let mut bounds: Option<(i64, i64, i64, i64)> = None;
    let mut include = |x: i64, y: i64| {
        bounds = Some(match bounds {
            None => (x, y, x, y),
            Some((x0, y0, x1, y1)) => (x0.min(x), y0.min(y), x1.max(x), y1.max(y)),
        });
    };
    for operation in operations {
        match *operation {
            Op::MoveTo { x, y } | Op::LineTo { x, y } => include(x, y),
            Op::QuadBezierTo { x1, y1, x, y } => {
                include(x1, y1);
                include(x, y);
            }
            Op::CubicBezierTo {
                x1,
                y1,
                x2,
                y2,
                x,
                y,
            } => {
                include(x1, y1);
                include(x2, y2);
                include(x, y);
            }
            Op::Close => {}
            _ => {
                return Err(style_invalid(
                    "an absolute freeform path accepts move_to, line_to, quad_bezier_to, cubic_bezier_to, and close",
                ))
            }
        }
    }
    let (x0, y0, x1, y1) = bounds
        .ok_or_else(|| style_invalid("an absolute freeform path needs at least one point"))?;
    let relative: Vec<FreeformPathOperation> = operations
        .iter()
        .map(|operation| match *operation {
            Op::MoveTo { x, y } => Op::MoveTo {
                x: x - x0,
                y: y - y0,
            },
            Op::LineTo { x, y } => Op::LineTo {
                x: x - x0,
                y: y - y0,
            },
            Op::QuadBezierTo { x1, y1, x, y } => Op::QuadBezierTo {
                x1: x1 - x0,
                y1: y1 - y0,
                x: x - x0,
                y: y - y0,
            },
            Op::CubicBezierTo {
                x1,
                y1,
                x2,
                y2,
                x,
                y,
            } => Op::CubicBezierTo {
                x1: x1 - x0,
                y1: y1 - y0,
                x2: x2 - x0,
                y2: y2 - y0,
                x: x - x0,
                y: y - y0,
            },
            _ => Op::Close,
        })
        .collect();
    let (width, height) = (x1 - x0, y1 - y0);
    add_slide_freeform_shape(
        input_path,
        output_path,
        slide_index,
        x0,
        y0,
        width,
        height,
        width,
        height,
        &relative,
    )
}
