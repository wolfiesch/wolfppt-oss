fn set_group_shape_child_text_in_slide(
    xml: &[u8],
    target_group_index: usize,
    target_child_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut group_index = 0;
    let mut group_depth = 0;
    let mut child_index = 0;
    let mut in_target_child = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"grpSp" {
                    if group_index == target_group_index {
                        group_depth = 1;
                        child_index = 0;
                    } else if group_depth > 0 {
                        group_depth += 1;
                    }
                    group_index += 1;
                } else if group_depth == 1 && name == b"sp" {
                    if child_index == target_child_index {
                        in_target_child = true;
                    }
                    child_index += 1;
                }
                if in_target_child && name == b"txBody" {
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
                if in_target_child && name == b"sp" {
                    in_target_child = false;
                }
                if group_depth > 0 && name == b"grpSp" {
                    group_depth -= 1;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_group_shape_child_paragraph_text_in_slide(
    xml: &[u8],
    target_group_index: usize,
    target_child_index: usize,
    target_paragraph_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut group_index = 0;
    let mut group_depth = 0;
    let mut child_index = 0;
    let mut paragraph_index = 0;
    let mut in_target_child = false;
    let mut in_target_paragraph = false;
    let mut in_text = false;
    let mut wrote_replacement = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"grpSp" {
                    if group_index == target_group_index {
                        group_depth = 1;
                        child_index = 0;
                    } else if group_depth > 0 {
                        group_depth += 1;
                    }
                    group_index += 1;
                } else if group_depth == 1 && name == b"sp" {
                    if child_index == target_child_index {
                        in_target_child = true;
                        paragraph_index = 0;
                    }
                    child_index += 1;
                } else if in_target_child && name == b"p" {
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
                    if !wrote_replacement {
                        writer.write_event(Event::Text(BytesText::new(replacement)))?;
                        wrote_replacement = true;
                        replacements += 1;
                    }
                    in_text = false;
                }
                if in_target_child && name == b"txBody" && paragraph_index == target_paragraph_index
                {
                    write_text_paragraph(&mut writer, replacement)?;
                    replacements += 1;
                }
                writer.write_event(Event::End(event))?;
                if in_target_paragraph && name == b"p" {
                    in_target_paragraph = false;
                    wrote_replacement = false;
                }
                if in_target_child && name == b"sp" {
                    in_target_child = false;
                }
                if group_depth > 0 && name == b"grpSp" {
                    group_depth -= 1;
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

fn set_group_shape_child_run_text_in_slide(
    xml: &[u8],
    target_group_index: usize,
    target_child_index: usize,
    target_paragraph_index: usize,
    target_run_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut group_index = 0;
    let mut group_depth = 0;
    let mut child_index = 0;
    let mut paragraph_index = 0;
    let mut run_index = 0;
    let mut in_target_child = false;
    let mut in_target_paragraph = false;
    let mut in_target_run = false;
    let mut target_run_seen = false;
    let mut in_text = false;
    let mut wrote_replacement = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"grpSp" {
                    if group_index == target_group_index {
                        group_depth = 1;
                        child_index = 0;
                    } else if group_depth > 0 {
                        group_depth += 1;
                    }
                    group_index += 1;
                } else if group_depth == 1 && name == b"sp" {
                    if child_index == target_child_index {
                        in_target_child = true;
                        paragraph_index = 0;
                    }
                    child_index += 1;
                } else if in_target_child && name == b"p" {
                    in_target_paragraph = paragraph_index == target_paragraph_index;
                    paragraph_index += 1;
                    run_index = 0;
                    target_run_seen = false;
                } else if in_target_paragraph && name == b"r" {
                    in_target_run = run_index == target_run_index;
                    if in_target_run {
                        target_run_seen = true;
                    }
                    run_index += 1;
                    wrote_replacement = false;
                } else if in_target_run && name == b"t" {
                    in_text = true;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_run && name == b"t" {
                    if !wrote_replacement {
                        writer.write_event(Event::Text(BytesText::new(replacement)))?;
                        wrote_replacement = true;
                        replacements += 1;
                    }
                    in_text = false;
                }
                if in_target_paragraph
                    && name == b"p"
                    && !target_run_seen
                    && run_index == target_run_index
                {
                    write_text_run(&mut writer, replacement)?;
                    replacements += 1;
                }
                writer.write_event(Event::End(event))?;
                if in_target_run && name == b"r" {
                    in_target_run = false;
                    wrote_replacement = false;
                }
                if in_target_paragraph && name == b"p" {
                    in_target_paragraph = false;
                }
                if in_target_child && name == b"sp" {
                    in_target_child = false;
                }
                if group_depth > 0 && name == b"grpSp" {
                    group_depth -= 1;
                }
            }
            Event::Text(_event) if in_target_run && in_text => {
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

fn set_group_shape_child_geometry_in_slide(
    xml: &[u8],
    target_group_index: usize,
    target_child_index: usize,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut group_index = 0;
    let mut group_depth: usize = 0;
    let mut child_index = 0;
    let mut child_depth: usize = 0;
    let mut in_target_child = false;
    let mut in_target_transform = false;
    let mut updated_offset = false;
    let mut updated_extent = false;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"grpSp" {
                    if group_index == target_group_index {
                        group_depth = 1;
                        child_index = 0;
                    } else if group_depth > 0 {
                        group_depth += 1;
                    }
                    group_index += 1;
                } else if group_depth == 1 && is_shape_element_name(&name) {
                    if child_index == target_child_index {
                        in_target_child = true;
                        child_depth = 1;
                    }
                    child_index += 1;
                } else if in_target_child && is_shape_element_name(&name) {
                    child_depth += 1;
                }

                if in_target_child && child_depth == 1 && name == b"xfrm" {
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
                if in_target_child && is_shape_element_name(&name) {
                    child_depth = child_depth.saturating_sub(1);
                    if child_depth == 0 {
                        in_target_child = false;
                    }
                }
                if group_depth > 0 && name == b"grpSp" {
                    group_depth -= 1;
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

fn extract_shape_id_from_event(
    name: &[u8],
    attributes: quick_xml::events::attributes::Attributes<'_>,
    decoder: quick_xml::encoding::Decoder,
) -> Option<usize> {
    if local_name(name) != b"cNvPr" {
        return None;
    }
    for attr in attributes.flatten() {
        if local_name(attr.key.as_ref()) == b"id" {
            if let Ok(val) = attr.decode_and_unescape_value(decoder) {
                if let Ok(id) = val.parse::<usize>() {
                    return Some(id);
                }
            }
        }
    }
    None
}

fn delete_group_shape_child_in_slide(
    xml: &[u8],
    target_group_shape_id: usize,
    target_child_shape_id: usize,
) -> Result<(Vec<u8>, usize, std::collections::BTreeSet<String>), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut target_group_found = false;
    let mut in_target_group = false;
    let mut target_group_depth = 0usize;
    let mut outer_group_depth = 0usize;
    let mut deleted = false;
    let mut removed_relationship_ids = std::collections::BTreeSet::new();

    loop {
        match reader.read_event()? {
            Event::Start(start) => {
                let name = local_name(start.name().as_ref()).to_vec();
                if !in_target_group {
                    if name == b"grpSp" {
                        let mut group_header_events = vec![Event::Start(start.into_owned())];
                        let mut group_id: Option<usize> = None;
                        loop {
                            let next_event = reader.read_event()?;
                            let is_break = match &next_event {
                                Event::Start(s) | Event::Empty(s) => {
                                    if local_name(s.name().as_ref()) == b"cNvPr" {
                                        group_id = extract_shape_id_from_event(
                                            s.name().as_ref(),
                                            s.attributes(),
                                            reader.decoder(),
                                        );
                                        true
                                    } else {
                                        local_name(s.name().as_ref()) == b"grpSpPr"
                                            || is_shape_element_name(local_name(s.name().as_ref()))
                                    }
                                }
                                Event::Eof => true,
                                _ => false,
                            };
                            group_header_events.push(next_event.into_owned());
                            if is_break {
                                break;
                            }
                        }
                        if group_id == Some(target_group_shape_id) {
                            in_target_group = true;
                            target_group_depth = 1;
                            target_group_found = true;
                        } else {
                            outer_group_depth += 1;
                        }
                        for ev in group_header_events {
                            writer.write_event(ev)?;
                        }
                        continue;
                    }
                    writer.write_event(Event::Start(start))?;
                } else {
                    if target_group_depth == 1 && is_shape_element_name(&name) {
                        let mut child_events = vec![Event::Start(start.into_owned())];
                        let mut child_depth = 1usize;
                        let mut child_id: Option<usize> = None;
                        while child_depth > 0 {
                            let event = reader.read_event()?;
                            match &event {
                                Event::Start(s) => {
                                    if child_id.is_none()
                                        && local_name(s.name().as_ref()) == b"cNvPr"
                                    {
                                        child_id = extract_shape_id_from_event(
                                            s.name().as_ref(),
                                            s.attributes(),
                                            reader.decoder(),
                                        );
                                    }
                                    child_depth += 1;
                                }
                                Event::Empty(e) => {
                                    if child_id.is_none()
                                        && local_name(e.name().as_ref()) == b"cNvPr"
                                    {
                                        child_id = extract_shape_id_from_event(
                                            e.name().as_ref(),
                                            e.attributes(),
                                            reader.decoder(),
                                        );
                                    }
                                }
                                Event::End(_) => {
                                    child_depth -= 1;
                                }
                                Event::Eof => {
                                    return Err(WolfPptError::XmlText(
                                        "unexpected EOF while reading group child shape"
                                            .to_string(),
                                    ));
                                }
                                _ => {}
                            }
                            child_events.push(event.into_owned());
                        }

                        if child_id == Some(target_child_shape_id) {
                            for ev in &child_events {
                                match ev {
                                    Event::Start(s) => {
                                        collect_relationship_ids(
                                            s,
                                            reader.decoder(),
                                            &mut removed_relationship_ids,
                                        );
                                    }
                                    Event::Empty(e) => {
                                        collect_relationship_ids(
                                            e,
                                            reader.decoder(),
                                            &mut removed_relationship_ids,
                                        );
                                    }
                                    _ => {}
                                }
                            }
                            deleted = true;
                        } else {
                            for ev in child_events {
                                writer.write_event(ev)?;
                            }
                        }
                        continue;
                    }
                    if name == b"grpSp" {
                        target_group_depth += 1;
                    }
                    writer.write_event(Event::Start(start))?;
                }
            }
            Event::Empty(empty) => {
                let name = local_name(empty.name().as_ref()).to_vec();
                if in_target_group && target_group_depth == 1 && is_shape_element_name(&name) {
                    let child_id = extract_shape_id_from_event(
                        empty.name().as_ref(),
                        empty.attributes(),
                        reader.decoder(),
                    );
                    if child_id == Some(target_child_shape_id) {
                        collect_relationship_ids(
                            &empty,
                            reader.decoder(),
                            &mut removed_relationship_ids,
                        );
                        deleted = true;
                        continue;
                    }
                }
                writer.write_event(Event::Empty(empty))?;
            }
            Event::End(end) => {
                let name = local_name(end.name().as_ref()).to_vec();
                if in_target_group {
                    if name == b"grpSp" {
                        target_group_depth -= 1;
                        if target_group_depth == 0 {
                            in_target_group = false;
                        }
                    }
                } else if name == b"grpSp" && outer_group_depth > 0 {
                    outer_group_depth -= 1;
                }
                writer.write_event(Event::End(end))?;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    if !target_group_found {
        return Err(WolfPptError::InvalidInput(format!(
            "group shape id {target_group_shape_id} was not found"
        )));
    }
    if !deleted {
        return Err(WolfPptError::InvalidInput(format!(
            "group child shape id {target_child_shape_id} was not found in group {target_group_shape_id}"
        )));
    }

    let rewritten = writer.into_inner();
    let surviving_relationship_ids = relationship_ids_in_xml(&rewritten);
    removed_relationship_ids.retain(|id| !surviving_relationship_ids.contains(id));
    Ok((rewritten, 1, removed_relationship_ids))
}
