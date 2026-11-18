// Chart authoring: slide chart frames, chart-part legends, axes, plot styles,
// and series data. Chart parts are edited through a small order-preserving
// element tree so untouched markup (formatting, extensions,
// markup-compatibility blocks) round-trips verbatim, and new elements land at
// their CT_* schema position.

pub const CHART_CONTENT_TYPE: &str =
    "application/vnd.openxmlformats-officedocument.drawingml.chart+xml";
const CHART_RELATIONSHIP_TYPE: &str =
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart";
const CHART_NAMESPACE: &str = "http://schemas.openxmlformats.org/drawingml/2006/chart";

macro_rules! chart_token_enum {
    ($(#[$meta:meta])* $name:ident { $($variant:ident => $token:literal),+ $(,)? }) => {
        $(#[$meta])*
        #[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
        pub enum $name {
            $(#[serde(rename = $token)] $variant),+
        }

        impl $name {
            /// The OOXML attribute token written to the chart part.
            pub fn token(self) -> &'static str {
                match self {
                    $(Self::$variant => $token),+
                }
            }
        }
    };
}

chart_token_enum!(
    /// ST_LegendPos.
    ChartLegendPosition { Bottom => "b", Left => "l", Right => "r", Top => "t", TopRight => "tr" }
);
chart_token_enum!(
    /// ST_LayoutTarget.
    ChartLayoutTarget { Inner => "inner", Outer => "outer" }
);
chart_token_enum!(
    /// ST_LayoutMode.
    ChartLayoutMode { Edge => "edge", Factor => "factor" }
);
chart_token_enum!(
    /// ST_AxPos.
    ChartAxisPosition { Bottom => "b", Left => "l", Right => "r", Top => "t" }
);
chart_token_enum!(
    /// ST_Orientation.
    ChartAxisOrientation { MaxMin => "maxMin", MinMax => "minMax" }
);
chart_token_enum!(
    /// ST_Crosses.
    ChartAxisCrosses { AutoZero => "autoZero", Max => "max", Min => "min" }
);
chart_token_enum!(
    /// ST_CrossBetween.
    ChartAxisCrossBetween { Between => "between", MidpointCategory => "midCat" }
);
chart_token_enum!(
    /// ST_TickMark.
    ChartTickMark { Cross => "cross", In => "in", None => "none", Out => "out" }
);
chart_token_enum!(
    /// ST_BarDir.
    ChartBarDirection { Bar => "bar", Column => "col" }
);
chart_token_enum!(
    /// ST_BarGrouping.
    ChartBarGrouping {
        Clustered => "clustered",
        PercentStacked => "percentStacked",
        Stacked => "stacked",
        Standard => "standard",
    }
);
chart_token_enum!(
    /// ST_Grouping (line and area plots).
    ChartGrouping { PercentStacked => "percentStacked", Stacked => "stacked", Standard => "standard" }
);
chart_token_enum!(
    /// ST_RadarStyle.
    ChartRadarStyle { Filled => "filled", Marker => "marker", Standard => "standard" }
);
chart_token_enum!(
    /// ST_ScatterStyle.
    ChartScatterStyle {
        Line => "line",
        LineMarker => "lineMarker",
        Marker => "marker",
        None => "none",
        Smooth => "smooth",
        SmoothMarker => "smoothMarker",
    }
);

/// Manual layout of a legend. Absent fields stay untouched.
#[derive(Debug, Clone, Default, PartialEq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartManualLayoutEdit {
    pub target: Option<ChartLayoutTarget>,
    pub x_mode: Option<ChartLayoutMode>,
    pub y_mode: Option<ChartLayoutMode>,
    pub width_mode: Option<ChartLayoutMode>,
    pub height_mode: Option<ChartLayoutMode>,
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub width: Option<f64>,
    pub height: Option<f64>,
}

/// Creates the legend when absent (position right, no overlay), then applies
/// the given fields. `manual_layout` creates `c:layout/c:manualLayout`.
#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartLegendEdit {
    pub slide_index: usize,
    pub chart_index: usize,
    pub overlay: Option<bool>,
    pub position: Option<ChartLegendPosition>,
    pub manual_layout: Option<ChartManualLayoutEdit>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartNumberFormatEdit {
    pub format_code: String,
    pub source_linked: Option<bool>,
}

/// Edits the axis whose `c:axId` equals `axis_id`. `crosses` and
/// `crosses_at` are alternatives; `cross_between` applies to value axes.
#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartAxisEdit {
    pub slide_index: usize,
    pub chart_index: usize,
    pub axis_id: i64,
    pub orientation: Option<ChartAxisOrientation>,
    pub position: Option<ChartAxisPosition>,
    pub crosses: Option<ChartAxisCrosses>,
    pub crosses_at: Option<f64>,
    pub cross_between: Option<ChartAxisCrossBetween>,
    pub number_format: Option<ChartNumberFormatEdit>,
    pub major_tick_mark: Option<ChartTickMark>,
    pub minor_tick_mark: Option<ChartTickMark>,
    pub visible: Option<bool>,
    pub log_base: Option<f64>,
    pub minimum: Option<f64>,
    pub maximum: Option<f64>,
}

/// Edits plot `plot_index` (zero-based among the plot area's chart-type
/// elements). Each field applies only to the plot types that define it.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartPlotEdit {
    pub slide_index: usize,
    pub chart_index: usize,
    pub plot_index: usize,
    pub bar_direction: Option<ChartBarDirection>,
    pub bar_grouping: Option<ChartBarGrouping>,
    pub gap_width: Option<u32>,
    pub grouping: Option<ChartGrouping>,
    pub radar_style: Option<ChartRadarStyle>,
    pub scatter_style: Option<ChartScatterStyle>,
}

/// Zero-based worksheet cell in the chart's embedded workbook.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartCellReference {
    pub row: u32,
    pub column: u32,
}

/// Zero-based, inclusive worksheet range in the chart's embedded workbook.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartCellRange {
    pub first_row: u32,
    pub last_row: u32,
    pub first_column: u32,
    pub last_column: u32,
}

