const DEFAULT_MOVIE_POSTER_PNG: &[u8] = &[
    137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6,
    0, 0, 0, 31, 21, 196, 137, 0, 0, 0, 10, 73, 68, 65, 84, 120, 156, 99, 96, 0, 0, 2, 0, 1, 0,
    255, 255, 3, 0, 0, 6, 0, 5, 87, 191, 171, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130,
];

#[allow(clippy::too_many_arguments)]
pub fn add_slide_movie(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    movie_path: impl AsRef<Path>,
    poster_frame_path: Option<&Path>,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    mime_type: &str,
) -> Result<MovieAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let movie_path = movie_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let movie_extension = media_extension(movie_path, "movie")?;
    let movie_payload = std::fs::read(movie_path)?;
    let (poster_extension, poster_content_type, poster_payload) = match poster_frame_path {
        Some(path) => {
            let extension = image_extension(path)?;
            let content_type = image_content_type(&extension)?.to_string();
            (extension, content_type, std::fs::read(path)?)
        }
        None => (
            "png".to_string(),
            "image/png".to_string(),
            DEFAULT_MOVIE_POSTER_PNG.to_vec(),
        ),
    };

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let media_part = next_numbered_media_part(&mut archive, "media", &movie_extension)?;
    let poster_part = next_numbered_media_part(&mut archive, "image", &poster_extension)?;
    let rels_part = relationship_part_name(&slide_part);
    let media_target = format!("../media/{}", media_part.rsplit('/').next().unwrap_or(""));
    let poster_target = format!("../media/{}", poster_part.rsplit('/').next().unwrap_or(""));
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let rels_xml =
        read_archive_text(&mut archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let content_types_xml =
        read_archive_text(&mut archive, "[Content_Types].xml")?.ok_or_else(|| {
            WolfPptError::InvalidInput("[Content_Types].xml was not found".to_string())
        })?;

    let media_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &media_relationship_id,
        "http://schemas.microsoft.com/office/2007/relationships/media",
        &media_target,
    )?;
    let video_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &video_relationship_id,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video",
        &media_target,
    )?;
    let poster_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml =
        add_image_relationship(&rels_xml, &poster_relationship_id, &poster_target)?;

    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let movie_name = movie_path
        .file_name()
        .and_then(|value| value.to_str())
        .map(str::to_string)
        .unwrap_or_else(|| format!("Movie {shape_id}"));
    slide_xml = add_movie_to_slide_xml(
        &slide_xml,
        &video_relationship_id,
        &media_relationship_id,
        &poster_relationship_id,
        shape_id,
        &movie_name,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    )?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &movie_extension, mime_type)?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &poster_extension, &poster_content_type)?;

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
        if name == media_part || name == poster_part {
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
        writer.start_file(rels_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    update_package_facts(&media_part, &mut part_count, &mut has_vba);
    writer.start_file(media_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(movie_payload), &mut writer)?;
    update_package_facts(&poster_part, &mut part_count, &mut has_vba);
    writer.start_file(poster_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(poster_payload), &mut writer)?;
    writer.finish()?;

    Ok(MovieAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        media_relationship_id,
        video_relationship_id,
        poster_relationship_id,
        media_part,
        poster_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::Slide,
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
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::Group { group_index },
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
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::NestedGroup {
            group_index,
            nested_group_child_index,
        },
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
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_deeper_nested_group_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::DeeperNestedGroup {
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        },
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
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_ole_object_in_new_group(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::NewNestedGroup { group_index },
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
}

enum OleObjectInsertTarget {
    Slide,
    Group {
        group_index: usize,
    },
    NestedGroup {
        group_index: usize,
        nested_group_child_index: usize,
    },
    DeeperNestedGroup {
        group_index: usize,
        nested_group_child_index: usize,
        deeper_group_child_index: usize,
    },
    NewNestedGroup {
        group_index: usize,
    },
}

#[allow(clippy::too_many_arguments)]
fn add_slide_ole_object_with_target(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    target: OleObjectInsertTarget,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let object_path = object_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let object_payload = std::fs::read(object_path)?;
    let (icon_extension, icon_content_type, icon_payload) = match icon_path {
        Some(path) => {
            let extension = image_extension(path)?;
            let content_type = image_content_type(&extension)?.to_string();
            (extension, content_type, std::fs::read(path)?)
        }
        None => (
            "png".to_string(),
            "image/png".to_string(),
            DEFAULT_MOVIE_POSTER_PNG.to_vec(),
        ),
    };

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let ole_part = next_embedding_part(&mut archive)?;
    let icon_part = next_numbered_media_part(&mut archive, "image", &icon_extension)?;
    let rels_part = relationship_part_name(&slide_part);
    let ole_target = format!(
        "../embeddings/{}",
        ole_part.rsplit('/').next().unwrap_or("")
    );
    let icon_target = format!("../media/{}", icon_part.rsplit('/').next().unwrap_or(""));
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let rels_xml =
        read_archive_text(&mut archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let content_types_xml =
        read_archive_text(&mut archive, "[Content_Types].xml")?.ok_or_else(|| {
            WolfPptError::InvalidInput("[Content_Types].xml was not found".to_string())
        })?;

    let ole_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &ole_relationship_id,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
        &ole_target,
    )?;
    let icon_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_image_relationship(&rels_xml, &icon_relationship_id, &icon_target)?;

    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let mut inserted_shape_id = shape_id;
    slide_xml = match target {
        OleObjectInsertTarget::Slide => add_ole_object_to_slide_xml(
            &slide_xml,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::Group { group_index } => add_ole_object_to_group_shape_xml(
            &slide_xml,
            group_index,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::NestedGroup {
            group_index,
            nested_group_child_index,
        } => add_ole_object_to_nested_group_shape_xml(
            &slide_xml,
            group_index,
            nested_group_child_index,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::DeeperNestedGroup {
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        } => add_ole_object_to_deeper_nested_group_shape_xml(
            &slide_xml,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::NewNestedGroup { group_index } => {
            inserted_shape_id = shape_id + 1;
            add_ole_object_to_new_nested_group_shape_xml(
                &slide_xml,
                group_index,
                &ole_relationship_id,
                &icon_relationship_id,
                shape_id,
                inserted_shape_id,
                prog_id,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                icon_cx_emu,
                icon_cy_emu,
            )?
        }
    };
    let content_types_xml = ensure_content_type_override(
        &content_types_xml,
        &format!("/{}", ole_part),
        "application/vnd.openxmlformats-officedocument.oleObject",
    )?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &icon_extension, &icon_content_type)?;

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
        if name == ole_part || name == icon_part {
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
    update_package_facts(&ole_part, &mut part_count, &mut has_vba);
    writer.start_file(ole_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(object_payload), &mut writer)?;
    update_package_facts(&icon_part, &mut part_count, &mut has_vba);
    writer.start_file(icon_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(icon_payload), &mut writer)?;
    writer.finish()?;

    Ok(OleObjectAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        ole_relationship_id,
        icon_relationship_id,
        ole_part,
        icon_part,
        shape_id: inserted_shape_id,
        part_count,
        has_vba,
    })
}

fn next_embedding_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
) -> Result<String, WolfPptError> {
    let mut names = Vec::new();
    for index in 0..archive.len() {
        names.push(archive.by_index(index)?.name().to_string());
    }
    for number in 1.. {
        let candidate = format!("ppt/embeddings/oleObject{number}.bin");
        if !names.iter().any(|name| name == &candidate) {
            return Ok(candidate);
        }
    }
    unreachable!()
}
