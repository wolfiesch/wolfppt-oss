use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::PathBuf;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum WolfPptError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("zip error: {0}")]
    Zip(#[from] zip::result::ZipError),
    #[error("xml error: {0}")]
    Xml(#[from] quick_xml::Error),
    #[error("xml text decode error: {0}")]
    XmlText(String),
    #[error("invalid input: {0}")]
    InvalidInput(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PartKind {
    Xml,
    Relationships,
    Media,
    Embedding,
    Vba,
    Binary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PartRecord {
    pub name: String,
    pub size: u64,
    pub sha256: String,
    pub kind: PartKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PackageManifest {
    pub path: PathBuf,
    pub parts: Vec<PartRecord>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PresentationSummary {
    pub path: PathBuf,
    pub slide_count: usize,
    pub slides: Vec<SlideSummary>,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TextReplacementSummary {
    pub path: PathBuf,
    pub replacements: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TextRunReplacementSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub run_index: usize,
    pub replacements: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ShapeTextSetSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub shape_index: usize,
    pub replacements: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ParagraphTextSetSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub shape_index: usize,
    pub paragraph_index: usize,
    pub replacements: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImageReplacementSummary {
    pub path: PathBuf,
    pub relationship_id: String,
    pub replacements: usize,
    pub replaced_parts: Vec<String>,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImageAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub relationship_id: String,
    pub image_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MovieAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub media_relationship_id: String,
    pub video_relationship_id: String,
    pub poster_relationship_id: String,
    pub media_part: String,
    pub poster_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct OleObjectAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub ole_relationship_id: String,
    pub icon_relationship_id: String,
    pub ole_part: String,
    pub icon_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TableCellReplacementSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub table_index: usize,
    pub row_index: usize,
    pub col_index: usize,
    pub replacements: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TableMutationSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub table_index: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TableAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub table_index: usize,
    pub shape_id: u64,
    pub rows: usize,
    pub cols: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TextBoxAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GroupShapeAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct FreeformShapeAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum FreeformPathOperation {
    MoveTo { x: i64, y: i64 },
    LineTo { x: i64, y: i64 },
    Close,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PlaceholderShapeAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub placeholder_type: Option<String>,
    pub placeholder_idx: Option<String>,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub struct PlaceholderShapeSpec {
    pub placeholder_type: Option<String>,
    pub placeholder_orient: Option<String>,
    pub placeholder_size: Option<String>,
    pub placeholder_idx: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PlaceholderShapeBatchAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub shape_ids: Vec<u64>,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct AutoShapeAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub preset_geometry: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ConnectorAddSummary {
    pub path: PathBuf,
    pub slide_index: usize,
    pub slide_part: String,
    pub preset_geometry: String,
    pub shape_id: u64,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SlideAddSummary {
    pub path: PathBuf,
    pub slide_part: String,
    pub relationship_id: String,
    pub layout_target: String,
    pub slide_id: u64,
    pub slide_count: usize,
    pub part_count: usize,
    pub has_vba: bool,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SlideDeleteSummary {
    pub path: PathBuf,
    pub deleted_slide_parts: Vec<String>,
    pub deleted_relationship_ids: Vec<String>,
    pub survivor_count: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum EditOperation {
    ReorderSlides {
        slide_indices: Vec<usize>,
    },
    DeleteShape {
        slide_index: usize,
        shape_index: usize,
    },
    DeleteGroupShapeChild {
        slide_index: usize,
        group_shape_id: usize,
        child_shape_id: usize,
    },
    SetShapeText {
        slide_index: usize,
        shape_index: usize,
        replacement: String,
    },
    SetGroupShapeChildText {
        slide_index: usize,
        group_index: usize,
        child_index: usize,
        replacement: String,
    },
    SetGroupShapeChildParagraphText {
        slide_index: usize,
        group_index: usize,
        child_index: usize,
        paragraph_index: usize,
        replacement: String,
    },
    SetGroupShapeChildRunText {
        slide_index: usize,
        group_index: usize,
        child_index: usize,
        paragraph_index: usize,
        run_index: usize,
        replacement: String,
    },
    SetParagraphText {
        slide_index: usize,
        shape_index: usize,
        paragraph_index: usize,
        replacement: String,
    },
    ReplaceTextRun {
        slide_index: usize,
        run_index: usize,
        replacement: String,
    },
    SetTextRunBold {
        slide_index: usize,
        run_index: usize,
        bold: Option<bool>,
    },
    SetTextRunItalic {
        slide_index: usize,
        run_index: usize,
        italic: Option<bool>,
    },
    SetTextRunUnderline {
        slide_index: usize,
        run_index: usize,
        underline: Option<bool>,
    },
    SetTextRunFontSize {
        slide_index: usize,
        run_index: usize,
        size: Option<i64>,
    },
    SetTextRunFontName {
        slide_index: usize,
        run_index: usize,
        name: Option<String>,
    },
    SetTextRunFormatting {
        slide_index: usize,
        run_index: usize,
        set_bold: bool,
        bold: Option<bool>,
        set_italic: bool,
        italic: Option<bool>,
        set_underline: bool,
        underline: Option<bool>,
        set_size: bool,
        size: Option<i64>,
        set_name: bool,
        name: Option<String>,
        #[serde(default)]
        set_color: bool,
        #[serde(default)]
        color: Option<String>,
    },
    AppendParagraphText {
        slide_index: usize,
        shape_index: usize,
        text: String,
    },
    AppendTextRun {
        slide_index: usize,
        shape_index: usize,
        paragraph_index: usize,
        text: String,
    },
    InsertParagraphLineBreak {
        slide_index: usize,
        shape_index: usize,
        paragraph_index: usize,
        run_slot: usize,
    },
    SetParagraphProperties {
        slide_index: usize,
        shape_index: usize,
        paragraph_index: usize,
        set_alignment: bool,
        alignment: Option<String>,
        set_level: bool,
        level: usize,
        #[serde(default)]
        spacing: ParagraphSpacingPatch,
    },
    SetParagraphFontProperties {
        slide_index: usize,
        shape_index: usize,
        paragraph_index: usize,
        set_bold: bool,
        bold: Option<bool>,
        set_italic: bool,
        italic: Option<bool>,
        set_underline: bool,
        underline: Option<bool>,
        set_size: bool,
        size: Option<i64>,
        set_name: bool,
        name: Option<String>,
        #[serde(default)]
        set_color: bool,
        #[serde(default)]
        color: Option<String>,
        #[serde(default)]
        set_fill_type: bool,
        #[serde(default)]
        fill_type: Option<String>,
        #[serde(default)]
        set_language: bool,
        #[serde(default)]
        language_id: Option<String>,
    },
    SetShapeGeometry {
        slide_index: usize,
        shape_index: usize,
        x_emu: i64,
        y_emu: i64,
        cx_emu: i64,
        cy_emu: i64,
    },
    SetGroupShapeChildGeometry {
        slide_index: usize,
        group_index: usize,
        child_index: usize,
        x_emu: i64,
        y_emu: i64,
        cx_emu: i64,
        cy_emu: i64,
    },
    SetTextFrameProperties {
        slide_index: usize,
        shape_index: usize,
        #[serde(default)]
        properties: TextFramePropertiesPatch,
    },
    ReplaceTableCellText {
        slide_index: usize,
        table_index: usize,
        row_index: usize,
        col_index: usize,
        replacement: String,
    },
    SetTableCellMerge {
        slide_index: usize,
        table_index: usize,
        row_min: usize,
        row_max: usize,
        col_min: usize,
        col_max: usize,
        kind: String,
        #[serde(default)]
        paragraphs: Vec<String>,
    },
    SetTableStyleFlags {
        slide_index: usize,
        table_index: usize,
        flags: BTreeMap<String, bool>,
    },
    InsertTableRow {
        slide_index: usize,
        table_index: usize,
        row_index: usize,
    },
    DeleteTableRow {
        slide_index: usize,
        table_index: usize,
        row_index: usize,
    },
    InsertTableColumn {
        slide_index: usize,
        table_index: usize,
        col_index: usize,
    },
    DeleteTableColumn {
        slide_index: usize,
        table_index: usize,
        col_index: usize,
    },
}

#[derive(Debug, Clone, Default, PartialEq, Deserialize, Serialize)]
pub struct ParagraphSpacingPatch {
    #[serde(default)]
    pub line_spacing: Option<ParagraphSpacingValue>,
    #[serde(default)]
    pub space_before: Option<ParagraphSpacingValue>,
    #[serde(default)]
    pub space_after: Option<ParagraphSpacingValue>,
}

#[derive(Debug, Clone, Default, PartialEq, Deserialize, Serialize)]
pub struct TextFramePropertiesPatch {
    #[serde(default)]
    pub margins: BTreeMap<String, i64>,
    #[serde(default)]
    pub set_word_wrap: bool,
    #[serde(default)]
    pub word_wrap: Option<String>,
    #[serde(default)]
    pub set_vertical_anchor: bool,
    #[serde(default)]
    pub vertical_anchor: Option<String>,
    #[serde(default)]
    pub set_auto_size: bool,
    #[serde(default)]
    pub auto_size: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ParagraphSpacingValue {
    Clear,
    Emu { value: i64 },
    Multiple { value: f64 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct EditBatchSummary {
    pub path: PathBuf,
    pub edits: usize,
    pub replacements: usize,
    pub part_count: usize,
    pub has_vba: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SlideSummary {
    pub part: String,
    pub texts: Vec<String>,
    pub shapes: Vec<ShapeSummary>,
    pub tables: Vec<TableSummary>,
    pub notes: Vec<String>,
    pub relationships: Vec<RelationshipSummary>,
    pub image_relationships: Vec<RelationshipSummary>,
    pub chart_relationships: Vec<RelationshipSummary>,
    pub comment_relationships: Vec<RelationshipSummary>,
    pub media_relationships: Vec<RelationshipSummary>,
    pub ole_relationships: Vec<RelationshipSummary>,
    pub has_transition: bool,
    pub has_timing: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ShapeSummary {
    pub id: Option<String>,
    pub name: Option<String>,
    pub kind: String,
    pub is_placeholder: bool,
    pub placeholder_type: Option<String>,
    pub placeholder_idx: Option<String>,
    pub text: String,
    pub paragraphs: Vec<String>,
    pub paragraph_runs: Vec<Vec<String>>,
    pub paragraph_line_breaks: Vec<Vec<usize>>,
    pub paragraph_run_bold: Vec<Vec<Option<bool>>>,
    pub paragraph_run_italic: Vec<Vec<Option<bool>>>,
    pub paragraph_run_underline: Vec<Vec<Option<bool>>>,
    pub paragraph_run_font_size: Vec<Vec<Option<i64>>>,
    pub paragraph_run_font_name: Vec<Vec<Option<String>>>,
    pub tables: Vec<TableSummary>,
    pub relationship_ids: Vec<String>,
    pub has_chart: bool,
    pub has_picture: bool,
    pub has_group: bool,
    pub transform: Option<TransformSummary>,
    pub effective_transform: Option<TransformSummary>,
    pub children: Vec<ShapeSummary>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct TransformSummary {
    pub x: i64,
    pub y: i64,
    pub cx: i64,
    pub cy: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct CoordinateFrame {
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) cx: i64,
    pub(crate) cy: i64,
    pub(crate) ch_x: i64,
    pub(crate) ch_y: i64,
    pub(crate) ch_cx: i64,
    pub(crate) ch_cy: i64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TableSummary {
    pub rows: Vec<Vec<String>>,
    pub row_count: usize,
    pub col_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RelationshipSummary {
    pub id: String,
    pub relationship_type: String,
    pub target: String,
    pub target_mode: Option<String>,
}

impl PackageManifest {
    pub fn has_vba(&self) -> bool {
        self.parts.iter().any(|part| part.kind == PartKind::Vba)
    }

    pub fn part_names(&self) -> Vec<&str> {
        self.parts.iter().map(|part| part.name.as_str()).collect()
    }
}
