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
                if local_name(event.name().as_ref().as_bytes()) == b"Relationship" =>
            {
                let mut id = String::new();
                let mut relationship_type = String::new();
                let mut target = String::new();
                let mut target_mode = None;
                for attr in event.attributes().flatten() {
                    let key = local_name(attr.key.as_ref().as_bytes());
                    let value = attr
                        .normalized_value(quick_xml::XmlVersion::Implicit1_0)
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
                if local_name(event.name().as_ref().as_bytes()) == b"sldId" =>
            {
                for attr in event.attributes().flatten() {
                    if local_name(attr.key.as_ref().as_bytes()) != b"id" {
                        continue;
                    }
                    let value = attr
                        .normalized_value(quick_xml::XmlVersion::Implicit1_0)
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
    if let Some((start, end)) = self_closing_slide_id_list_span(xml)? {
        let mut output = Vec::with_capacity(xml.len() + entry.len() + b"</p:sldIdLst>".len() - 1);
        output.extend_from_slice(&xml[..start]);
        output.extend_from_slice(&xml[start..end - 2]);
        output.push(b'>');
        output.extend_from_slice(entry.as_bytes());
        output.extend_from_slice(b"</p:sldIdLst>");
        output.extend_from_slice(&xml[end..]);
        return Ok(output);
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

fn self_closing_slide_id_list_span(xml: &[u8]) -> Result<Option<(usize, usize)>, WolfPptError> {
    let bom = utf8_bom_offset(xml);
    let mut reader = Reader::from_reader(xml);
    loop {
        let start = bom + reader.buffer_position() as usize;
        match reader.read_event()? {
            Event::Empty(event) if event.name().as_ref().as_bytes() == b"p:sldIdLst" => {
                let end = bom + reader.buffer_position() as usize;
                return Ok(Some((start, end)));
            }
            Event::Eof => return Ok(None),
            _ => {}
        }
    }
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

struct ContentTypesRoot {
    qname: Vec<u8>,
    start: usize,
    end: usize,
    closing_start: Option<usize>,
}

fn content_types_root(xml: &[u8]) -> Result<ContentTypesRoot, WolfPptError> {
    const CONTENT_TYPES_NAMESPACE: &str =
        "http://schemas.openxmlformats.org/package/2006/content-types";
    let bom = utf8_bom_offset(xml);
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    loop {
        let (event, self_closing) = match reader.read_event() {
            Ok(Event::Start(event)) => (event, false),
            Ok(Event::Empty(event)) => (event, true),
            Ok(Event::Eof) | Err(_) => {
                return Err(WolfPptError::InvalidInput(
                    "[Content_Types].xml has an invalid root".to_string(),
                ))
            }
            _ => continue,
        };
        let qname = event.name().as_ref().as_bytes().to_vec();
        if local_name(&qname) != b"Types" {
            return Err(WolfPptError::InvalidInput(
                "[Content_Types].xml has an invalid root".to_string(),
            ));
        }
        let namespace_attribute = match qname.rsplit(|byte| *byte == b':').nth(1) {
            Some(prefix) if !prefix.is_empty() => {
                let mut attribute = b"xmlns:".to_vec();
                attribute.extend_from_slice(prefix);
                attribute
            }
            _ => b"xmlns".to_vec(),
        };
        let has_content_types_namespace = event.attributes().flatten().any(|attribute| {
            attribute.key.as_ref().as_bytes() == namespace_attribute.as_slice()
                && attribute
                    .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                    .map(|value| value.as_ref() == CONTENT_TYPES_NAMESPACE)
                    .unwrap_or(false)
        });
        if !has_content_types_namespace {
            return Err(WolfPptError::InvalidInput(
                "[Content_Types].xml has an invalid content-types namespace".to_string(),
            ));
        }
        drop(event);
        let end = bom + reader.buffer_position() as usize;
        let start = xml[..end]
            .iter()
            .rposition(|byte| *byte == b'<')
            .ok_or_else(|| {
                WolfPptError::InvalidInput("[Content_Types].xml has an invalid root".to_string())
            })?;
        if self_closing {
            return Ok(ContentTypesRoot {
                qname,
                start,
                end,
                closing_start: None,
            });
        }
        let mut depth = 1usize;
        loop {
            match reader.read_event() {
                Ok(Event::Start(_)) => depth += 1,
                Ok(Event::End(end_event)) => {
                    depth -= 1;
                    if depth == 0 {
                        if end_event.name().as_ref().as_bytes() != qname.as_slice() {
                            return Err(WolfPptError::InvalidInput(
                                "[Content_Types].xml has an invalid root".to_string(),
                            ));
                        }
                        let end = bom + reader.buffer_position() as usize;
                        let closing_start = xml[..end]
                            .iter()
                            .rposition(|byte| *byte == b'<')
                            .ok_or_else(|| {
                                WolfPptError::InvalidInput(
                                    "[Content_Types].xml has an invalid root".to_string(),
                                )
                            })?;
                        return Ok(ContentTypesRoot {
                            qname,
                            start,
                            end,
                            closing_start: Some(closing_start),
                        });
                    }
                }
                Ok(Event::Eof) | Err(_) => {
                    return Err(WolfPptError::InvalidInput(
                        "[Content_Types].xml has an invalid root".to_string(),
                    ))
                }
                _ => {}
            }
        }
    }
}

fn append_content_type_element(
    xml: &[u8],
    local_name: &str,
    attributes: &str,
) -> Result<Vec<u8>, WolfPptError> {
    let root = content_types_root(xml)?;
    let root_qname =
        std::str::from_utf8(&root.qname).map_err(|err| WolfPptError::XmlText(err.to_string()))?;
    let child_qname = match root_qname.rsplit_once(':') {
        Some((prefix, "Types")) => format!("{prefix}:{local_name}"),
        None if root_qname == "Types" => local_name.to_string(),
        _ => {
            return Err(WolfPptError::InvalidInput(
                "[Content_Types].xml has an invalid root".to_string(),
            ))
        }
    };
    let child = format!("<{child_qname} {attributes}/>");
    let mut output = Vec::with_capacity(xml.len() + child.len() + root.qname.len() + 3);
    match root.closing_start {
        Some(closing_start) => {
            output.extend_from_slice(&xml[..closing_start]);
            output.extend_from_slice(child.as_bytes());
            output.extend_from_slice(&xml[closing_start..]);
        }
        None => {
            if !xml[root.start..root.end].ends_with(b"/>") {
                return Err(WolfPptError::InvalidInput(
                    "[Content_Types].xml has an invalid root".to_string(),
                ));
            }
            output.extend_from_slice(&xml[..root.end - 2]);
            output.push(b'>');
            output.extend_from_slice(child.as_bytes());
            output.extend_from_slice(b"</");
            output.extend_from_slice(&root.qname);
            output.push(b'>');
            output.extend_from_slice(&xml[root.end..]);
        }
    }
    Ok(output)
}

fn append_content_type_override(
    xml: &[u8],
    part_name: &str,
    content_type: &str,
) -> Result<Vec<u8>, WolfPptError> {
    append_content_type_element(
        xml,
        "Override",
        &format!(r#"PartName="{part_name}" ContentType="{content_type}""#),
    )
}

/// quick-xml skips a leading UTF-8 byte order mark without counting it in
/// `buffer_position()`; add this to a reader position to index `xml` itself.
fn utf8_bom_offset(xml: &[u8]) -> usize {
    if xml.starts_with(b"\xEF\xBB\xBF") {
        3
    } else {
        0
    }
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