#[derive(Debug, Clone, PartialEq, serde::Deserialize, serde::Serialize)]
#[serde(untagged)]
pub enum ChartPointValue {
    Number(f64),
    Text(String),
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartSeriesTitleEdit {
    pub text: String,
    pub reference: Option<ChartCellReference>,
}

#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartCategoryDataEdit {
    pub values: Vec<ChartPointValue>,
    pub range: Option<ChartCellRange>,
}

#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartValueDataEdit {
    pub values: Vec<f64>,
    pub range: Option<ChartCellRange>,
    pub format_code: Option<String>,
}

/// Edits series `series_index` of plot `plot_index`. Categories and values
/// replace the series' `c:cat`/`c:val` (`c:xVal`/`c:yVal` for scatter and
/// bubble plots) with a cached reference into the embedded workbook's first
/// sheet when a range is given, else a literal. The embedded workbook itself
/// is not rewritten.
#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChartSeriesEdit {
    pub slide_index: usize,
    pub chart_index: usize,
    pub plot_index: usize,
    pub series_index: usize,
    pub explosion: Option<u32>,
    pub title: Option<ChartSeriesTitleEdit>,
    pub categories: Option<ChartCategoryDataEdit>,
    pub values: Option<ChartValueDataEdit>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ChartAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub relationship_id: String,
    pub chart_part: String,
    pub content_type: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ChartEditSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub chart_index: usize,
    pub chart_part: String,
    pub relationship_id: String,
    pub part_count: usize,
    pub has_vba: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedded_workbook_updated: Option<bool>,
}

// ---------------------------------------------------------------------------
// Order-preserving chart element tree
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
enum ChartXmlNode {
    Element(ChartXmlElement),
    /// Escaped character data, written verbatim.
    Text(String),
    /// Comments, processing instructions, and the XML declaration, verbatim.
    Markup(String),
}

#[derive(Debug, Clone)]
struct ChartXmlElement {
    name: String,
    /// Attribute names with escaped values.
    attributes: Vec<(String, String)>,
    children: Vec<ChartXmlNode>,
}

struct ChartXmlDocument {
    prolog: Vec<ChartXmlNode>,
    root: ChartXmlElement,
    epilog: Vec<ChartXmlNode>,
}

fn chart_invalid(message: impl Into<String>) -> WolfPptError {
    WolfPptError::InvalidInput(message.into())
}

fn chart_xml_text_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn chart_xml_unescape(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut rest = raw;
    while let Some(start) = rest.find('&') {
        out.push_str(&rest[..start]);
        let tail = &rest[start..];
        let Some(end) = tail.find(';') else {
            out.push_str(tail);
            return out;
        };
        let entity = &tail[1..end];
        let decoded = match entity {
            "amp" => Some('&'),
            "lt" => Some('<'),
            "gt" => Some('>'),
            "quot" => Some('"'),
            "apos" => Some('\''),
            _ => entity
                .strip_prefix("#x")
                .or_else(|| entity.strip_prefix("#X"))
                .and_then(|hex| u32::from_str_radix(hex, 16).ok())
                .or_else(|| entity.strip_prefix('#').and_then(|dec| dec.parse().ok()))
                .and_then(char::from_u32),
        };
        match decoded {
            Some(ch) => out.push(ch),
            None => out.push_str(&tail[..=end]),
        }
        rest = &tail[end + 1..];
    }
    out.push_str(rest);
    out
}

fn chart_rank(order: &[&str], local: &str) -> Option<usize> {
    order
        .iter()
        .position(|entry| entry.split('|').any(|name| name == local))
}

impl ChartXmlElement {
    fn new(name: String) -> Self {
        Self {
            name,
            attributes: Vec::new(),
            children: Vec::new(),
        }
    }

    fn from_start(start: &BytesStart<'_>) -> Result<Self, WolfPptError> {
        let mut element = Self::new(start.name().as_ref().to_string());
        for attribute in start.attributes() {
            let attribute = attribute.map_err(|err| WolfPptError::XmlText(err.to_string()))?;
            element.attributes.push((
                attribute.key.as_ref().to_string(),
                attribute.value.into_owned(),
            ));
        }
        Ok(element)
    }

    fn local(&self) -> &str {
        self.name
            .rsplit_once(':')
            .map_or(self.name.as_str(), |(_, local)| local)
    }

    fn qualified(&self, local: &str) -> String {
        match self.name.split_once(':') {
            Some((prefix, _)) => format!("{prefix}:{local}"),
            None => local.to_string(),
        }
    }

    fn with_val(mut self, value: &str) -> Self {
        self.set_attribute("val", value);
        self
    }

    fn with_text(mut self, value: &str) -> Self {
        self.children
            .push(ChartXmlNode::Text(chart_xml_text_escape(value)));
        self
    }

    fn push(&mut self, child: ChartXmlElement) {
        self.children.push(ChartXmlNode::Element(child));
    }

    fn elements(&self) -> impl Iterator<Item = &ChartXmlElement> {
        self.children.iter().filter_map(|node| match node {
            ChartXmlNode::Element(element) => Some(element),
            _ => None,
        })
    }

    fn elements_mut(&mut self) -> impl Iterator<Item = &mut ChartXmlElement> {
        self.children.iter_mut().filter_map(|node| match node {
            ChartXmlNode::Element(element) => Some(element),
            _ => None,
        })
    }

    fn child(&self, local: &str) -> Option<&ChartXmlElement> {
        self.elements().find(|element| element.local() == local)
    }

    fn child_mut(&mut self, local: &str) -> Option<&mut ChartXmlElement> {
        self.elements_mut().find(|element| element.local() == local)
    }

    fn attribute(&self, local: &str) -> Option<String> {
        self.attributes
            .iter()
            .find(|(name, _)| name.rsplit_once(':').map_or(name.as_str(), |(_, l)| l) == local)
            .map(|(_, value)| chart_xml_unescape(value))
    }

