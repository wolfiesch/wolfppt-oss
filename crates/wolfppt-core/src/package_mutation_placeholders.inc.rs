pub fn add_slide_placeholder_shape(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    placeholder_type: Option<&str>,
    placeholder_orient: Option<&str>,
    placeholder_size: Option<&str>,
    placeholder_idx: Option<&str>,
) -> Result<PlaceholderShapeAddSummary, WolfPptError> {
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
    slide_xml = add_placeholder_shape_to_slide_xml(
        &slide_xml,
        shape_id,
        placeholder_type,
        placeholder_orient,
        placeholder_size,
        placeholder_idx,
    )?;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);

    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }

        writer.start_file(name.clone(), options)?;
        if name == slide_part {
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;

    let manifest = inspect_package(output_path)?;
    Ok(PlaceholderShapeAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        placeholder_type: placeholder_type.map(str::to_string),
        placeholder_idx: placeholder_idx.map(str::to_string),
        shape_id,
        part_count: manifest.parts.len(),
        has_vba: manifest.has_vba(),
    })
}

pub fn add_slide_placeholder_shapes(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    placeholders: &[PlaceholderShapeSpec],
) -> Result<PlaceholderShapeBatchAddSummary, WolfPptError> {
    if placeholders.is_empty() {
        return Err(WolfPptError::InvalidInput(
            "at least one placeholder shape is required".to_string(),
        ));
    }
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
    let mut shape_id = max_cnvpr_id(&slide_xml) + 1;
    let mut shape_ids = Vec::with_capacity(placeholders.len());
    for placeholder in placeholders {
        slide_xml = add_placeholder_shape_to_slide_xml(
            &slide_xml,
            shape_id,
            placeholder.placeholder_type.as_deref(),
            placeholder.placeholder_orient.as_deref(),
            placeholder.placeholder_size.as_deref(),
            placeholder.placeholder_idx.as_deref(),
        )?;
        shape_ids.push(shape_id);
        shape_id += 1;
    }

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);

    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }

        writer.start_file(name.clone(), options)?;
        if name == slide_part {
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;

    let manifest = inspect_package(output_path)?;
    Ok(PlaceholderShapeBatchAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_ids,
        part_count: manifest.parts.len(),
        has_vba: manifest.has_vba(),
    })
}

pub fn add_slide_layout_placeholders(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    layout_index: usize,
) -> Result<PlaceholderShapeBatchAddSummary, WolfPptError> {
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
    let layout_target = slide_layout_target_at_index(&mut archive, layout_index)?;
    let layout_part = resolve_target(&slide_part, &layout_target);
    let layout_xml = read_archive_text(&mut archive, &layout_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide layout part {layout_part} was not found"))
    })?;
    let placeholders = placeholder_specs_from_layout_xml(&layout_xml);
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let mut shape_id = max_cnvpr_id(&slide_xml) + 1;
    let mut shape_ids = Vec::with_capacity(placeholders.len());
    for placeholder in &placeholders {
        slide_xml = add_placeholder_shape_to_slide_xml(
            &slide_xml,
            shape_id,
            placeholder.placeholder_type.as_deref(),
            placeholder.placeholder_orient.as_deref(),
            placeholder.placeholder_size.as_deref(),
            placeholder.placeholder_idx.as_deref(),
        )?;
        shape_ids.push(shape_id);
        shape_id += 1;
    }

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);

    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }

        writer.start_file(name.clone(), options)?;
        if name == slide_part {
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;

    let manifest = inspect_package(output_path)?;
    Ok(PlaceholderShapeBatchAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        shape_ids,
        part_count: manifest.parts.len(),
        has_vba: manifest.has_vba(),
    })
}

