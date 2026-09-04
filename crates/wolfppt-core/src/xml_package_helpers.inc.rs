fn xml_attr(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('"', "&quot;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn is_slide_layout_part(name: &str) -> bool {
    let Some(rest) = name.strip_prefix("ppt/slideLayouts/slideLayout") else {
        return false;
    };
    let Some(number) = rest.strip_suffix(".xml") else {
        return false;
    };
    !number.is_empty() && number.chars().all(|ch| ch.is_ascii_digit())
}

fn parse_relationships(xml: &[u8]) -> Vec<RelationshipSummary> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    let mut relationships = Vec::new();
    loop {
        match reader.read_event() {
            Ok(Event::Empty(event)) | Ok(Event::Start(event))
                if local_name(event.name().as_ref()) == b"Relationship" =>
            {
                let mut id = String::new();
                let mut relationship_type = String::new();
                let mut target = String::new();
                let mut target_mode = None;
                for attr in event.attributes().flatten() {
                    let key = local_name(attr.key.as_ref());
                    let value = attr
                        .decode_and_unescape_value(reader.decoder())
                        .map(|value| value.into_owned())
                        .unwrap_or_default();
                    match key {
                        b"Id" => id = value,
                        b"Type" => relationship_type = value,
                        b"Target" => target = value,
                        b"TargetMode" => target_mode = Some(value),
                        _ => {}
                    }
                }
                relationships.push(RelationshipSummary {
                    id,
                    relationship_type,
                    target,
                    target_mode,
                });
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }
    relationships
        .sort_by(|left, right| left.id.cmp(&right.id).then(left.target.cmp(&right.target)));
    relationships
}

fn next_relationship_id(xml: &[u8]) -> String {
    let relationships = parse_relationships(xml);
    let max_id = relationships
        .iter()
        .filter_map(|rel| rel.id.strip_prefix("rId")?.parse::<u64>().ok())
        .max()
        .unwrap_or(0);
    format!("rId{}", max_id + 1)
}

fn next_slide_id(xml: &[u8]) -> u64 {
    let mut max_id = 255;
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    loop {
        match reader.read_event() {
            Ok(Event::Empty(event)) | Ok(Event::Start(event))
                if local_name(event.name().as_ref()) == b"sldId" =>
            {
                for attr in event.attributes().flatten() {
                    if local_name(attr.key.as_ref()) != b"id" {
                        continue;
                    }
                    let value = attr
                        .decode_and_unescape_value(reader.decoder())
                        .map(|value| value.into_owned())
                        .unwrap_or_default();
                    if let Ok(id) = value.parse::<u64>() {
                        max_id = max_id.max(id);
                    }
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }
    max_id + 1
}

fn append_slide_id(
    xml: &[u8],
    slide_id: u64,
    relationship_id: &str,
) -> Result<Vec<u8>, WolfPptError> {
    let entry = format!(r#"<p:sldId id="{slide_id}" r:id="{relationship_id}"/>"#);
    let text = String::from_utf8_lossy(xml);
    if text.contains("</p:sldIdLst>") {
        return insert_before(xml, "</p:sldIdLst>", &entry);
    }

    let list = format!(r#"<p:sldIdLst>{entry}</p:sldIdLst>"#);
    if text.contains("</p:sldMasterIdLst>") {
        return insert_after(xml, "</p:sldMasterIdLst>", &list);
    }
    for marker in ["<p:sldSz", "<p:notesSz", "<p:defaultTextStyle"] {
        if text.contains(marker) {
            return insert_before(xml, marker, &list);
        }
    }
    insert_before(xml, "</p:presentation>", &list)
}

fn append_relationship(
    xml: &[u8],
    relationship_id: &str,
    relationship_type: &str,
    target: &str,
) -> Result<Vec<u8>, WolfPptError> {
    insert_before(
        xml,
        "</Relationships>",
        &format!(
            r#"<Relationship Id="{relationship_id}" Type="{relationship_type}" Target="{target}"/>"#
        ),
    )
}

fn append_content_type_override(
    xml: &[u8],
    part_name: &str,
    content_type: &str,
) -> Result<Vec<u8>, WolfPptError> {
    insert_before(
        xml,
        "</Types>",
        &format!(r#"<Override PartName="{part_name}" ContentType="{content_type}"/>"#),
    )
}

fn insert_before(xml: &[u8], needle: &str, insert: &str) -> Result<Vec<u8>, WolfPptError> {
    let text = String::from_utf8_lossy(xml);
    let Some(index) = text.rfind(needle) else {
        return Err(WolfPptError::XmlText(format!(
            "expected closing marker {needle}"
        )));
    };
    let mut output = String::with_capacity(text.len() + insert.len());
    output.push_str(&text[..index]);
    output.push_str(insert);
    output.push_str(&text[index..]);
    Ok(output.into_bytes())
}

fn insert_after(xml: &[u8], needle: &str, insert: &str) -> Result<Vec<u8>, WolfPptError> {
    let text = String::from_utf8_lossy(xml);
    let Some(index) = text.rfind(needle) else {
        return Err(WolfPptError::XmlText(format!(
            "expected closing marker {needle}"
        )));
    };
    let insert_index = index + needle.len();
    let mut output = String::with_capacity(text.len() + insert.len());
    output.push_str(&text[..insert_index]);
    output.push_str(insert);
    output.push_str(&text[insert_index..]);
    Ok(output.into_bytes())
}

fn slide_number(part: &str) -> Option<u64> {
    let rest = part.strip_prefix("ppt/slides/slide")?;
    let number = rest.strip_suffix(".xml")?;
    number.parse().ok()
}