    fn set_attribute(&mut self, name: &str, value: &str) {
        let escaped = xml_attr(value);
        match self.attributes.iter_mut().find(|(key, _)| key == name) {
            Some((_, current)) => *current = escaped,
            None => self.attributes.push((name.to_string(), escaped)),
        }
    }

    fn child_val(&self, local: &str) -> Option<String> {
        self.child(local).and_then(|child| child.attribute("val"))
    }

    fn child_bool(&self, local: &str) -> Option<bool> {
        // CT_Boolean: an element without `val` means true.
        self.child(local).map(|child| {
            child
                .attribute("val")
                .is_none_or(|value| value == "1" || value == "true")
        })
    }

    fn child_number<T: std::str::FromStr>(&self, local: &str) -> Option<T> {
        self.child_val(local)
            .and_then(|value| value.trim().parse().ok())
    }

    fn text(&self) -> String {
        let mut text = String::new();
        for node in &self.children {
            if let ChartXmlNode::Text(raw) = node {
                text.push_str(&chart_xml_unescape(raw));
            }
        }
        text
    }

    fn insert_position(&self, local: &str, order: &[&str]) -> usize {
        let Some(rank) = chart_rank(order, local) else {
            return self.children.len();
        };
        self.children
            .iter()
            .position(|node| match node {
                ChartXmlNode::Element(element) => {
                    chart_rank(order, element.local()).is_some_and(|other| other > rank)
                }
                _ => false,
            })
            .unwrap_or(self.children.len())
    }

    fn ensure_child(&mut self, local: &str, order: &[&str]) -> &mut ChartXmlElement {
        let existing = self.children.iter().position(
            |node| matches!(node, ChartXmlNode::Element(element) if element.local() == local),
        );
        let position = match existing {
            Some(position) => position,
            None => {
                let position = self.insert_position(local, order);
                let element = ChartXmlElement::new(self.qualified(local));
                self.children
                    .insert(position, ChartXmlNode::Element(element));
                position
            }
        };
        match &mut self.children[position] {
            ChartXmlNode::Element(element) => element,
            _ => unreachable!("position selects an element"),
        }
    }

    fn set_child_val(&mut self, local: &str, order: &[&str], value: &str) {
        self.ensure_child(local, order).set_attribute("val", value);
    }

    fn remove_children(&mut self, local: &str) {
        self.children.retain(
            |node| !matches!(node, ChartXmlNode::Element(element) if element.local() == local),
        );
    }

    /// Replaces every child named like `element` with `element`, placed at
    /// the first replaced position or else its schema position.
    fn replace_child(&mut self, element: ChartXmlElement, order: &[&str]) {
        let local = element.local().to_string();
        let existing = self.children.iter().position(
            |node| matches!(node, ChartXmlNode::Element(child) if child.local() == local),
        );
        self.remove_children(&local);
        let position = existing.unwrap_or_else(|| self.insert_position(&local, order));
        self.children
            .insert(position, ChartXmlNode::Element(element));
    }

    fn write(&self, out: &mut String) {
        out.push('<');
        out.push_str(&self.name);
        for (name, value) in &self.attributes {
            out.push(' ');
            out.push_str(name);
            out.push_str("=\"");
            // A raw `"` can only come from a single-quoted source attribute.
            out.push_str(&value.replace('"', "&quot;"));
            out.push('"');
        }
        if self.children.is_empty() {
            out.push_str("/>");
            return;
        }
        out.push('>');
        for node in &self.children {
            chart_xml_write_node(node, out);
        }
        out.push_str("</");
        out.push_str(&self.name);
        out.push('>');
    }
}

fn chart_xml_write_node(node: &ChartXmlNode, out: &mut String) {
    match node {
        ChartXmlNode::Element(element) => element.write(out),
        ChartXmlNode::Text(raw) | ChartXmlNode::Markup(raw) => out.push_str(raw),
    }
}

fn chart_xml_parse(xml: &str) -> Result<ChartXmlDocument, WolfPptError> {
    let mut reader = Reader::from_str(xml);
    let mut stack: Vec<ChartXmlElement> = Vec::new();
    let mut prolog = Vec::new();
    let mut root = None;
    let mut epilog = Vec::new();
    loop {
        let node = match reader.read_event()? {
            Event::Start(start) => {
                stack.push(ChartXmlElement::from_start(&start)?);
                continue;
            }
            Event::End(_) => ChartXmlNode::Element(
                stack
                    .pop()
                    .ok_or_else(|| chart_invalid("chart XML has an unmatched end tag"))?,
            ),
            Event::Empty(start) => ChartXmlNode::Element(ChartXmlElement::from_start(&start)?),
            Event::Text(text) => ChartXmlNode::Text(String::from(&*text)),
            Event::GeneralRef(reference) => ChartXmlNode::Text(format!("&{};", &*reference)),
            Event::CData(data) => ChartXmlNode::Text(chart_xml_text_escape(&data)),
            Event::Comment(comment) => ChartXmlNode::Markup(format!("<!--{}-->", &*comment)),
            Event::Decl(declaration) => ChartXmlNode::Markup(format!("<?{}?>", &*declaration)),
            Event::PI(instruction) => ChartXmlNode::Markup(format!("<?{}?>", &*instruction)),
            Event::DocType(_) => return Err(chart_invalid("chart XML with a DTD is unsupported")),
            Event::Eof => break,
        };
        match (stack.last_mut(), node) {
            (Some(parent), node) => parent.children.push(node),
            (None, ChartXmlNode::Element(element)) if root.is_none() => root = Some(element),
            (None, ChartXmlNode::Element(_)) => {
                return Err(chart_invalid("chart XML has more than one root element"))
            }
            (None, node) if root.is_none() => prolog.push(node),
            (None, node) => epilog.push(node),
        }
    }
    if !stack.is_empty() {
        return Err(chart_invalid("chart XML has an unclosed element"));
    }
    let root = root.ok_or_else(|| chart_invalid("chart XML has no root element"))?;
    Ok(ChartXmlDocument {
        prolog,
        root,
        epilog,
    })
}

