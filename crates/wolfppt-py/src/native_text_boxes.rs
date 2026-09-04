use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use wolfppt_core::{
    add_slide_deeper_nested_group_text_box_with_text, add_slide_group_text_box_with_text,
    add_slide_nested_group_text_box_in_new_group_with_text,
    add_slide_nested_group_text_box_with_text, add_slide_text_box, add_slide_text_box_with_text,
};

#[pyfunction]
fn add_slide_text_box_json(
    input: &str,
    output: &str,
    slide_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_text_box(input, output, slide_index, x_emu, y_emu, cx_emu, cy_emu)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_text_box_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_text_box_with_text(
        input,
        output,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_group_text_box_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_group_text_box_with_text(
        input,
        output,
        slide_index,
        group_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_text_box_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_nested_group_text_box_with_text(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_deeper_nested_group_text_box_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_deeper_nested_group_text_box_with_text(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_text_box_in_new_group_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_nested_group_text_box_in_new_group_with_text(
        input,
        output,
        slide_index,
        group_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(add_slide_text_box_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_text_box_with_text_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_group_text_box_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_text_box_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_deeper_nested_group_text_box_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_text_box_in_new_group_with_text_json,
        module
    )?)?;
    Ok(())
}
