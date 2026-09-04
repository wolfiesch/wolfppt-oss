use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::path::Path;
use wolfppt_core::{
    add_slide_deeper_nested_group_image, add_slide_deeper_nested_group_ole_object,
    add_slide_group_image, add_slide_group_ole_object, add_slide_image, add_slide_movie,
    add_slide_nested_group_image, add_slide_nested_group_image_in_new_group,
    add_slide_nested_group_ole_object, add_slide_nested_group_ole_object_in_new_group,
    add_slide_ole_object, replace_slide_image, replace_slide_image_at_index,
};

#[pyfunction]
fn replace_slide_image_json(
    input: &str,
    output: &str,
    relationship_id: &str,
    image_path: &str,
) -> PyResult<String> {
    let summary = replace_slide_image(input, output, relationship_id, image_path)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn replace_slide_image_at_index_json(
    input: &str,
    output: &str,
    slide_index: usize,
    relationship_id: &str,
    image_path: &str,
) -> PyResult<String> {
    let summary =
        replace_slide_image_at_index(input, output, slide_index, relationship_id, image_path)
            .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
fn add_slide_image_json(
    input: &str,
    output: &str,
    slide_index: usize,
    image_path: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_image(
        input,
        output,
        slide_index,
        image_path,
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
fn add_slide_group_image_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    image_path: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_group_image(
        input,
        output,
        slide_index,
        group_index,
        image_path,
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
fn add_slide_nested_group_image_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    image_path: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_nested_group_image(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        image_path,
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
fn add_slide_deeper_nested_group_image_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    image_path: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_deeper_nested_group_image(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        image_path,
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
fn add_slide_nested_group_image_in_new_group_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    image_path: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> PyResult<String> {
    let summary = add_slide_nested_group_image_in_new_group(
        input,
        output,
        slide_index,
        group_index,
        image_path,
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
fn add_slide_movie_json(
    input: &str,
    output: &str,
    slide_index: usize,
    movie_path: &str,
    poster_frame_path: Option<&str>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    mime_type: &str,
) -> PyResult<String> {
    let poster_frame_path = poster_frame_path.map(Path::new);
    let summary = add_slide_movie(
        input,
        output,
        slide_index,
        movie_path,
        poster_frame_path,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        mime_type,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_ole_object_json(
    input: &str,
    output: &str,
    slide_index: usize,
    object_path: &str,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&str>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> PyResult<String> {
    let icon_path = icon_path.map(Path::new);
    let summary = add_slide_ole_object(
        input,
        output,
        slide_index,
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_group_ole_object_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    object_path: &str,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&str>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> PyResult<String> {
    let icon_path = icon_path.map(Path::new);
    let summary = add_slide_group_ole_object(
        input,
        output,
        slide_index,
        group_index,
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_ole_object_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    object_path: &str,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&str>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> PyResult<String> {
    let icon_path = icon_path.map(Path::new);
    let summary = add_slide_nested_group_ole_object(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_deeper_nested_group_ole_object_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    object_path: &str,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&str>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> PyResult<String> {
    let icon_path = icon_path.map(Path::new);
    let summary = add_slide_deeper_nested_group_ole_object(
        input,
        output,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn add_slide_nested_group_ole_object_in_new_group_json(
    input: &str,
    output: &str,
    slide_index: usize,
    group_index: usize,
    object_path: &str,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&str>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> PyResult<String> {
    let icon_path = icon_path.map(Path::new);
    let summary = add_slide_nested_group_ole_object_in_new_group(
        input,
        output,
        slide_index,
        group_index,
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
    .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    serde_json::to_string_pretty(&summary).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(replace_slide_image_json, module)?)?;
    module.add_function(wrap_pyfunction!(replace_slide_image_at_index_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_image_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_group_image_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_nested_group_image_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_deeper_nested_group_image_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_image_in_new_group_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(add_slide_movie_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_ole_object_json, module)?)?;
    module.add_function(wrap_pyfunction!(add_slide_group_ole_object_json, module)?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_ole_object_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_deeper_nested_group_ole_object_json,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        add_slide_nested_group_ole_object_in_new_group_json,
        module
    )?)?;
    Ok(())
}