fn chart_xml_serialize(document: &ChartXmlDocument) -> String {
    let mut out = String::new();
    for node in &document.prolog {
        chart_xml_write_node(node, &mut out);
    }
    document.root.write(&mut out);
    for node in &document.epilog {
        chart_xml_write_node(node, &mut out);
    }
    out
}

// ---------------------------------------------------------------------------
// Schema orders (ECMA-376 Part 1, DrawingML charts)
// ---------------------------------------------------------------------------

const CHART_ORDER: &[&str] = &[
    "title",
    "autoTitleDeleted",
    "pivotFmts",
    "view3D",
    "floor",
    "sideWall",
    "backWall",
    "plotArea",
    "legend",
    "plotVisOnly",
    "dispBlanksAs",
    "showDLblsOverMax",
    "extLst",
];
const CHART_LEGEND_ORDER: &[&str] = &[
    "legendPos",
    "legendEntry",
    "layout",
    "overlay",
    "spPr",
    "txPr",
    "extLst",
];
const CHART_LAYOUT_ORDER: &[&str] = &["manualLayout", "extLst"];
const CHART_MANUAL_LAYOUT_ORDER: &[&str] = &[
    "layoutTarget",
    "xMode",
    "yMode",
    "wMode",
    "hMode",
    "x",
    "y",
    "w",
    "h",
    "extLst",
];
// Shared prefix of CT_CatAx/CT_ValAx/CT_DateAx/CT_SerAx, then a merged tail
// that is order-consistent with every axis type.
const CHART_AXIS_ORDER: &[&str] = &[
    "axId",
    "scaling",
    "delete",
    "axPos",
    "majorGridlines",
    "minorGridlines",
    "title",
    "numFmt",
    "majorTickMark",
    "minorTickMark",
    "tickLblPos",
    "spPr",
    "txPr",
    "crossAx",
    "crosses|crossesAt",
    "crossBetween",
    "auto",
    "lblAlgn",
    "lblOffset",
    "baseTimeUnit",
    "majorUnit",
    "majorTimeUnit",
    "minorUnit",
    "minorTimeUnit",
    "tickLblSkip",
    "tickMarkSkip",
    "noMultiLvlLbl",
    "dispUnits",
    "extLst",
];
const CHART_SCALING_ORDER: &[&str] = &["logBase", "orientation", "max", "min", "extLst"];
// Merged order of the chart-type elements this module edits.
const CHART_PLOT_ORDER: &[&str] = &[
    "barDir",
    "radarStyle",
    "scatterStyle",
    "grouping",
    "varyColors",
    "ser",
    "dLbls",
    "dropLines",
    "hiLowLines",
    "upDownBars",
    "marker",
    "smooth",
    "gapWidth",
    "gapDepth",
    "overlap",
    "shape",
    "serLines",
    "firstSliceAng",
    "holeSize",
    "axId",
    "extLst",
];
// Merged order of the series types (CT_BarSer, CT_LineSer, CT_PieSer, ...).
const CHART_SERIES_ORDER: &[&str] = &[
    "idx",
    "order",
    "tx",
    "spPr",
    "invertIfNegative",
    "pictureOptions",
    "marker",
    "explosion",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "cat",
    "val",
    "xVal",
    "yVal",
    "shape",
    "smooth",
    "bubbleSize",
    "bubble3D",
    "extLst",
];
const CHART_AXIS_KINDS: &[&str] = &["catAx", "valAx", "dateAx", "serAx"];
const CHART_BAR_PLOTS: &[&str] = &["barChart", "bar3DChart"];
const CHART_GROUPED_PLOTS: &[&str] = &["lineChart", "line3DChart", "areaChart", "area3DChart"];
const CHART_PIE_PLOTS: &[&str] = &["pieChart", "pie3DChart", "doughnutChart", "ofPieChart"];
const CHART_XY_PLOTS: &[&str] = &["scatterChart", "bubbleChart"];

fn chart_is_plot(element: &ChartXmlElement) -> bool {
    let local = element.local();
    local.ends_with("Chart") && local != "chart"
}

fn chart_bool_token(value: bool) -> &'static str {
    if value {
        "1"
    } else {
        "0"
    }
}

fn chart_number_token(value: f64) -> String {
    if value.fract() == 0.0 && value.abs() < 1e15 {
        format!("{}", value as i64)
    } else {
        format!("{value}")
    }
}

// ---------------------------------------------------------------------------
// Package access
// ---------------------------------------------------------------------------

fn chart_relationship_ids_in_slide(xml: &str) -> Result<Vec<String>, WolfPptError> {
    let mut reader = Reader::from_str(xml);
    let mut ids = Vec::new();
    loop {
        match reader.read_event()? {
            Event::Start(event) | Event::Empty(event)
                if local_name(event.name().as_ref().as_bytes()) == b"chart" =>
            {
                for attribute in event.attributes().flatten() {
                    if local_name(attribute.key.as_ref().as_bytes()) == b"id" {
                        ids.push(chart_xml_unescape(&attribute.value));
                    }
                }
            }
            Event::Eof => break,
            _ => {}
        }
    }
    Ok(ids)
}

/// Chart frames of a slide in document order: (relationship id, chart part).
fn slide_chart_references<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_part: &str,
) -> Result<Vec<(String, String)>, WolfPptError> {
    let slide_xml = read_archive_text(archive, slide_part)?
        .ok_or_else(|| chart_invalid(format!("slide part {slide_part} was not found")))?;
    let relationships = read_relationships(archive, slide_part)?;
    Ok(chart_relationship_ids_in_slide(&slide_xml)?
        .into_iter()
        .filter_map(|id| {
            relationships
                .iter()
                .find(|relationship| {
                    relationship.id == id
                        && relationship.relationship_type.ends_with("/chart")
                        && relationship.target_mode.as_deref() != Some("External")
                })
                .map(|relationship| (id.clone(), resolve_target(slide_part, &relationship.target)))
        })
        .collect())
}

