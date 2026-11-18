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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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

/// Replace one shape paragraph's text the way python-pptx `_Paragraph.text`
/// does: every run, field, and line break is removed, then one plain run
/// holding the replacement is added before `a:endParaRPr`. Paragraph
/// properties survive; run properties do not. Run appends, line breaks, and
/// run-indexed edits queued after the text therefore address the runs the
/// facade reports.
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
    // Element depth below the target `a:p`; 0 means a direct child.
    let mut depth = 0usize;
    let mut skip_depth = 0usize;
    let mut wrote_replacement = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                if skip_depth > 0 {
                    skip_depth += 1;
                    continue;
                }
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_paragraph {
                    if depth == 0 {
                        if is_paragraph_content(&name) {
                            skip_depth = 1;
                            continue;
                        }
                        if name == b"endParaRPr" {
                            write_text_run(&mut writer, replacement)?;
                            wrote_replacement = true;
                            replacements += 1;
                        }
                    }
                    depth += 1;
                    writer.write_event(Event::Start(event))?;
                    continue;
                }
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                        paragraph_index = 0;
                    }
                    shape_index += 1;
                } else if in_target_shape && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    depth = 0;
                    wrote_replacement = false;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                if skip_depth > 0 {
                    continue;
                }
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_paragraph {
                    if depth == 0 {
                        if is_paragraph_content(&name) {
                            continue;
                        }
                        if name == b"endParaRPr" {
                            write_text_run(&mut writer, replacement)?;
                            wrote_replacement = true;
                            replacements += 1;
                        }
                    }
                    writer.write_event(Event::Empty(event))?;
                    continue;
                }
                if in_target_shape && name == b"p" {
                    let is_target = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    if is_target {
                        let end = event.to_end().into_owned();
                        writer.write_event(Event::Start(event))?;
                        write_text_run(&mut writer, replacement)?;
                        writer.write_event(Event::End(end))?;
                        replacements += 1;
                        continue;
                    }
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                if skip_depth > 0 {
                    skip_depth -= 1;
                    continue;
                }
                if in_target_paragraph {
                    if depth == 0 {
                        if !wrote_replacement {
                            write_text_run(&mut writer, replacement)?;
                            replacements += 1;
                        }
                        in_target_paragraph = false;
                    } else {
                        depth -= 1;
                    }
                    writer.write_event(Event::End(event))?;
                    continue;
                }
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                writer.write_event(Event::End(event))?;
                if in_target_shape && name == b"sp" {
                    in_target_shape = false;
                }
            }
            Event::Eof => break,
            _ if skip_depth > 0 => {}
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

