// Table structure authoring: empty tables, row append and height, cell
// append, cell text, text direction, vertical alignment, borders, and row
// merges, plus the structured table and table-style catalog readback behind
// the FFI `table_structure` and `table_styles` queries. Values are reported as
// stored, with null where the element or attribute is absent; text direction,
// vertical alignment, and the table style are also reported resolved.

/// A table cell's text direction (`a:tcPr/@vert`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TableTextDirection {
    Horizontal,
    Vertical,
    #[serde(rename = "vertical_270")]
    Vertical270,
    Stacked,
}

impl TableTextDirection {
    fn token(self) -> &'static str {
        match self {
            Self::Horizontal => "horz",
            Self::Vertical => "vert",
            Self::Vertical270 => "vert270",
            Self::Stacked => "wordArtVert",
        }
    }
}

/// A table cell's vertical text anchor (`a:tcPr/@anchor`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TableVerticalAlignment {
    Top,
    Middle,
    Bottom,
    Justified,
    Distributed,
}

impl TableVerticalAlignment {
    fn token(self) -> &'static str {
        match self {
            Self::Top => "t",
            Self::Middle => "ctr",
            Self::Bottom => "b",
            Self::Justified => "just",
            Self::Distributed => "dist",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TableBorderEdge {
    Left,
    Right,
    Top,
    Bottom,
}

impl TableBorderEdge {
    fn local(self) -> &'static str {
        match self {
            Self::Left => "lnL",
            Self::Right => "lnR",
            Self::Top => "lnT",
            Self::Bottom => "lnB",
        }
    }
}

/// One cell edge. `width_emu` sets `a:ln/@w` and keeps the fill; a `dash`
/// or `color` first gives the edge a visible solid line (removes `a:noFill`
/// and adds a solid dash, single compound, centre alignment, flat cap, round
/// join, and plain line ends where absent), then sets the dash or replaces
/// the line fill with the solid colour.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TableBorderEdit {
    pub edge: TableBorderEdge,
    #[serde(default)]
    pub width_emu: Option<u64>,
    #[serde(default)]
    pub dash: Option<StyleLineDash>,
    #[serde(default)]
    pub color: Option<StyleColor>,
}

/// Appends an empty row (no cells) to table `shape_id` on slide
/// `slide_index`; the height defaults to 20 pt.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TableRowAdd {
    pub slide_index: usize,
    pub shape_id: u64,
    #[serde(default)]
    pub height_emu: Option<u64>,
}

/// Sets the height of row `row_index`.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TableRowEdit {
    pub slide_index: usize,
    pub shape_id: u64,
    pub row_index: usize,
    pub height_emu: u64,
}

/// Appends a cell to row `row_index`: no text body unless `text` is given,
/// and four `a:noFill` borders. When the row then has more cells than the
/// grid has columns, the grid gains a 100 pt column.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TableCellAdd {
    pub slide_index: usize,
    pub shape_id: u64,
    pub row_index: usize,
    #[serde(default)]
    pub text: Option<String>,
}

/// Edits cell `column_index` (zero-based among the row's `a:tc` elements) of
/// row `row_index`. Absent fields stay untouched; `text` replaces the cell's
/// paragraphs (one per line); a null `text_direction` or
/// `vertical_alignment` removes the attribute. Borders apply in order.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TableCellEdit {
    pub slide_index: usize,
    pub shape_id: u64,
    pub row_index: usize,
    pub column_index: usize,
    #[serde(default)]
    pub text: Option<String>,
    #[serde(default, deserialize_with = "style_tri")]
    pub text_direction: Option<Option<TableTextDirection>>,
    #[serde(default, deserialize_with = "style_tri")]
    pub vertical_alignment: Option<Option<TableVerticalAlignment>>,
    #[serde(default)]
    pub borders: Vec<TableBorderEdit>,
}

