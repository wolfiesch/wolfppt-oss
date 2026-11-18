fn extract_tables(xml: &[u8]) -> Vec<TableSummary> {
    extract_tables_from_effective(xml)
}

fn extract_tables_from_effective(xml: &[u8]) -> Vec<TableSummary> {
    extract_tables_in_str(&String::from_utf8_lossy(xml))
}

/// [`extract_tables_from_effective`] for XML already held as `str`, so a shape
/// block sliced from validated text is not validated again.
fn extract_tables_in_str(xml: &str) -> Vec<TableSummary> {
    let mut tables = Vec::new();
    let mut table_offset = 0;

    while let Some(start) = find_tag_start(xml, table_offset, "a:tbl") {
        let Some(end) = find_element_end(xml, start, "a:tbl") else {
            break;
        };
        let rows = extract_table_rows(&xml[start..end]);
        let row_count = rows.len();
        let col_count = rows.iter().map(Vec::len).max().unwrap_or(0);
        tables.push(TableSummary {
            rows,
            row_count,
            col_count,
        });
        table_offset = end;
    }

    tables
}

fn extract_table_rows(table_xml: &str) -> Vec<Vec<String>> {
    let mut rows = Vec::new();
    let mut row_offset = 0;
    while let Some(start) = find_tag_start(table_xml, row_offset, "a:tr") {
        let Some(end) = find_element_end(table_xml, start, "a:tr") else {
            break;
        };
        rows.push(extract_table_cells(&table_xml[start..end]));
        row_offset = end;
    }
    rows
}

fn extract_table_cells(row_xml: &str) -> Vec<String> {
    let mut cells = Vec::new();
    let mut cell_offset = 0;
    while let Some(start) = find_tag_start(row_xml, cell_offset, "a:tc") {
        let Some(end) = find_element_end(row_xml, start, "a:tc") else {
            break;
        };
        let cell_xml = &row_xml[start..end];
        cells.push(extract_paragraph_texts(cell_xml.as_bytes()).join("\n"));
        cell_offset = end;
    }
    cells
}

#[cfg(test)]
fn extract_shapes(xml: &[u8]) -> Vec<ShapeSummary> {
    let effective_xml = effective_mc_xml(xml);
    extract_shapes_from_effective(&effective_xml)
}

const DRAWINGML_MAIN_NS: &[u8] = b"http://schemas.openxmlformats.org/drawingml/2006/main";
const STRICT_PRESENTATION_MAIN_NS: &[u8] = b"http://purl.oclc.org/ooxml/presentationml/main";
const STRICT_DRAWINGML_MAIN_NS: &[u8] = b"http://purl.oclc.org/ooxml/drawingml/main";

fn extract_shapes_from_effective(xml: &[u8]) -> Vec<ShapeSummary> {
    let normalized_xml = match canonical_shape_qnames(xml) {
        Ok(xml) => xml,
        Err(()) => return Vec::new(),
    };
    let xml = String::from_utf8_lossy(normalized_xml.as_deref().unwrap_or(xml));
    let Some(sp_tree) = element_inner(&xml, "p:spTree") else {
        return Vec::new();
    };
    let media_playback = extract_media_playback(&xml);
    extract_shape_blocks(sp_tree)
        .into_iter()
        .map(|block| summarize_shape_block(block, None, &media_playback))
        .collect()
}

