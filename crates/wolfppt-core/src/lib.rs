//! Rust package-inspection core for WolfPPT.
//!
//! This first slice deliberately stays below the typed PresentationML layer. It
//! provides loss-aware package inspection that the Python harness can later call
//! through a binding layer.

use quick_xml::events::{BytesEnd, BytesRef, BytesStart, BytesText, Event};
use quick_xml::Reader;
use quick_xml::Writer;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs::File;
use std::io::{Cursor, Read};
use std::path::{Path, PathBuf};
use zip::write::SimpleFileOptions;
use zip::ZipArchive;

mod models;

use models::CoordinateFrame;
pub use models::*;

include!("package_ops.inc.rs");
include!("package_inspection.inc.rs");
include!("package_mutation_image.inc.rs");
include!("package_mutation_batch.inc.rs");
include!("package_mutation_table.inc.rs");
include!("package_mutation_text_boxes.inc.rs");
include!("package_mutation_shapes.inc.rs");
include!("package_mutation_connectors.inc.rs");
include!("package_mutation_group_shapes.inc.rs");
include!("package_mutation_placeholders.inc.rs");
include!("package_mutation_slides.inc.rs");
include!("package_mutation_slide_duplicate.inc.rs");
include!("package_mutation_slide_delete.inc.rs");
include!("media_ops.inc.rs");
include!("summary_text_extract.inc.rs");
include!("summary_shape_extract.inc.rs");
include!("summary_package_extract.inc.rs");
include!("xml_package_helpers.inc.rs");
include!("xml_media_builders.inc.rs");
include!("xml_placeholder_builders.inc.rs");
include!("xml_builders.inc.rs");
include!("xml_auto_shape_builders.inc.rs");
include!("xml_connector_builders.inc.rs");
include!("xml_group_builders.inc.rs");
include!("text_xml_helpers.inc.rs");
include!("text_rewrite.inc.rs");
include!("shape_text_rewrite.inc.rs");
include!("group_shape_child_rewrite.inc.rs");
include!("text_rewrite_paragraph.inc.rs");
include!("text_frame_rewrite.inc.rs");
include!("table_and_misc.inc.rs");
include!("tests.inc.rs");
