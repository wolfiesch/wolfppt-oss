fn write_paragraph_properties(
    writer: &mut Writer<Vec<u8>>,
    alignment: Option<Option<&str>>,
    level: Option<usize>,
    spacing: &ParagraphSpacingPatch,
) -> Result<(), WolfPptError> {
    let paragraph_properties = paragraph_property_start(alignment, level);
    if paragraph_spacing_replacement_count(spacing) == 0 {
        writer.write_event(Event::Empty(paragraph_properties))?;
    } else {
        writer.write_event(Event::Start(paragraph_properties))?;
        write_paragraph_spacing_children(writer, spacing)?;
        writer.write_event(Event::End(BytesEnd::new("a:pPr")))?;
    }
    Ok(())
}

fn write_paragraph_properties_with_default_run_properties(
    writer: &mut Writer<Vec<u8>>,
    patch: &ParagraphFontPatch<'_>,
) -> Result<(), WolfPptError> {
    writer.write_event(Event::Start(BytesStart::new("a:pPr")))?;
    write_default_run_properties(writer, patch)?;
    writer.write_event(Event::End(BytesEnd::new("a:pPr")))?;
    Ok(())
}

fn write_default_run_properties(
    writer: &mut Writer<Vec<u8>>,
    patch: &ParagraphFontPatch<'_>,
) -> Result<(), WolfPptError> {
    let attribute_replacements = patch.attribute_replacements();
    let mut default_run_properties = BytesStart::new("a:defRPr");
    for (attribute_name, value) in &attribute_replacements {
        if let Some(value) = value {
            default_run_properties.push_attribute((*attribute_name, value.as_str()));
        }
    }
    if default_run_property_child_count(patch) == 0 {
        writer.write_event(Event::Empty(default_run_properties))?;
    } else {
        writer.write_event(Event::Start(default_run_properties))?;
        write_default_run_property_children(writer, patch)?;
        writer.write_event(Event::End(BytesEnd::new("a:defRPr")))?;
    }
    Ok(())
}

fn write_default_run_property_children(
    writer: &mut Writer<Vec<u8>>,
    patch: &ParagraphFontPatch<'_>,
) -> Result<(), WolfPptError> {
    write_default_run_fill(writer, patch)?;
    if let Some(font_name) = patch.name {
        write_latin_typeface(writer, font_name)?;
    }
    Ok(())
}

fn write_default_run_fill(
    writer: &mut Writer<Vec<u8>>,
    patch: &ParagraphFontPatch<'_>,
) -> Result<(), WolfPptError> {
    if let Some(Some(color)) = patch.color {
        writer.write_event(Event::Start(BytesStart::new("a:solidFill")))?;
        let mut srgb_color = BytesStart::new("a:srgbClr");
        srgb_color.push_attribute(("val", color));
        writer.write_event(Event::Empty(srgb_color))?;
        writer.write_event(Event::End(BytesEnd::new("a:solidFill")))?;
        return Ok(());
    }
    if let Some(Some("solid")) = patch.fill_type {
        writer.write_event(Event::Empty(BytesStart::new("a:solidFill")))?;
    } else if let Some(Some("background")) = patch.fill_type {
        writer.write_event(Event::Empty(BytesStart::new("a:noFill")))?;
    }
    Ok(())
}

fn default_run_property_child_count(patch: &ParagraphFontPatch<'_>) -> usize {
    usize::from(matches!(patch.name, Some(Some(_))))
        + usize::from(matches!(patch.color, Some(Some(_))))
        + usize::from(matches!(
            patch.fill_type,
            Some(Some("solid")) | Some(Some("background"))
        ))
}

fn paragraph_property_start(
    alignment: Option<Option<&str>>,
    level: Option<usize>,
) -> BytesStart<'static> {
    let mut paragraph_properties = BytesStart::new("a:pPr");
    if let Some(Some(alignment)) = alignment {
        paragraph_properties.push_attribute(("algn", alignment));
    }
    if let Some(level) = level {
        if level != 0 {
            let level = level.to_string();
            paragraph_properties.push_attribute(("lvl", level.as_str()));
        }
    }
    paragraph_properties
}