fn chart_embedded_workbook_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    chart_part: &str,
) -> Result<Option<String>, WolfPptError> {
    Ok(read_relationships(archive, chart_part)?
        .into_iter()
        .find(|relationship| {
            relationship.relationship_type.ends_with("/package")
                && relationship.target_mode.as_deref() != Some("External")
        })
        .map(|relationship| resolve_target(chart_part, &relationship.target)))
}

/// The first worksheet name of an embedded SpreadsheetML package.
fn chart_workbook_first_sheet(payload: &[u8]) -> Option<String> {
    let mut workbook = ZipArchive::new(Cursor::new(payload)).ok()?;
    let xml = read_archive_text(&mut workbook, "xl/workbook.xml").ok()??;
    let mut reader = Reader::from_str(&xml);
    loop {
        match reader.read_event().ok()? {
            Event::Start(event) | Event::Empty(event)
                if local_name(event.name().as_ref().as_bytes()) == b"sheet" =>
            {
                return event
                    .attributes()
                    .flatten()
                    .find(|attribute| attribute.key.as_ref() == "name")
                    .map(|attribute| chart_xml_unescape(&attribute.value));
            }
            Event::Eof => return None,
            _ => {}
        }
    }
}

/// The embedded workbook part and its first sheet name, when both exist.
fn chart_sheet_name<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    chart_part: &str,
) -> Result<Option<(String, String)>, WolfPptError> {
    let Some(workbook_part) = chart_embedded_workbook_part(archive, chart_part)? else {
        return Ok(None);
    };
    let Some(payload) = read_archive_bytes(archive, &workbook_part)? else {
        return Ok(None);
    };
    Ok(chart_workbook_first_sheet(&payload).map(|sheet| (workbook_part, sheet)))
}

fn chart_column_letters(column: u32) -> String {
    let mut column = u64::from(column) + 1;
    let mut letters = Vec::new();
    while column > 0 {
        let remainder = ((column - 1) % 26) as u8;
        letters.push(char::from(b'A' + remainder));
        column = (column - 1) / 26;
    }
    letters.iter().rev().collect()
}

fn chart_sheet_prefix(sheet: &str) -> String {
    let plain = sheet
        .chars()
        .next()
        .is_some_and(|first| first.is_ascii_alphabetic() || first == '_')
        && sheet
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '.');
    // A plain name that reads as an A1 reference (letters then digits) still
    // needs quotes.
    let letters = sheet.trim_end_matches(|ch: char| ch.is_ascii_digit());
    let cell_like = letters.len() < sheet.len()
        && letters.len() <= 3
        && letters.chars().all(|ch| ch.is_ascii_alphabetic());
    if plain && !cell_like {
        format!("{sheet}!")
    } else {
        format!("'{}'!", sheet.replace('\'', "''"))
    }
}

fn chart_cell(row: u32, column: u32) -> String {
    format!("${}${}", chart_column_letters(column), u64::from(row) + 1)
}

/// `Sheet!$A$2:$A$4`, or `Sheet!$A$2` for a single cell, as POI formats a
/// chart range.
fn chart_range_formula(sheet: &str, range: &ChartCellRange) -> Result<String, WolfPptError> {
    if range.first_row > range.last_row || range.first_column > range.last_column {
        return Err(chart_invalid(
            "range first_row/first_column must not exceed last_row/last_column",
        ));
    }
    let first = chart_cell(range.first_row, range.first_column);
    let last = chart_cell(range.last_row, range.last_column);
    Ok(if first == last {
        format!("{}{first}", chart_sheet_prefix(sheet))
    } else {
        format!("{}{first}:{last}", chart_sheet_prefix(sheet))
    })
}

// ---------------------------------------------------------------------------
// Authoring entry points
// ---------------------------------------------------------------------------

fn chart_graphic_frame_xml(
    shape_id: u64,
    relationship_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> String {
    format!(
        concat!(
            r#"<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{id}" name="Chart {id}"/>"#,
            r#"<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>"#,
            r#"<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm>"#,
            r#"<a:graphic><a:graphicData uri="{ns}"><c:chart xmlns:c="{ns}" "#,
            r#"xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" "#,
            r#"r:id="{rid}"/></a:graphicData></a:graphic></p:graphicFrame>"#
        ),
        id = shape_id,
        x = x_emu,
        y = y_emu,
        cx = cx_emu,
        cy = cy_emu,
        ns = CHART_NAMESPACE,
        rid = xml_attr(relationship_id),
    )
}

fn empty_chart_part_xml() -> String {
    format!(
        concat!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n",
            r#"<c:chartSpace xmlns:c="{ns}" "#,
            r#"xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" "#,
            r#"xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">"#,
            r#"<c:roundedCorners val="0"/><c:chart><c:autoTitleDeleted val="0"/>"#,
            r#"<c:plotArea><c:layout/></c:plotArea><c:plotVisOnly val="1"/>"#,
            r#"<c:dispBlanksAs val="gap"/></c:chart></c:chartSpace>"#
        ),
        ns = CHART_NAMESPACE,
    )
}