// Shape summaries retain the established string-slice helpers below, but XML
// namespace prefixes are serialization details. Resolve each element through
// `NsReader`, then rewrite exact PresentationML and DrawingML element names
// into those helpers' canonical spellings. A foreign element that happens to
// use the legacy `p:` or `a:` spelling is instead made unmatchable, so it
// cannot be confused with an OOXML shape-tree element.
fn canonical_shape_qnames(xml: &[u8]) -> Result<Option<Vec<u8>>, ()> {
    let bom = utf8_bom_offset(xml);
    let mut reader = quick_xml::NsReader::from_reader(xml);
    let mut copied = 0;
    let mut rewritten = None;

    loop {
        let event_start = bom + reader.buffer_position() as usize;
        let (resolved, event) = reader.read_resolved_event().map_err(|_| ())?;
        let (raw_name, name_start) = match &event {
            Event::Start(element) | Event::Empty(element) => {
                (element.name().into_inner().as_bytes(), event_start + 1)
            }
            Event::End(element) => (element.name().into_inner().as_bytes(), event_start + 2),
            Event::Eof => break,
            _ => continue,
        };
        let (prefix, local) = match resolved {
            quick_xml::name::ResolveResult::Bound(namespace)
                if namespace.0.as_bytes() == PRESENTATION_MAIN_NS
                    || namespace.0.as_bytes() == STRICT_PRESENTATION_MAIN_NS =>
            {
                (b"p:".as_slice(), local_name(raw_name))
            }
            quick_xml::name::ResolveResult::Bound(namespace)
                if namespace.0.as_bytes() == DRAWINGML_MAIN_NS
                    || namespace.0.as_bytes() == STRICT_DRAWINGML_MAIN_NS =>
            {
                (b"a:".as_slice(), local_name(raw_name))
            }
            _ if raw_name.starts_with(b"p:") => {
                (b"wolfppt-foreign-p:".as_slice(), local_name(raw_name))
            }
            _ if raw_name.starts_with(b"a:") => {
                (b"wolfppt-foreign-a:".as_slice(), local_name(raw_name))
            }
            _ => continue,
        };
        if raw_name
            .strip_prefix(prefix)
            .is_some_and(|name| name == local)
        {
            continue;
        }
        let name_end = name_start + raw_name.len();
        let output = rewritten.get_or_insert_with(|| Vec::with_capacity(xml.len()));
        output.extend_from_slice(&xml[copied..name_start]);
        output.extend_from_slice(prefix);
        output.extend_from_slice(local);
        copied = name_end;
    }

    Ok(rewritten.map(|mut output| {
        output.extend_from_slice(&xml[copied..]);
        output
    }))
}

fn summarize_shape_block(
    block: &str,
    parent_frame: Option<CoordinateFrame>,
    media_playback_by_shape_id: &[(String, MediaPlaybackSummary)],
) -> ShapeSummary {
    let tag = shape_tag_name(block).unwrap_or("unknown");
    let is_movie = tag == "p:pic" && block.contains("<a:videoFile");
    let is_audio = tag == "p:pic" && block.contains("<a:audioFile");
    let is_ole_object = tag == "p:graphicFrame" && block.contains("<p:oleObj");
    let kind = match tag {
        "p:sp" => "shape",
        "p:pic" if is_movie => "movie",
        "p:pic" if is_audio => "audio",
        "p:pic" => "picture",
        "p:graphicFrame" if is_ole_object => "ole_object",
        "p:graphicFrame" => "graphic_frame",
        "p:grpSp" => "group",
        "p:cxnSp" => "connector",
        _ => "unknown",
    }
    .to_string();
    let (id, name) = non_visual_properties(block);
    let shape_media_playback = id.as_deref().and_then(|shape_id| {
        media_playback_by_shape_id
            .iter()
            .find_map(|(id, playback)| (id.as_str() == shape_id).then_some(*playback))
    });
    let (is_placeholder, placeholder_type, placeholder_idx) = placeholder_properties(block);
    let ParagraphSummary {
        runs: paragraph_runs,
        line_breaks: paragraph_line_breaks,
        run_bold: paragraph_run_bold,
        run_italic: paragraph_run_italic,
        run_underline: paragraph_run_underline,
        run_strike: paragraph_run_strike,
        run_font_size: paragraph_run_font_size,
        run_font_name: paragraph_run_font_name,
        run_color: paragraph_run_color,
        texts: paragraphs,
    } = extract_paragraph_summary(block.as_bytes());
    let text = paragraphs.join("\n");
    let transform = extract_transform(block);
    let effective_transform = apply_parent_transform(transform, parent_frame);
    let child_frame = group_frame(block, parent_frame);
    let children = extract_group_children(block)
        .into_iter()
        .map(|child| summarize_shape_block(child, child_frame, media_playback_by_shape_id))
        .collect();

    ShapeSummary {
        id,
        name,
        kind,
        media_playback: shape_media_playback,
        is_placeholder,
        placeholder_type,
        placeholder_idx,
        text,
        paragraphs,
        paragraph_runs,
        paragraph_line_breaks,
        paragraph_run_bold,
        paragraph_run_italic,
        paragraph_run_underline,
        paragraph_run_strike,
        paragraph_run_font_size,
        paragraph_run_font_name,
        paragraph_run_color,
        tables: extract_tables_in_str(block),
        relationship_ids: relationship_ids_from_block(block),
        // Only a graphic frame hosts a chart; a group merely containing one is
        // still a group, and its chart child is summarized separately.
        has_chart: tag == "p:graphicFrame"
            && (block.contains(":chart") || block.contains("<c:chart")),
        has_picture: tag == "p:pic" && !is_movie && !is_audio,
        has_group: tag == "p:grpSp",
        transform,
        effective_transform,
        children,
    }
}

