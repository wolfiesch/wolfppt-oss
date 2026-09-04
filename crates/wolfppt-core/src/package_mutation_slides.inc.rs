pub fn add_slide_connector(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
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
    slide_xml = add_connector_to_slide_xml(
        &slide_xml,
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
pub fn add_slide_connected_connector(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
    slide_xml = add_connected_connector_to_slide_xml(
        &slide_xml,
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        begin_connection,
        end_connection,
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
pub fn add_slide_connected_connector_with_auto_shapes(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
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
    connector_preset_geom: &str,
    connector_begin_x_emu: u64,
    connector_begin_y_emu: u64,
    connector_end_x_emu: u64,
    connector_end_y_emu: u64,
    begin_cxn_pt_idx: u64,
    end_cxn_pt_idx: u64,
) -> Result<ConnectorAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    auto_shape_display_name(begin_preset_geometry)?;
    auto_shape_display_name(end_preset_geometry)?;
    connector_preset_geometry(connector_preset_geom)?;
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
    let begin_shape_id = max_cnvpr_id(&slide_xml) + 1;
    let end_shape_id = begin_shape_id + 1;
    let connector_shape_id = begin_shape_id + 2;
    slide_xml = add_connected_connector_with_auto_shapes_to_slide_xml(
        &slide_xml,
        begin_shape_id,
        begin_preset_geometry,
        begin_x_emu,
        begin_y_emu,
        begin_cx_emu,
        begin_cy_emu,
        end_shape_id,
        end_preset_geometry,
        end_x_emu,
        end_y_emu,
        end_cx_emu,
        end_cy_emu,
        connector_shape_id,
        connector_preset_geom,
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
        preset_geometry: connector_preset_geom.to_string(),
        shape_id: connector_shape_id,
        part_count,
        has_vba,
    })
}

pub fn add_blank_slide_from_existing_layout(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
) -> Result<SlideAddSummary, WolfPptError> {
    add_blank_slide(input_path, output_path, None)
}

pub fn add_blank_slide_from_layout_index(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    layout_index: usize,
) -> Result<SlideAddSummary, WolfPptError> {
    add_blank_slide(input_path, output_path, Some(layout_index))
}

fn add_blank_slide(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    layout_index: Option<usize>,
) -> Result<SlideAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let mut slide_parts = slide_parts(&mut archive)?;
    let layout_target = match layout_index {
        Some(index) => slide_layout_target_at_index(&mut archive, index)?,
        None => first_slide_layout_target(&mut archive, &slide_parts)?,
    };
    let next_slide_number = slide_parts
        .iter()
        .filter_map(|part| slide_number(part))
        .max()
        .unwrap_or(0)
        + 1;
    let new_slide_part = format!("ppt/slides/slide{next_slide_number}.xml");
    let new_slide_rels_part = relationship_part_name(&new_slide_part);
    slide_parts.push(new_slide_part.clone());
    slide_parts.sort_by_key(|part| natural_key(part));

    let mut presentation_xml = Vec::new();
    archive
        .by_name("ppt/presentation.xml")?
        .read_to_end(&mut presentation_xml)?;
    let mut presentation_rels = Vec::new();
    archive
        .by_name("ppt/_rels/presentation.xml.rels")?
        .read_to_end(&mut presentation_rels)?;
    let mut content_types = Vec::new();
    archive
        .by_name("[Content_Types].xml")?
        .read_to_end(&mut content_types)?;

    let relationship_id = next_relationship_id(&presentation_rels);
    let slide_id = next_slide_id(&presentation_xml);
    let new_presentation_xml = append_slide_id(&presentation_xml, slide_id, &relationship_id)?;
    let new_presentation_rels = append_relationship(
        &presentation_rels,
        &relationship_id,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
        &format!("slides/slide{next_slide_number}.xml"),
    )?;
    let new_content_types = append_content_type_override(
        &content_types,
        &format!("/ppt/slides/slide{next_slide_number}.xml"),
        "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
    )?;
    let placeholder_shapes =
        placeholder_shapes_from_layout(&mut archive, &new_slide_part, &layout_target)?;
    let new_slide_xml = blank_slide_xml(&placeholder_shapes);
    let new_slide_rels = slide_layout_rels_xml(&layout_target);

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
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
        match name.as_str() {
            "ppt/presentation.xml" => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(&new_presentation_xml), &mut writer)?
            }
            "ppt/_rels/presentation.xml.rels" => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(&new_presentation_rels), &mut writer)?
            }
            "[Content_Types].xml" => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(&new_content_types), &mut writer)?
            }
            _ => {
                writer.raw_copy_file(file)?;
                0
            }
        };
    }
    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    writer.start_file(new_slide_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(new_slide_xml.as_bytes()), &mut writer)?;
    update_package_facts(&new_slide_part, &mut part_count, &mut has_vba);
    writer.start_file(new_slide_rels_part, options)?;
    std::io::copy(&mut Cursor::new(new_slide_rels.as_bytes()), &mut writer)?;
    update_package_facts(&relationship_part_name(&new_slide_part), &mut part_count, &mut has_vba);
    writer.finish()?;

    Ok(SlideAddSummary {
        path: output_path.to_path_buf(),
        slide_part: new_slide_part,
        relationship_id,
        layout_target,
        slide_id,
        slide_count: slide_parts.len(),
        part_count,
        has_vba,
    })
}