/// Adds an empty chart part (`ppt/charts/chartN.xml`, no plots and no
/// embedded workbook) and a graphic frame referencing it to a slide.
pub fn add_slide_chart(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<ChartAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(chart_invalid(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let mut names = std::collections::HashSet::new();
    for index in 0..archive.len() {
        names.insert(archive.by_index(index)?.name()?.into_owned());
    }
    let chart_part = next_free_numbered_part(&mut names, "ppt/charts/chart1.xml");
    let rels_part = relationship_part_name(&slide_part);
    let rels_xml =
        read_archive_text(&mut archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let relationship_id = next_relationship_id(rels_xml.as_bytes());
    let Some(end) = rels_xml.rfind("</Relationships>") else {
        return Err(chart_invalid(
            "relationships part is missing </Relationships>",
        ));
    };
    let target = make_relative_target(&slide_part, &chart_part);
    let rels_xml = format!(
        r#"{}<Relationship Id="{}" Type="{CHART_RELATIONSHIP_TYPE}" Target="{}"/>{}"#,
        &rels_xml[..end],
        xml_attr(&relationship_id),
        xml_attr(&target),
        &rels_xml[end..]
    );
    let content_types_xml = read_archive_text(&mut archive, "[Content_Types].xml")?
        .ok_or_else(|| chart_invalid("[Content_Types].xml was not found"))?;
    let content_types_xml = ensure_content_type_override(
        &content_types_xml,
        &format!("/{chart_part}"),
        CHART_CONTENT_TYPE,
    )?;
    let slide_xml = read_archive_text(&mut archive, &slide_part)?
        .ok_or_else(|| chart_invalid(format!("slide part {slide_part} was not found")))?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let Some(tree_end) = slide_xml.rfind("</p:spTree>") else {
        return Err(chart_invalid("slide XML is missing </p:spTree>"));
    };
    let slide_xml = format!(
        "{}{}{}",
        &slide_xml[..tree_end],
        chart_graphic_frame_xml(shape_id, &relationship_id, x_emu, y_emu, cx_emu, cy_emu),
        &slide_xml[tree_end..]
    );

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
    let mut part_count = 0;
    let mut has_vba = false;
    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name()?.into_owned();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        let replacement = if name == slide_part {
            Some(slide_xml.as_bytes())
        } else if name == rels_part {
            wrote_rels = true;
            Some(rels_xml.as_bytes())
        } else if name == "[Content_Types].xml" {
            Some(content_types_xml.as_bytes())
        } else {
            None
        };
        match replacement {
            Some(payload) => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(payload), &mut writer)?;
            }
            None => writer.raw_copy_file(file)?,
        }
    }
    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    update_package_facts(&chart_part, &mut part_count, &mut has_vba);
    writer.start_file(chart_part.clone(), options)?;
    std::io::copy(
        &mut Cursor::new(empty_chart_part_xml().as_bytes()),
        &mut writer,
    )?;
    writer.finish()?;

    Ok(ChartAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        relationship_id,
        chart_part,
        content_type: CHART_CONTENT_TYPE.to_string(),
        shape_id,
        part_count,
        has_vba,
    })
}

/// Rewrites chart `chart_index` of slide `slide_index` with `edit`, which
/// receives the chart root and, when `needs_sheet`, the embedded workbook's
/// first sheet name.
fn edit_slide_chart(
    input_path: &Path,
    output_path: &Path,
    slide_index: usize,
    chart_index: usize,
    needs_sheet: bool,
    edit: impl FnOnce(&mut ChartXmlElement, Option<&str>) -> Result<(), WolfPptError>,
) -> Result<ChartEditSummary, WolfPptError> {
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(chart_invalid(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let charts = slide_chart_references(&mut archive, &slide_part)?;
    let Some((relationship_id, chart_part)) = charts.into_iter().nth(chart_index) else {
        return Err(chart_invalid(format!(
            "chart index {chart_index} was not found on slide {slide_index}"
        )));
    };
    let xml = read_archive_text(&mut archive, &chart_part)?
        .ok_or_else(|| chart_invalid(format!("chart part {chart_part} was not found")))?;
    let mut document = chart_xml_parse(&xml)?;
    let sheet = if needs_sheet {
        let sheet = chart_sheet_name(&mut archive, &chart_part)?.ok_or_else(|| {
            chart_invalid(format!(
                "chart part {chart_part} has no embedded workbook sheet for cell references"
            ))
        })?;
        Some(sheet.1)
    } else {
        None
    };
    edit(&mut document.root, sheet.as_deref())?;
    let payload = chart_xml_serialize(&document);
    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &chart_part,
        payload.as_bytes(),
    )?;
    Ok(ChartEditSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        chart_index,
        chart_part,
        relationship_id,
        part_count,
        has_vba,
        embedded_workbook_updated: None,
    })
}

fn chart_element_mut(root: &mut ChartXmlElement) -> Result<&mut ChartXmlElement, WolfPptError> {
    root.child_mut("chart")
        .ok_or_else(|| chart_invalid("chart part has no c:chart element"))
}

fn chart_plot_area_mut(root: &mut ChartXmlElement) -> Result<&mut ChartXmlElement, WolfPptError> {
    chart_element_mut(root)?
        .child_mut("plotArea")
        .ok_or_else(|| chart_invalid("chart part has no c:plotArea element"))
}

fn chart_plot_mut(
    root: &mut ChartXmlElement,
    plot_index: usize,
) -> Result<&mut ChartXmlElement, WolfPptError> {
    chart_plot_area_mut(root)?
        .elements_mut()
        .filter(|element| chart_is_plot(element))
        .nth(plot_index)
        .ok_or_else(|| chart_invalid(format!("plot index {plot_index} was not found")))
}

fn chart_require_plot(kind: &str, allowed: &[&str], field: &str) -> Result<(), WolfPptError> {
    if allowed.contains(&kind) {
        Ok(())
    } else {
        Err(chart_invalid(format!(
            "{field} does not apply to a {kind} plot (applies to {})",
            allowed.join(", ")
        )))
    }
}