fn extract_media_playback(xml: &str) -> Vec<(String, MediaPlaybackSummary)> {
    let Some((list_start, list_end)) = timing_root_child_list_bounds(xml) else {
        return Vec::new();
    };
    let parent_start_end = xml[list_start..].find('>').map(|end| list_start + end + 1);
    let parent_end_start = list_end.checked_sub("</p:childTnLst>".len());
    let (Some(mut offset), Some(parent_end_start)) = (parent_start_end, parent_end_start) else {
        return Vec::new();
    };
    let mut playback = Vec::new();
    while let Some(relative_start) = xml[offset..parent_end_start].find('<') {
        let child_start = offset + relative_start;
        if xml[child_start..].starts_with("</") {
            break;
        }
        let tag_name_start = child_start + 1;
        let Some(tag_name_end) = xml[tag_name_start..]
            .find(|ch: char| ch == '>' || ch == '/' || ch.is_whitespace())
            .map(|end| tag_name_start + end)
        else {
            break;
        };
        let tag = &xml[tag_name_start..tag_name_end];
        let Some(child_end) = find_element_end(xml, child_start, tag) else {
            break;
        };
        if matches!(tag, "p:audio" | "p:video") {
            if let Some((shape_id, settings)) =
                media_playback_from_timing_xml(&xml[child_start..child_end])
            {
                if let Some((_, existing)) = playback.iter_mut().find(|(id, _)| id == &shape_id) {
                    *existing = settings;
                } else {
                    playback.push((shape_id, settings));
                }
            }
        }
        offset = child_end;
    }
    for (shape_id, settings) in &mut playback {
        settings.auto_play = settings.auto_play
            || media_play_call_effects(xml, shape_id)
                .iter()
                .any(|(_, _, node_type)| is_auto_media_call_node_type(node_type.as_deref()));
    }
    playback
}

