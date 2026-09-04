pub fn group_slide_existing_group_children(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    child_indices: &[usize],
) -> Result<GroupShapeAddSummary, WolfPptError> {
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
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let slide_xml =
        group_existing_group_children_xml(&slide_xml, group_index, None, child_indices, shape_id)?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;
    Ok(GroupShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

pub fn add_slide_group_shape_to_deeper_nested_group(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
) -> Result<GroupShapeAddSummary, WolfPptError> {
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
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let slide_xml = add_group_shape_to_deeper_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        shape_id,
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;
    Ok(GroupShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

pub fn group_slide_existing_nested_group_children(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    child_indices: &[usize],
) -> Result<GroupShapeAddSummary, WolfPptError> {
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
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let slide_xml = group_existing_group_children_xml(
        &slide_xml,
        group_index,
        Some((nested_group_child_index, None)),
        child_indices,
        shape_id,
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;
    Ok(GroupShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

pub fn group_slide_existing_deeper_nested_group_children(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    child_indices: &[usize],
) -> Result<GroupShapeAddSummary, WolfPptError> {
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
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let slide_xml = group_existing_group_children_xml(
        &slide_xml,
        group_index,
        Some((nested_group_child_index, Some(deeper_group_child_index))),
        child_indices,
        shape_id,
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;
    Ok(GroupShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}