pub fn set_slide_chart_legend(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &ChartLegendEdit,
) -> Result<ChartEditSummary, WolfPptError> {
    edit_slide_chart(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.chart_index,
        false,
        |root, _| {
            let chart = chart_element_mut(root)?;
            if chart.child("legend").is_none() {
                let legend = chart.ensure_child("legend", CHART_ORDER);
                legend.set_child_val("legendPos", CHART_LEGEND_ORDER, "r");
                legend.set_child_val("overlay", CHART_LEGEND_ORDER, "0");
            }
            let legend = chart.ensure_child("legend", CHART_ORDER);
            if let Some(position) = edit.position {
                legend.set_child_val("legendPos", CHART_LEGEND_ORDER, position.token());
            }
            if let Some(overlay) = edit.overlay {
                legend.set_child_val("overlay", CHART_LEGEND_ORDER, chart_bool_token(overlay));
            }
            let Some(layout) = &edit.manual_layout else {
                return Ok(());
            };
            let manual = legend
                .ensure_child("layout", CHART_LEGEND_ORDER)
                .ensure_child("manualLayout", CHART_LAYOUT_ORDER);
            let order = CHART_MANUAL_LAYOUT_ORDER;
            if let Some(target) = layout.target {
                manual.set_child_val("layoutTarget", order, target.token());
            }
            let modes = [
                ("xMode", layout.x_mode),
                ("yMode", layout.y_mode),
                ("wMode", layout.width_mode),
                ("hMode", layout.height_mode),
            ];
            for (local, mode) in modes {
                if let Some(mode) = mode {
                    manual.set_child_val(local, order, mode.token());
                }
            }
            let values = [
                ("x", layout.x),
                ("y", layout.y),
                ("w", layout.width),
                ("h", layout.height),
            ];
            for (local, value) in values {
                if let Some(value) = value {
                    manual.set_child_val(local, order, &chart_number_token(value));
                }
            }
            Ok(())
        },
    )
}

pub fn set_slide_chart_axis(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &ChartAxisEdit,
) -> Result<ChartEditSummary, WolfPptError> {
    if let Some(log_base) = edit.log_base {
        if !(2.0..=1000.0).contains(&log_base) {
            return Err(chart_invalid(format!(
                "log_base {log_base} is outside the ST_LogBase range 2 to 1000"
            )));
        }
    }
    if edit.crosses.is_some() && edit.crosses_at.is_some() {
        return Err(chart_invalid(
            "crosses and crosses_at are mutually exclusive",
        ));
    }
    edit_slide_chart(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.chart_index,
        false,
        |root, _| {
            let axis_id = edit.axis_id;
            let axis = chart_plot_area_mut(root)?
                .elements_mut()
                .find(|element| {
                    CHART_AXIS_KINDS.contains(&element.local())
                        && element.child_number::<i64>("axId") == Some(axis_id)
                })
                .ok_or_else(|| chart_invalid(format!("axis id {axis_id} was not found")))?;
            if edit.cross_between.is_some() && axis.local() != "valAx" {
                return Err(chart_invalid(format!(
                    "cross_between applies to value axes; axis {axis_id} is a {}",
                    axis.local()
                )));
            }
            let order = CHART_AXIS_ORDER;
            let scaled = [
                ("logBase", edit.log_base),
                ("max", edit.maximum),
                ("min", edit.minimum),
            ];
            if edit.orientation.is_some() || scaled.iter().any(|(_, value)| value.is_some()) {
                let scaling = axis.ensure_child("scaling", order);
                for (local, value) in scaled {
                    if let Some(value) = value {
                        scaling.set_child_val(
                            local,
                            CHART_SCALING_ORDER,
                            &chart_number_token(value),
                        );
                    }
                }
                if let Some(orientation) = edit.orientation {
                    scaling.set_child_val("orientation", CHART_SCALING_ORDER, orientation.token());
                }
            }
            if let Some(visible) = edit.visible {
                axis.set_child_val("delete", order, chart_bool_token(!visible));
            }
            if let Some(position) = edit.position {
                axis.set_child_val("axPos", order, position.token());
            }
            if let Some(format) = &edit.number_format {
                let number_format = axis.ensure_child("numFmt", order);
                number_format.set_attribute("formatCode", &format.format_code);
                match format.source_linked {
                    Some(linked) => {
                        number_format.set_attribute("sourceLinked", chart_bool_token(linked))
                    }
                    None if number_format.attribute("sourceLinked").is_none() => {
                        number_format.set_attribute("sourceLinked", "0")
                    }
                    None => {}
                }
            }
            if let Some(mark) = edit.major_tick_mark {
                axis.set_child_val("majorTickMark", order, mark.token());
            }
            if let Some(mark) = edit.minor_tick_mark {
                axis.set_child_val("minorTickMark", order, mark.token());
            }
            if let Some(crosses) = edit.crosses {
                axis.remove_children("crossesAt");
                axis.set_child_val("crosses", order, crosses.token());
            }
            if let Some(crosses_at) = edit.crosses_at {
                axis.remove_children("crosses");
                axis.set_child_val("crossesAt", order, &chart_number_token(crosses_at));
            }
            if let Some(cross_between) = edit.cross_between {
                axis.set_child_val("crossBetween", order, cross_between.token());
            }
            Ok(())
        },
    )
}

pub fn set_slide_chart_plot(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &ChartPlotEdit,
) -> Result<ChartEditSummary, WolfPptError> {
    if edit.gap_width.is_some_and(|gap| gap > 500) {
        return Err(chart_invalid("gap_width must be 0 to 500 (ST_GapAmount)"));
    }
    edit_slide_chart(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.chart_index,
        false,
        |root, _| {
            let plot = chart_plot_mut(root, edit.plot_index)?;
            let kind = plot.local().to_string();
            let order = CHART_PLOT_ORDER;
            if let Some(direction) = edit.bar_direction {
                chart_require_plot(&kind, CHART_BAR_PLOTS, "bar_direction")?;
                plot.set_child_val("barDir", order, direction.token());
            }
            if let Some(grouping) = edit.bar_grouping {
                chart_require_plot(&kind, CHART_BAR_PLOTS, "bar_grouping")?;
                plot.set_child_val("grouping", order, grouping.token());
            }
            if let Some(gap) = edit.gap_width {
                chart_require_plot(&kind, CHART_BAR_PLOTS, "gap_width")?;
                plot.set_child_val("gapWidth", order, &gap.to_string());
            }
            if let Some(grouping) = edit.grouping {
                chart_require_plot(&kind, CHART_GROUPED_PLOTS, "grouping")?;
                plot.set_child_val("grouping", order, grouping.token());
            }
            if let Some(style) = edit.radar_style {
                chart_require_plot(&kind, &["radarChart"], "radar_style")?;
                plot.set_child_val("radarStyle", order, style.token());
            }
            if let Some(style) = edit.scatter_style {
                chart_require_plot(&kind, &["scatterChart"], "scatter_style")?;
                plot.set_child_val("scatterStyle", order, style.token());
            }
            Ok(())
        },
    )
}