fn media_playback_from_timing_xml(xml: &str) -> Option<(String, MediaPlaybackSummary)> {
    let media_node = element_start_tag(xml, "p:cMediaNode")?;
    let target = element_start_tag(xml, "p:spTgt")?;
    let shape_id = extract_string_attribute(target, "spid")?;
    let timing_start = find_tag_start(xml, 0, "p:cTn")?;
    let timing_end = find_element_end(xml, timing_start, "p:cTn")?;
    let timing_tag = element_start_tag(&xml[timing_start..timing_end], "p:cTn")?;
    let volume = extract_string_attribute(media_node, "vol")
        .and_then(|value| value.parse::<u32>().ok())
        .map(|value| (value / 1000).min(100) as u8)
        .unwrap_or(80);
    let play_across_slides = extract_string_attribute(media_node, "numSld")
        .and_then(|value| value.parse::<u32>().ok())
        .is_some_and(|count| count > 1);
    let playback = MediaPlaybackSummary {
        r#loop: extract_string_attribute(timing_tag, "repeatCount").as_deref()
            == Some("indefinite"),
        play_across_slides,
        volume,
        // Legacy WolfPPT output started the media node itself at slide begin;
        // PowerPoint's own form is a main-sequence media call, read above.
        auto_play: xml[timing_start..timing_end].contains(r#"delay="0""#),
    };
    Some((shape_id, playback))
}

fn extract_group_children(block: &str) -> Vec<&str> {
    // MC selection and QName canonicalization already ran on the whole slide.
    // Read raw canonical names here: sliced groups may lack namespace bindings.
    let mut reader = Reader::from_str(block);
    let Ok(Event::Start(group)) = reader.read_event() else {
        return Vec::new();
    };
    if group.name().as_ref() != "p:grpSp" {
        return Vec::new();
    }
    let mut children = Vec::new();
    loop {
        let start = reader.buffer_position() as usize;
        let event = match reader.read_event() {
            Ok(event) => event,
            Err(_) => break,
        };
        let child = match event {
            Event::Start(child) => {
                if reader.read_to_end(child.name()).is_err() {
                    break;
                }
                child
            }
            Event::Empty(child) => child,
            Event::End(_) | Event::Eof => break,
            _ => continue,
        };
        // Consume each direct child as one subtree. Properties and extension
        // payloads are not shape containers; nested groups recurse separately.
        if matches!(
            child.name().as_ref(),
            "p:sp" | "p:pic" | "p:graphicFrame" | "p:grpSp" | "p:cxnSp"
        ) {
            children.push(&block[start..reader.buffer_position() as usize]);
        }
    }
    children
}

fn extract_shape_blocks(xml: &str) -> Vec<&str> {
    let mut blocks = Vec::new();
    let mut offset = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        blocks.push(&xml[start..end]);
        offset = end;
    }
    blocks
}

fn find_next_shape_start(xml: &str, mut offset: usize) -> Option<(usize, &'static str)> {
    const TAGS: [&str; 5] = ["p:sp", "p:pic", "p:graphicFrame", "p:grpSp", "p:cxnSp"];
    // One forward walk over `<` finds the earliest shape tag. Searching each
    // tag separately rescans the rest of the input for every tag that no longer
    // occurs. At most one tag can match at a given `<`: a match needs a tag
    // boundary after the name, and no tag name is a prefix of another.
    while let Some(relative) = xml[offset..].find('<') {
        let position = offset + relative;
        let name_start = position + 1;
        let name = &xml[name_start..];
        for tag in TAGS {
            if name.starts_with(tag) && is_tag_boundary(xml, name_start + tag.len()) {
                return Some((position, tag));
            }
        }
        offset = name_start;
    }
    None
}

fn find_tag_start(xml: &str, offset: usize, tag: &str) -> Option<usize> {
    find_tag_start_before(xml, offset, tag, xml.len())
}

/// First `<tag` at or after `offset` that starts before `limit` and is
/// followed by a tag boundary. The boundary is read from the whole of `xml`.
fn find_tag_start_before(xml: &str, mut offset: usize, tag: &str, limit: usize) -> Option<usize> {
    while let Some(relative) = xml[offset..].find('<') {
        let position = offset + relative;
        if position >= limit {
            return None;
        }
        let name_start = position + 1;
        if xml[name_start..].starts_with(tag) && is_tag_boundary(xml, name_start + tag.len()) {
            return Some(position);
        }
        offset = name_start;
    }
    None
}

fn is_tag_boundary(xml: &str, position: usize) -> bool {
    xml[position..]
        .chars()
        .next()
        .is_some_and(|ch| ch == '>' || ch == '/' || ch.is_whitespace())
}

