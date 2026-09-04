#[cfg(test)]
mod tests {
    use super::*;

    fn read_zip_text(path: impl AsRef<Path>, part_name: &str) -> String {
        let file = File::open(path).unwrap();
        let mut archive = ZipArchive::new(file).unwrap();
        let mut part = archive.by_name(part_name).unwrap();
        let mut payload = String::new();
        part.read_to_string(&mut payload).unwrap();
        payload
    }

    fn read_zip_bytes(path: impl AsRef<Path>, part_name: &str) -> Vec<u8> {
        let file = File::open(path).unwrap();
        let mut archive = ZipArchive::new(file).unwrap();
        let mut part = archive.by_name(part_name).unwrap();
        let mut payload = Vec::new();
        part.read_to_end(&mut payload).unwrap();
        payload
    }

    include!("tests_text_extract_package.inc.rs");
    include!("tests_slide_shape_adds.inc.rs");
    include!("tests_group_shape_adds.inc.rs");
    include!("tests_group_shape_child_edits.inc.rs");
    include!("tests_text_shapes.inc.rs");
    include!("tests_text_batch.inc.rs");
    include!("tests_slide_reorder_shape_delete.inc.rs");
    include!("tests_slide_duplicate.inc.rs");
    include!("tests_slide_delete.inc.rs");
    include!("tests_package.inc.rs");
    include!("tests_table_row_column_mutation.inc.rs");
}