fn rewrite_paragraph_property_attributes(
    event: &BytesStart<'_>,
    alignment: Option<Option<&str>>,
    level: Option<usize>,
) -> BytesStart<'static> {
    let mut replacements = Vec::new();
    if let Some(alignment) = alignment {
        replacements.push(("algn", alignment.map(str::to_string)));
    }
    if let Some(level) = level {
        replacements.push((
            "lvl",
            if level == 0 {
                None
            } else {
                Some(level.to_string())
            },
        ));
    }
    rewrite_event_optional_attributes(event, &replacements)
}

fn write_paragraph_spacing_children(
    writer: &mut Writer<Vec<u8>>,
    spacing: &ParagraphSpacingPatch,
) -> Result<(), WolfPptError> {
    for key in ["line_spacing", "space_before", "space_after"] {
        if let Some(value) = paragraph_spacing_value(spacing, key) {
            write_paragraph_spacing_child(writer, key, value)?;
        }
    }
    Ok(())
}

fn write_paragraph_spacing_child(
    writer: &mut Writer<Vec<u8>>,
    key: &'static str,
    value: &ParagraphSpacingValue,
) -> Result<(), WolfPptError> {
    if matches!(value, ParagraphSpacingValue::Clear) {
        return Ok(());
    }
    let tag = paragraph_spacing_tag(key);
    writer.write_event(Event::Start(BytesStart::new(format!("a:{tag}"))))?;
    match value {
        ParagraphSpacingValue::Clear => {}
        ParagraphSpacingValue::Emu { value } => {
            let mut spacing = BytesStart::new("a:spcPts");
            let centipoints = ((*value as f64) / 127.0).round() as i64;
            let value = centipoints.to_string();
            spacing.push_attribute(("val", value.as_str()));
            writer.write_event(Event::Empty(spacing))?;
        }
        ParagraphSpacingValue::Multiple { value } => {
            let mut spacing = BytesStart::new("a:spcPct");
            let value = (value * 100000.0).round() as i64;
            let value = value.to_string();
            spacing.push_attribute(("val", value.as_str()));
            writer.write_event(Event::Empty(spacing))?;
        }
    }
    writer.write_event(Event::End(BytesEnd::new(format!("a:{tag}"))))?;
    Ok(())
}

fn paragraph_property_replacement_count(
    alignment: Option<Option<&str>>,
    level: Option<usize>,
    spacing: &ParagraphSpacingPatch,
) -> usize {
    usize::from(alignment.is_some())
        + usize::from(level.is_some())
        + paragraph_spacing_replacement_count(spacing)
}

fn paragraph_spacing_replacement_count(spacing: &ParagraphSpacingPatch) -> usize {
    usize::from(spacing.line_spacing.is_some())
        + usize::from(spacing.space_before.is_some())
        + usize::from(spacing.space_after.is_some())
}

fn paragraph_spacing_value<'a>(
    spacing: &'a ParagraphSpacingPatch,
    key: &'static str,
) -> Option<&'a ParagraphSpacingValue> {
    match key {
        "line_spacing" => spacing.line_spacing.as_ref(),
        "space_before" => spacing.space_before.as_ref(),
        "space_after" => spacing.space_after.as_ref(),
        _ => None,
    }
}

fn paragraph_spacing_key(name: &[u8]) -> Option<&'static str> {
    match name {
        b"lnSpc" => Some("line_spacing"),
        b"spcBef" => Some("space_before"),
        b"spcAft" => Some("space_after"),
        _ => None,
    }
}

fn paragraph_spacing_tag(key: &'static str) -> &'static str {
    match key {
        "line_spacing" => "lnSpc",
        "space_before" => "spcBef",
        "space_after" => "spcAft",
        _ => key,
    }
}