fn find_element_end(xml: &str, start: usize, tag: &str) -> Option<usize> {
    let close = format!("</{tag}>");
    let start_end = xml[start..].find('>')? + start + 1;
    if xml[start..start_end].trim_end().ends_with("/>") {
        return Some(start_end);
    }
    let mut depth = 1;
    let mut offset = start_end;
    loop {
        let next_close = xml[offset..].find(&close).map(|relative| offset + relative);
        // An opening tag after the next closing tag cannot affect this step
        // (the closing tag is handled first), so do not search past it.
        let next_open = match next_close {
            Some(close_position) => find_tag_start_before(xml, offset, tag, close_position),
            None => find_tag_start(xml, offset, tag),
        };
        match (next_open, next_close) {
            (None, Some(close_position)) => {
                depth -= 1;
                offset = close_position + close.len();
                if depth == 0 {
                    return Some(offset);
                }
            }
            (Some(open_position), Some(close_position)) if close_position < open_position => {
                depth -= 1;
                offset = close_position + close.len();
                if depth == 0 {
                    return Some(offset);
                }
            }
            (Some(open_position), _) => {
                let open_end = xml[open_position..].find('>')? + open_position + 1;
                if !xml[open_position..open_end].trim_end().ends_with("/>") {
                    depth += 1;
                }
                offset = open_end;
            }
            (None, None) => return None,
        }
    }
}

fn element_inner<'a>(xml: &'a str, tag: &str) -> Option<&'a str> {
    let start = find_tag_start(xml, 0, tag)?;
    let start_end = xml[start..].find('>')? + start + 1;
    let end = find_element_end(xml, start, tag)? - format!("</{tag}>").len();
    Some(&xml[start_end..end])
}

fn shape_tag_name(block: &str) -> Option<&'static str> {
    ["p:sp", "p:pic", "p:graphicFrame", "p:grpSp", "p:cxnSp"]
        .into_iter()
        .find(|tag| block.starts_with(&format!("<{tag}")))
}

fn non_visual_properties(block: &str) -> (Option<String>, Option<String>) {
    // Element names were namespace-resolved by canonical_shape_qnames before
    // slicing this block; inherited namespace declarations need not be present.
    let mut reader = Reader::from_str(block);
    while let Ok(event) = reader.read_event() {
        match event {
            Event::Start(event) | Event::Empty(event)
                if event.name().as_ref() == "p:cNvPr" =>
            {
                let mut id = None;
                let mut name = None;
                for attribute in event.attributes().flatten() {
                    let target = match attribute.key.as_ref() {
                        "id" => &mut id,
                        "name" => &mut name,
                        _ => continue,
                    };
                    if let Ok(value) = attribute.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                        *target = Some(value.into_owned());
                    }
                }
                return (id, name);
            }
            Event::Eof => break,
            _ => {}
        }
    }
    (None, None)
}

fn placeholder_properties(block: &str) -> (bool, Option<String>, Option<String>) {
    // `p:ph` belongs to the shape's own non-visual `p:nvPr`, which precedes any
    // group children. A placeholder nested inside a group must not mark the
    // enclosing group itself as a placeholder.
    let Some(nv_start) = find_tag_start(block, 0, "p:nvPr") else {
        return (false, None, None);
    };
    let Some(nv_end) = find_element_end(block, nv_start, "p:nvPr") else {
        return (false, None, None);
    };
    let Some(tag) = element_start_tag(&block[nv_start..nv_end], "p:ph") else {
        return (false, None, None);
    };
    (
        true,
        attribute_value(tag, "type"),
        attribute_value(tag, "idx"),
    )
}

fn extract_transform(block: &str) -> Option<TransformSummary> {
    let xfrm_start =
        find_tag_start(block, 0, "a:xfrm").or_else(|| find_tag_start(block, 0, "p:xfrm"))?;
    let xfrm_end = if block[xfrm_start..].starts_with("<a:xfrm") {
        find_element_end(block, xfrm_start, "a:xfrm")?
    } else {
        find_element_end(block, xfrm_start, "p:xfrm")?
    };
    let xfrm = &block[xfrm_start..xfrm_end];
    let off = element_start_tag(xfrm, "a:off")?;
    let ext = element_start_tag(xfrm, "a:ext")?;
    Some(TransformSummary {
        x: attribute_i64(off, "x"),
        y: attribute_i64(off, "y"),
        cx: attribute_i64(ext, "cx"),
        cy: attribute_i64(ext, "cy"),
    })
}