/// Direct `a:p` children that `_Paragraph.clear` removes.
fn is_paragraph_content(name: &[u8]) -> bool {
    name == b"r" || name == b"br" || name == b"fld"
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if name == b"sp" {
                    if shape_index == target_shape_index {
                        in_target_shape = true;
                    }
                    shape_index += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_shape && name == b"p" {
                    if paragraph_index == target_paragraph_index {
                        writer.write_event(Event::Start(event))?;
                        write_text_run(&mut writer, text)?;
                        writer.write_event(Event::End(BytesEnd::new("a:p")))?;
                        replacements += 1;
                    } else {
                        writer.write_event(Event::Empty(event))?;
                    }
                    paragraph_index += 1;
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                        writer.write_event(Event::Start(rewrite_paragraph_property_attributes(
                            &event, alignment, level,
                        )))?;
                        write_paragraph_spacing_children(&mut writer, spacing)?;
                        handled_paragraph_properties = true;
                        replacements +=
                            paragraph_property_replacement_count(alignment, level, spacing);
                        ppr_depth = 1;
                        continue;
                    }
                    if !handled_paragraph_properties {
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        handled_paragraph_properties = true;
                        replacements +=
                            paragraph_property_replacement_count(alignment, level, spacing);
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_shape && ppr_depth == 0 && name == b"p" {
                    // A self-closing <a:p/> is still a paragraph: count it, and
                    // expand it when it is the target so pPr can be written.
                    let is_target = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    if is_target {
                        writer.write_event(Event::Start(event.to_owned()))?;
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        writer.write_event(Event::End(BytesEnd::new("a:p")))?;
                        replacements +=
                            paragraph_property_replacement_count(alignment, level, spacing);
                    } else {
                        writer.write_event(Event::Empty(event))?;
                    }
                    continue;
                }
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
                        replacements +=
                            paragraph_property_replacement_count(alignment, level, spacing);
                        continue;
                    }
                    if !handled_paragraph_properties {
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        handled_paragraph_properties = true;
                        replacements +=
                            paragraph_property_replacement_count(alignment, level, spacing);
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_paragraph && name == b"p" {
                    if !handled_paragraph_properties {
                        write_paragraph_properties(&mut writer, alignment, level, spacing)?;
                        replacements +=
                            paragraph_property_replacement_count(alignment, level, spacing);
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                        write_paragraph_properties_with_default_run_properties(&mut writer, patch)?;
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_shape && ppr_depth == 0 && name == b"p" {
                    // A self-closing <a:p/> is still a paragraph: count it, and
                    // expand it when it is the target so pPr/defRPr can be written.
                    let is_target = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    if is_target {
                        writer.write_event(Event::Start(event.to_owned()))?;
                        write_paragraph_properties_with_default_run_properties(&mut writer, patch)?;
                        writer.write_event(Event::End(BytesEnd::new("a:p")))?;
                        replacements += patch.replacement_count();
                    } else {
                        writer.write_event(Event::Empty(event))?;
                    }
                    continue;
                }
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
                        write_paragraph_properties_with_default_run_properties(&mut writer, patch)?;
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
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
                        write_paragraph_properties_with_default_run_properties(&mut writer, patch)?;
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
    let mut reader = quick_xml::NsReader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut shape_depth: usize = 0;
    let mut in_target_shape = false;
    let mut in_target_transform = false;
    let mut updated_offset = false;
    let mut updated_extent = false;
    let mut depth = 0usize;
    let mut target_depth = 0usize;
    let mut transform_depth = 0usize;
    let mut properties = None;
    let mut transform_seen = false;
    let mut found_target = false;
    let drawing_namespace = |strict: bool| {
        if strict {
            "http://purl.oclc.org/ooxml/drawingml/main"
        } else {
            "http://schemas.openxmlformats.org/drawingml/2006/main"
        }
    };
    let geometry_xml = |strict: bool| {
        let namespace = drawing_namespace(strict);
        format!(
            r#"<a:xfrm xmlns:a="{namespace}"><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm>"#
        )
    };

    loop {
        let (resolved, event) = reader.read_resolved_event()?;
        let presentation_ns = matches!(
            &resolved,
            quick_xml::name::ResolveResult::Bound(ns)
                if ns.0.as_bytes() == PRESENTATION_MAIN_NS
                    || ns.0.as_bytes() == STRICT_PRESENTATION_MAIN_NS
        );
        let drawing_ns = matches!(
            &resolved,
            quick_xml::name::ResolveResult::Bound(ns)
                if ns.0.as_bytes() == DRAWINGML_MAIN_NS
                    || ns.0.as_bytes() == STRICT_DRAWINGML_MAIN_NS
        );
        let strict = matches!(
            &resolved,
            quick_xml::name::ResolveResult::Bound(ns)
                if ns.0.as_bytes() == STRICT_PRESENTATION_MAIN_NS
                    || ns.0.as_bytes() == STRICT_DRAWINGML_MAIN_NS
        );
        match event {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if presentation_ns && is_shape_element_name(&name) {
                    if shape_depth == 0 {
                        in_target_shape = shape_index == target_shape_index;
                        found_target |= in_target_shape;
                        if in_target_shape {
                            target_depth = depth + 1;
                        }
                        shape_index += 1;
                    }
                    shape_depth += 1;
                }
                depth += 1;

                if in_target_shape
                    && depth == target_depth + 1
                    && presentation_ns
                    && matches!(name.as_slice(), b"spPr" | b"grpSpPr")
                {
                    writer.write_event(Event::Start(event))?;
                    properties = Some((depth, writer.get_ref().len(), strict));
                    transform_seen = false;
                    continue;
                }

                if in_target_shape
                    && name == b"xfrm"
                    && ((presentation_ns && depth == target_depth + 1)
                        || (drawing_ns
                            && properties
                                .is_some_and(|(parent_depth, _, _)| depth == parent_depth + 1)))
                {
                    in_target_transform = true;
                    transform_seen = true;
                    transform_depth = depth;
                }

                if in_target_transform
                    && drawing_ns
                    && depth == transform_depth + 1
                    && name == b"off"
                    && !updated_offset
                {
                    writer.write_event(Event::Start(rewrite_event_attributes(
                        &event,
                        &[("x", x_emu.to_string()), ("y", y_emu.to_string())],
                    )))?;
                    updated_offset = true;
                } else if in_target_transform
                    && drawing_ns
                    && depth == transform_depth + 1
                    && name == b"ext"
                    && !updated_extent
                {
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_shape
                    && depth == target_depth
                    && presentation_ns
                    && matches!(name.as_slice(), b"spPr" | b"grpSpPr")
                {
                    writer.write_event(Event::Start(event.borrow()))?;
                    writer
                        .get_mut()
                        .extend_from_slice(geometry_xml(strict).as_bytes());
                    writer.write_event(Event::End(event.to_end()))?;
                    updated_offset = true;
                    updated_extent = true;
                    continue;
                }
                if in_target_shape
                    && name == b"xfrm"
                    && ((presentation_ns && depth == target_depth)
                        || (drawing_ns
                            && properties
                                .is_some_and(|(parent_depth, _, _)| depth == parent_depth)))
                {
                    // Preserve the transform's QName and attributes, including
                    // flips/rotation, while adding DrawingML children in profile.
                    writer.write_event(Event::Start(event.borrow()))?;
                    let namespace = drawing_namespace(strict);
                    // The existing xfrm can use any prefix; bind only new nodes.
                    let children = format!(
                        r#"<a:off xmlns:a="{namespace}" x="{x_emu}" y="{y_emu}"/><a:ext xmlns:a="{namespace}" cx="{cx_emu}" cy="{cy_emu}"/>"#
                    );
                    writer.get_mut().extend_from_slice(children.as_bytes());
                    writer.write_event(Event::End(event.to_end()))?;
                    transform_seen = true;
                    updated_offset = true;
                    updated_extent = true;
                    continue;
                }
                if in_target_transform
                    && drawing_ns
                    && depth == transform_depth
                    && name == b"off"
                    && !updated_offset
                {
                    writer.write_event(Event::Empty(rewrite_event_attributes(
                        &event,
                        &[("x", x_emu.to_string()), ("y", y_emu.to_string())],
                    )))?;
                    updated_offset = true;
                } else if in_target_transform
                    && drawing_ns
                    && depth == transform_depth
                    && name == b"ext"
                    && !updated_extent
                {
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
                let name = local_name(event.name().as_ref().as_bytes()).to_vec();
                if in_target_transform && depth == transform_depth {
                    in_target_transform = false;
                }
                if let Some((properties_depth, content_start, strict)) = properties {
                    if depth == properties_depth {
                        if !transform_seen {
                            writer
                                .get_mut()
                                .splice(content_start..content_start, geometry_xml(strict).bytes());
                            updated_offset = true;
                            updated_extent = true;
                        }
                        properties = None;
                    }
                }
                writer.write_event(Event::End(event))?;
                depth = depth.saturating_sub(1);
                if presentation_ns && is_shape_element_name(&name) {
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
    if found_target && !(updated_offset && updated_extent) {
        return Err(WolfPptError::InvalidInput(
            "shape geometry requires a shape-properties container or a complete transform"
                .to_string(),
        ));
    }

    Ok((
        writer.into_inner(),
        usize::from(updated_offset || updated_extent),
    ))
}
