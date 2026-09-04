fn is_shape_element_name(name: &[u8]) -> bool {
    matches!(name, b"sp" | b"pic" | b"graphicFrame" | b"grpSp" | b"cxnSp")
}

fn rewrite_event_attributes(
    event: &BytesStart<'_>,
    replacements: &[(&str, String)],
) -> BytesStart<'static> {
    let mut rewritten = event.to_owned();
    rewritten.clear_attributes();
    let mut seen = vec![false; replacements.len()];

    for attr in event.attributes().flatten() {
        let key = std::str::from_utf8(attr.key.as_ref()).unwrap_or_default();
        let mut value = std::str::from_utf8(attr.value.as_ref())
            .unwrap_or_default()
            .to_string();
        for (index, (replacement_key, replacement_value)) in replacements.iter().enumerate() {
            if key == *replacement_key {
                value = replacement_value.clone();
                seen[index] = true;
                break;
            }
        }
        rewritten.push_attribute((key, value.as_str()));
    }

    for (index, (key, value)) in replacements.iter().enumerate() {
        if !seen[index] {
            rewritten.push_attribute((*key, value.as_str()));
        }
    }

    rewritten
}

fn rewrite_event_optional_attributes(
    event: &BytesStart<'_>,
    replacements: &[(&str, Option<String>)],
) -> BytesStart<'static> {
    let mut rewritten = event.to_owned();
    rewritten.clear_attributes();
    let mut seen = vec![false; replacements.len()];

    for attr in event.attributes().flatten() {
        let key = std::str::from_utf8(attr.key.as_ref()).unwrap_or_default();
        let value = std::str::from_utf8(attr.value.as_ref())
            .unwrap_or_default()
            .to_string();
        let mut matched = false;
        for (index, (replacement_key, replacement_value)) in replacements.iter().enumerate() {
            if key == *replacement_key {
                matched = true;
                seen[index] = true;
                if let Some(value) = replacement_value {
                    rewritten.push_attribute((key, value.as_str()));
                }
                break;
            }
        }
        if !matched {
            rewritten.push_attribute((key, value.as_str()));
        }
    }

    for (index, (key, value)) in replacements.iter().enumerate() {
        if !seen[index] {
            if let Some(value) = value {
                rewritten.push_attribute((*key, value.as_str()));
            }
        }
    }

    rewritten
}

fn write_run_properties_optional_attribute(
    writer: &mut Writer<Vec<u8>>,
    attribute_name: &'static str,
    value: Option<&str>,
) -> Result<(), WolfPptError> {
    let mut run_properties = BytesStart::new("a:rPr");
    if let Some(value) = value {
        run_properties.push_attribute((attribute_name, value));
    }
    writer.write_event(Event::Empty(run_properties))?;
    Ok(())
}

