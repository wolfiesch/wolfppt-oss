fn replace_text_nodes(
    xml: &[u8],
    search: &str,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut in_text = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                if local_name(event.name().as_ref()) == b"t" {
                    in_text = true;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                if local_name(event.name().as_ref()) == b"t" {
                    in_text = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Text(event) if in_text => {
                let text = event
                    .decode()
                    .map_err(|err| WolfPptError::XmlText(err.to_string()))?
                    .into_owned();
                let count = text.matches(search).count();
                if count == 0 {
                    writer.write_event(Event::Text(event))?;
                } else {
                    replacements += count;
                    let replaced = text.replace(search, replacement);
                    writer.write_event(Event::Text(BytesText::new(&replaced)))?;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}
fn replace_text_run_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut in_text = false;
    let mut run_index = 0;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                if local_name(event.name().as_ref()) == b"t" {
                    in_text = true;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                if local_name(event.name().as_ref()) == b"t" {
                    in_text = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Text(event) if in_text => {
                if run_index == target_run_index {
                    writer.write_event(Event::Text(BytesText::new(replacement)))?;
                    replacements += 1;
                } else {
                    writer.write_event(Event::Text(event))?;
                }
                run_index += 1;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_text_run_bold_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    bold: Option<bool>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    set_text_run_bool_attribute_at_index_in_slide(xml, target_run_index, "b", bold)
}

fn set_text_run_italic_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    italic: Option<bool>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    set_text_run_bool_attribute_at_index_in_slide(xml, target_run_index, "i", italic)
}

fn set_text_run_underline_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    underline: Option<bool>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let value = underline.map(|value| {
        if value {
            "sng".to_string()
        } else {
            "none".to_string()
        }
    });
    set_text_run_optional_attribute_at_index_in_slide(xml, target_run_index, "u", value)
}

fn set_text_run_font_size_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    size: Option<i64>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let value = size.map(|value| (value / 127).to_string());
    set_text_run_optional_attribute_at_index_in_slide(xml, target_run_index, "sz", value)
}

fn set_text_run_font_name_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    font_name: Option<&str>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut run_index = 0;
    let mut target_depth = 0usize;
    let mut rpr_depth = 0usize;
    let mut skip_latin_depth = 0usize;
    let mut in_target_run = false;
    let mut handled_run_properties = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if skip_latin_depth > 0 {
                    skip_latin_depth += 1;
                    continue;
                }
                if name == b"r" && !in_target_run {
                    in_target_run = run_index == target_run_index;
                    run_index += 1;
                    if in_target_run {
                        target_depth = 1;
                        rpr_depth = 0;
                        handled_run_properties = false;
                    }
                    writer.write_event(Event::Start(event))?;
                    continue;
                }

                if in_target_run {
                    if target_depth == 1 && name != b"rPr" && !handled_run_properties {
                        write_run_properties_font_name(&mut writer, font_name)?;
                        handled_run_properties = true;
                        replacements += 1;
                    }
                    if name == b"rPr" && !handled_run_properties {
                        writer.write_event(Event::Start(event))?;
                        write_latin_typeface(&mut writer, font_name)?;
                        handled_run_properties = true;
                        replacements += 1;
                        rpr_depth = 1;
                        target_depth += 1;
                        continue;
                    }
                    if rpr_depth > 0 && name == b"latin" {
                        skip_latin_depth = 1;
                        continue;
                    }
                    writer.write_event(Event::Start(event))?;
                    target_depth += 1;
                    if rpr_depth > 0 {
                        rpr_depth += 1;
                    }
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if skip_latin_depth > 0 {
                    continue;
                }
                if in_target_run {
                    if target_depth == 1 && name != b"rPr" && !handled_run_properties {
                        write_run_properties_font_name(&mut writer, font_name)?;
                        handled_run_properties = true;
                        replacements += 1;
                    }
                    if name == b"rPr" && !handled_run_properties {
                        if font_name.is_some() {
                            let start = event.to_owned();
                            writer.write_event(Event::Start(start))?;
                            write_latin_typeface(&mut writer, font_name)?;
                            writer.write_event(Event::End(BytesEnd::new("a:rPr")))?;
                        } else {
                            writer.write_event(Event::Empty(event))?;
                        }
                        handled_run_properties = true;
                        replacements += 1;
                    } else if rpr_depth > 0 && name == b"latin" {
                        continue;
                    } else {
                        writer.write_event(Event::Empty(event))?;
                    }
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::End(event) => {
                if skip_latin_depth > 0 {
                    skip_latin_depth = skip_latin_depth.saturating_sub(1);
                    continue;
                }
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_run {
                    if target_depth == 1 && name == b"r" && !handled_run_properties {
                        write_run_properties_font_name(&mut writer, font_name)?;
                        replacements += 1;
                    }
                    writer.write_event(Event::End(event))?;
                    target_depth = target_depth.saturating_sub(1);
                    if rpr_depth > 0 {
                        rpr_depth = rpr_depth.saturating_sub(1);
                    }
                    if target_depth == 0 {
                        in_target_run = false;
                    }
                } else {
                    writer.write_event(Event::End(event))?;
                }
            }
            Event::Eof => break,
            event => {
                if skip_latin_depth == 0 {
                    writer.write_event(event)?;
                }
            }
        }
    }

    Ok((writer.into_inner(), replacements))
}

#[derive(Clone, Copy)]
struct TextRunFormattingPatch<'a> {
    bold: Option<Option<bool>>,
    italic: Option<Option<bool>>,
    underline: Option<Option<bool>>,
    size: Option<Option<i64>>,
    name: Option<Option<&'a str>>,
    color: Option<Option<&'a str>>,
}

impl<'a> TextRunFormattingPatch<'a> {
    fn merge(&mut self, patch: TextRunFormattingPatch<'a>) {
        if patch.bold.is_some() {
            self.bold = patch.bold;
        }
        if patch.italic.is_some() {
            self.italic = patch.italic;
        }
        if patch.underline.is_some() {
            self.underline = patch.underline;
        }
        if patch.size.is_some() {
            self.size = patch.size;
        }
        if patch.name.is_some() {
            self.name = patch.name;
        }
        if patch.color.is_some() {
            self.color = patch.color;
        }
    }

    fn attribute_replacements(&self) -> Vec<(&'static str, Option<String>)> {
        let mut replacements = Vec::new();
        if let Some(bold) = self.bold {
            replacements.push((
                "b",
                bold.map(|value| if value { "1" } else { "0" }.to_string()),
            ));
        }
        if let Some(italic) = self.italic {
            replacements.push((
                "i",
                italic.map(|value| if value { "1" } else { "0" }.to_string()),
            ));
        }
        if let Some(underline) = self.underline {
            replacements.push((
                "u",
                underline.map(|value| {
                    if value {
                        "sng".to_string()
                    } else {
                        "none".to_string()
                    }
                }),
            ));
        }
        if let Some(size) = self.size {
            replacements.push(("sz", size.map(|value| (value / 127).to_string())));
        }
        replacements
    }

    fn replacement_count(&self) -> usize {
        usize::from(self.bold.is_some())
            + usize::from(self.italic.is_some())
            + usize::from(self.underline.is_some())
            + usize::from(self.size.is_some())
            + usize::from(self.name.is_some())
            + usize::from(self.color.is_some())
    }
}

struct ParagraphFontPatch<'a> {
    bold: Option<Option<bool>>,
    italic: Option<Option<bool>>,
    underline: Option<Option<bool>>,
    size: Option<Option<i64>>,
    name: Option<Option<&'a str>>,
    color: Option<Option<&'a str>>,
    fill_type: Option<Option<&'a str>>,
    language_id: Option<Option<&'a str>>,
}