fn group_frame(block: &str, parent_frame: Option<CoordinateFrame>) -> Option<CoordinateFrame> {
    if !block.starts_with("<p:grpSp") {
        return None;
    }
    let effective = apply_parent_transform(extract_transform(block), parent_frame)?;
    let xfrm_start = find_tag_start(block, 0, "a:xfrm")?;
    let xfrm_end = find_element_end(block, xfrm_start, "a:xfrm")?;
    let xfrm = &block[xfrm_start..xfrm_end];
    let ch_off = element_start_tag(xfrm, "a:chOff");
    let ch_ext = element_start_tag(xfrm, "a:chExt");
    Some(CoordinateFrame {
        x: effective.x,
        y: effective.y,
        cx: effective.cx,
        cy: effective.cy,
        ch_x: ch_off.map_or(0, |tag| attribute_i64(tag, "x")),
        ch_y: ch_off.map_or(0, |tag| attribute_i64(tag, "y")),
        ch_cx: ch_ext.map_or(effective.cx, |tag| attribute_i64(tag, "cx")),
        ch_cy: ch_ext.map_or(effective.cy, |tag| attribute_i64(tag, "cy")),
    })
}

fn apply_parent_transform(
    transform: Option<TransformSummary>,
    parent_frame: Option<CoordinateFrame>,
) -> Option<TransformSummary> {
    let transform = transform?;
    let Some(parent_frame) = parent_frame else {
        return Some(transform);
    };
    Some(TransformSummary {
        x: parent_frame.x
            + scale_child_coordinate(
                transform.x - parent_frame.ch_x,
                parent_frame.cx,
                parent_frame.ch_cx,
            ),
        y: parent_frame.y
            + scale_child_coordinate(
                transform.y - parent_frame.ch_y,
                parent_frame.cy,
                parent_frame.ch_cy,
            ),
        cx: scale_child_coordinate(transform.cx, parent_frame.cx, parent_frame.ch_cx),
        cy: scale_child_coordinate(transform.cy, parent_frame.cy, parent_frame.ch_cy),
    })
}

fn scale_child_coordinate(value: i64, parent_extent: i64, child_extent: i64) -> i64 {
    if child_extent == 0 {
        return value;
    }
    ((value as f64) * (parent_extent as f64) / (child_extent as f64)).round() as i64
}

fn relationship_ids_from_block(block: &str) -> Vec<String> {
    let mut ids = Vec::new();
    for name in ["r:embed", "r:link", "r:id"] {
        ids.extend(attribute_values(block, name));
    }
    ids.sort();
    ids.dedup();
    ids
}

fn attribute_values(xml: &str, name: &str) -> Vec<String> {
    let mut values = Vec::new();
    let mut offset = 0;
    let needle = format!("{name}=\"");
    while let Some(relative) = xml[offset..].find(&needle) {
        let start = offset + relative + needle.len();
        let Some(relative_end) = xml[start..].find('"') else {
            break;
        };
        values.push(xml[start..start + relative_end].to_string());
        offset = start + relative_end + 1;
    }
    values
}

fn element_start_tag<'a>(xml: &'a str, tag: &str) -> Option<&'a str> {
    let start = find_tag_start(xml, 0, tag)?;
    let end = xml[start..].find('>')? + start + 1;
    Some(&xml[start..end])
}

fn attribute_value(tag: &str, name: &str) -> Option<String> {
    let needle = format!("{name}=\"");
    let start = tag.find(&needle)? + needle.len();
    let end = tag[start..].find('"')?;
    Some(tag[start..start + end].to_string())
}

fn attribute_i64(tag: &str, name: &str) -> i64 {
    attribute_value(tag, name)
        .and_then(|value| value.parse().ok())
        .unwrap_or(0)
}

fn drawingml_attribute(event: &BytesStart<'_>, name: &[u8]) -> Option<String> {
    for attr in event.attributes().flatten() {
        if local_name(attr.key.as_ref().as_bytes()) != name {
            continue;
        }
        return Some(attr.value.into_owned());
    }
    None
}
