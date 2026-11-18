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
        let key = attr.key.as_ref();
        let mut value = attr.value.as_ref();
        for (index, (replacement_key, replacement_value)) in replacements.iter().enumerate() {
            if key == *replacement_key {
                value = replacement_value.as_str();
                seen[index] = true;
                break;
            }
        }
        rewritten.push_attribute((key, value));
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
        let key = attr.key.as_ref();
        let value = attr.value.as_ref();
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
            rewritten.push_attribute((key, value));
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
    font_color: Option<Option<RunFillColor<'_>>>,
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

/// A validated run fill colour, written as the single child of `a:solidFill`.
#[derive(Clone, Copy)]
enum RunFillColor<'a> {
    /// The legacy `color` string, written verbatim as `a:srgbClr/@val`.
    Hex(&'a str),
    Srgb([u8; 6]),
    Preset(&'static str),
    System {
        value: &'static str,
        last_color: Option<[u8; 6]>,
    },
    /// Channels already clamped into `0..=100000`.
    ScRgb {
        r: i64,
        g: i64,
        b: i64,
    },
}

/// Upper bound of an `ST_Percentage` scRGB channel (100%, in 1/1000 percent).
const SCRGB_CHANNEL_MAX: i64 = 100_000;

impl<'a> RunFillColor<'a> {
    /// Resolves the `color` / `color_model` pair of a run formatting edit.
    /// `None` means the fill is removed.
    fn from_request(
        color: Option<&'a str>,
        color_model: Option<&DrawingColor>,
    ) -> Result<Option<Self>, WolfPptError> {
        match (color, color_model) {
            (Some(_), Some(_)) => Err(WolfPptError::InvalidInput(
                "text run formatting accepts either color or color_model, not both".to_string(),
            )),
            (Some(hex), None) => Ok(Some(Self::Hex(hex))),
            (None, None) => Ok(None),
            (None, Some(model)) => Self::from_model(model).map(Some),
        }
    }

    fn from_model(model: &DrawingColor) -> Result<Self, WolfPptError> {
        match model {
            DrawingColor::Srgb { value } => {
                uppercase_hex6(value).map(Self::Srgb).ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "srgb color value must be six hex digits, got {value:?}"
                    ))
                })
            }
            DrawingColor::Preset { value } => PRESET_COLOR_TOKENS
                .iter()
                .find(|token| **token == value.as_str())
                .copied()
                .map(Self::Preset)
                .ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "preset color value must be an ST_PresetColorVal token, got {value:?}"
                    ))
                }),
            DrawingColor::System { value, last_color } => {
                let value = SYSTEM_COLOR_TOKENS
                    .iter()
                    .find(|token| **token == value.as_str())
                    .copied()
                    .ok_or_else(|| {
                        WolfPptError::InvalidInput(format!(
                            "system color value must be an ST_SystemColorVal token, got {value:?}"
                        ))
                    })?;
                let last_color = match last_color {
                    Some(hex) => Some(uppercase_hex6(hex).ok_or_else(|| {
                        WolfPptError::InvalidInput(format!(
                            "system color last_color must be six hex digits, got {hex:?}"
                        ))
                    })?),
                    None => None,
                };
                Ok(Self::System { value, last_color })
            }
            DrawingColor::Scrgb { r, g, b } => Ok(Self::ScRgb {
                r: (*r).clamp(0, SCRGB_CHANNEL_MAX),
                g: (*g).clamp(0, SCRGB_CHANNEL_MAX),
                b: (*b).clamp(0, SCRGB_CHANNEL_MAX),
            }),
        }
    }

    fn element(&self) -> BytesStart<'static> {
        match self {
            Self::Hex(hex) => {
                let mut element = BytesStart::new("a:srgbClr");
                element.push_attribute(("val", *hex));
                element
            }
            Self::Srgb(hex) => {
                let mut element = BytesStart::new("a:srgbClr");
                element.push_attribute(("val", hex_str(hex)));
                element
            }
            Self::Preset(value) => {
                let mut element = BytesStart::new("a:prstClr");
                element.push_attribute(("val", *value));
                element
            }
            Self::System { value, last_color } => {
                let mut element = BytesStart::new("a:sysClr");
                element.push_attribute(("val", *value));
                if let Some(last_color) = last_color {
                    element.push_attribute(("lastClr", hex_str(last_color)));
                }
                element
            }
            Self::ScRgb { r, g, b } => {
                let mut element = BytesStart::new("a:scrgbClr");
                element.push_attribute(("r", r.to_string().as_str()));
                element.push_attribute(("g", g.to_string().as_str()));
                element.push_attribute(("b", b.to_string().as_str()));
                element
            }
        }
    }
}

fn hex_str(hex: &[u8; 6]) -> &str {
    std::str::from_utf8(hex).expect("validated hex digits are ASCII")
}

/// Six ASCII hex digits, uppercased.
fn uppercase_hex6(value: &str) -> Option<[u8; 6]> {
    let digits: [u8; 6] = value.as_bytes().try_into().ok()?;
    digits
        .iter()
        .all(u8::is_ascii_hexdigit)
        .then(|| digits.map(|digit| digit.to_ascii_uppercase()))
}

fn write_run_fill(
    writer: &mut Writer<Vec<u8>>,
    font_color: Option<Option<RunFillColor<'_>>>,
) -> Result<(), WolfPptError> {
    if let Some(Some(color)) = font_color {
        writer.write_event(Event::Start(BytesStart::new("a:solidFill")))?;
        writer.write_event(Event::Empty(color.element()))?;
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
            Event::Start(event) if local_name(event.name().as_ref().as_bytes()) == b"p" => {
                replaced_paragraphs += 1;
                skip_current_element(reader)?;
            }
            Event::Empty(event) if local_name(event.name().as_ref().as_bytes()) == b"p" => {
                replaced_paragraphs += 1;
            }
            Event::End(event) if local_name(event.name().as_ref().as_bytes()) == b"txBody" => {
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