fn chart_points(owner: &ChartXmlElement, cache: &str, values: &[String]) -> ChartXmlElement {
    let mut element = ChartXmlElement::new(owner.qualified(cache));
    element
        .push(ChartXmlElement::new(owner.qualified("ptCount")).with_val(&values.len().to_string()));
    for (index, value) in values.iter().enumerate() {
        let mut point = ChartXmlElement::new(owner.qualified("pt"));
        point.set_attribute("idx", &index.to_string());
        point.push(ChartXmlElement::new(owner.qualified("v")).with_text(value));
        element.push(point);
    }
    element
}

/// Builds `local` holding `c:strRef`/`c:numRef` (with a formula) or
/// `c:strLit`/`c:numLit`.
fn chart_data_source(
    owner: &ChartXmlElement,
    local: &str,
    numeric: bool,
    values: &[String],
    formula: Option<String>,
    format_code: Option<&str>,
) -> ChartXmlElement {
    let cache = match (numeric, formula.is_some()) {
        (true, true) => "numCache",
        (false, true) => "strCache",
        (true, false) => "numLit",
        (false, false) => "strLit",
    };
    let mut cache = chart_points(owner, cache, values);
    if let (true, Some(code)) = (numeric, format_code) {
        let format = ChartXmlElement::new(owner.qualified("formatCode")).with_text(code);
        cache.children.insert(0, ChartXmlNode::Element(format));
    }
    let mut data = ChartXmlElement::new(owner.qualified(local));
    match formula {
        Some(formula) => {
            let reference = if numeric { "numRef" } else { "strRef" };
            let mut reference = ChartXmlElement::new(owner.qualified(reference));
            reference.push(ChartXmlElement::new(owner.qualified("f")).with_text(&formula));
            reference.push(cache);
            data.push(reference);
        }
        None => data.push(cache),
    }
    data
}

fn chart_range_values(
    sheet: Option<&str>,
    range: Option<&ChartCellRange>,
    count: usize,
) -> Result<Option<String>, WolfPptError> {
    let Some(range) = range else {
        return Ok(None);
    };
    let sheet = sheet.ok_or_else(|| chart_invalid("cell references need an embedded workbook"))?;
    let formula = chart_range_formula(sheet, range)?;
    let cells = (u64::from(range.last_row - range.first_row) + 1)
        * (u64::from(range.last_column - range.first_column) + 1);
    if cells != count as u64 {
        return Err(chart_invalid(format!(
            "range covers {cells} cells but {count} values were given"
        )));
    }
    Ok(Some(formula))
}

pub fn set_slide_chart_series(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &ChartSeriesEdit,
) -> Result<ChartEditSummary, WolfPptError> {
    let needs_sheet = edit
        .title
        .as_ref()
        .is_some_and(|title| title.reference.is_some())
        || edit
            .categories
            .as_ref()
            .is_some_and(|data| data.range.is_some())
        || edit
            .values
            .as_ref()
            .is_some_and(|data| data.range.is_some());
    let mut summary = edit_slide_chart(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.chart_index,
        needs_sheet,
        |root, sheet| {
            let plot = chart_plot_mut(root, edit.plot_index)?;
            let kind = plot.local().to_string();
            let xy = CHART_XY_PLOTS.contains(&kind.as_str());
            let series_index = edit.series_index;
            let series = plot
                .elements_mut()
                .filter(|element| element.local() == "ser")
                .nth(series_index)
                .ok_or_else(|| {
                    chart_invalid(format!("series index {series_index} was not found"))
                })?;
            let order = CHART_SERIES_ORDER;
            if let Some(explosion) = edit.explosion {
                chart_require_plot(&kind, CHART_PIE_PLOTS, "explosion")?;
                series.set_child_val("explosion", order, &explosion.to_string());
            }
            if let Some(title) = &edit.title {
                let mut tx = ChartXmlElement::new(series.qualified("tx"));
                match (title.reference, sheet) {
                    (Some(cell), Some(sheet)) => {
                        let formula = format!(
                            "{}{}",
                            chart_sheet_prefix(sheet),
                            chart_cell(cell.row, cell.column)
                        );
                        let mut reference = ChartXmlElement::new(series.qualified("strRef"));
                        reference
                            .push(ChartXmlElement::new(series.qualified("f")).with_text(&formula));
                        reference.push(chart_points(
                            series,
                            "strCache",
                            std::slice::from_ref(&title.text),
                        ));
                        tx.push(reference);
                    }
                    _ => {
                        tx.push(ChartXmlElement::new(series.qualified("v")).with_text(&title.text))
                    }
                }
                series.replace_child(tx, order);
            }
            if let Some(categories) = &edit.categories {
                let numeric = !categories.values.is_empty()
                    && categories
                        .values
                        .iter()
                        .all(|value| matches!(value, ChartPointValue::Number(_)));
                let values: Vec<String> = categories
                    .values
                    .iter()
                    .map(|value| match value {
                        ChartPointValue::Number(number) => chart_number_token(*number),
                        ChartPointValue::Text(text) => text.clone(),
                    })
                    .collect();
                let formula = chart_range_values(sheet, categories.range.as_ref(), values.len())?;
                let local = if xy { "xVal" } else { "cat" };
                let data = chart_data_source(series, local, numeric, &values, formula, None);
                series.replace_child(data, order);
            }
            if let Some(data) = &edit.values {
                let values: Vec<String> = data
                    .values
                    .iter()
                    .map(|value| chart_number_token(*value))
                    .collect();
                let formula = chart_range_values(sheet, data.range.as_ref(), values.len())?;
                let local = if xy { "yVal" } else { "val" };
                let format_code = data.format_code.as_deref();
                let source = chart_data_source(series, local, true, &values, formula, format_code);
                series.replace_child(source, order);
            }
            Ok(())
        },
    )?;
    summary.embedded_workbook_updated = Some(false);
    Ok(summary)
}