fn write_run_properties_formatting(
    writer: &mut Writer<Vec<u8>>,
    attribute_replacements: &[(&'static str, Option<String>)],
    font_name: Option<Option<&str>>,
    font_color: Option<Option<&str>>,
) -> Result<(), WolfPptError> {
    let mut run_properties = BytesStart::new("a:rPr");
    for (attribute_name, value) in attribute_replacements {
        if let Some(value) = value {
            run_properties.push_attribute((*attribute_name, value.as_str()));
        }
    }
    if matches!(font_name, Some(Some(_))) || matches!(font_color, Some(Some(_))) {
        writer.write_event(Event::Start(run_properties))?;
        write_run_fill(writer, font_color)?;
        if let Some(font_name) = font_name {
            write_latin_typeface(writer, font_name)?;
        }
        writer.write_event(Event::End(BytesEnd::new("a:rPr")))?;
    } else {
        writer.write_event(Event::Empty(run_properties))?;
    }
    Ok(())
}

fn write_run_fill(
    writer: &mut Writer<Vec<u8>>,
    font_color: Option<Option<&str>>,
) -> Result<(), WolfPptError> {
    if let Some(Some(color)) = font_color {
        writer.write_event(Event::Start(BytesStart::new("a:solidFill")))?;
        let mut srgb_color = BytesStart::new("a:srgbClr");
        srgb_color.push_attribute(("val", color));
        writer.write_event(Event::Empty(srgb_color))?;
        writer.write_event(Event::End(BytesEnd::new("a:solidFill")))?;
    }
    Ok(())
}

fn is_fill_property(name: &[u8]) -> bool {
    matches!(
        name,
        b"solidFill" | b"noFill" | b"pattFill" | b"gradFill" | b"blipFill" | b"grpFill"
    )
}

fn write_run_properties_font_name(
    writer: &mut Writer<Vec<u8>>,
    font_name: Option<&str>,
) -> Result<(), WolfPptError> {
    if font_name.is_none() {
        writer.write_event(Event::Empty(BytesStart::new("a:rPr")))?;
        return Ok(());
    }
    writer.write_event(Event::Start(BytesStart::new("a:rPr")))?;
    write_latin_typeface(writer, font_name)?;
    writer.write_event(Event::End(BytesEnd::new("a:rPr")))?;
    Ok(())
}

fn write_latin_typeface(
    writer: &mut Writer<Vec<u8>>,
    font_name: Option<&str>,
) -> Result<(), WolfPptError> {
    if let Some(font_name) = font_name {
        let mut latin = BytesStart::new("a:latin");
        latin.push_attribute(("typeface", font_name));
        writer.write_event(Event::Empty(latin))?;
    }
    Ok(())
}

fn rewrite_text_body_content(
    reader: &mut Reader<&[u8]>,
    writer: &mut Writer<Vec<u8>>,
    replacement: &str,
) -> Result<usize, WolfPptError> {
    let mut replaced_paragraphs = 0;
    loop {
        match reader.read_event()? {
            Event::Start(event) if local_name(event.name().as_ref()) == b"p" => {
                replaced_paragraphs += 1;
                skip_current_element(reader)?;
            }
            Event::Empty(event) if local_name(event.name().as_ref()) == b"p" => {
                replaced_paragraphs += 1;
            }
            Event::End(event) if local_name(event.name().as_ref()) == b"txBody" => {
                write_replacement_paragraphs(writer, replacement)?;
                writer.write_event(Event::End(event))?;
                return Ok(replaced_paragraphs.max(1));
            }
            Event::Eof => {
                return Err(WolfPptError::XmlText(
                    "unexpected end of XML while rewriting text body".to_string(),
                ));
            }
            event => writer.write_event(event)?,
        }
    }
}

fn skip_current_element(reader: &mut Reader<&[u8]>) -> Result<(), WolfPptError> {
    let mut depth = 1;
    while depth > 0 {
        match reader.read_event()? {
            Event::Start(_) => depth += 1,
            Event::End(_) => depth -= 1,
            Event::Eof => {
                return Err(WolfPptError::XmlText(
                    "unexpected end of XML while skipping element".to_string(),
                ));
            }
            _ => {}
        }
    }
    Ok(())
}

fn write_replacement_paragraphs(
    writer: &mut Writer<Vec<u8>>,
    replacement: &str,
) -> Result<(), WolfPptError> {
    for line in replacement.split('\n') {
        write_text_paragraph(writer, line)?;
    }
    Ok(())
}

fn write_text_paragraph(writer: &mut Writer<Vec<u8>>, text: &str) -> Result<(), WolfPptError> {
    writer.write_event(Event::Start(BytesStart::new("a:p")))?;
    write_text_run(writer, text)?;
    writer.write_event(Event::End(BytesEnd::new("a:p")))?;
    Ok(())
}

fn write_text_run(writer: &mut Writer<Vec<u8>>, text: &str) -> Result<(), WolfPptError> {
    writer.write_event(Event::Start(BytesStart::new("a:r")))?;
    writer.write_event(Event::Start(BytesStart::new("a:t")))?;
    writer.write_event(Event::Text(BytesText::new(text)))?;
    writer.write_event(Event::End(BytesEnd::new("a:t")))?;
    writer.write_event(Event::End(BytesEnd::new("a:r")))?;
    Ok(())
}

fn write_paragraph_line_break(writer: &mut Writer<Vec<u8>>) -> Result<(), WolfPptError> {
    writer.write_event(Event::Empty(BytesStart::new("a:br")))?;
    Ok(())
}
