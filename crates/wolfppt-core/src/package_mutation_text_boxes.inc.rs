#[allow(clippy::too_many_arguments)]
pub fn add_slide_text_box(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<TextBoxAddSummary, WolfPptError> {
    add_slide_text_box_impl(
        input_path,
        output_path,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_text_box_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<TextBoxAddSummary, WolfPptError> {
    add_slide_text_box_impl(
        input_path,
        output_path,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_text_box_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<TextBoxAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
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
    slide_xml = add_text_box_to_group_shape_xml(
        &slide_xml,
        group_index,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(TextBoxAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_text_box_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<TextBoxAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
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
    slide_xml = add_text_box_to_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(TextBoxAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_deeper_nested_group_text_box_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<TextBoxAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
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
    slide_xml = add_text_box_to_deeper_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(TextBoxAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_text_box_in_new_group_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<TextBoxAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
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
    let slide_xml = add_group_shape_with_text_box_to_group_shape_xml(
        &slide_xml,
        group_index,
        group_shape_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;

    Ok(TextBoxAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_auto_shape_with_text_and_adjustments(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides: &[(String, i64)],
) -> Result<AutoShapeAddSummary, WolfPptError> {
    add_slide_auto_shape_impl(
        input_path,
        output_path,
        slide_index,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
        adjustment_guides,
    )
}

#[allow(clippy::too_many_arguments)]
fn add_slide_text_box_impl(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<TextBoxAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
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
    slide_xml = add_text_box_to_slide_xml(&slide_xml, shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(TextBoxAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}