impl<'a> ParagraphFontPatch<'a> {
    fn attribute_replacements(&self) -> Vec<(&'static str, Option<String>)> {
        let mut replacements = Vec::new();
        if let Some(bold) = self.bold {
            replacements.push((
                "b",
                bold.map(|value| if value { "1" } else { "0" }.to_string()),
            ));
        }
        if let Some(italic) = self.italic {
            replacements.push((
                "i",
                italic.map(|value| if value { "1" } else { "0" }.to_string()),
            ));
        }
        if let Some(underline) = self.underline {
            replacements.push((
                "u",
                underline.map(|value| {
                    if value {
                        "sng".to_string()
                    } else {
                        "none".to_string()
                    }
                }),
            ));
        }
        if let Some(size) = self.size {
            replacements.push(("sz", size.map(|value| (value / 127).to_string())));
        }
        if let Some(language_id) = self.language_id {
            replacements.push(("lang", language_id.map(str::to_string)));
        }
        replacements
    }

    fn replaces_fill(&self) -> bool {
        self.color.is_some() || self.fill_type.is_some()
    }

    fn replacement_count(&self) -> usize {
        usize::from(self.bold.is_some())
            + usize::from(self.italic.is_some())
            + usize::from(self.underline.is_some())
            + usize::from(self.size.is_some())
            + usize::from(self.name.is_some())
            + usize::from(self.color.is_some())
            + usize::from(self.fill_type.is_some())
            + usize::from(self.language_id.is_some())
    }
}

