use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use wolfppt_core::{
    add_slide_connected_group_connector, add_slide_connected_group_connector_with_auto_shapes,
    add_slide_deeper_nested_group_auto_shape_with_text, add_slide_deeper_nested_group_connector,
    add_slide_deeper_nested_group_freeform_shape_with_text, add_slide_freeform_shape,
    add_slide_freeform_shape_with_text, add_slide_group_auto_shape_with_text,
    add_slide_group_connector, add_slide_group_freeform_shape_with_text, add_slide_group_shape,
    add_slide_group_shape_to_deeper_nested_group, add_slide_group_shape_to_nested_group,
    add_slide_nested_group_auto_shape_in_new_group_with_text,
    add_slide_nested_group_auto_shape_with_text, add_slide_nested_group_connector,
    add_slide_nested_group_connector_in_new_group,
    add_slide_nested_group_freeform_shape_in_new_group_with_text,
    add_slide_nested_group_freeform_shape_with_text, add_slide_nested_group_shape,
    apply_edit_batch, group_slide_existing_deeper_nested_group_children,
    group_slide_existing_group_children, group_slide_existing_nested_group_children, EditOperation,
    FreeformPathOperation,
};

mod native_core;
mod native_media;
mod native_shapes;
mod native_text_boxes;

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_group_auto_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_group_auto_shape_with_text(
        input,
        output,
        slide_index,
        group_index,
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
fn add_slide_nested_group_auto_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_nested_group_auto_shape_with_text(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
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
fn add_slide_deeper_nested_group_auto_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_deeper_nested_group_auto_shape_with_text(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
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
fn add_slide_nested_group_auto_shape_in_new_group_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> PyResult<String> {
    let summary = add_slide_nested_group_auto_shape_in_new_group_with_text(
        input,
        output,
        slide_index,
        group_index,
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
fn add_slide_group_connector_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_group_connector(
        input,
        output,
        slide_index,
        group_index,
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
fn add_slide_connected_group_connector_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
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
    let summary = add_slide_connected_group_connector(
        input,
        output,
        slide_index,
        group_index,
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
fn add_slide_connected_group_connector_with_auto_shapes_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
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
    let summary = add_slide_connected_group_connector_with_auto_shapes(
        input,
        output,
        slide_index,
        group_index,
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

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_connector_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_nested_group_connector(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
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
fn add_slide_deeper_nested_group_connector_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_deeper_nested_group_connector(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
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
fn add_slide_nested_group_connector_in_new_group_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_nested_group_connector_in_new_group(
        input,
        output,
        slide_index,
        group_index,
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
fn add_slide_group_shape_json(input: &str, output: &str, slide_index: usize) -> PyResult<String> {
    let summary = add_slide_group_shape(input, output, slide_index)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_nested_group_shape_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
) -> PyResult<String> {
    let summary = add_slide_nested_group_shape(input, output, slide_index, group_index)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_group_shape_to_nested_group_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
) -> PyResult<String> {
    let summary = add_slide_group_shape_to_nested_group(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_group_shape_to_deeper_nested_group_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
) -> PyResult<String> {
    let summary = add_slide_group_shape_to_deeper_nested_group(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn group_slide_existing_group_children_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    child_indices: Vec<usize>,
) -> PyResult<String> {
    let summary = group_slide_existing_group_children(
        input,
        output,
        slide_index,
        group_index,
        &child_indices,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn group_slide_existing_nested_group_children_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    child_indices: Vec<usize>,
) -> PyResult<String> {
    let summary = group_slide_existing_nested_group_children(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        &child_indices,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn group_slide_existing_deeper_nested_group_children_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    child_indices: Vec<usize>,
) -> PyResult<String> {
    let summary = group_slide_existing_deeper_nested_group_children(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        &child_indices,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_freeform_shape_json(
    input: &str,
    output: &str,
    slide_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations_json: &str,
) -> PyResult<String> {
    let operations: Vec<FreeformPathOperation> = serde_json::from_str(operations_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_freeform_shape(
        input,
        output,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        &operations,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_freeform_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations_json: &str,
    text: &str,
) -> PyResult<String> {
    let operations: Vec<FreeformPathOperation> = serde_json::from_str(operations_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_freeform_shape_with_text(
        input,
        output,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        &operations,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_group_freeform_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations_json: &str,
    text: &str,
) -> PyResult<String> {
    let operations: Vec<FreeformPathOperation> = serde_json::from_str(operations_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_group_freeform_shape_with_text(
        input,
        output,
        slide_index,
        group_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        &operations,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_freeform_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations_json: &str,
    text: &str,
) -> PyResult<String> {
    let operations: Vec<FreeformPathOperation> = serde_json::from_str(operations_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_nested_group_freeform_shape_with_text(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        &operations,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_deeper_nested_group_freeform_shape_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations_json: &str,
    text: &str,
) -> PyResult<String> {
    let operations: Vec<FreeformPathOperation> = serde_json::from_str(operations_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_deeper_nested_group_freeform_shape_with_text(
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
        path_w,
        path_h,
        &operations,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_freeform_shape_in_new_group_with_text_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations_json: &str,
    text: &str,
) -> PyResult<String> {
    let operations: Vec<FreeformPathOperation> = serde_json::from_str(operations_json)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = add_slide_nested_group_freeform_shape_in_new_group_with_text(
        input,
        output,
        slide_index,
        group_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        &operations,
        text,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn apply_edit_batch_json(input: &str, output: &str, edits_json: &str) -> PyResult<String> {
    let edits: Vec<EditOperation> =
        serde_json::from_str(edits_json).map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    let summary = apply_edit_batch(input, output, &edits)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pymodule]
fn wolfppt_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    native_core::register(module)?;
    native_media::register(module)?;
    native_shapes::register(module)?;
    native_text_boxes::register(module)?;
    module.add_function(wrap_pyfunction!(
        add_slide_group_auto_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_auto_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_deeper_nested_group_auto_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_auto_shape_in_new_group_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(add_slide_group_connector_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_connected_group_connector_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_connected_group_connector_with_auto_shapes_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_connector_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_deeper_nested_group_connector_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_connector_in_new_group_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(add_slide_group_shape_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_nested_group_shape_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_group_shape_to_nested_group_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_group_shape_to_deeper_nested_group_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        group_slide_existing_group_children_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        group_slide_existing_nested_group_children_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        group_slide_existing_deeper_nested_group_children_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(add_slide_freeform_shape_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_freeform_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_group_freeform_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_freeform_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_deeper_nested_group_freeform_shape_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_freeform_shape_in_new_group_with_text_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(apply_edit_batch_json, module)?)?;
    Ok(())
}
