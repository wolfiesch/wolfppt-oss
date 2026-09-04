use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use wolfppt_core::{
    add_slide_auto_shape, add_slide_auto_shape_with_text,
    add_slide_auto_shape_with_text_and_adjustments, add_slide_connected_connector,
    add_slide_connected_connector_with_auto_shapes, add_slide_connector,
    add_slide_layout_placeholders, add_slide_placeholder_shape, add_slide_placeholder_shapes,
    PlaceholderShapeSpec,
};

#[pyfunction]
fn add_slide_placeholder_shape_json(
    input: &str,
    output: &str,
    slide_index: usize,
    placeholder_type: Option<&str>,
    placeholder_orient: Option<&str>,
    placeholder_size: Option<&str>,
    placeholder_idx: Option<&str>,
) -> PyResult<String> {
    let summary = add_slide_placeholder_shape(
        input,
        output,
        slide_index,
        placeholder_type,
        placeholder_orient,
        placeholder_size,
        placeholder_idx,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_placeholder_shapes_json(
    input: &str,
    output: &str,
    slide_index: usize,
    placeholders_json: &str,
) -> PyResult<String> {
    let placeholders: Vec<PlaceholderShapeSpec> = serde_json::from_str(placeholders_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_placeholder_shapes(input, output, slide_index, &placeholders)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_layout_placeholders_json(
    input: &str,
    output: &str,
    slide_index: usize,
    layout_index: usize,
) -> PyResult<String> {
    let summary = add_slide_layout_placeholders(input, output, slide_index, layout_index)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_auto_shape_json(
    input: &str,
    output: &str,
    slide_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_auto_shape(
        input,
        output,
        slide_index,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_auto_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_auto_shape_with_text(
        input,
        output,
        slide_index,
        preset_geometry,
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
fn add_slide_auto_shape_with_options_json(
    input: &str,
    output: &str,
    slide_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides_json: &str,
) -> PyResult<String> {
    let adjustment_guides: Vec<(String, i64)> = serde_json::from_str(adjustment_guides_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_auto_shape_with_text_and_adjustments(
        input,
        output,
        slide_index,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
        &adjustment_guides,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_connector_json(
    input: &str,
    output: &str,
    slide_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_connector(
        input,
        output,
        slide_index,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_connected_connector_json(
    input: &str,
    output: &str,
    slide_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
    begin_shape_id: Option<u64>,
    begin_cxn_pt_idx: Option<u64>,
    end_shape_id: Option<u64>,
    end_cxn_pt_idx: Option<u64>,
) -> PyResult<String> {
    let summary = add_slide_connected_connector(
        input,
        output,
        slide_index,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        begin_shape_id,
        begin_cxn_pt_idx,
        end_shape_id,
        end_cxn_pt_idx,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_connected_connector_with_auto_shapes_json(
    input: &str,
    output: &str,
    slide_index: usize,
    begin_preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    begin_cx_emu: u64,
    begin_cy_emu: u64,
    end_preset_geometry: &str,
    end_x_emu: u64,
    end_y_emu: u64,
    end_cx_emu: u64,
    end_cy_emu: u64,
    connector_preset_geometry: &str,
    connector_begin_x_emu: u64,
    connector_begin_y_emu: u64,
    connector_end_x_emu: u64,
    connector_end_y_emu: u64,
    begin_cxn_pt_idx: u64,
    end_cxn_pt_idx: u64,
) -> PyResult<String> {
    let summary = add_slide_connected_connector_with_auto_shapes(
        input,
        output,
        slide_index,
        begin_preset_geometry,
        begin_x_emu,
        begin_y_emu,
        begin_cx_emu,
        begin_cy_emu,
        end_preset_geometry,
        end_x_emu,
        end_y_emu,
        end_cx_emu,
        end_cy_emu,
        connector_preset_geometry,
        connector_begin_x_emu,
        connector_begin_y_emu,
        connector_end_x_emu,
        connector_end_y_emu,
        begin_cxn_pt_idx,
        end_cxn_pt_idx,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(add_slide_placeholder_shape_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_placeholder_shapes_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_layout_placeholders_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(add_slide_auto_shape_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_auto_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_auto_shape_with_options_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(add_slide_connector_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_connected_connector_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_connected_connector_with_auto_shapes_json,
        module
    )?)?;
    Ok(())
}