fn set_text_run_formatting_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    patch: &TextRunFormattingPatch<'_>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    set_text_run_formatting_batch_in_slide(xml, &[(target_run_index, *patch)])
}

fn set_text_run_formatting_batch_in_slide(
    xml: &[u8],
    patches: &[(usize, TextRunFormattingPatch<'_>)],
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut patches_by_run: BTreeMap<usize, TextRunFormattingPatch<'_>> = BTreeMap::new();
    for (run_index, patch) in patches.iter().copied() {
        patches_by_run
            .entry(run_index)
            .and_modify(|existing| existing.merge(patch))
            .or_insert(patch);
    }
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut run_index = 0;
    let mut target_depth = 0usize;
    let mut rpr_depth = 0usize;
    let mut skip_latin_depth = 0usize;
    let mut skip_fill_depth = 0usize;
    let mut in_target_run = false;
    let mut handled_run_properties = false;
    let mut replacements = 0;
    let mut active_patch: Option<TextRunFormattingPatch<'_>> = None;
    let mut attribute_replacements = Vec::new();

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if skip_latin_depth > 0 {
                    skip_latin_depth += 1;
                    continue;
                }
                if skip_fill_depth > 0 {
                    skip_fill_depth += 1;
                    continue;
                }
                if name == b"r" && !in_target_run {
                    active_patch = patches_by_run.get(&run_index).copied();
                    in_target_run = active_patch.is_some();
                    run_index += 1;
                    if in_target_run {
                        target_depth = 1;
                        rpr_depth = 0;
                        handled_run_properties = false;
                        attribute_replacements = active_patch
                            .expect("target run has an active formatting patch")
                            .attribute_replacements();
                    }
                    writer.write_event(Event::Start(event))?;
                    continue;
                }

                if in_target_run {
                    let patch = active_patch.expect("target run has an active formatting patch");
                    if target_depth == 1 && name != b"rPr" && !handled_run_properties {
                        write_run_properties_formatting(
                            &mut writer,
                            &attribute_replacements,
                            patch.name,
                            patch.color,
                        )?;
                        handled_run_properties = true;
                        replacements += patch.replacement_count();
                    }
                    if name == b"rPr" && !handled_run_properties {
                        writer.write_event(Event::Start(rewrite_event_optional_attributes(
                            &event,
                            &attribute_replacements,
                        )))?;
                        write_run_fill(&mut writer, patch.color)?;
                        if let Some(font_name) = patch.name {
                            write_latin_typeface(&mut writer, font_name)?;
                        }
                        handled_run_properties = true;
                        replacements += patch.replacement_count();
                        rpr_depth = 1;
                        target_depth += 1;
                        continue;
                    }
                    if rpr_depth > 0 && name == b"latin" && patch.name.is_some() {
                        skip_latin_depth = 1;
                        continue;
                    }
                    if rpr_depth > 0 && is_fill_property(&name) && patch.color.is_some() {
                        skip_fill_depth = 1;
                        continue;
                    }
                    writer.write_event(Event::Start(event))?;
                    target_depth += 1;
                    if rpr_depth > 0 {
                        rpr_depth += 1;
                    }
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if skip_latin_depth > 0 {
                    continue;
                }
                if skip_fill_depth > 0 {
                    continue;
                }
                if in_target_run {
                    let patch = active_patch.expect("target run has an active formatting patch");
                    if target_depth == 1 && name != b"rPr" && !handled_run_properties {
                        write_run_properties_formatting(
                            &mut writer,
                            &attribute_replacements,
                            patch.name,
                            patch.color,
                        )?;
                        handled_run_properties = true;
                        replacements += patch.replacement_count();
                    }
                    if name == b"rPr" && !handled_run_properties {
                        let rewritten =
                            rewrite_event_optional_attributes(&event, &attribute_replacements);
                        if matches!(patch.name, Some(Some(_)))
                            || matches!(patch.color, Some(Some(_)))
                        {
                            writer.write_event(Event::Start(rewritten))?;
                            write_run_fill(&mut writer, patch.color)?;
                            if let Some(font_name) = patch.name {
                                write_latin_typeface(&mut writer, font_name)?;
                            }
                            writer.write_event(Event::End(BytesEnd::new("a:rPr")))?;
                        } else {
                            writer.write_event(Event::Empty(rewritten))?;
                        }
                        handled_run_properties = true;
                        replacements += patch.replacement_count();
                    } else if rpr_depth > 0 && name == b"latin" && patch.name.is_some() {
                        continue;
                    } else if rpr_depth > 0 && is_fill_property(&name) && patch.color.is_some() {
                        continue;
                    } else {
                        writer.write_event(Event::Empty(event))?;
                    }
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::End(event) => {
                if skip_latin_depth > 0 {
                    skip_latin_depth = skip_latin_depth.saturating_sub(1);
                    continue;
                }
                if skip_fill_depth > 0 {
                    skip_fill_depth = skip_fill_depth.saturating_sub(1);
                    continue;
                }
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_run {
                    let patch = active_patch.expect("target run has an active formatting patch");
                    if target_depth == 1 && name == b"r" && !handled_run_properties {
                        write_run_properties_formatting(
                            &mut writer,
                            &attribute_replacements,
                            patch.name,
                            patch.color,
                        )?;
                        replacements += patch.replacement_count();
                    }
                    writer.write_event(Event::End(event))?;
                    target_depth = target_depth.saturating_sub(1);
                    if rpr_depth > 0 {
                        rpr_depth = rpr_depth.saturating_sub(1);
                    }
                    if target_depth == 0 {
                        in_target_run = false;
                        active_patch = None;
                        attribute_replacements.clear();
                    }
                } else {
                    writer.write_event(Event::End(event))?;
                }
            }
            Event::Eof => break,
            event => {
                if skip_latin_depth == 0 && skip_fill_depth == 0 {
                    writer.write_event(event)?;
                }
            }
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn set_text_run_bool_attribute_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    attribute_name: &'static str,
    value: Option<bool>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    set_text_run_optional_attribute_at_index_in_slide(
        xml,
        target_run_index,
        attribute_name,
        value.map(|value| if value { "1" } else { "0" }.to_string()),
    )
}

fn set_text_run_optional_attribute_at_index_in_slide(
    xml: &[u8],
    target_run_index: usize,
    attribute_name: &'static str,
    value: Option<String>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut run_index = 0;
    let mut target_depth = 0usize;
    let mut in_target_run = false;
    let mut handled_run_properties = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"r" && !in_target_run {
                    in_target_run = run_index == target_run_index;
                    run_index += 1;
                    if in_target_run {
                        target_depth = 1;
                        handled_run_properties = false;
                    }
                    writer.write_event(Event::Start(event))?;
                    continue;
                }

                if in_target_run {
                    if target_depth == 1 && name != b"rPr" && !handled_run_properties {
                        write_run_properties_optional_attribute(
                            &mut writer,
                            attribute_name,
                            value.as_deref(),
                        )?;
                        handled_run_properties = true;
                        replacements += 1;
                    }
                    if name == b"rPr" && !handled_run_properties {
                        writer.write_event(Event::Start(rewrite_event_optional_attributes(
                            &event,
                            &[(attribute_name, value.clone())],
                        )))?;
                        handled_run_properties = true;
                        replacements += 1;
                    } else {
                        writer.write_event(Event::Start(event))?;
                    }
                    target_depth += 1;
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_run {
                    if target_depth == 1 && name != b"rPr" && !handled_run_properties {
                        write_run_properties_optional_attribute(
                            &mut writer,
                            attribute_name,
                            value.as_deref(),
                        )?;
                        handled_run_properties = true;
                        replacements += 1;
                    }
                    if name == b"rPr" && !handled_run_properties {
                        writer.write_event(Event::Empty(rewrite_event_optional_attributes(
                            &event,
                            &[(attribute_name, value.clone())],
                        )))?;
                        handled_run_properties = true;
                        replacements += 1;
                    } else {
                        writer.write_event(Event::Empty(event))?;
                    }
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_run {
                    if target_depth == 1 && name == b"r" && !handled_run_properties {
                        write_run_properties_optional_attribute(
                            &mut writer,
                            attribute_name,
                            value.as_deref(),
                        )?;
                        replacements += 1;
                    }
                    writer.write_event(Event::End(event))?;
                    target_depth = target_depth.saturating_sub(1);
                    if target_depth == 0 {
                        in_target_run = false;
                    }
                } else {
                    writer.write_event(Event::End(event))?;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}
