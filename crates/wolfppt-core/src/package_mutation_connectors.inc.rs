#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_connector(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> Result<ConnectorAddSummary, WolfPptError> {
    add_slide_group_connector_impl(
        input_path,
        output_path,
        slide_index,
        group_index,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        None,
        None,
        None,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_connected_group_connector(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
) -> Result<ConnectorAddSummary, WolfPptError> {
    add_slide_group_connector_impl(
        input_path,
        output_path,
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
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_connected_group_connector_with_auto_shapes(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
    connector_geometry: &str,
    connector_begin_x_emu: u64,
    connector_begin_y_emu: u64,
    connector_end_x_emu: u64,
    connector_end_y_emu: u64,
    begin_cxn_pt_idx: u64,
    end_cxn_pt_idx: u64,
) -> Result<ConnectorAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let begin_display_name = auto_shape_display_name(begin_preset_geometry)?;
    let end_display_name = auto_shape_display_name(end_preset_geometry)?;
    connector_preset_geometry(connector_geometry)?;
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let begin_shape_id = max_cnvpr_id(&slide_xml) + 1;
    let end_shape_id = begin_shape_id + 1;
    let connector_shape_id = end_shape_id + 1;
    let slide_xml = add_connected_connector_with_auto_shapes_to_group_shape_xml(
        &slide_xml,
        group_index,
        begin_shape_id,
        begin_display_name,
        begin_preset_geometry,
        begin_x_emu,
        begin_y_emu,
        begin_cx_emu,
        begin_cy_emu,
        end_shape_id,
        end_display_name,
        end_preset_geometry,
        end_x_emu,
        end_y_emu,
        end_cx_emu,
        end_cy_emu,
        connector_shape_id,
        connector_geometry,
        connector_begin_x_emu,
        connector_begin_y_emu,
        connector_end_x_emu,
        connector_end_y_emu,
        begin_cxn_pt_idx,
        end_cxn_pt_idx,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(ConnectorAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        preset_geometry: connector_geometry.to_string(),
        shape_id: connector_shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
fn add_slide_group_connector_impl(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
) -> Result<ConnectorAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    connector_preset_geometry(preset_geometry)?;
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let begin_connection = begin_shape_id.map(|target_shape_id| ConnectorConnectionSpec {
        target_shape_id,
        cxn_pt_idx: begin_cxn_pt_idx.unwrap_or(0),
    });
    let end_connection = end_shape_id.map(|target_shape_id| ConnectorConnectionSpec {
        target_shape_id,
        cxn_pt_idx: end_cxn_pt_idx.unwrap_or(0),
    });
    slide_xml = add_connector_to_group_shape_xml(
        &slide_xml,
        group_index,
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        begin_connection,
        end_connection,
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(ConnectorAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        preset_geometry: preset_geometry.to_string(),
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_connector(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> Result<ConnectorAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    connector_preset_geometry(preset_geometry)?;
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_connector_to_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(ConnectorAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        preset_geometry: preset_geometry.to_string(),
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_deeper_nested_group_connector(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> Result<ConnectorAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    connector_preset_geometry(preset_geometry)?;
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_connector_to_deeper_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(ConnectorAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        preset_geometry: preset_geometry.to_string(),
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_connector_in_new_group(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> Result<ConnectorAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    connector_preset_geometry(preset_geometry)?;
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let group_shape_id = max_cnvpr_id(&slide_xml) + 1;
    let shape_id = group_shape_id + 1;
    let slide_xml = add_group_shape_with_connector_to_group_shape_xml(
        &slide_xml,
        group_index,
        group_shape_id,
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(ConnectorAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        preset_geometry: preset_geometry.to_string(),
        shape_id,
        part_count,
        has_vba,
    })
}
