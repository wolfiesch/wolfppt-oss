struct ImageInsertionPlan {
    image_payload: Vec<u8>,
    media_part: String,
    rels_part: String,
    relationship_id: String,
    rels_xml: String,
    content_types_xml: String,
    reuse_existing_media: bool,
}

fn plan_image_insertion<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_part: &str,
    image_path: &Path,
) -> Result<ImageInsertionPlan, WolfPptError> {
    let extension = image_extension(image_path)?;
    let content_type = image_content_type(&extension)?;
    let image_payload = std::fs::read(image_path)?;
    let existing_media_part = matching_image_media_part(archive, &extension, &image_payload)?;
    let reuse_existing_media = existing_media_part.is_some();
    let media_part = match existing_media_part {
        Some(part) => part,
        None => next_media_part(archive, &extension)?,
    };
    let rels_part = relationship_part_name(slide_part);
    let image_target = format!("../media/{}", media_part.rsplit('/').next().unwrap_or(""));
    let rels_xml = read_archive_text(archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let content_types_xml = read_archive_text(archive, "[Content_Types].xml")?.ok_or_else(|| {
        WolfPptError::InvalidInput("[Content_Types].xml was not found".to_string())
    })?;
    let existing_relationship_id = if reuse_existing_media {
        existing_image_relationship_id(&rels_xml, &image_target)
    } else {
        None
    };
    let reuse_existing_relationship = existing_relationship_id.is_some();
    let relationship_id =
        existing_relationship_id.unwrap_or_else(|| next_relationship_id(rels_xml.as_bytes()));
    let rels_xml = if reuse_existing_relationship {
        rels_xml
    } else {
        add_image_relationship(&rels_xml, &relationship_id, &image_target)?
    };
    let content_types_xml = ensure_default_content_type(&content_types_xml, &extension, content_type)?;

    Ok(ImageInsertionPlan {
        image_payload,
        media_part,
        rels_part,
        relationship_id,
        rels_xml,
        content_types_xml,
        reuse_existing_media,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_image(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    image_path: impl AsRef<Path>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<ImageAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let image_path = image_path.as_ref();
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
    let image_plan = plan_image_insertion(&mut archive, &slide_part, image_path)?;
    let media_part = image_plan.media_part.clone();
    let rels_part = image_plan.rels_part.clone();
    let relationship_id = image_plan.relationship_id.clone();
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_picture_to_slide_xml(
        &slide_xml,
        &relationship_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )?;
    let rels_xml = image_plan.rels_xml;
    let content_types_xml = image_plan.content_types_xml;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }
        if !image_plan.reuse_existing_media && name == media_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    if !image_plan.reuse_existing_media {
        update_package_facts(&media_part, &mut part_count, &mut has_vba);
        writer.start_file(media_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(image_plan.image_payload), &mut writer)?;
    }
    writer.finish()?;

    Ok(ImageAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        relationship_id,
        image_part: media_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_image(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    image_path: impl AsRef<Path>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<ImageAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let image_path = image_path.as_ref();
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
    let image_plan = plan_image_insertion(&mut archive, &slide_part, image_path)?;
    let media_part = image_plan.media_part.clone();
    let rels_part = image_plan.rels_part.clone();
    let relationship_id = image_plan.relationship_id.clone();
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_picture_to_group_shape_xml(
        &slide_xml,
        group_index,
        &relationship_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )?;
    let rels_xml = image_plan.rels_xml;
    let content_types_xml = image_plan.content_types_xml;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }
        if !image_plan.reuse_existing_media && name == media_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    if !image_plan.reuse_existing_media {
        update_package_facts(&media_part, &mut part_count, &mut has_vba);
        writer.start_file(media_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(image_plan.image_payload), &mut writer)?;
    }
    writer.finish()?;

    Ok(ImageAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        relationship_id,
        image_part: media_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_image(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    image_path: impl AsRef<Path>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<ImageAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let image_path = image_path.as_ref();
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
    let image_plan = plan_image_insertion(&mut archive, &slide_part, image_path)?;
    let media_part = image_plan.media_part.clone();
    let rels_part = image_plan.rels_part.clone();
    let relationship_id = image_plan.relationship_id.clone();
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_picture_to_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        &relationship_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )?;
    let rels_xml = image_plan.rels_xml;
    let content_types_xml = image_plan.content_types_xml;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }
        if !image_plan.reuse_existing_media && name == media_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    if !image_plan.reuse_existing_media {
        update_package_facts(&media_part, &mut part_count, &mut has_vba);
        writer.start_file(media_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(image_plan.image_payload), &mut writer)?;
    }
    writer.finish()?;

    Ok(ImageAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        relationship_id,
        image_part: media_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_deeper_nested_group_image(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    image_path: impl AsRef<Path>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<ImageAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let image_path = image_path.as_ref();
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
    let image_plan = plan_image_insertion(&mut archive, &slide_part, image_path)?;
    let media_part = image_plan.media_part.clone();
    let rels_part = image_plan.rels_part.clone();
    let relationship_id = image_plan.relationship_id.clone();
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_picture_to_deeper_nested_group_shape_xml(
        &slide_xml,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        &relationship_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )?;
    let rels_xml = image_plan.rels_xml;
    let content_types_xml = image_plan.content_types_xml;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }
        if !image_plan.reuse_existing_media && name == media_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    if !image_plan.reuse_existing_media {
        update_package_facts(&media_part, &mut part_count, &mut has_vba);
        writer.start_file(media_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(image_plan.image_payload), &mut writer)?;
    }
    writer.finish()?;

    Ok(ImageAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        relationship_id,
        image_part: media_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_image_in_new_group(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    image_path: impl AsRef<Path>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<ImageAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let image_path = image_path.as_ref();
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
    let image_plan = plan_image_insertion(&mut archive, &slide_part, image_path)?;
    let media_part = image_plan.media_part.clone();
    let rels_part = image_plan.rels_part.clone();
    let relationship_id = image_plan.relationship_id.clone();
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let group_shape_id = max_cnvpr_id(&slide_xml) + 1;
    let shape_id = group_shape_id + 1;
    slide_xml = add_picture_to_new_nested_group_shape_xml(
        &slide_xml,
        group_index,
        &relationship_id,
        group_shape_id,
        shape_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )?;
    let rels_xml = image_plan.rels_xml;
    let content_types_xml = image_plan.content_types_xml;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }
        if !image_plan.reuse_existing_media && name == media_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    if !image_plan.reuse_existing_media {
        update_package_facts(&media_part, &mut part_count, &mut has_vba);
        writer.start_file(media_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(image_plan.image_payload), &mut writer)?;
    }
    writer.finish()?;

    Ok(ImageAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        relationship_id,
        image_part: media_part,
        shape_id,
        part_count,
        has_vba,
    })
}
