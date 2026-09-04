use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use serde_json::json;
use wolfppt_core::{
    add_blank_slide_from_existing_layout, add_blank_slide_from_layout_index, add_slide_table,
    add_slide_table_with_cell_texts, delete_slide, delete_slides, duplicate_slide, inspect_package,
    replace_slide_text, replace_slide_text_at_index, replace_slide_text_run_at_index,
    replace_table_cell_text, roundtrip_package, set_slide_shape_paragraph_text_at_index,
    set_slide_shape_text_at_index, summarize_presentation, summarize_slide_at_index,
};

#[pyfunction]
fn inspect_package_json(path: &str) -> PyResult<String> {
    let manifest = inspect_package(path).map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&manifest).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn build_info_json() -> PyResult<String> {
    let build_profile = if cfg!(debug_assertions) {
        "debug"
    } else {
        "release"
    };
    let info = json!({
        "package": env!("CARGO_PKG_NAME"),
        "version": env!("CARGO_PKG_VERSION"),
        "build_profile": build_profile,
        "debug_assertions": cfg!(debug_assertions),
    });
    serde_json::to_string_pretty(&info).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn summarize_presentation_json(path: &str) -> PyResult<String> {
    let summary =
        summarize_presentation(path).map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn summarize_slide_at_index_json(path: &str, slide_index: usize) -> PyResult<String> {
    let summary = summarize_slide_at_index(path, slide_index)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn roundtrip_package_json(input: &str, output: &str) -> PyResult<String> {
    let manifest =
        roundtrip_package(input, output).map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&manifest).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_blank_slide_json(input: &str, output: &str) -> PyResult<String> {
    let summary = add_blank_slide_from_existing_layout(input, output)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_blank_slide_with_layout_json(
    input: &str,
    output: &str,
    layout_index: usize,
) -> PyResult<String> {
    let summary = add_blank_slide_from_layout_index(input, output, layout_index)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn duplicate_slide_json(input: &str, output: &str, source_slide_part: &str) -> PyResult<String> {
    let summary = duplicate_slide(input, output, source_slide_part)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}
#[pyfunction]
fn delete_slide_json(input: &str, output: &str, target_slide_part: &str) -> PyResult<String> {
    let summary = delete_slide(input, output, target_slide_part)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[pyo3(signature = (input, output, target_slide_parts, ordered_survivor_parts=None))]
fn delete_slides_json(
    input: &str,
    output: &str,
    target_slide_parts: Vec<String>,
    ordered_survivor_parts: Option<Vec<String>>,
) -> PyResult<String> {
    let target_refs: Vec<&str> = target_slide_parts.iter().map(|s| s.as_str()).collect();
    let survivor_refs: Option<Vec<&str>> = ordered_survivor_parts
        .as_ref()
        .map(|parts| parts.iter().map(|s| s.as_str()).collect());
    let summary = delete_slides(input, output, &target_refs, survivor_refs.as_deref())
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn replace_slide_text_json(
    input: &str,
    output: &str,
    search: &str,
    replacement: &str,
) -> PyResult<String> {
    let summary = replace_slide_text(input, output, search, replacement)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn replace_slide_text_at_index_json(
    input: &str,
    output: &str,
    slide_index: usize,
    search: &str,
    replacement: &str,
) -> PyResult<String> {
    let summary = replace_slide_text_at_index(input, output, slide_index, search, replacement)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn replace_slide_text_run_at_index_json(
    input: &str,
    output: &str,
    slide_index: usize,
    run_index: usize,
    replacement: &str,
) -> PyResult<String> {
    let summary =
        replace_slide_text_run_at_index(input, output, slide_index, run_index, replacement)
            .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn set_slide_shape_text_at_index_json(
    input: &str,
    output: &str,
    slide_index: usize,
    shape_index: usize,
    replacement: &str,
) -> PyResult<String> {
    let summary =
        set_slide_shape_text_at_index(input, output, slide_index, shape_index, replacement)
            .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn set_slide_shape_paragraph_text_at_index_json(
    input: &str,
    output: &str,
    slide_index: usize,
    shape_index: usize,
    paragraph_index: usize,
    replacement: &str,
) -> PyResult<String> {
    let summary = set_slide_shape_paragraph_text_at_index(
        input,
        output,
        slide_index,
        shape_index,
        paragraph_index,
        replacement,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn replace_table_cell_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    table_index: usize,
    row_index: usize,
    col_index: usize,
    replacement: &str,
) -> PyResult<String> {
    let summary = replace_table_cell_text(
        input,
        output,
        slide_index,
        table_index,
        row_index,
        col_index,
        replacement,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_table_json(
    input: &str,
    output: &str,
    slide_index: usize,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_table(
        input,
        output,
        slide_index,
        rows,
        cols,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_table_with_cell_texts_json(
    input: &str,
    output: &str,
    slide_index: usize,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    cell_texts_json: &str,
) -> PyResult<String> {
    let cell_texts: Vec<(usize, usize, String)> = serde_json::from_str(cell_texts_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_table_with_cell_texts(
        input,
        output,
        slide_index,
        rows,
        cols,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        &cell_texts,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(build_info_json, module)?)?;
    module.add_function(wrap_pyfunction!(inspect_package_json, module)?)?;
    module.add_function(wrap_pyfunction!(summarize_presentation_json, module)?)?;
    module.add_function(wrap_pyfunction!(summarize_slide_at_index_json, module)?)?;
    module.add_function(wrap_pyfunction!(roundtrip_package_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_blank_slide_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_blank_slide_with_layout_json, module)?)?;
    module.add_function(wrap_pyfunction!(duplicate_slide_json, module)?)?;
    module.add_function(wrap_pyfunction!(delete_slide_json, module)?)?;
    module.add_function(wrap_pyfunction!(delete_slides_json, module)?)?;
    module.add_function(wrap_pyfunction!(replace_slide_text_json, module)?)?;
    module.add_function(wrap_pyfunction!(replace_slide_text_at_index_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        replace_slide_text_run_at_index_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        set_slide_shape_text_at_index_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        set_slide_shape_paragraph_text_at_index_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(replace_table_cell_text_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_table_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_table_with_cell_texts_json,
        module
    )?)?;
    Ok(())
}