/// Merges cells `first_column..=last_column` of row `row_index`: the first
/// cell spans them (`gridSpan`) and the others become `hMerge` cells. Cell
/// text is untouched. At least two cells are required.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TableCellMerge {
    pub slide_index: usize,
    pub shape_id: u64,
    pub row_index: usize,
    pub first_column: usize,
    pub last_column: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct TableStructureEditSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub shape_id: u64,
    pub rows: usize,
    pub columns: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct TableStyleSummary {
    pub style_id: Option<String>,
    pub name: Option<String>,
}

/// The presentation's table style catalog (`a:tblStyleLst`). `part` is null
/// when the package has no table styles part.
#[derive(Debug, Clone, Default, PartialEq, Eq, serde::Serialize)]
pub struct TableStylesSummary {
    pub part: Option<String>,
    pub default_style_id: Option<String>,
    pub styles: Vec<TableStyleSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct TableCellBordersSummary {
    pub left: Option<StyleLineSummary>,
    pub right: Option<StyleLineSummary>,
    pub top: Option<StyleLineSummary>,
    pub bottom: Option<StyleLineSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct TableCellSummary {
    /// Paragraph texts joined by newlines; empty without a text body.
    pub text: String,
    pub has_text_body: bool,
    pub paragraph_count: usize,
    pub grid_span: u64,
    pub row_span: u64,
    pub h_merge: bool,
    pub v_merge: bool,
    /// `h_merge` or `v_merge`: the cell is covered by another cell's span.
    pub merged: bool,
    /// `horizontal` (the default), `vertical`, `vertical_270`, or `stacked`.
    pub text_direction: &'static str,
    pub vert: Option<String>,
    /// `top` (the default), `middle`, `bottom`, `justified`, or `distributed`.
    pub vertical_alignment: &'static str,
    pub anchor: Option<String>,
    pub borders: TableCellBordersSummary,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct TableRowSummary {
    pub height_emu: Option<i64>,
    pub cells: Vec<TableCellSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct TableStructureSummary {
    /// Zero-based among the slide's tables in document order.
    pub table_index: usize,
    pub shape_id: Option<u64>,
    pub name: Option<String>,
    pub x: Option<i64>,
    pub y: Option<i64>,
    pub cx: Option<i64>,
    pub cy: Option<i64>,
    pub style_id: Option<String>,
    /// The catalog entry `style_id` names; null when absent from the catalog.
    pub style: Option<TableStyleSummary>,
    pub first_row: bool,
    pub first_column: bool,
    pub last_row: bool,
    pub last_column: bool,
    pub band_row: bool,
    pub band_column: bool,
    pub column_widths_emu: Vec<Option<i64>>,
    pub rows: Vec<TableRowSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct SlideTablesSummary {
    pub index: usize,
    pub part: String,
    pub tables: Vec<TableStructureSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct TableStructuresSummary {
    pub slides: Vec<SlideTablesSummary>,
    pub table_styles: TableStylesSummary,
}

const TABLE_GRAPHIC_DATA_URI: &str = "http://schemas.openxmlformats.org/drawingml/2006/table";
const TABLE_DRAWINGML_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/main";
const TABLE_TBL_ORDER: &[&str] = &["tblPr", "tblGrid", "tr", "extLst"];
const TABLE_TR_ORDER: &[&str] = &["tc", "extLst"];
const TABLE_TC_ORDER: &[&str] = &["txBody", "tcPr", "extLst"];
const TABLE_TX_BODY_ORDER: &[&str] = &["bodyPr", "lstStyle", "p"];
const TABLE_TC_PR_ORDER: &[&str] = &[
    "lnL",
    "lnR",
    "lnT",
    "lnB",
    "lnTlToBr",
    "lnBlToTr",
    "cell3D",
    "noFill|solidFill|gradFill|blipFill|pattFill|grpFill",
    "headers",
    "extLst",
];
const TABLE_SP_TREE_ORDER: &[&str] = &[
    "nvGrpSpPr",
    "grpSpPr",
    "sp|grpSp|graphicFrame|cxnSp|pic|contentPart",
    "extLst",
];
const TABLE_LINE_FILLS: &[&str] = &["noFill", "solidFill", "gradFill", "pattFill"];
/// Row height of an appended row: 20 pt, as POI `XSLFTable.addRow`.
const TABLE_DEFAULT_ROW_HEIGHT_EMU: u64 = 254_000;
/// Width of a grid column added for an appended cell: 100 pt.
const TABLE_DEFAULT_COLUMN_WIDTH_EMU: u64 = 1_270_000;

fn table_of(frame: &ChartXmlElement) -> Option<&ChartXmlElement> {
    if frame.local() != "graphicFrame" {
        return None;
    }
    frame.child("graphic")?.child("graphicData")?.child("tbl")
}

fn table_of_mut(frame: &mut ChartXmlElement) -> Option<&mut ChartXmlElement> {
    if frame.local() != "graphicFrame" {
        return None;
    }
    frame
        .child_mut("graphic")?
        .child_mut("graphicData")?
        .child_mut("tbl")
}

/// Table graphic frames at any group depth, in document order.
fn table_frames<'e>(container: &'e ChartXmlElement, frames: &mut Vec<&'e ChartXmlElement>) {
    for element in container.elements() {
        if table_of(element).is_some() {
            frames.push(element);
        } else if element.local() == "grpSp" {
            table_frames(element, frames);
        }
    }
}

fn table_named<'e>(
    parent: &'e ChartXmlElement,
    local: &'e str,
) -> impl Iterator<Item = &'e ChartXmlElement> + 'e {
    parent
        .elements()
        .filter(move |element| element.local() == local)
}

fn table_named_mut<'e>(
    parent: &'e mut ChartXmlElement,
    local: &'e str,
) -> impl Iterator<Item = &'e mut ChartXmlElement> + 'e {
    parent
        .elements_mut()
        .filter(move |element| element.local() == local)
}

fn table_row_mut(
    table: &mut ChartXmlElement,
    row_index: usize,
    shape_id: u64,
) -> Result<&mut ChartXmlElement, WolfPptError> {
    let rows = table_named(table, "tr").count();
    table_named_mut(table, "tr").nth(row_index).ok_or_else(|| {
        style_invalid(format!(
            "row {row_index} was not found in table {shape_id} ({rows} rows)"
        ))
    })
}

fn table_column_count(table: &ChartXmlElement) -> usize {
    table
        .child("tblGrid")
        .map_or(0, |grid| table_named(grid, "gridCol").count())
}

/// Replaces the cell's paragraphs with one paragraph per line, creating the
/// text body when absent.
fn table_set_cell_text(a: &str, cell: &mut ChartXmlElement, text: &str) {
    let has_body = cell.child("txBody").is_some();
    let body = style_ensure(cell, &format!("{a}:txBody"), TABLE_TC_ORDER);
    if !has_body {
        body.push(ChartXmlElement::new(format!("{a}:bodyPr")));
        body.push(ChartXmlElement::new(format!("{a}:lstStyle")));
    }
    body.remove_children("p");
    for line in text.split('\n') {
        let mut paragraph = ChartXmlElement::new(format!("{a}:p"));
        if !line.is_empty() {
            let mut run = ChartXmlElement::new(format!("{a}:r"));
            run.push(ChartXmlElement::new(format!("{a}:t")).with_text(line));
            paragraph.push(run);
        }
        let position = body.insert_position("p", TABLE_TX_BODY_ORDER);
        body.children
            .insert(position, ChartXmlNode::Element(paragraph));
    }
}

/// POI `XSLFTableCell.setBorderDefaults`: a visible solid edge.
fn table_border_defaults(a: &str, line: &mut ChartXmlElement) {
    line.remove_children("noFill");
    if line.child("prstDash").is_none() && line.child("custDash").is_none() {
        style_ensure(line, &format!("{a}:prstDash"), STYLE_LN_ORDER).set_attribute("val", "solid");
    }
    for (name, value) in [("cmpd", "sng"), ("algn", "ctr"), ("cap", "flat")] {
        if line.attribute(name).is_none() {
            line.set_attribute(name, value);
        }
    }
    if ["round", "bevel", "miter"]
        .iter()
        .all(|join| line.child(join).is_none())
    {
        style_ensure(line, &format!("{a}:round"), STYLE_LN_ORDER);
    }
    for end in ["headEnd", "tailEnd"] {
        if line.child(end).is_none() {
            let element = style_ensure(line, &format!("{a}:{end}"), STYLE_LN_ORDER);
            element.set_attribute("type", "none");
            element.set_attribute("w", "med");
            element.set_attribute("len", "med");
        }
    }
}

fn table_apply_border(
    a: &str,
    properties: &mut ChartXmlElement,
    border: &TableBorderEdit,
) -> Result<(), WolfPptError> {
    if let Some(width) = border.width_emu {
        if width > STYLE_MAX_LINE_WIDTH_EMU {
            return Err(style_invalid(format!(
                "border width_emu must be at most {STYLE_MAX_LINE_WIDTH_EMU}, got {width}"
            )));
        }
    }
    let fill = border
        .color
        .as_ref()
        .map(|color| style_fill_element(a, Some(color)))
        .transpose()?;
    let line = style_ensure(
        properties,
        &format!("{a}:{}", border.edge.local()),
        TABLE_TC_PR_ORDER,
    );
    if let Some(width) = border.width_emu {
        line.set_attribute("w", &width.to_string());
    }
    if border.dash.is_none() && fill.is_none() {
        return Ok(());
    }
    table_border_defaults(a, line);
    if let Some(dash) = border.dash {
        line.remove_children("custDash");
        style_ensure(line, &format!("{a}:prstDash"), STYLE_LN_ORDER)
            .set_attribute("val", dash.token());
    }
    if let Some(fill) = fill {
        style_replace_choice(line, TABLE_LINE_FILLS, Some(fill), STYLE_LN_ORDER);
    }
    Ok(())
}

/// Rewrites table `shape_id` on slide `slide_index` with `edit`, which gets
/// the DrawingML prefix and the `a:tbl` element.
fn table_rewrite(
    input_path: &Path,
    output_path: &Path,
    slide_index: usize,
    shape_id: u64,
    edit: impl FnOnce(&str, &mut ChartXmlElement) -> Result<(), WolfPptError>,
) -> Result<TableStructureEditSummary, WolfPptError> {
    let mut counts = (0, 0);
    let (slide_part, part_count, has_vba) = style_rewrite_part(
        input_path,
        output_path,
        |archive| style_slide_part(archive, slide_index),
        |root| {
            let a = style_drawing_prefix(root);
            let tree = root
                .child_mut("cSld")
                .and_then(|common| common.child_mut("spTree"))
                .ok_or_else(|| style_invalid("slide has no p:cSld/p:spTree"))?;
            let frame = style_shape_mut(tree, shape_id).ok_or_else(|| {
                style_invalid(format!(
                    "shape {shape_id} was not found on slide {slide_index}"
                ))
            })?;
            let table = table_of_mut(frame)
                .ok_or_else(|| style_invalid(format!("shape {shape_id} is not a table")))?;
            edit(&a, table)?;
            counts = (table_named(table, "tr").count(), table_column_count(table));
            Ok(())
        },
    )?;
    Ok(TableStructureEditSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        rows: counts.0,
        columns: counts.1,
        part_count,
        has_vba,
    })
}

/// Adds an empty table (no rows, no grid columns, no table style) in a new
/// graphic frame named `Table <id>`, as POI `XSLFSheet.createTable()`.
pub fn add_slide_empty_table(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<TableAddSummary, WolfPptError> {
    let output_path = output_path.as_ref();
    let mut added = (0, 0);
    let (slide_part, part_count, has_vba) = style_rewrite_part(
        input_path.as_ref(),
        output_path,
        |archive| style_slide_part(archive, slide_index),
        |root| {
            let a = style_drawing_prefix(root);
            let binding = format!("xmlns:{a}");
            if !root.attributes.iter().any(|(name, _)| *name == binding) {
                root.set_attribute(&binding, TABLE_DRAWINGML_NS);
            }
            let tree = root
                .child_mut("cSld")
                .and_then(|common| common.child_mut("spTree"))
                .ok_or_else(|| style_invalid("slide has no p:cSld/p:spTree"))?;
            let mut ids = std::collections::BTreeSet::new();
            style_collect_ids(tree, &mut ids);
            let shape_id = ids.last().copied().max(style_shape_id(tree)).unwrap_or(0) + 1;
            let mut frames = Vec::new();
            table_frames(tree, &mut frames);
            added = (frames.len(), shape_id);
            let p = |local: &str| tree.qualified(local);
            let element = |name: String| ChartXmlElement::new(name);
            let mut frame = element(p("graphicFrame"));
            let mut non_visual = element(p("nvGraphicFramePr"));
            let mut properties = element(p("cNvPr"));
            properties.set_attribute("id", &shape_id.to_string());
            properties.set_attribute("name", &format!("Table {shape_id}"));
            non_visual.push(properties);
            let mut frame_properties = element(p("cNvGraphicFramePr"));
            let mut locks = element(format!("{a}:graphicFrameLocks"));
            locks.set_attribute("noGrp", "1");
            frame_properties.push(locks);
            non_visual.push(frame_properties);
            non_visual.push(element(p("nvPr")));
            frame.push(non_visual);
            let mut xfrm = element(p("xfrm"));
            let mut offset = element(format!("{a}:off"));
            offset.set_attribute("x", &x_emu.to_string());
            offset.set_attribute("y", &y_emu.to_string());
            xfrm.push(offset);
            let mut extent = element(format!("{a}:ext"));
            extent.set_attribute("cx", &cx_emu.to_string());
            extent.set_attribute("cy", &cy_emu.to_string());
            xfrm.push(extent);
            frame.push(xfrm);
            let mut table = element(format!("{a}:tbl"));
            table.push(element(format!("{a}:tblPr")));
            table.push(element(format!("{a}:tblGrid")));
            let mut data = element(format!("{a}:graphicData"));
            data.set_attribute("uri", TABLE_GRAPHIC_DATA_URI);
            data.push(table);
            let mut graphic = element(format!("{a}:graphic"));
            graphic.push(data);
            frame.push(graphic);
            let position = tree.insert_position("graphicFrame", TABLE_SP_TREE_ORDER);
            tree.children.insert(position, ChartXmlNode::Element(frame));
            Ok(())
        },
    )?;
    Ok(TableAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        table_index: added.0,
        shape_id: added.1,
        rows: 0,
        cols: 0,
        part_count,
        has_vba,
    })
}

pub fn add_table_row(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &TableRowAdd,
) -> Result<TableStructureEditSummary, WolfPptError> {
    let height = edit.height_emu.unwrap_or(TABLE_DEFAULT_ROW_HEIGHT_EMU);
    table_rewrite(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.shape_id,
        |a, table| {
            style_ensure(table, &format!("{a}:tblGrid"), TABLE_TBL_ORDER);
            let mut row = ChartXmlElement::new(format!("{a}:tr"));
            row.set_attribute("h", &height.to_string());
            let position = table.insert_position("tr", TABLE_TBL_ORDER);
            table.children.insert(position, ChartXmlNode::Element(row));
            Ok(())
        },
    )
}

pub fn set_table_row(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &TableRowEdit,
) -> Result<TableStructureEditSummary, WolfPptError> {
    table_rewrite(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.shape_id,
        |_, table| {
            table_row_mut(table, edit.row_index, edit.shape_id)?
                .set_attribute("h", &edit.height_emu.to_string());
            Ok(())
        },
    )
}

pub fn add_table_cell(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &TableCellAdd,
) -> Result<TableStructureEditSummary, WolfPptError> {
    table_rewrite(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.shape_id,
        |a, table| {
            let mut cell = ChartXmlElement::new(format!("{a}:tc"));
            if let Some(text) = &edit.text {
                table_set_cell_text(a, &mut cell, text);
            }
            let mut properties = ChartXmlElement::new(format!("{a}:tcPr"));
            for edge in ["lnL", "lnR", "lnT", "lnB"] {
                let mut line = ChartXmlElement::new(format!("{a}:{edge}"));
                line.push(ChartXmlElement::new(format!("{a}:noFill")));
                properties.push(line);
            }
            cell.push(properties);
            let row = table_row_mut(table, edit.row_index, edit.shape_id)?;
            let position = row.insert_position("tc", TABLE_TR_ORDER);
            row.children.insert(position, ChartXmlNode::Element(cell));
            let cells = table_named(row, "tc").count();
            let grid = style_ensure(table, &format!("{a}:tblGrid"), TABLE_TBL_ORDER);
            if table_named(grid, "gridCol").count() < cells {
                let mut column = ChartXmlElement::new(format!("{a}:gridCol"));
                column.set_attribute("w", &TABLE_DEFAULT_COLUMN_WIDTH_EMU.to_string());
                let position = grid.insert_position("gridCol", &["gridCol", "extLst"]);
                grid.children
                    .insert(position, ChartXmlNode::Element(column));
            }
            Ok(())
        },
    )
}

pub fn set_table_cell(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &TableCellEdit,
) -> Result<TableStructureEditSummary, WolfPptError> {
    table_rewrite(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.shape_id,
        |a, table| {
            let row = table_row_mut(table, edit.row_index, edit.shape_id)?;
            let cells = table_named(row, "tc").count();
            let cell = table_named_mut(row, "tc")
                .nth(edit.column_index)
                .ok_or_else(|| {
                    style_invalid(format!(
                        "cell {} was not found in row {} of table {} ({cells} cells)",
                        edit.column_index, edit.row_index, edit.shape_id
                    ))
                })?;
            if let Some(text) = &edit.text {
                table_set_cell_text(a, cell, text);
            }
            if edit.text_direction.is_none()
                && edit.vertical_alignment.is_none()
                && edit.borders.is_empty()
            {
                return Ok(());
            }
            let properties = style_ensure(cell, &format!("{a}:tcPr"), TABLE_TC_ORDER);
            match edit.text_direction {
                Some(Some(direction)) => properties.set_attribute("vert", direction.token()),
                Some(None) => style_remove_attribute(properties, "vert"),
                None => {}
            }
            match edit.vertical_alignment {
                Some(Some(alignment)) => properties.set_attribute("anchor", alignment.token()),
                Some(None) => style_remove_attribute(properties, "anchor"),
                None => {}
            }
            for border in &edit.borders {
                table_apply_border(a, properties, border)?;
            }
            Ok(())
        },
    )
}

pub fn merge_table_cells(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edit: &TableCellMerge,
) -> Result<TableStructureEditSummary, WolfPptError> {
    let (first, last) = (edit.first_column, edit.last_column);
    if first >= last {
        return Err(style_invalid(format!(
            "a merge needs at least two cells: first_column {first} must be less than last_column {last}"
        )));
    }
    table_rewrite(
        input_path.as_ref(),
        output_path.as_ref(),
        edit.slide_index,
        edit.shape_id,
        |_, table| {
            let row = table_row_mut(table, edit.row_index, edit.shape_id)?;
            let cells = table_named(row, "tc").count();
            if last >= cells {
                return Err(style_invalid(format!(
                    "last_column {last} is outside row {} of table {} ({cells} cells)",
                    edit.row_index, edit.shape_id
                )));
            }
            for (index, cell) in table_named_mut(row, "tc").enumerate() {
                if index == first {
                    cell.set_attribute("gridSpan", &(last - first + 1).to_string());
                } else if index > first && index <= last {
                    cell.set_attribute("hMerge", "1");
                }
            }
            Ok(())
        },
    )
}

fn table_paragraph_text(paragraph: &ChartXmlElement) -> String {
    let mut text = String::new();
    for child in paragraph.elements() {
        match child.local() {
            "r" | "fld" => {
                if let Some(run_text) = child.child("t") {
                    text.push_str(&run_text.text());
                }
            }
            "br" => text.push('\n'),
            _ => {}
        }
    }
    text
}

fn table_cell_summary(cell: &ChartXmlElement, theme: Option<&StyleTheme>) -> TableCellSummary {
    let body = cell.child("txBody");
    let paragraphs: Vec<String> = body
        .map(|body| table_named(body, "p").map(table_paragraph_text).collect())
        .unwrap_or_default();
    let properties = cell.child("tcPr");
    let vert = properties.and_then(|properties| properties.attribute("vert"));
    let anchor = properties.and_then(|properties| properties.attribute("anchor"));
    let border = |local: &str| {
        properties
            .and_then(|properties| properties.child(local))
            .map(|line| style_line_summary(line, theme))
    };
    let h_merge = style_bool(cell, "hMerge").unwrap_or(false);
    let v_merge = style_bool(cell, "vMerge").unwrap_or(false);
    TableCellSummary {
        text: paragraphs.join("\n"),
        has_text_body: body.is_some(),
        paragraph_count: paragraphs.len(),
        grid_span: style_number(cell, "gridSpan").unwrap_or(1),
        row_span: style_number(cell, "rowSpan").unwrap_or(1),
        h_merge,
        v_merge,
        merged: h_merge || v_merge,
        text_direction: match vert.as_deref() {
            Some("vert" | "eaVert" | "mongolianVert") => "vertical",
            Some("vert270") => "vertical_270",
            Some("wordArtVert" | "wordArtVertRtl") => "stacked",
            _ => "horizontal",
        },
        vert,
        vertical_alignment: match anchor.as_deref() {
            Some("ctr") => "middle",
            Some("b") => "bottom",
            Some("just") => "justified",
            Some("dist") => "distributed",
            _ => "top",
        },
        anchor,
        borders: TableCellBordersSummary {
            left: border("lnL"),
            right: border("lnR"),
            top: border("lnT"),
            bottom: border("lnB"),
        },
    }
}

fn table_structure_summary(
    table_index: usize,
    frame: &ChartXmlElement,
    styles: &TableStylesSummary,
    theme: Option<&StyleTheme>,
) -> TableStructureSummary {
    let table = table_of(frame).expect("table_frames selects table frames");
    let c_nv_pr = style_non_visual(frame).and_then(|nv| nv.child("cNvPr"));
    let xfrm = frame.child("xfrm");
    let pair = |local: &str, first: &str, second: &str| {
        xfrm.and_then(|xfrm| xfrm.child(local))
            .map_or((None, None), |element| {
                (style_number(element, first), style_number(element, second))
            })
    };
    let (x, y) = pair("off", "x", "y");
    let (cx, cy) = pair("ext", "cx", "cy");
    let table_properties = table.child("tblPr");
    let flag = |name: &str| {
        table_properties
            .and_then(|properties| style_bool(properties, name))
            .unwrap_or(false)
    };
    let style_id = table_properties.and_then(|properties| {
        properties
            .child("tableStyleId")
            .map(|id| id.text().trim().to_string())
    });
    let style = style_id.as_ref().and_then(|id| {
        styles
            .styles
            .iter()
            .find(|style| style.style_id.as_ref() == Some(id))
            .cloned()
    });
    TableStructureSummary {
        table_index,
        shape_id: c_nv_pr.and_then(|properties| style_number(properties, "id")),
        name: c_nv_pr.and_then(|properties| properties.attribute("name")),
        x,
        y,
        cx,
        cy,
        style_id,
        style,
        first_row: flag("firstRow"),
        first_column: flag("firstCol"),
        last_row: flag("lastRow"),
        last_column: flag("lastCol"),
        band_row: flag("bandRow"),
        band_column: flag("bandCol"),
        column_widths_emu: table
            .child("tblGrid")
            .map(|grid| {
                table_named(grid, "gridCol")
                    .map(|column| style_number(column, "w"))
                    .collect()
            })
            .unwrap_or_default(),
        rows: table_named(table, "tr")
            .map(|row| TableRowSummary {
                height_emu: style_number(row, "h"),
                cells: table_named(row, "tc")
                    .map(|cell| table_cell_summary(cell, theme))
                    .collect(),
            })
            .collect(),
    }
}

fn table_styles_summary<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
) -> Result<TableStylesSummary, WolfPptError> {
    let Some(part) = style_related_part(archive, "ppt/presentation.xml", "/tableStyles")? else {
        return Ok(TableStylesSummary::default());
    };
    let Some(root) = style_read_root(archive, &part)? else {
        return Ok(TableStylesSummary {
            part: Some(part),
            ..TableStylesSummary::default()
        });
    };
    Ok(TableStylesSummary {
        default_style_id: root.attribute("def"),
        styles: table_named(&root, "tblStyle")
            .map(|style| TableStyleSummary {
                style_id: style.attribute("styleId"),
                name: style.attribute("styleName"),
            })
            .collect(),
        part: Some(part),
    })
}

/// The colour context of a slide: its master's theme and colour map, with
/// the slide's colour map override.
fn table_slide_theme<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    part: &str,
    slide: &ChartXmlElement,
) -> Result<Option<StyleTheme>, WolfPptError> {
    let master_part = match style_related_part(archive, part, "/slideLayout")? {
        Some(layout) => style_related_part(archive, &layout, "/slideMaster")?,
        None => None,
    };
    let Some(master_part) = master_part else {
        return Ok(None);
    };
    let Some(master) = style_read_root(archive, &master_part)? else {
        return Ok(None);
    };
    let (map, _, theme_root) = style_master_theme(archive, &master_part, &master)?;
    let map = match slide
        .child("clrMapOvr")
        .and_then(|over| over.child("overrideClrMapping"))
    {
        Some(over) => style_color_map(Some(over)),
        None => map,
    };
    Ok(Some(StyleTheme {
        slots: style_theme_slots(theme_root.as_ref()),
        map,
    }))
}

/// Structured tables of every slide plus the table style catalog.
pub fn summarize_table_structure_bytes(
    bytes: &[u8],
) -> Result<TableStructuresSummary, WolfPptError> {
    let mut archive = ZipArchive::new(Cursor::new(bytes))?;
    let table_styles = table_styles_summary(&mut archive)?;
    let mut slides = Vec::new();
    for (index, part) in slide_parts(&mut archive)?.into_iter().enumerate() {
        let Some(slide) = style_read_root(&mut archive, &part)? else {
            continue;
        };
        let mut frames = Vec::new();
        if let Some(tree) = slide
            .child("cSld")
            .and_then(|common| common.child("spTree"))
        {
            table_frames(tree, &mut frames);
        }
        let theme = if frames.is_empty() {
            None
        } else {
            table_slide_theme(&mut archive, &part, &slide)?
        };
        let tables = frames
            .into_iter()
            .enumerate()
            .map(|(table_index, frame)| {
                table_structure_summary(table_index, frame, &table_styles, theme.as_ref())
            })
            .collect();
        slides.push(SlideTablesSummary {
            index,
            part,
            tables,
        });
    }
    Ok(TableStructuresSummary {
        slides,
        table_styles,
    })
}
