fn write_package_with_replaced_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    output_path: &Path,
    target_part: &str,
    replacement_payload: &[u8],
) -> Result<(usize, bool), WolfPptError> {
    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        if name == target_part {
            let options = SimpleFileOptions::default().compression_method(file.compression());
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(replacement_payload), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }
    writer.finish()?;

    Ok((part_count, has_vba))
}

pub fn add_slide_group_shape(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
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
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_group_shape_to_slide_xml(&slide_xml, shape_id)?;

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

pub fn add_slide_nested_group_shape(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
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
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_group_shape_to_group_shape_xml(&slide_xml, group_index, shape_id)?;

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

pub fn add_slide_group_shape_to_nested_group(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
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
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_group_shape_to_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
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

#[allow(clippy::too_many_arguments)]
pub fn add_slide_freeform_shape(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
) -> Result<FreeformShapeAddSummary, WolfPptError> {
    add_slide_freeform_shape_impl(
        input_path,
        output_path,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        operations,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_freeform_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: &str,
) -> Result<FreeformShapeAddSummary, WolfPptError> {
    add_slide_freeform_shape_impl(
        input_path,
        output_path,
        slide_index,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        operations,
        Some(text),
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_freeform_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: &str,
) -> Result<FreeformShapeAddSummary, WolfPptError> {
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
    slide_xml = add_freeform_shape_to_group_shape_xml(
        &slide_xml,
        group_index,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        operations,
        Some(text),
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(FreeformShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_freeform_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: &str,
) -> Result<FreeformShapeAddSummary, WolfPptError> {
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
    slide_xml = add_freeform_shape_to_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        operations,
        Some(text),
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(FreeformShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_deeper_nested_group_freeform_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
    operations: &[FreeformPathOperation],
    text: &str,
) -> Result<FreeformShapeAddSummary, WolfPptError> {
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
    slide_xml = add_freeform_shape_to_deeper_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        operations,
        Some(text),
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(FreeformShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_freeform_shape_in_new_group_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: &str,
) -> Result<FreeformShapeAddSummary, WolfPptError> {
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
    let slide_xml = add_group_shape_with_freeform_to_group_shape_xml(
        &slide_xml,
        group_index,
        group_shape_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        path_w,
        path_h,
        operations,
        Some(text),
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;

    Ok(FreeformShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
fn add_slide_freeform_shape_impl(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<FreeformShapeAddSummary, WolfPptError> {
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
    slide_xml = add_freeform_shape_to_slide_xml(
        &slide_xml, shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;

    Ok(FreeformShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_auto_shape(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
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
        None,
        &[],
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_auto_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
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
        Some(text),
        &[],
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_auto_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<AutoShapeAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let display_name = auto_shape_display_name(preset_geometry)?;
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
    slide_xml = add_auto_shape_to_group_shape_xml(
        &slide_xml,
        group_index,
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
        &[],
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(AutoShapeAddSummary {
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
pub fn add_slide_nested_group_auto_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<AutoShapeAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let display_name = auto_shape_display_name(preset_geometry)?;
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
    slide_xml = add_auto_shape_to_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
        &[],
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(AutoShapeAddSummary {
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
pub fn add_slide_deeper_nested_group_auto_shape_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
) -> Result<AutoShapeAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let display_name = auto_shape_display_name(preset_geometry)?;
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
    slide_xml = add_auto_shape_to_deeper_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        Some(text),
        &[],
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(AutoShapeAddSummary {
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
pub fn add_slide_nested_group_auto_shape_in_new_group_with_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<AutoShapeAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let display_name = auto_shape_display_name(preset_geometry)?;
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
    let slide_xml = add_group_shape_with_auto_shape_to_group_shape_xml(
        &slide_xml,
        group_index,
        group_shape_id,
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(AutoShapeAddSummary {
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
fn add_slide_auto_shape_impl(
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
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let display_name = auto_shape_display_name(preset_geometry)?;
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
    slide_xml = add_auto_shape_to_slide_xml(
        &slide_xml,
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
        adjustment_guides,
    )?;

    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, slide_xml.as_bytes())?;
    Ok(AutoShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        preset_geometry: preset_geometry.to_string(),
        shape_id,
        part_count,
        has_vba,
    })
}

fn delete_shape_at_index_in_slide(
    xml: &[u8],
    target_shape_index: usize,
) -> Result<(Vec<u8>, usize, std::collections::BTreeSet<String>), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    let mut writer = Writer::new(Cursor::new(Vec::new()));
    let mut in_shape_tree = false;
    let mut shape_tree_depth = 0usize;
    let mut skipping_depth = 0usize;
    let mut shape_index = 0usize;
    let mut deleted = false;
    let mut removed_relationship_ids = std::collections::BTreeSet::new();

    loop {
        let event = reader.read_event()?;
        if skipping_depth > 0 {
            match event {
                Event::Start(start) => {
                    collect_relationship_ids(
                        &start,
                        reader.decoder(),
                        &mut removed_relationship_ids,
                    );
                    skipping_depth += 1;
                }
                Event::Empty(empty) => collect_relationship_ids(
                    &empty,
                    reader.decoder(),
                    &mut removed_relationship_ids,
                ),
                Event::End(_) => skipping_depth -= 1,
                Event::Eof => {
                    return Err(WolfPptError::XmlText(
                        "unexpected EOF while deleting shape".to_string(),
                    ));
                }
                _ => {}
            }
            continue;
        }

        match event {
            Event::Start(start) => {
                let qname = start.name();
                let name = local_name(qname.as_ref());
                if !in_shape_tree && name == b"spTree" {
                    in_shape_tree = true;
                    shape_tree_depth = 1;
                    writer.write_event(Event::Start(start.into_owned()))?;
                } else if in_shape_tree
                    && shape_tree_depth == 1
                    && is_shape_tree_shape(name)
                {
                    if shape_index == target_shape_index {
                        collect_relationship_ids(
                            &start,
                            reader.decoder(),
                            &mut removed_relationship_ids,
                        );
                        skipping_depth = 1;
                        deleted = true;
                    } else {
                        writer.write_event(Event::Start(start.into_owned()))?;
                        shape_tree_depth += 1;
                    }
                    shape_index += 1;
                } else {
                    if in_shape_tree {
                        shape_tree_depth += 1;
                    }
                    writer.write_event(Event::Start(start.into_owned()))?;
                }
            }
            Event::Empty(empty) => {
                let qname = empty.name();
                let name = local_name(qname.as_ref());
                if in_shape_tree && shape_tree_depth == 1 && is_shape_tree_shape(name) {
                    if shape_index == target_shape_index {
                        collect_relationship_ids(
                            &empty,
                            reader.decoder(),
                            &mut removed_relationship_ids,
                        );
                        deleted = true;
                    } else {
                        writer.write_event(Event::Empty(empty.into_owned()))?;
                    }
                    shape_index += 1;
                } else {
                    writer.write_event(Event::Empty(empty.into_owned()))?;
                }
            }
            Event::End(end) => {
                let qname = end.name();
                let name = local_name(qname.as_ref());
                if in_shape_tree && shape_tree_depth == 1 && name == b"spTree" {
                    in_shape_tree = false;
                    shape_tree_depth = 0;
                } else if in_shape_tree {
                    shape_tree_depth = shape_tree_depth.saturating_sub(1);
                }
                writer.write_event(Event::End(end.into_owned()))?;
            }
            Event::Eof => break,
            other => writer.write_event(other.into_owned())?,
        }
    }

    if !deleted {
        return Err(WolfPptError::InvalidInput(format!(
            "shape index {target_shape_index} was not found"
        )));
    }
    let rewritten = writer.into_inner().into_inner();
    let surviving_relationship_ids = relationship_ids_in_xml(&rewritten);
    removed_relationship_ids.retain(|id| !surviving_relationship_ids.contains(id));
    Ok((rewritten, 1, removed_relationship_ids))
}

fn is_shape_tree_shape(name: &[u8]) -> bool {
    matches!(
        name,
        b"sp" | b"grpSp" | b"graphicFrame" | b"cxnSp" | b"pic"
    )
}

fn collect_relationship_ids(
    event: &BytesStart<'_>,
    decoder: quick_xml::encoding::Decoder,
    ids: &mut std::collections::BTreeSet<String>,
) {
    for attr in event.attributes().flatten() {
        let key = attr.key.as_ref();
        if !key.contains(&b':') || !matches!(local_name(key), b"id" | b"embed" | b"link") {
            continue;
        }
        if let Ok(value) = attr.decode_and_unescape_value(decoder) {
            ids.insert(value.into_owned());
        }
    }
}

fn relationship_ids_in_xml(xml: &[u8]) -> std::collections::BTreeSet<String> {
    let mut reader = Reader::from_reader(xml);
    let mut ids = std::collections::BTreeSet::new();
    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) | Ok(Event::Empty(event)) => {
                collect_relationship_ids(&event, reader.decoder(), &mut ids);
            }
            Ok(Event::Eof) | Err(_) => break,
            _ => {}
        }
    }
    ids
}

fn remove_relationships_by_id(
    xml: &[u8],
    relationship_ids: &std::collections::BTreeSet<String>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    if relationship_ids.is_empty() {
        return Ok((xml.to_vec(), 0));
    }
    let mut reader = Reader::from_reader(xml);
    let mut writer = Writer::new(Cursor::new(Vec::new()));
    let mut skipping_depth = 0usize;
    let mut removed = 0usize;
    loop {
        let event = reader.read_event()?;
        if skipping_depth > 0 {
            match event {
                Event::Start(_) => skipping_depth += 1,
                Event::End(_) => skipping_depth -= 1,
                Event::Eof => {
                    return Err(WolfPptError::XmlText(
                        "unexpected EOF while removing relationship".to_string(),
                    ));
                }
                _ => {}
            }
            continue;
        }
        match event {
            Event::Start(start) if local_name(start.name().as_ref()) == b"Relationship" => {
                if relationship_ids.contains(&relationship_id(&start, reader.decoder())) {
                    skipping_depth = 1;
                    removed += 1;
                } else {
                    writer.write_event(Event::Start(start.into_owned()))?;
                }
            }
            Event::Empty(empty) if local_name(empty.name().as_ref()) == b"Relationship" => {
                if relationship_ids.contains(&relationship_id(&empty, reader.decoder())) {
                    removed += 1;
                } else {
                    writer.write_event(Event::Empty(empty.into_owned()))?;
                }
            }
            Event::Eof => break,
            other => writer.write_event(other.into_owned())?,
        }
    }
    Ok((writer.into_inner().into_inner(), removed))
}

fn relationship_id(event: &BytesStart<'_>, decoder: quick_xml::encoding::Decoder) -> String {
    event
        .attributes()
        .flatten()
        .find(|attr| local_name(attr.key.as_ref()) == b"Id")
        .and_then(|attr| attr.decode_and_unescape_value(decoder).ok())
        .map(|value| value.into_owned())
        .unwrap_or_default()
}
