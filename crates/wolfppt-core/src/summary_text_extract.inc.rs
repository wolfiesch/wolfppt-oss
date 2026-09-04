fn is_slide_part(name: &str) -> bool {
    let Some(rest) = name.strip_prefix("ppt/slides/slide") else {
        return false;
    };
    let Some(number) = rest.strip_suffix(".xml") else {
        return false;
    };
    !number.is_empty() && number.chars().all(|ch| ch.is_ascii_digit())
}

fn xml_text_content(event: &BytesText<'_>) -> Option<String> {
    event
        .xml10_content()
        .ok()
        .map(|text| text.into_owned())
        .filter(|text| !text.is_empty())
}

fn xml_reference_content(event: &BytesRef<'_>) -> Option<String> {
    if let Ok(Some(ch)) = event.resolve_char_ref() {
        return Some(ch.to_string());
    }

    let name = event.decode().ok()?;
    let text = match name.as_ref() {
        "amp" => "&".to_string(),
        "lt" => "<".to_string(),
        "gt" => ">".to_string(),
        "quot" => "\"".to_string(),
        "apos" => "'".to_string(),
        other => format!("&{other};"),
    };
    (!text.is_empty()).then_some(text)
}

fn extract_text_runs(xml: &[u8]) -> Vec<String> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    let mut in_text = false;
    let mut current_text = String::new();
    let mut texts = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => {
                in_text = event.name().as_ref().ends_with(b":t") || event.name().as_ref() == b"t";
                if in_text {
                    current_text.clear();
                }
            }
            Ok(Event::End(event)) => {
                if event.name().as_ref().ends_with(b":t") || event.name().as_ref() == b"t" {
                    if !current_text.is_empty() {
                        texts.push(std::mem::take(&mut current_text));
                    }
                    in_text = false;
                }
            }
            Ok(Event::Text(event)) if in_text => {
                if let Some(text) = xml_text_content(&event) {
                    current_text.push_str(&text);
                }
            }
            Ok(Event::GeneralRef(event)) if in_text => {
                if let Some(text) = xml_reference_content(&event) {
                    current_text.push_str(&text);
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    texts
}

fn extract_paragraph_runs(xml: &[u8]) -> Vec<Vec<String>> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut in_paragraph = false;
    let mut in_text = false;
    let mut current_text = String::new();
    let mut current_runs = Vec::new();
    let mut paragraphs = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => match local_name(event.name().as_ref()) {
                b"p" => {
                    in_paragraph = true;
                    current_runs.clear();
                }
                b"t" if in_paragraph => {
                    in_text = true;
                    current_text.clear();
                }
                _ => {}
            },
            Ok(Event::Empty(event)) if local_name(event.name().as_ref()) == b"p" => {
                paragraphs.push(Vec::new());
            }
            Ok(Event::End(event)) => match local_name(event.name().as_ref()) {
                b"t" => {
                    if !current_text.is_empty() {
                        current_runs.push(std::mem::take(&mut current_text));
                    }
                    in_text = false;
                }
                b"p" if in_paragraph => {
                    paragraphs.push(std::mem::take(&mut current_runs));
                    in_paragraph = false;
                }
                _ => {}
            },
            Ok(Event::Text(event)) if in_paragraph && in_text => {
                if let Some(text) = xml_text_content(&event) {
                    current_text.push_str(&text);
                }
            }
            Ok(Event::GeneralRef(event)) if in_paragraph && in_text => {
                if let Some(text) = xml_reference_content(&event) {
                    current_text.push_str(&text);
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    paragraphs
}

fn extract_paragraph_texts(xml: &[u8]) -> Vec<String> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut in_paragraph = false;
    let mut in_text = false;
    let mut current_parts = Vec::new();
    let mut paragraphs = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => match local_name(event.name().as_ref()) {
                b"p" => {
                    in_paragraph = true;
                    current_parts.clear();
                }
                b"br" if in_paragraph => {
                    current_parts.push("\u{000b}".to_string());
                }
                b"t" if in_paragraph => {
                    in_text = true;
                }
                _ => {}
            },
            Ok(Event::Empty(event)) => match local_name(event.name().as_ref()) {
                b"p" => paragraphs.push(String::new()),
                b"br" if in_paragraph => current_parts.push("\u{000b}".to_string()),
                _ => {}
            },
            Ok(Event::End(event)) => match local_name(event.name().as_ref()) {
                b"t" => {
                    in_text = false;
                }
                b"p" if in_paragraph => {
                    paragraphs.push(std::mem::take(&mut current_parts).join(""));
                    in_paragraph = false;
                }
                _ => {}
            },
            Ok(Event::Text(event)) if in_paragraph && in_text => {
                if let Some(text) = xml_text_content(&event) {
                    current_parts.push(text);
                }
            }
            Ok(Event::GeneralRef(event)) if in_paragraph && in_text => {
                if let Some(text) = xml_reference_content(&event) {
                    current_parts.push(text);
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    paragraphs
}

fn extract_paragraph_line_breaks(xml: &[u8]) -> Vec<Vec<usize>> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut in_paragraph = false;
    let mut in_run = false;
    let mut in_text = false;
    let mut current_run_has_text = false;
    let mut current_run_count = 0usize;
    let mut current_breaks = Vec::new();
    let mut paragraphs = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => match local_name(event.name().as_ref()) {
                b"p" => {
                    in_paragraph = true;
                    current_run_count = 0;
                    current_breaks.clear();
                }
                b"r" if in_paragraph => {
                    in_run = true;
                    current_run_has_text = false;
                }
                b"br" if in_paragraph => current_breaks.push(current_run_count),
                b"t" if in_run => in_text = true,
                _ => {}
            },
            Ok(Event::Empty(event)) => match local_name(event.name().as_ref()) {
                b"p" => paragraphs.push(Vec::new()),
                b"br" if in_paragraph => current_breaks.push(current_run_count),
                _ => {}
            },
            Ok(Event::End(event)) => match local_name(event.name().as_ref()) {
                b"t" => in_text = false,
                b"r" if in_run => {
                    if current_run_has_text {
                        current_run_count += 1;
                    }
                    in_run = false;
                    current_run_has_text = false;
                }
                b"p" if in_paragraph => {
                    paragraphs.push(std::mem::take(&mut current_breaks));
                    in_paragraph = false;
                }
                _ => {}
            },
            Ok(Event::Text(event)) if in_run && in_text => {
                if xml_text_content(&event).is_some() {
                    current_run_has_text = true;
                }
            }
            Ok(Event::GeneralRef(event)) if in_run && in_text => {
                if xml_reference_content(&event).is_some() {
                    current_run_has_text = true;
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    paragraphs
}

fn extract_paragraph_run_bold(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    extract_paragraph_run_bool_attribute(xml, b"b")
}

fn extract_paragraph_run_italic(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    extract_paragraph_run_bool_attribute(xml, b"i")
}

fn extract_paragraph_run_underline(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    let raw = extract_paragraph_run_text_attribute(xml, b"u");
    raw.into_iter()
        .map(|paragraph| {
            paragraph
                .into_iter()
                .map(|value| match value.as_deref() {
                    Some("none") => Some(false),
                    Some(_) => Some(true),
                    None => None,
                })
                .collect()
        })
        .collect()
}

fn extract_paragraph_run_font_size(xml: &[u8]) -> Vec<Vec<Option<i64>>> {
    let raw = extract_paragraph_run_text_attribute(xml, b"sz");
    raw.into_iter()
        .map(|paragraph| {
            paragraph
                .into_iter()
                .map(|value| {
                    value
                        .and_then(|value| value.parse::<i64>().ok())
                        .map(|centipoints| centipoints * 127)
                })
                .collect()
        })
        .collect()
}

fn extract_paragraph_run_font_name(xml: &[u8]) -> Vec<Vec<Option<String>>> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut in_paragraph = false;
    let mut in_run = false;
    let mut in_text = false;
    let mut current_text_has_content = false;
    let mut current_run_typeface = None;
    let mut current_runs = Vec::new();
    let mut paragraphs = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => match local_name(event.name().as_ref()) {
                b"p" => {
                    in_paragraph = true;
                    current_runs.clear();
                }
                b"r" if in_paragraph => {
                    in_run = true;
                    current_run_typeface = None;
                }
                b"latin" if in_run => {
                    current_run_typeface = drawingml_attribute(&event, b"typeface");
                }
                b"t" if in_run => {
                    in_text = true;
                    current_text_has_content = false;
                }
                _ => {}
            },
            Ok(Event::Empty(event)) => match local_name(event.name().as_ref()) {
                b"p" => paragraphs.push(Vec::new()),
                b"latin" if in_run => {
                    current_run_typeface = drawingml_attribute(&event, b"typeface");
                }
                _ => {}
            },
            Ok(Event::End(event)) => match local_name(event.name().as_ref()) {
                b"t" => {
                    if current_text_has_content {
                        current_runs.push(current_run_typeface.clone());
                    }
                    in_text = false;
                }
                b"r" if in_run => {
                    in_run = false;
                    current_run_typeface = None;
                }
                b"p" if in_paragraph => {
                    paragraphs.push(std::mem::take(&mut current_runs));
                    in_paragraph = false;
                }
                _ => {}
            },
            Ok(Event::Text(event)) if in_run && in_text => {
                if xml_text_content(&event).is_some() {
                    current_text_has_content = true;
                }
            }
            Ok(Event::GeneralRef(event)) if in_run && in_text => {
                if xml_reference_content(&event).is_some() {
                    current_text_has_content = true;
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    paragraphs
}

fn extract_paragraph_run_bool_attribute(xml: &[u8], attr_name: &[u8]) -> Vec<Vec<Option<bool>>> {
    let raw = extract_paragraph_run_text_attribute(xml, attr_name);
    raw.into_iter()
        .map(|paragraph| {
            paragraph
                .into_iter()
                .map(|value| match value.as_deref() {
                    Some("1") | Some("true") | Some("on") => Some(true),
                    Some("0") | Some("false") | Some("off") => Some(false),
                    _ => None,
                })
                .collect()
        })
        .collect()
}

fn extract_paragraph_run_text_attribute(xml: &[u8], attr_name: &[u8]) -> Vec<Vec<Option<String>>> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut in_paragraph = false;
    let mut in_run = false;
    let mut in_text = false;
    let mut current_text_has_content = false;
    let mut current_run_attribute = None;
    let mut current_runs = Vec::new();
    let mut paragraphs = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => match local_name(event.name().as_ref()) {
                b"p" => {
                    in_paragraph = true;
                    current_runs.clear();
                }
                b"r" if in_paragraph => {
                    in_run = true;
                    current_run_attribute = None;
                }
                b"rPr" if in_run => {
                    current_run_attribute = drawingml_attribute(&event, attr_name);
                }
                b"t" if in_run => {
                    in_text = true;
                    current_text_has_content = false;
                }
                _ => {}
            },
            Ok(Event::Empty(event)) => match local_name(event.name().as_ref()) {
                b"p" => paragraphs.push(Vec::new()),
                b"rPr" if in_run => {
                    current_run_attribute = drawingml_attribute(&event, attr_name);
                }
                _ => {}
            },
            Ok(Event::End(event)) => match local_name(event.name().as_ref()) {
                b"t" => {
                    if current_text_has_content {
                        current_runs.push(current_run_attribute.clone());
                    }
                    in_text = false;
                }
                b"r" if in_run => {
                    in_run = false;
                    current_run_attribute = None;
                }
                b"p" if in_paragraph => {
                    paragraphs.push(std::mem::take(&mut current_runs));
                    in_paragraph = false;
                }
                _ => {}
            },
            Ok(Event::Text(event)) if in_run && in_text => {
                if xml_text_content(&event).is_some() {
                    current_text_has_content = true;
                }
            }
            Ok(Event::GeneralRef(event)) if in_run && in_text => {
                if xml_reference_content(&event).is_some() {
                    current_text_has_content = true;
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    paragraphs
}
