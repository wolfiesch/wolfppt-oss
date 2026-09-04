fn set_text_frame_properties_in_slide(
    xml: &[u8],
    target_shape_index: usize,
    patch: &TextFramePropertiesPatch,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    validate_text_frame_properties_patch(patch)?;
    let replacement_count = text_frame_property_replacement_count(patch);
    if replacement_count == 0 {
        return Ok((xml.to_vec(), 0));
    }

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut shape_index = 0;
    let mut in_target_shape = false;
    let mut in_target_text_body = false;
    let mut in_body_properties = false;
    let mut body_properties_depth = 0usize;
    let mut handled_body_properties = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"sp" {
                    in_target_shape = shape_index == target_shape_index;
                    shape_index += 1;
                }

                if in_target_shape && name == b"txBody" {
                    in_target_text_body = true;
                    handled_body_properties = false;
                    writer.write_event(Event::Start(event))?;
                    continue;
                }

                if in_body_properties {
                    if patch.set_auto_size && is_text_frame_auto_size_element(&name) {
                        skip_current_element(&mut reader)?;
                        continue;
                    }
                    body_properties_depth += 1;
                    writer.write_event(Event::Start(event))?;
                    continue;
                }

                if in_target_text_body && !handled_body_properties {
                    if name == b"bodyPr" {
                        write_rewritten_text_frame_body_properties_start(
                            &mut writer,
                            &event,
                            patch,
                        )?;
                        handled_body_properties = true;
                        replacements += replacement_count;
                        in_body_properties = true;
                        body_properties_depth = 1;
                        continue;
                    }
                    write_text_frame_body_properties(&mut writer, patch)?;
                    handled_body_properties = true;
                    replacements += replacement_count;
                }

                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_body_properties && patch.set_auto_size && is_text_frame_auto_size_element(&name)
                {
                    continue;
                }

                if in_target_text_body && !handled_body_properties {
                    if name == b"bodyPr" {
                        write_rewritten_text_frame_body_properties_empty(
                            &mut writer,
                            &event,
                            patch,
                        )?;
                        handled_body_properties = true;
                        replacements += replacement_count;
                        continue;
                    }
                    write_text_frame_body_properties(&mut writer, patch)?;
                    handled_body_properties = true;
                    replacements += replacement_count;
                }

                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_body_properties {
                    writer.write_event(Event::End(event))?;
                    body_properties_depth = body_properties_depth.saturating_sub(1);
                    if body_properties_depth == 0 {
                        in_body_properties = false;
                    }
                    continue;
                }

                if in_target_text_body && name == b"txBody" {
                    if !handled_body_properties {
                        write_text_frame_body_properties(&mut writer, patch)?;
                        replacements += replacement_count;
                    }
                    in_target_text_body = false;
                    handled_body_properties = false;
                    writer.write_event(Event::End(event))?;
                    continue;
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

fn validate_text_frame_properties_patch(
    patch: &TextFramePropertiesPatch,
) -> Result<(), WolfPptError> {
    for key in patch.margins.keys() {
        if text_frame_margin_attribute(key).is_none() {
            return Err(WolfPptError::InvalidInput(format!(
                "unsupported text frame margin attribute: {key}"
            )));
        }
    }
    if patch.set_word_wrap {
        if let Some(value) = patch.word_wrap.as_deref() {
            if !matches!(value, "square" | "none") {
                return Err(WolfPptError::InvalidInput(format!(
                    "unsupported text frame word wrap value: {value}"
                )));
            }
        }
    }
    if patch.set_vertical_anchor {
        if let Some(value) = patch.vertical_anchor.as_deref() {
            if !matches!(value, "t" | "ctr" | "b" | "just" | "dist") {
                return Err(WolfPptError::InvalidInput(format!(
                    "unsupported text frame vertical anchor value: {value}"
                )));
            }
        }
    }
    if patch.set_auto_size {
        if let Some(value) = patch.auto_size.as_deref() {
            if !matches!(value, "noAutofit" | "spAutoFit" | "normAutofit") {
                return Err(WolfPptError::InvalidInput(format!(
                    "unsupported text frame auto-size value: {value}"
                )));
            }
        }
    }
    Ok(())
}

fn write_rewritten_text_frame_body_properties_start(
    writer: &mut Writer<Vec<u8>>,
    event: &BytesStart<'_>,
    patch: &TextFramePropertiesPatch,
) -> Result<(), WolfPptError> {
    writer.write_event(Event::Start(rewrite_event_optional_attributes(
        event,
        &text_frame_body_property_attributes(patch),
    )))?;
    write_text_frame_auto_size(writer, patch)?;
    Ok(())
}

fn write_rewritten_text_frame_body_properties_empty(
    writer: &mut Writer<Vec<u8>>,
    event: &BytesStart<'_>,
    patch: &TextFramePropertiesPatch,
) -> Result<(), WolfPptError> {
    let rewritten = rewrite_event_optional_attributes(
        event,
        &text_frame_body_property_attributes(patch),
    );
    if patch.set_auto_size && patch.auto_size.is_some() {
        writer.write_event(Event::Start(rewritten))?;
        write_text_frame_auto_size(writer, patch)?;
        writer.write_event(Event::End(BytesEnd::new("a:bodyPr")))?;
    } else {
        writer.write_event(Event::Empty(rewritten))?;
    }
    Ok(())
}

fn write_text_frame_body_properties(
    writer: &mut Writer<Vec<u8>>,
    patch: &TextFramePropertiesPatch,
) -> Result<(), WolfPptError> {
    let mut body_properties = BytesStart::new("a:bodyPr");
    for (attribute, value) in text_frame_body_property_attributes(patch) {
        if let Some(value) = value {
            body_properties.push_attribute((attribute, value.as_str()));
        }
    }
    if patch.set_auto_size && patch.auto_size.is_some() {
        writer.write_event(Event::Start(body_properties))?;
        write_text_frame_auto_size(writer, patch)?;
        writer.write_event(Event::End(BytesEnd::new("a:bodyPr")))?;
    } else {
        writer.write_event(Event::Empty(body_properties))?;
    }
    Ok(())
}

fn write_text_frame_auto_size(
    writer: &mut Writer<Vec<u8>>,
    patch: &TextFramePropertiesPatch,
) -> Result<(), WolfPptError> {
    if let Some(tag) = patch.auto_size.as_deref().filter(|_| patch.set_auto_size) {
        writer.write_event(Event::Empty(BytesStart::new(format!("a:{tag}"))))?;
    }
    Ok(())
}

fn text_frame_body_property_attributes(
    patch: &TextFramePropertiesPatch,
) -> Vec<(&'static str, Option<String>)> {
    let mut attributes = Vec::new();
    for (key, value) in &patch.margins {
        if let Some(attribute) = text_frame_margin_attribute(key) {
            attributes.push((attribute, Some(value.to_string())));
        }
    }
    if patch.set_word_wrap {
        attributes.push(("wrap", patch.word_wrap.clone()));
    }
    if patch.set_vertical_anchor {
        attributes.push(("anchor", patch.vertical_anchor.clone()));
    }
    attributes
}

fn text_frame_margin_attribute(key: &str) -> Option<&'static str> {
    match key {
        "lIns" => Some("lIns"),
        "rIns" => Some("rIns"),
        "tIns" => Some("tIns"),
        "bIns" => Some("bIns"),
        _ => None,
    }
}

fn text_frame_property_replacement_count(patch: &TextFramePropertiesPatch) -> usize {
    patch.margins.len()
        + usize::from(patch.set_word_wrap)
        + usize::from(patch.set_vertical_anchor)
        + usize::from(patch.set_auto_size)
}

fn is_text_frame_auto_size_element(name: &[u8]) -> bool {
    matches!(name, b"noAutofit" | b"spAutoFit" | b"normAutofit")
}
