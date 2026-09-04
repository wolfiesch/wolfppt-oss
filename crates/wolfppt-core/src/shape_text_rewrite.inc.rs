fn set_shape_text_at_index_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut in_target_shape = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                    }
                    shape_index += 1;
                }
                if in_target_shape && name == b"txBody" {
                    writer.write_event(Event::Start(event))?;
                    replacements +=
                        rewrite_text_body_content(&mut reader, &mut writer, replacement)?;
                    continue;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                writer.write_event(Event::End(event))?;
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_shape_paragraph_text_at_index_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    target_paragraph_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut paragraph_index = 0;
    let mut in_target_shape = false;
    let mut in_target_paragraph = false;
    let mut in_text = false;
    let mut wrote_replacement = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                        paragraph_index = 0;
                    }
                    shape_index += 1;
                } else if in_target_shape && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    wrote_replacement = false;
                } else if in_target_paragraph && name == b"t" {
                    in_text = true;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph && name == b"t" {
                    in_text = false;
                }
                writer.write_event(Event::End(event))?;
                if in_target_paragraph && name == b"p" {
                    in_target_paragraph = false;
                    wrote_replacement = false;
                }
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Text(_event) if in_target_paragraph && in_text => {
                if wrote_replacement {
                    writer.write_event(Event::Text(BytesText::new("")))?;
                } else {
                    writer.write_event(Event::Text(BytesText::new(replacement)))?;
                    wrote_replacement = true;
                }
                replacements += 1;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn append_shape_paragraph_text_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    text: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut in_target_shape = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                    }
                    shape_index += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_shape && name == b"txBody" {
                    write_text_paragraph(&mut writer, text)?;
                    replacements += 1;
                }
                writer.write_event(Event::End(event))?;
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn append_shape_text_run_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    target_paragraph_index: usize,
    text: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut paragraph_index = 0;
    let mut in_target_shape = false;
    let mut in_target_paragraph = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                        paragraph_index = 0;
                    }
                    shape_index += 1;
                } else if in_target_shape && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph && name == b"p" {
                    write_text_run(&mut writer, text)?;
                    replacements += 1;
                    in_target_paragraph = false;
                }
                writer.write_event(Event::End(event))?;
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn insert_shape_paragraph_line_break_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    target_paragraph_index: usize,
    target_run_slot: usize,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut paragraph_index = 0;
    let mut run_slot = 0;
    let mut in_target_shape = false;
    let mut in_target_paragraph = false;
    let mut inserted = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                        paragraph_index = 0;
                    }
                    shape_index += 1;
                } else if in_target_shape && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    run_slot = 0;
                    inserted = false;
                } else if in_target_paragraph && name == b"r" {
                    if !inserted && run_slot == target_run_slot {
                        write_paragraph_line_break(&mut writer)?;
                        inserted = true;
                        replacements += 1;
                    }
                    run_slot += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_shape && name == b"p" {
                    if paragraph_index == target_paragraph_index {
                        if target_run_slot != 0 {
                            return Err(WolfPptError::InvalidInput(
                                "run slot out of range".to_string(),
                            ));
                        }
                        writer.write_event(Event::Start(event.to_owned()))?;
                        write_paragraph_line_break(&mut writer)?;
                        writer.write_event(Event::End(BytesEnd::new("a:p")))?;
                        paragraph_index += 1;
                        replacements += 1;
                    } else {
                        paragraph_index += 1;
                        writer.write_event(Event::Empty(event))?;
                    }
                    continue;
                }
                if in_target_paragraph && name == b"r" {
                    if !inserted && run_slot == target_run_slot {
                        write_paragraph_line_break(&mut writer)?;
                        inserted = true;
                        replacements += 1;
                    }
                    run_slot += 1;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph && name == b"p" {
                    if !inserted {
                        if run_slot != target_run_slot {
                            return Err(WolfPptError::InvalidInput(
                                "run slot out of range".to_string(),
                            ));
                        }
                        write_paragraph_line_break(&mut writer)?;
                        replacements += 1;
                    }
                    in_target_paragraph = false;
                }
                writer.write_event(Event::End(event))?;
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_shape_paragraph_properties_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    target_paragraph_index: usize,
    alignment: Option<Option<&str>>,
    level: Option<usize>,
    spacing: &ParagraphSpacingPatch,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut paragraph_index = 0;
    let mut in_target_shape = false;
    let mut in_target_paragraph = false;
    let mut ppr_depth = 0usize;
    let mut handled_paragraph_properties = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                        paragraph_index = 0;
                    }
                    shape_index += 1;
                } else if in_target_shape && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    handled_paragraph_properties = false;
                } else if in_target_paragraph && ppr_depth == 0 {
                    if name == b"pPr" {
                        writer.write_event(Event::Start(
                            rewrite_paragraph_property_attributes(&event, alignment, level),
                        ))?;
                        write_paragraph_spacing_children(&mut writer, spacing)?;
                        handled_paragraph_properties = true;
                        replacements += paragraph_property_replacement_count(
                            alignment, level, spacing,
                        );
                        ppr_depth = 1;
                        continue;
                    }
                    if !handled_paragraph_properties {
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        handled_paragraph_properties = true;
                        replacements += paragraph_property_replacement_count(
                            alignment, level, spacing,
                        );
                    }
                } else if ppr_depth > 0 {
                    if paragraph_spacing_key(&name)
                        .is_some_and(|key| paragraph_spacing_value(spacing, key).is_some())
                    {
                        skip_current_element(&mut reader)?;
                        continue;
                    }
                    ppr_depth += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph && ppr_depth == 0 {
                    if name == b"pPr" {
                        let rewritten =
                            rewrite_paragraph_property_attributes(&event, alignment, level);
                        if paragraph_spacing_replacement_count(spacing) == 0 {
                            writer.write_event(Event::Empty(rewritten))?;
                        } else {
                            writer.write_event(Event::Start(rewritten))?;
                            write_paragraph_spacing_children(&mut writer, spacing)?;
                            writer.write_event(Event::End(BytesEnd::new("a:pPr")))?;
                        }
                        handled_paragraph_properties = true;
                        replacements += paragraph_property_replacement_count(
                            alignment, level, spacing,
                        );
                        continue;
                    }
                    if name == b"p" {
                        if !handled_paragraph_properties {
                            writer.write_event(Event::Start(event.to_owned()))?;
                            write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                            writer.write_event(Event::End(BytesEnd::new("a:p")))?;
                            handled_paragraph_properties = true;
                            replacements += paragraph_property_replacement_count(
                                alignment, level, spacing,
                            );
                        } else {
                            writer.write_event(Event::Empty(event))?;
                        }
                        continue;
                    }
                    if !handled_paragraph_properties {
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        handled_paragraph_properties = true;
                        replacements += paragraph_property_replacement_count(
                            alignment, level, spacing,
                        );
                    }
                }
                if ppr_depth > 0
                    && paragraph_spacing_key(&name)
                        .is_some_and(|key| paragraph_spacing_value(spacing, key).is_some())
                {
                    continue;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph && name == b"p" {
                    if !handled_paragraph_properties {
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        replacements += paragraph_property_replacement_count(
                            alignment, level, spacing,
                        );
                    }
                    in_target_paragraph = false;
                }
                writer.write_event(Event::End(event))?;
                if ppr_depth > 0 {
                    ppr_depth = ppr_depth.saturating_sub(1);
                }
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_shape_paragraph_font_properties_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    target_paragraph_index: usize,
    patch: &ParagraphFontPatch<'_>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut paragraph_index = 0;
    let mut in_target_shape = false;
    let mut in_target_paragraph = false;
    let mut ppr_depth = 0usize;
    let mut defrpr_depth = 0usize;
    let mut handled_paragraph_properties = false;
    let mut handled_default_run_properties = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                        paragraph_index = 0;
                    }
                    shape_index += 1;
                } else if in_target_shape && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    handled_paragraph_properties = false;
                    handled_default_run_properties = false;
                    ppr_depth = 0;
                    defrpr_depth = 0;
                } else if in_target_paragraph && ppr_depth == 0 {
                    if name == b"pPr" {
                        handled_paragraph_properties = true;
                        ppr_depth = 1;
                        writer.write_event(Event::Start(event))?;
                        continue;
                    }
                    if !handled_paragraph_properties {
                        write_paragraph_properties_with_default_run_properties(
                            &mut writer,
                            patch,
                        )?;
                        handled_paragraph_properties = true;
                        handled_default_run_properties = true;
                        replacements += patch.replacement_count();
                    }
                } else if ppr_depth > 0 && defrpr_depth == 0 {
                    if name == b"defRPr" {
                        let attribute_replacements = patch.attribute_replacements();
                        writer.write_event(Event::Start(rewrite_event_optional_attributes(
                            &event,
                            &attribute_replacements,
                        )))?;
                        write_default_run_property_children(&mut writer, patch)?;
                        handled_default_run_properties = true;
                        replacements += patch.replacement_count();
                        defrpr_depth = 1;
                        ppr_depth += 1;
                        continue;
                    }
                    ppr_depth += 1;
                } else if defrpr_depth > 0 {
                    if name == b"latin" && patch.name.is_some() {
                        skip_current_element(&mut reader)?;
                        continue;
                    }
                    if is_fill_property(&name) && patch.replaces_fill() {
                        skip_current_element(&mut reader)?;
                        continue;
                    }
                    defrpr_depth += 1;
                    ppr_depth += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph && ppr_depth == 0 {
                    if name == b"pPr" {
                        writer.write_event(Event::Start(event.to_owned()))?;
                        write_default_run_properties(&mut writer, patch)?;
                        writer.write_event(Event::End(BytesEnd::new("a:pPr")))?;
                        handled_paragraph_properties = true;
                        handled_default_run_properties = true;
                        replacements += patch.replacement_count();
                        continue;
                    }
                    if !handled_paragraph_properties {
                        write_paragraph_properties_with_default_run_properties(
                            &mut writer,
                            patch,
                        )?;
                        handled_paragraph_properties = true;
                        handled_default_run_properties = true;
                        replacements += patch.replacement_count();
                    }
                }
                if ppr_depth > 0 && defrpr_depth == 0 && name == b"defRPr" {
                    let attribute_replacements = patch.attribute_replacements();
                    let rewritten =
                        rewrite_event_optional_attributes(&event, &attribute_replacements);
                    if default_run_property_child_count(patch) == 0 {
                        writer.write_event(Event::Empty(rewritten))?;
                    } else {
                        writer.write_event(Event::Start(rewritten))?;
                        write_default_run_property_children(&mut writer, patch)?;
                        writer.write_event(Event::End(BytesEnd::new("a:defRPr")))?;
                    }
                    handled_default_run_properties = true;
                    replacements += patch.replacement_count();
                    continue;
                }
                if defrpr_depth > 0 && name == b"latin" && patch.name.is_some() {
                    continue;
                }
                if defrpr_depth > 0 && is_fill_property(&name) && patch.replaces_fill() {
                    continue;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_paragraph
                    && ppr_depth == 1
                    && name == b"pPr"
                    && !handled_default_run_properties
                {
                    write_default_run_properties(&mut writer, patch)?;
                    handled_default_run_properties = true;
                    replacements += patch.replacement_count();
                }
                if in_target_paragraph && name == b"p" {
                    if !handled_paragraph_properties {
                        write_paragraph_properties_with_default_run_properties(
                            &mut writer,
                            patch,
                        )?;
                        replacements += patch.replacement_count();
                    }
                    in_target_paragraph = false;
                }
                writer.write_event(Event::End(event))?;
                if defrpr_depth > 0 {
                    defrpr_depth = defrpr_depth.saturating_sub(1);
                }
                if ppr_depth > 0 {
                    ppr_depth = ppr_depth.saturating_sub(1);
                }
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_shape_geometry_at_index_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut shape_depth: usize = 0;
    let mut in_target_shape = false;
    let mut in_target_transform = false;
    let mut updated_offset = false;
    let mut updated_extent = false;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if is_shape_element_name(&name) {
                    if shape_depth == 0 {
                        in_target_shape = shape_index == target_shape_index;
                        shape_index += 1;
                    }
                    shape_depth += 1;
                }

                if in_target_shape && shape_depth == 1 && name == b"xfrm" {
                    in_target_transform = true;
                }

                if in_target_transform && name == b"off" && !updated_offset {
                    writer.write_event(Event::Start(rewrite_event_attributes(
                        &event,
                        &[("x", x_emu.to_string()), ("y", y_emu.to_string())],
                    )))?;
                    updated_offset = true;
                } else if in_target_transform && name == b"ext" && !updated_extent {
                    writer.write_event(Event::Start(rewrite_event_attributes(
                        &event,
                        &[("cx", cx_emu.to_string()), ("cy", cy_emu.to_string())],
                    )))?;
                    updated_extent = true;
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_transform && name == b"off" && !updated_offset {
                    writer.write_event(Event::Empty(rewrite_event_attributes(
                        &event,
                        &[("x", x_emu.to_string()), ("y", y_emu.to_string())],
                    )))?;
                    updated_offset = true;
                } else if in_target_transform && name == b"ext" && !updated_extent {
                    writer.write_event(Event::Empty(rewrite_event_attributes(
                        &event,
                        &[("cx", cx_emu.to_string()), ("cy", cy_emu.to_string())],
                    )))?;
                    updated_extent = true;
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_transform && name == b"xfrm" {
                    in_target_transform = false;
                }
                writer.write_event(Event::End(event))?;
                if is_shape_element_name(&name) {
                    shape_depth = shape_depth.saturating_sub(1);
                    if shape_depth == 0 {
                        in_target_shape = false;
                    }
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((
        writer.into_inner(),
        usize::from(updated_offset || updated_extent),
    ))
}
