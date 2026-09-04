fn replace_table_cell_text_in_slide(
    xml: &[u8],
    target_table_index: usize,
    target_row_index: usize,
    target_col_index: usize,
    replacement: &str,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut table_index = 0;
    let mut row_index = 0;
    let mut col_index = 0;
    let mut in_target_table = false;
    let mut in_target_row = false;
    let mut in_target_cell = false;
    let mut in_text = false;
    let mut wrote_replacement = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                match local_name(event.name().as_ref()) {
                    b"tbl" => {
                        in_target_table = table_index == target_table_index;
                        table_index += 1;
                        row_index = 0;
                    }
                    b"tr" if in_target_table => {
                        in_target_row = row_index == target_row_index;
                        row_index += 1;
                        col_index = 0;
                    }
                    b"tc" if in_target_row => {
                        in_target_cell = col_index == target_col_index;
                        col_index += 1;
                        wrote_replacement = false;
                    }
                    b"t" => in_text = true,
                    _ => {}
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                match local_name(event.name().as_ref()) {
                    b"t" => {
                        if in_text && in_target_cell && !wrote_replacement {
                            writer.write_event(Event::Text(BytesText::new(replacement)))?;
                            wrote_replacement = true;
                            replacements += 1;
                        }
                        in_text = false;
                    }
                    b"tc" => {
                        in_target_cell = false;
                        wrote_replacement = false;
                    }
                    b"tr" => in_target_row = false,
                    b"tbl" => in_target_table = false,
                    _ => {}
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Text(_event) if in_text && in_target_cell => {
                if wrote_replacement {
                    writer.write_event(Event::Text(BytesText::new("")))?;
                } else {
                    writer.write_event(Event::Text(BytesText::new(replacement)))?;
                    wrote_replacement = true;
                    replacements += 1;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn replace_table_cell_text_batch_in_slide(
    xml: &[u8],
    replacements_to_apply: &[(usize, usize, usize, &str)],
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let mut replacements_by_cell: BTreeMap<(usize, usize, usize), &str> = BTreeMap::new();
    for (table_index, row_index, col_index, replacement) in replacements_to_apply {
        replacements_by_cell.insert((*table_index, *row_index, *col_index), *replacement);
    }

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut table_index = 0;
    let mut row_index = 0;
    let mut col_index = 0;
    let mut current_table: Option<usize> = None;
    let mut current_row: Option<usize> = None;
    let mut current_cell_replacement: Option<&str> = None;
    let mut in_text = false;
    let mut wrote_replacement = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                match local_name(event.name().as_ref()) {
                    b"tbl" => {
                        current_table = Some(table_index);
                        table_index += 1;
                        row_index = 0;
                    }
                    b"tr" if current_table.is_some() => {
                        current_row = Some(row_index);
                        row_index += 1;
                        col_index = 0;
                    }
                    b"tc" if current_table.is_some() && current_row.is_some() => {
                        let table = current_table.unwrap_or(usize::MAX);
                        let row = current_row.unwrap_or(usize::MAX);
                        let col = col_index;
                        col_index += 1;
                        current_cell_replacement =
                            replacements_by_cell.get(&(table, row, col)).copied();
                        wrote_replacement = false;
                    }
                    b"t" => in_text = true,
                    _ => {}
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                match local_name(event.name().as_ref()) {
                    b"t" => {
                        if in_text {
                            if let Some(replacement) = current_cell_replacement {
                                if !wrote_replacement {
                                    writer.write_event(Event::Text(BytesText::new(replacement)))?;
                                    wrote_replacement = true;
                                    replacements += 1;
                                }
                            }
                        }
                        in_text = false;
                    }
                    b"tc" => {
                        current_cell_replacement = None;
                        wrote_replacement = false;
                    }
                    b"tr" => current_row = None,
                    b"tbl" => current_table = None,
                    _ => {}
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Text(_event) if in_text && current_cell_replacement.is_some() => {
                let replacement = current_cell_replacement.unwrap_or("");
                if wrote_replacement {
                    writer.write_event(Event::Text(BytesText::new("")))?;
                } else {
                    writer.write_event(Event::Text(BytesText::new(replacement)))?;
                    wrote_replacement = true;
                    replacements += 1;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

#[allow(clippy::too_many_arguments)]
fn set_table_cell_merge_in_slide(
    xml: &[u8],
    target_table_index: usize,
    row_min: usize,
    row_max: usize,
    col_min: usize,
    col_max: usize,
    kind: &str,
    paragraphs: &[String],
) -> Result<(Vec<u8>, usize), WolfPptError> {
    if row_min > row_max || col_min > col_max {
        return Err(WolfPptError::InvalidInput(
            "table merge range is invalid".to_string(),
        ));
    }
    if !matches!(kind, "merge" | "split") {
        return Err(WolfPptError::InvalidInput(format!(
            "unknown table cell merge edit: {kind}"
        )));
    }

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut table_index = 0;
    let mut row_index = 0;
    let mut col_index = 0;
    let mut in_target_table = false;
    let mut current_row: Option<usize> = None;
    let mut current_cell: Option<(usize, usize)> = None;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    in_target_table = table_index == target_table_index;
                    table_index += 1;
                    row_index = 0;
                } else if in_target_table && name == b"tr" {
                    current_row = Some(row_index);
                    row_index += 1;
                    col_index = 0;
                } else if in_target_table && name == b"tc" {
                    let row = current_row.unwrap_or(usize::MAX);
                    let col = col_index;
                    col_index += 1;
                    if row >= row_min && row <= row_max && col >= col_min && col <= col_max {
                        current_cell = Some((row, col));
                        writer.write_event(Event::Start(rewrite_event_optional_attributes(
                            &event,
                            &table_cell_merge_attributes(
                                kind, row, col, row_min, row_max, col_min, col_max,
                            ),
                        )))?;
                        replacements += 1;
                        continue;
                    }
                } else if name == b"txBody" {
                    if let Some((row, col)) = current_cell {
                        if kind == "merge" {
                            writer.write_event(Event::Start(event))?;
                            let replacement = if (row, col) == (row_min, col_min) {
                                paragraphs
                                    .iter()
                                    .map(String::as_str)
                                    .collect::<Vec<_>>()
                                    .join("\n")
                            } else {
                                String::new()
                            };
                            replacements += rewrite_text_body_content(
                                &mut reader,
                                &mut writer,
                                &replacement,
                            )?;
                            continue;
                        }
                    }
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && name == b"tc" {
                    let row = current_row.unwrap_or(usize::MAX);
                    let col = col_index;
                    col_index += 1;
                    if row >= row_min && row <= row_max && col >= col_min && col <= col_max {
                        writer.write_event(Event::Empty(rewrite_event_optional_attributes(
                            &event,
                            &table_cell_merge_attributes(
                                kind, row, col, row_min, row_max, col_min, col_max,
                            ),
                        )))?;
                        replacements += 1;
                        continue;
                    }
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                writer.write_event(Event::End(event))?;
                if name == b"tc" {
                    current_cell = None;
                } else if name == b"tr" {
                    current_row = None;
                } else if name == b"tbl" {
                    in_target_table = false;
                }
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

#[allow(clippy::too_many_arguments)]
fn table_cell_merge_attributes(
    kind: &str,
    row: usize,
    col: usize,
    row_min: usize,
    row_max: usize,
    col_min: usize,
    col_max: usize,
) -> Vec<(&'static str, Option<String>)> {
    if kind == "split" {
        return vec![
            ("rowSpan", None),
            ("gridSpan", None),
            ("hMerge", None),
            ("vMerge", None),
        ];
    }
    let row_count = row_max - row_min + 1;
    let col_count = col_max - col_min + 1;
    vec![
        (
            "rowSpan",
            (row == row_min && row_count > 1).then(|| row_count.to_string()),
        ),
        (
            "gridSpan",
            (col == col_min && col_count > 1).then(|| col_count.to_string()),
        ),
        ("hMerge", (col != col_min).then(|| "1".to_string())),
        ("vMerge", (row != row_min).then(|| "1".to_string())),
    ]
}

fn set_table_style_flags_in_slide(
    xml: &[u8],
    target_table_index: usize,
    flags: &BTreeMap<String, bool>,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let attribute_replacements = table_style_flag_attributes(flags)?;
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut table_index = 0;
    let mut in_target_table = false;
    let mut wrote_table_properties = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    in_target_table = table_index == target_table_index;
                    table_index += 1;
                    wrote_table_properties = false;
                    writer.write_event(Event::Start(event))?;
                    continue;
                }
                if in_target_table && name == b"tblPr" {
                    writer.write_event(Event::Start(rewrite_event_optional_attributes(
                        &event,
                        &attribute_replacements,
                    )))?;
                    wrote_table_properties = true;
                    replacements += 1;
                    continue;
                }
                if in_target_table
                    && !wrote_table_properties
                    && matches!(name.as_slice(), b"tblGrid" | b"tr" | b"extLst")
                {
                    writer.write_event(Event::Empty(table_style_flags_event(
                        &attribute_replacements,
                    )))?;
                    wrote_table_properties = true;
                    replacements += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && name == b"tblPr" {
                    writer.write_event(Event::Empty(rewrite_event_optional_attributes(
                        &event,
                        &attribute_replacements,
                    )))?;
                    wrote_table_properties = true;
                    replacements += 1;
                    continue;
                }
                if in_target_table
                    && !wrote_table_properties
                    && matches!(name.as_slice(), b"tblGrid" | b"tr" | b"extLst")
                {
                    writer.write_event(Event::Empty(table_style_flags_event(
                        &attribute_replacements,
                    )))?;
                    wrote_table_properties = true;
                    replacements += 1;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                if local_name(event.name().as_ref()) == b"tbl" {
                    in_target_table = false;
                    wrote_table_properties = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }

    Ok((writer.into_inner(), replacements))
}

fn table_style_flag_attributes(
    flags: &BTreeMap<String, bool>,
) -> Result<Vec<(&'static str, Option<String>)>, WolfPptError> {
    for key in flags.keys() {
        if !matches!(
            key.as_str(),
            "firstCol" | "firstRow" | "bandRow" | "lastCol" | "lastRow" | "bandCol"
        ) {
            return Err(WolfPptError::InvalidInput(format!(
                "unsupported table style flag: {key}"
            )));
        }
    }
    Ok([
        "firstCol", "firstRow", "bandRow", "lastCol", "lastRow", "bandCol",
    ]
    .into_iter()
    .filter_map(|key| flags.get(key).map(|value| (key, *value)))
    .map(|(key, value)| (key, value.then(|| "1".to_string())))
    .collect())
}

fn table_style_flags_event(
    attribute_replacements: &[(&'static str, Option<String>)],
) -> BytesStart<'static> {
    let mut table_properties = BytesStart::new("a:tblPr");
    for (key, value) in attribute_replacements {
        if let Some(value) = value {
            table_properties.push_attribute((*key, value.as_str()));
        }
    }
    table_properties
}

fn relationships_by_type(
    relationships: &[RelationshipSummary],
    suffixes: &[&str],
) -> Vec<RelationshipSummary> {
    relationships
        .iter()
        .filter(|rel| {
            suffixes
                .iter()
                .any(|suffix| rel.relationship_type.ends_with(suffix))
        })
        .cloned()
        .collect()
}

fn has_element(xml: &[u8], name: &[u8]) -> bool {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) | Ok(Event::Empty(event)) => {
                if local_name(event.name().as_ref()) == name {
                    return true;
                }
            }
            Ok(Event::Eof) => return false,
            Err(_) => return false,
            _ => {}
        }
    }
}

fn relationship_part_name(part_name: &str) -> String {
    let Some((prefix, name)) = part_name.rsplit_once('/') else {
        return format!("_rels/{part_name}.rels");
    };
    format!("{prefix}/_rels/{name}.rels")
}

fn resolve_target(source: &str, target: &str) -> String {
    if let Some(stripped) = target.strip_prefix('/') {
        return stripped.to_string();
    }
    let mut parts: Vec<&str> = source.split('/').collect();
    parts.pop();
    for chunk in target.split('/') {
        match chunk {
            "" | "." => {}
            ".." => {
                parts.pop();
            }
            value => parts.push(value),
        }
    }
    parts.join("/")
}

fn local_name(name: &[u8]) -> &[u8] {
    name.rsplit(|byte| *byte == b':').next().unwrap_or(name)
}

fn natural_key(value: &str) -> Vec<NaturalChunk> {
    let mut chunks = Vec::new();
    let mut current = String::new();
    let mut current_is_digit = None;
    for ch in value.chars() {
        let is_digit = ch.is_ascii_digit();
        if current_is_digit == Some(is_digit) || current_is_digit.is_none() {
            current.push(ch);
            current_is_digit = Some(is_digit);
        } else {
            chunks.push(NaturalChunk::from(
                current.as_str(),
                current_is_digit.unwrap_or(false),
            ));
            current.clear();
            current.push(ch);
            current_is_digit = Some(is_digit);
        }
    }
    if !current.is_empty() {
        chunks.push(NaturalChunk::from(
            current.as_str(),
            current_is_digit.unwrap_or(false),
        ));
    }
    chunks
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum NaturalChunk {
    Text(String),
    Number(u64),
}

impl NaturalChunk {
    fn from(value: &str, is_digit: bool) -> Self {
        if is_digit {
            Self::Number(value.parse().unwrap_or(0))
        } else {
            Self::Text(value.to_string())
        }
    }
}