fn reorder_slide_ids(
    xml: &[u8],
    slide_indices: &[usize],
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    let mut writer = Writer::new(Cursor::new(Vec::new()));
    let mut in_slide_id_list = false;
    let mut slide_id_list_depth = 0usize;
    let mut slide_entries: Vec<Vec<Event<'static>>> = Vec::new();
    let mut captured_entry: Option<(usize, Vec<Event<'static>>)> = None;
    let mut found_list = false;
    let mut changed = false;

    loop {
        let event = reader.read_event()?;
        if let Some((depth, events)) = captured_entry.as_mut() {
            let mut next_depth = *depth;
            match &event {
                Event::Start(_) => next_depth += 1,
                Event::End(_) => next_depth -= 1,
                Event::Eof => {
                    return Err(WolfPptError::XmlText(
                        "unexpected EOF while reading slide id".to_string(),
                    ));
                }
                _ => {}
            }
            events.push(event.into_owned());
            if next_depth == 0 {
                let (_, completed) = captured_entry.take().unwrap();
                slide_entries.push(completed);
            } else if let Some((stored_depth, _)) = captured_entry.as_mut() {
                *stored_depth = next_depth;
            }
            continue;
        }

        match event {
            Event::Start(start) => {
                let qname = start.name();
                let name = local_name(qname.as_ref());
                if !in_slide_id_list && name == b"sldIdLst" {
                    in_slide_id_list = true;
                    slide_id_list_depth = 1;
                    found_list = true;
                    writer.write_event(Event::Start(start.into_owned()))?;
                } else if in_slide_id_list
                    && slide_id_list_depth == 1
                    && name == b"sldId"
                {
                    captured_entry = Some((1, vec![Event::Start(start.into_owned())]));
                } else {
                    if in_slide_id_list {
                        slide_id_list_depth += 1;
                    }
                    writer.write_event(Event::Start(start.into_owned()))?;
                }
            }
            Event::Empty(empty) => {
                let qname = empty.name();
                if in_slide_id_list
                    && slide_id_list_depth == 1
                    && local_name(qname.as_ref()) == b"sldId"
                {
                    slide_entries.push(vec![Event::Empty(empty.into_owned())]);
                } else {
                    writer.write_event(Event::Empty(empty.into_owned()))?;
                }
            }
            Event::End(end) => {
                let qname = end.name();
                let name = local_name(qname.as_ref());
                if in_slide_id_list && slide_id_list_depth == 1 && name == b"sldIdLst" {
                    validate_slide_order(slide_indices, slide_entries.len())?;
                    changed = slide_indices
                        .iter()
                        .copied()
                        .ne(0..slide_entries.len());
                    for slide_index in slide_indices {
                        for entry_event in &slide_entries[*slide_index] {
                            writer.write_event(entry_event.clone())?;
                        }
                    }
                    in_slide_id_list = false;
                    slide_id_list_depth = 0;
                    writer.write_event(Event::End(end.into_owned()))?;
                } else {
                    if in_slide_id_list {
                        slide_id_list_depth = slide_id_list_depth.saturating_sub(1);
                    }
                    writer.write_event(Event::End(end.into_owned()))?;
                }
            }
            Event::Eof => break,
            other => writer.write_event(other.into_owned())?,
        }
    }

    if !found_list {
        return Err(WolfPptError::XmlText(
            "presentation has no slide id list".to_string(),
        ));
    }
    if !changed {
        return Ok((xml.to_vec(), 0));
    }
    Ok((writer.into_inner().into_inner(), 1))
}

fn validate_slide_order(slide_indices: &[usize], slide_count: usize) -> Result<(), WolfPptError> {
    if slide_indices.len() != slide_count {
        return Err(WolfPptError::InvalidInput(format!(
            "slide order has {} entries for {slide_count} slides",
            slide_indices.len()
        )));
    }
    let mut seen = vec![false; slide_count];
    for slide_index in slide_indices {
        if *slide_index >= slide_count {
            return Err(WolfPptError::InvalidInput(format!(
                "slide order index {slide_index} was not found"
            )));
        }
        if seen[*slide_index] {
            return Err(WolfPptError::InvalidInput(format!(
                "slide order index {slide_index} is duplicated"
            )));
        }
        seen[*slide_index] = true;
    }
    Ok(())
}
