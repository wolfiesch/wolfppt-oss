fn extract_tables(xml: &[u8]) -> Vec<TableSummary> {
    let xml = String::from_utf8_lossy(xml);
    let mut tables = Vec::new();
    let mut table_offset = 0;

    while let Some(start) = find_tag_start(&xml, table_offset, "a:tbl") {
        let Some(end) = find_element_end(&xml, start, "a:tbl") else {
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

fn extract_shapes(xml: &[u8]) -> Vec<ShapeSummary> {
    let xml = String::from_utf8_lossy(xml);
    let Some(sp_tree) = element_inner(&xml, "p:spTree") else {
        return Vec::new();
    };
    extract_shape_blocks(sp_tree)
        .into_iter()
        .map(|block| summarize_shape_block(block, None))
        .collect()
}

fn summarize_shape_block(block: &str, parent_frame: Option<CoordinateFrame>) -> ShapeSummary {
    let tag = shape_tag_name(block).unwrap_or("unknown");
    let is_movie = tag == "p:pic" && block.contains("<a:videoFile");
    let is_ole_object = tag == "p:graphicFrame" && block.contains("<p:oleObj");
    let kind = match tag {
        "p:sp" => "shape",
        "p:pic" if is_movie => "movie",
        "p:pic" => "picture",
        "p:graphicFrame" if is_ole_object => "ole_object",
        "p:graphicFrame" => "graphic_frame",
        "p:grpSp" => "group",
        "p:cxnSp" => "connector",
        _ => "unknown",
    }
    .to_string();
    let (id, name) = non_visual_properties(block);
    let (is_placeholder, placeholder_type, placeholder_idx) = placeholder_properties(block);
    let paragraph_runs = extract_paragraph_runs(block.as_bytes());
    let paragraph_line_breaks = extract_paragraph_line_breaks(block.as_bytes());
    let paragraph_run_bold = extract_paragraph_run_bold(block.as_bytes());
    let paragraph_run_italic = extract_paragraph_run_italic(block.as_bytes());
    let paragraph_run_underline = extract_paragraph_run_underline(block.as_bytes());
    let paragraph_run_font_size = extract_paragraph_run_font_size(block.as_bytes());
    let paragraph_run_font_name = extract_paragraph_run_font_name(block.as_bytes());
    let paragraphs = extract_paragraph_texts(block.as_bytes());
    let text = paragraphs.join("\n");
    let transform = extract_transform(block);
    let effective_transform = apply_parent_transform(transform, parent_frame);
    let child_frame = group_frame(block, parent_frame);
    let children = extract_group_children(block)
        .into_iter()
        .map(|child| summarize_shape_block(child, child_frame))
        .collect();

    ShapeSummary {
        id,
        name,
        kind,
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
        paragraph_run_font_size,
        paragraph_run_font_name,
        tables: extract_tables(block.as_bytes()),
        relationship_ids: relationship_ids_from_block(block),
        has_chart: block.contains(":chart") || block.contains("<c:chart"),
        has_picture: tag == "p:pic" && !is_movie,
        has_group: tag == "p:grpSp",
        transform,
        effective_transform,
        children,
    }
}

fn extract_group_children(block: &str) -> Vec<&str> {
    if !block.starts_with("<p:grpSp") {
        return Vec::new();
    }
    let Some(start) = block.find("</p:grpSpPr>") else {
        return Vec::new();
    };
    let content_start = start + "</p:grpSpPr>".len();
    let content_end = block.rfind("</p:grpSp>").unwrap_or(block.len());
    extract_shape_blocks(&block[content_start..content_end])
}

fn extract_shape_blocks(xml: &str) -> Vec<&str> {
    let mut blocks = Vec::new();
    let mut offset = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        if let Some(end) = containing_alternate_content_end(xml, start) {
            offset = end;
            continue;
        }
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        blocks.push(&xml[start..end]);
        offset = end;
    }
    blocks
}

fn find_next_shape_start(xml: &str, offset: usize) -> Option<(usize, &'static str)> {
    let tags = ["p:sp", "p:pic", "p:graphicFrame", "p:grpSp", "p:cxnSp"];
    tags.iter()
        .filter_map(|tag| find_tag_start(xml, offset, tag).map(|position| (position, *tag)))
        .min_by_key(|(position, _)| *position)
}

fn containing_alternate_content_end(xml: &str, position: usize) -> Option<usize> {
    let open = xml[..position].rfind("<mc:AlternateContent")?;
    if xml[..position]
        .rfind("</mc:AlternateContent>")
        .is_some_and(|close| close > open)
    {
        return None;
    }
    find_element_end(xml, open, "mc:AlternateContent")
}

fn find_tag_start(xml: &str, mut offset: usize, tag: &str) -> Option<usize> {
    let needle = format!("<{tag}");
    while let Some(relative) = xml[offset..].find(&needle) {
        let position = offset + relative;
        let next = position + needle.len();
        if is_tag_boundary(xml, next) {
            return Some(position);
        }
        offset = next;
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
    let open = format!("<{tag}");
    let close = format!("</{tag}>");
    let mut depth = 1;
    let mut offset = start + open.len();
    loop {
        let next_open = find_tag_start(xml, offset, tag);
        let next_close = xml[offset..].find(&close).map(|relative| offset + relative);
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
                depth += 1;
                offset = open_position + open.len();
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
    let Some(tag) = element_start_tag(block, "p:cNvPr") else {
        return (None, None);
    };
    (attribute_value(tag, "id"), attribute_value(tag, "name"))
}

fn placeholder_properties(block: &str) -> (bool, Option<String>, Option<String>) {
    let Some(tag) = element_start_tag(block, "p:ph") else {
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
        if local_name(attr.key.as_ref()) != name {
            continue;
        }
        return Some(
            std::str::from_utf8(attr.value.as_ref())
                .unwrap_or_default()
                .to_string(),
        );
    }
    None
}
