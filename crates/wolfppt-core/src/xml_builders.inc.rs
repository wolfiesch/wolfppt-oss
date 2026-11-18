fn add_relationship(
    xml: &str,
    relationship_id: &str,
    relationship_type: &str,
    target: &str,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</Relationships>") else {
        return Err(WolfPptError::InvalidInput(
            "relationships part is missing </Relationships>".to_string(),
        ));
    };
    let relationship = format!(
        r#"<Relationship Id="{relationship_id}" Type="{relationship_type}" Target="{target}"/>"#,
        relationship_id = xml_attr(relationship_id),
        relationship_type = xml_attr(relationship_type),
        target = xml_attr(target),
    );
    Ok(format!("{}{}{}", &xml[..end], relationship, &xml[end..]))
}

fn ensure_default_content_type(
    xml: &str,
    extension: &str,
    content_type: &str,
) -> Result<String, WolfPptError> {
    // Check if this extension already exists (case-insensitive)
    let mut reader = quick_xml::Reader::from_str(xml);
    let mut buf = Vec::new();
    let extension_lower = extension.to_ascii_lowercase();
    
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(quick_xml::events::Event::Empty(e)) | Ok(quick_xml::events::Event::Start(e))
                if e.local_name().as_ref().as_bytes() == b"Default" =>
            {
                for attr in e.attributes().flatten() {
                    if attr.key.local_name().as_ref().as_bytes() == b"Extension" {
                        if let Ok(val) = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                            if val.to_ascii_lowercase() == extension_lower {
                                return Ok(xml.to_string());
                            }
                        }
                    }
                }
            }
            Ok(quick_xml::events::Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }
    
    String::from_utf8(append_content_type_element(
        xml.as_bytes(),
        "Default",
        &format!(
            r#"Extension="{}" ContentType="{}""#,
            xml_attr(extension),
            xml_attr(content_type)
        ),
    )?)
    .map_err(|err| WolfPptError::XmlText(err.to_string()))
}

fn ensure_content_type_override(
    xml: &str,
    part_name: &str,
    content_type: &str,
) -> Result<String, WolfPptError> {
    // Check if this PartName already exists (case-insensitive)
    let mut reader = quick_xml::Reader::from_str(xml);
    let mut buf = Vec::new();
    let part_name_lower = part_name.to_ascii_lowercase();
    
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(quick_xml::events::Event::Empty(e)) | Ok(quick_xml::events::Event::Start(e))
                if e.local_name().as_ref().as_bytes() == b"Override" =>
            {
                for attr in e.attributes().flatten() {
                    if attr.key.local_name().as_ref().as_bytes() == b"PartName" {
                        if let Ok(val) = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                            if val.to_ascii_lowercase() == part_name_lower {
                                return Ok(xml.to_string());
                            }
                        }
                    }
                }
            }
            Ok(quick_xml::events::Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }
    
    String::from_utf8(append_content_type_element(
        xml.as_bytes(),
        "Override",
        &format!(
            r#"PartName="{}" ContentType="{}""#,
            xml_attr(part_name),
            xml_attr(content_type)
        ),
    )?)
    .map_err(|err| WolfPptError::XmlText(err.to_string()))
}

// Match the public table insertion and shape builder's flat unsigned EMUs
// instead of adding a table-only frame wrapper or narrowing to the signed frame.
#[allow(clippy::too_many_arguments)]
fn add_table_to_slide_xml(
    xml: &str,
    shape_id: u64,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    cell_texts: &[(usize, usize, String)],
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let table = table_shape_xml(
        shape_id, rows, cols, x_emu, y_emu, cx_emu, cy_emu, cell_texts,
    )?;
    Ok(format!("{}{}{}", &xml[..end], table, &xml[end..]))
}

fn add_text_box_to_slide_xml(
    xml: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let bom = utf8_bom_offset(xml.as_bytes());
    let mut reader = quick_xml::NsReader::from_str(xml);
    let mut depth = 0usize;
    let mut profile = None;
    let mut common_slide_seen = false;
    let mut in_common_slide = false;
    let mut shape_tree_seen = false;
    let mut in_shape_tree = false;
    let mut insert_at = None;
    let invalid_owner = || {
        WolfPptError::InvalidInput(
            "slide XML must contain one PML sld/cSld/spTree owner".to_string(),
        )
    };

    // Scan the complete owner before publishing; preserve every original byte.
    loop {
        let offset = bom + reader.buffer_position() as usize;
        let (resolved, event) = reader.read_resolved_event()?;
        let namespace = match &resolved {
            quick_xml::name::ResolveResult::Bound(ns) => Some(ns.0.as_bytes()),
            quick_xml::name::ResolveResult::Unknown(_) => return Err(invalid_owner()),
            quick_xml::name::ResolveResult::Unbound => None,
        };
        let empty = matches!(&event, Event::Empty(_));
        match event {
            Event::Start(event) | Event::Empty(event) => {
                let name = event.local_name();
                if depth == 0 {
                    if profile.is_some() || name.as_ref().as_bytes() != b"sld" || empty {
                        return Err(invalid_owner());
                    }
                    profile = Some(match namespace {
                        Some(ns) if ns == PRESENTATION_MAIN_NS => (
                            "http://schemas.openxmlformats.org/presentationml/2006/main",
                            "http://schemas.openxmlformats.org/drawingml/2006/main",
                        ),
                        Some(ns) if ns == STRICT_PRESENTATION_MAIN_NS => (
                            "http://purl.oclc.org/ooxml/presentationml/main",
                            "http://purl.oclc.org/ooxml/drawingml/main",
                        ),
                        _ => return Err(invalid_owner()),
                    });
                }
                let presentation_ns = profile
                    .is_some_and(|(pml, _)| namespace == Some(pml.as_bytes()));
                if presentation_ns && depth == 1 && name.as_ref().as_bytes() == b"cSld" {
                    if common_slide_seen || empty {
                        return Err(invalid_owner());
                    }
                    common_slide_seen = true;
                    in_common_slide = true;
                }
                if presentation_ns
                    && depth == 2
                    && in_common_slide
                    && name.as_ref().as_bytes() == b"spTree"
                {
                    if shape_tree_seen || empty {
                        return Err(invalid_owner());
                    }
                    shape_tree_seen = true;
                    in_shape_tree = true;
                }
                if presentation_ns
                    && depth == 3
                    && in_shape_tree
                    && name.as_ref().as_bytes() == b"extLst"
                {
                    insert_at.get_or_insert(offset);
                }
                for attribute in event.attributes() {
                    let attribute = attribute
                        .map_err(|err| WolfPptError::XmlText(err.to_string()))?;
                    if matches!(
                        reader.resolver().resolve_attribute(attribute.key).0,
                        quick_xml::name::ResolveResult::Unknown(_)
                    ) {
                        return Err(invalid_owner());
                    }
                    attribute.normalized_value(quick_xml::XmlVersion::Implicit1_0)?;
                }
                if !empty {
                    depth += 1;
                }
            }
            Event::End(_) => {
                if depth == 3 && in_shape_tree {
                    insert_at.get_or_insert(offset);
                    in_shape_tree = false;
                }
                if depth == 2 && in_common_slide {
                    in_common_slide = false;
                }
                depth = depth.checked_sub(1).ok_or_else(invalid_owner)?;
            }
            Event::Text(event) if depth == 0 => {
                if !event.as_ref().as_bytes().iter().all(u8::is_ascii_whitespace) {
                    return Err(invalid_owner());
                }
            }
            Event::GeneralRef(_) if depth == 0 => return Err(invalid_owner()),
            Event::Eof => break,
            _ => {}
        }
    }
    if depth != 0 {
        return Err(invalid_owner());
    }
    let end = insert_at.ok_or_else(invalid_owner)?;
    let (pml, dml) = profile.ok_or_else(invalid_owner)?;
    let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
    // Bind only the new fragment. Grouped callers retain their existing contract.
    let mut output = String::with_capacity(xml.len() + text_box.len() + pml.len() + dml.len() + 24);
    output.push_str(&xml[..end]);
    output.push_str("<p:sp xmlns:p=\"");
    output.push_str(pml);
    output.push_str("\" xmlns:a=\"");
    output.push_str(dml);
    output.push('"');
    output.push_str(&text_box["<p:sp".len()..]);
    output.push_str(&xml[end..]);
    Ok(output)
}

// Match sibling text-box builders' flat signed-offset/unsigned-extent contract
// instead of introducing a geometry wrapper only for existing-group insertion.
#[allow(clippy::too_many_arguments)]
fn add_text_box_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
                let rewritten_group = append_group_children_xml(block, &text_box)?;
                return replace_group_subtree_xml(xml, start, end, &rewritten_group);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_text_box_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
    let rewritten_group = append_group_children_xml(block, &text_box)?;
    replace_group_subtree_xml(xml, nested_start, nested_end, &rewritten_group)
}

#[allow(clippy::too_many_arguments)]
fn add_text_box_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let nested_block = &xml[nested_start..nested_end];
    let Some((deeper_start, deeper_end, deeper_tag)) =
        direct_group_child_bounds(nested_block, deeper_group_child_index)
    else {
        return Err(WolfPptError::InvalidInput(format!(
            "deeper nested group child index {deeper_group_child_index} was not found"
        )));
    };
    if deeper_tag != "p:grpSp" {
        return Err(WolfPptError::InvalidInput(format!(
            "deeper nested group child index {deeper_group_child_index} is not a group shape"
        )));
    }
    let deeper_block = &nested_block[deeper_start..deeper_end];
    let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
    let rewritten_group = append_group_children_xml(deeper_block, &text_box)?;
    let deeper_absolute_start = nested_start + deeper_start;
    let deeper_absolute_end = nested_start + deeper_end;
    replace_group_subtree_xml(xml, deeper_absolute_start, deeper_absolute_end, &rewritten_group)
}

fn nested_group_child_bounds(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
) -> Result<(usize, usize), WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some((child_start, child_end, child_tag)) =
                    direct_group_child_bounds(block, nested_group_child_index)
                else {
                    return Err(WolfPptError::InvalidInput(format!(
                        "nested group child index {nested_group_child_index} was not found"
                    )));
                };
                if child_tag != "p:grpSp" {
                    return Err(WolfPptError::InvalidInput(format!(
                        "nested group child index {nested_group_child_index} is not a group shape"
                    )));
                }
                return Ok((start + child_start, start + child_end));
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

fn direct_group_child_bounds(
    group_block: &str,
    child_index: usize,
) -> Option<(usize, usize, &'static str)> {
    let content_start = group_block.find("</p:grpSpPr>")? + "</p:grpSpPr>".len();
    let content_end = group_block.rfind("</p:grpSp>")?;
    let mut offset = content_start;
    let mut current_child_index = 0;
    while let Some((start, tag)) = find_next_shape_start(group_block, offset) {
        if start >= content_end {
            break;
        }
        let end = find_element_end(group_block, start, tag)?;
        if end > content_end {
            break;
        }
        if current_child_index == child_index {
            return Some((start, end, tag));
        }
        current_child_index += 1;
        offset = end;
    }
    None
}

fn top_level_group_bounds(xml: &str, group_index: usize) -> Result<(usize, usize), WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                return Ok((start, end));
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

fn shape_block_bounds(block: &str) -> Option<(i64, i64, i64, i64)> {
    let transform = extract_transform(block)?;
    Some((transform.x, transform.y, transform.cx, transform.cy))
}

fn group_child_bounds(xml: &str) -> Result<Vec<(i64, i64, i64, i64)>, WolfPptError> {
    let mut bounds = Vec::new();
    let mut offset = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let end = find_element_end(xml, start, tag).ok_or_else(|| {
            WolfPptError::InvalidInput("group child XML is malformed".to_string())
        })?;
        let child_bounds = shape_block_bounds(&xml[start..end]).ok_or_else(|| {
            WolfPptError::InvalidInput("group child is missing transform".to_string())
        })?;
        bounds.push(child_bounds);
        offset = end;
    }
    if bounds.is_empty() {
        return Err(WolfPptError::InvalidInput(
            "group child XML has no drawable shapes".to_string(),
        ));
    }
    Ok(bounds)
}

fn existing_group_child_bounds(
    group_block: &str,
) -> Result<Vec<(i64, i64, i64, i64)>, WolfPptError> {
    let mut bounds = Vec::new();
    let mut child_index = 0;
    while let Some((start, end, _tag)) = direct_group_child_bounds(group_block, child_index) {
        let child_bounds = shape_block_bounds(&group_block[start..end]).ok_or_else(|| {
            WolfPptError::InvalidInput("group child is missing transform".to_string())
        })?;
        bounds.push(child_bounds);
        child_index += 1;
    }
    Ok(bounds)
}

fn group_bounds_with_children(
    xfrm: &str,
    children: &[(i64, i64, i64, i64)],
) -> (i64, i64, i64, i64, i64, i64, i64, i64) {
    let off = element_start_tag(xfrm, "a:off");
    let ext = element_start_tag(xfrm, "a:ext");
    let ch_off = element_start_tag(xfrm, "a:chOff");
    let ch_ext = element_start_tag(xfrm, "a:chExt");
    let off_x = off.map_or(0, |tag| attribute_i64(tag, "x"));
    let off_y = off.map_or(0, |tag| attribute_i64(tag, "y"));
    let ext_x = ext.map_or(0, |tag| attribute_i64(tag, "cx"));
    let ext_y = ext.map_or(0, |tag| attribute_i64(tag, "cy"));
    let ch_off_x = ch_off.map_or(0, |tag| attribute_i64(tag, "x"));
    let ch_off_y = ch_off.map_or(0, |tag| attribute_i64(tag, "y"));
    let ch_ext_x = ch_ext.map_or(0, |tag| attribute_i64(tag, "cx"));
    let ch_ext_y = ch_ext.map_or(0, |tag| attribute_i64(tag, "cy"));
    let initialized = ext_x > 0 && ext_y > 0 && ch_ext_x > 0 && ch_ext_y > 0;

    let (mut left, mut top, mut right, mut bottom) = if initialized {
        (
            ch_off_x,
            ch_off_y,
            ch_off_x + ch_ext_x,
            ch_off_y + ch_ext_y,
        )
    } else {
        let (x, y, cx, cy) = children[0];
        (x, y, x + cx, y + cy)
    };
    for &(x, y, cx, cy) in children {
        left = left.min(x);
        top = top.min(y);
        right = right.max(x + cx);
        bottom = bottom.max(y + cy);
    }
    let child_width = right - left;
    let child_height = bottom - top;
    if !initialized {
        return (
            left,
            top,
            child_width,
            child_height,
            left,
            top,
            child_width,
            child_height,
        );
    }

    let flip_h = attribute_value(xfrm, "flipH").is_some_and(|value| value != "0");
    let flip_v = attribute_value(xfrm, "flipV").is_some_and(|value| value != "0");
    let scale = |value, extent, child_extent| {
        ((value as f64) * (extent as f64) / (child_extent as f64)).round() as i64
    };
    let new_off_x = if flip_h {
        off_x + scale(ch_off_x + ch_ext_x - left - child_width, ext_x, ch_ext_x)
    } else {
        off_x + scale(left - ch_off_x, ext_x, ch_ext_x)
    };
    let new_off_y = if flip_v {
        off_y + scale(ch_off_y + ch_ext_y - top - child_height, ext_y, ch_ext_y)
    } else {
        off_y + scale(top - ch_off_y, ext_y, ch_ext_y)
    };
    (
        new_off_x,
        new_off_y,
        scale(child_width, ext_x, ch_ext_x),
        scale(child_height, ext_y, ch_ext_y),
        left,
        top,
        child_width,
        child_height,
    )
}

fn replace_group_transform_field(xfrm: String, tag: &str, attrs: &str) -> Result<String, WolfPptError> {
    let replacement = format!("<{tag} {attrs}/>");
    if let Some(start) = find_tag_start(&xfrm, 0, tag) {
        let end = xfrm[start..].find('>').map(|length| start + length + 1).ok_or_else(|| {
            WolfPptError::InvalidInput("group transform field is malformed".to_string())
        })?;
        return Ok(format!("{}{}{}", &xfrm[..start], replacement, &xfrm[end..]));
    }
    let end = xfrm.rfind("</a:xfrm>").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape transform is missing </a:xfrm>".to_string())
    })?;
    Ok(format!("{}{}{}", &xfrm[..end], replacement, &xfrm[end..]))
}

// Replace a group subtree (or insert a coalesced child) and initialize enclosing
// frames bottom-up. Valid ancestor frames are coordinate systems, not bounds to
// recompute whenever a descendant changes.
fn replace_group_subtree_xml(
    xml: &str,
    start: usize,
    end: usize,
    replacement: &str,
) -> Result<String, WolfPptError> {
    if start == 0 && end == xml.len() {
        return Ok(replacement.to_string());
    }
    let is_group = find_tag_start(xml, 0, "p:grpSp") == Some(0);
    let mut offset = if is_group {
        xml.find("</p:grpSpPr>").ok_or_else(|| {
            WolfPptError::InvalidInput("group shape XML is missing properties".to_string())
        })? + "</p:grpSpPr>".len()
    } else {
        0
    };
    let mut rewritten = None;
    while let Some((child_start, tag)) = find_next_shape_start(xml, offset) {
        let child_end = find_element_end(xml, child_start, tag).ok_or_else(|| {
            WolfPptError::InvalidInput("group child XML is malformed".to_string())
        })?;
        if tag == "p:grpSp" && child_start <= start && start < child_end && end <= child_end {
            let child = replace_group_subtree_xml(
                &xml[child_start..child_end],
                start - child_start,
                end - child_start,
                replacement,
            )?;
            rewritten = Some(format!("{}{}{}", &xml[..child_start], child, &xml[child_end..]));
            break;
        }
        offset = child_end;
    }
    let rewritten = rewritten.unwrap_or_else(|| {
        format!("{}{}{}", &xml[..start], replacement, &xml[end..])
    });
    if is_group {
        initialize_group_ancestor_xml(&rewritten)
    } else {
        Ok(rewritten)
    }
}

fn initialize_group_ancestor_xml(group: &str) -> Result<String, WolfPptError> {
    let properties_end = group.find("</p:grpSpPr>").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape XML is missing properties".to_string())
    })?;
    let properties = &group[..properties_end];
    let initialized = element_start_tag(properties, "a:ext")
        .is_some_and(|tag| attribute_i64(tag, "cx") > 0 && attribute_i64(tag, "cy") > 0)
        && element_start_tag(properties, "a:chExt")
            .is_some_and(|tag| attribute_i64(tag, "cx") > 0 && attribute_i64(tag, "cy") > 0);
    if initialized {
        return Ok(group.to_string());
    }
    let children = existing_group_child_bounds(group)?;
    if children.is_empty() {
        return Ok(group.to_string());
    }
    rewrite_group_bounds_xml(group, &children)
}

fn append_group_children_xml(group_block: &str, children_xml: &str) -> Result<String, WolfPptError> {
    let mut children = group_child_bounds(children_xml)?;
    let properties_end = group_block.find("</p:grpSpPr>").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape XML is missing properties".to_string())
    })?;
    let properties = &group_block[..properties_end];
    let initialized = element_start_tag(properties, "a:ext")
        .is_some_and(|tag| attribute_i64(tag, "cx") > 0 && attribute_i64(tag, "cy") > 0)
        && element_start_tag(properties, "a:chExt")
            .is_some_and(|tag| attribute_i64(tag, "cx") > 0 && attribute_i64(tag, "cy") > 0);
    if !initialized {
        children.extend(existing_group_child_bounds(group_block)?);
    }
    let rewritten_group = rewrite_group_bounds_xml(group_block, &children)?;
    let relative_end = rewritten_group.rfind("</p:grpSp>").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape XML is missing </p:grpSp>".to_string())
    })?;
    Ok(format!(
        "{}{}{}",
        &rewritten_group[..relative_end],
        children_xml,
        &rewritten_group[relative_end..]
    ))
}

fn rewrite_group_bounds_xml(
    group_block: &str,
    children: &[(i64, i64, i64, i64)],
) -> Result<String, WolfPptError> {
    let properties_end = group_block.find("</p:grpSpPr>").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape XML is missing </p:grpSpPr>".to_string())
    })?;
    let xfrm_start = find_tag_start(&group_block[..properties_end], 0, "a:xfrm").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape XML is missing transform".to_string())
    })?;
    let xfrm_end = find_element_end(group_block, xfrm_start, "a:xfrm").ok_or_else(|| {
        WolfPptError::InvalidInput("group shape transform is malformed".to_string())
    })?;
    let xfrm = &group_block[xfrm_start..xfrm_end];
    let (off_x, off_y, ext_x, ext_y, ch_off_x, ch_off_y, ch_ext_x, ch_ext_y) =
        group_bounds_with_children(xfrm, children);
    let xfrm = replace_group_transform_field(xfrm.to_string(), "a:off", &format!("x=\"{off_x}\" y=\"{off_y}\""))?;
    let xfrm = replace_group_transform_field(xfrm, "a:ext", &format!("cx=\"{ext_x}\" cy=\"{ext_y}\""))?;
    let xfrm = replace_group_transform_field(xfrm, "a:chOff", &format!("x=\"{ch_off_x}\" y=\"{ch_off_y}\""))?;
    let xfrm = replace_group_transform_field(xfrm, "a:chExt", &format!("cx=\"{ch_ext_x}\" cy=\"{ch_ext_y}\""))?;
    Ok(format!(
        "{}{}{}",
        &group_block[..xfrm_start],
        xfrm,
        &group_block[xfrm_end..]
    ))
}

fn add_group_shape_to_slide_xml(xml: &str, shape_id: u64) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let group_shape = group_shape_xml(shape_id);
    Ok(format!("{}{}{}", &xml[..end], group_shape, &xml[end..]))
}

fn add_group_shape_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    shape_id: u64,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let group_shape = group_shape_xml(shape_id);
                return replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

fn add_group_shape_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    shape_id: u64,
) -> Result<String, WolfPptError> {
    let (start, end) = nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[start..end];
    let Some(relative_end) = block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = start + relative_end;
    let group_shape = group_shape_xml(shape_id);
    replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape)
}

#[allow(clippy::too_many_arguments)]
fn add_group_shape_with_text_box_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    group_shape_id: u64,
    text_box_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let text_box =
                    text_box_shape_xml(text_box_id, x_emu, y_emu, cx_emu, cy_emu, Some(text))?;
                let group_shape = group_shape_with_child_xml(group_shape_id, &text_box)?;
                return replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_group_shape_with_auto_shape_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    group_shape_id: u64,
    auto_shape_id: u64,
    display_name: &str,
    preset_geometry: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: &str,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let auto_shape = auto_shape_xml(
                    auto_shape_id,
                    display_name,
                    preset_geometry,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    Some(text),
                    &[],
                )?;
                let group_shape = group_shape_with_child_xml(group_shape_id, &auto_shape)?;
                return replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_group_shape_with_freeform_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    group_shape_id: u64,
    freeform_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let freeform = freeform_shape_xml(
                    freeform_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    operations,
                    text,
                )?;
                let group_shape = group_shape_with_child_xml(group_shape_id, &freeform)?;
                return replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_freeform_shape_to_slide_xml(
    xml: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let freeform = freeform_shape_xml(
        shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
    )?;
    Ok(format!("{}{}{}", &xml[..end], freeform, &xml[end..]))
}

#[allow(clippy::too_many_arguments)]
fn add_freeform_shape_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let freeform = freeform_shape_xml(
                    shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
                )?;
                let rewritten_group = append_group_children_xml(block, &freeform)?;
                return replace_group_subtree_xml(xml, start, end, &rewritten_group);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_freeform_shape_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let freeform = freeform_shape_xml(
        shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
    )?;
    let rewritten_group = append_group_children_xml(block, &freeform)?;
    replace_group_subtree_xml(xml, nested_start, nested_end, &rewritten_group)
}

#[allow(clippy::too_many_arguments)]
fn add_freeform_shape_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let nested_block = &xml[nested_start..nested_end];
    let Some((deeper_start, deeper_end, deeper_tag)) =
        direct_group_child_bounds(nested_block, deeper_group_child_index)
    else {
        return Err(WolfPptError::InvalidInput(format!(
            "deeper nested group child index {deeper_group_child_index} was not found"
        )));
    };
    if deeper_tag != "p:grpSp" {
        return Err(WolfPptError::InvalidInput(format!(
            "deeper nested group child index {deeper_group_child_index} is not a group shape"
        )));
    }
    let deeper_block = &nested_block[deeper_start..deeper_end];
    let freeform = freeform_shape_xml(
        shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
    )?;
    let rewritten_group = append_group_children_xml(deeper_block, &freeform)?;
    let deeper_absolute_start = nested_start + deeper_start;
    let deeper_absolute_end = nested_start + deeper_end;
    replace_group_subtree_xml(xml, deeper_absolute_start, deeper_absolute_end, &rewritten_group)
}

fn add_placeholder_shape_to_slide_xml(
    xml: &str,
    shape_id: u64,
    placeholder_type: Option<&str>,
    placeholder_orient: Option<&str>,
    placeholder_size: Option<&str>,
    placeholder_idx: Option<&str>,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let placeholder = placeholder_shape_xml(
        xml,
        shape_id,
        placeholder_type,
        placeholder_orient,
        placeholder_size,
        placeholder_idx,
    );
    Ok(format!("{}{}{}", &xml[..end], placeholder, &xml[end..]))
}

fn replacement_paragraphs_xml(text: &str) -> Result<String, WolfPptError> {
    let mut writer = Writer::new(Vec::new());
    write_replacement_paragraphs(&mut writer, text)?;
    String::from_utf8(writer.into_inner()).map_err(|err| WolfPptError::XmlText(err.to_string()))
}

fn text_box_shape_xml(
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let text_box_number = shape_id.saturating_sub(1);
    let paragraph_xml = match text {
        Some(text) => replacement_paragraphs_xml(text)?,
        None => "<a:p/>".to_string(),
    };
    Ok(format!(
        r#"<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="TextBox {text_box_number}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="none"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{paragraph_xml}</p:txBody></p:sp>"#
    ))
}

fn group_shape_xml(shape_id: u64) -> String {
    let group_number = shape_id.saturating_sub(1);
    format!(
        r#"<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{shape_id}" name="Group {group_number}"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:grpSp>"#
    )
}

fn group_shape_with_child_xml(
    shape_id: u64,
    child_xml: &str,
) -> Result<String, WolfPptError> {
    let children = group_child_bounds(child_xml)?;
    let (mut left, mut top, mut right, mut bottom) = {
        let (x, y, cx, cy) = children[0];
        (x, y, x + cx, y + cy)
    };
    for &(x, y, cx, cy) in &children {
        left = left.min(x);
        top = top.min(y);
        right = right.max(x + cx);
        bottom = bottom.max(y + cy);
    }
    Ok(group_shape_with_children_xml(
        shape_id,
        left,
        top,
        right - left,
        bottom - top,
        child_xml,
    ))
}

fn group_shape_with_children_xml(
    shape_id: u64,
    left: i64,
    top: i64,
    width: i64,
    height: i64,
    child_xml: &str,
) -> String {
    let group_number = shape_id.saturating_sub(1);
    format!(
        r#"<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{shape_id}" name="Group {group_number}"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/><a:chOff x="{left}" y="{top}"/><a:chExt cx="{width}" cy="{height}"/></a:xfrm></p:grpSpPr>{child_xml}</p:grpSp>"#
    )
}

#[allow(clippy::too_many_arguments)]
fn freeform_shape_xml(
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: i64,
    cy_emu: i64,
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let freeform_number = shape_id.saturating_sub(1);
    let geometry_xml = freeform_custom_geometry_xml(path_w, path_h, operations)?;
    let paragraph_xml = match text {
        Some(text) => replacement_paragraphs_xml(text)?,
        None => r#"<a:p><a:pPr algn="ctr"/></a:p>"#.to_string(),
    };
    Ok(format!(
        r#"<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Freeform {freeform_number}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm>{geometry_xml}</p:spPr><p:style><a:lnRef idx="1"><a:schemeClr val="accent1"/></a:lnRef><a:fillRef idx="3"><a:schemeClr val="accent1"/></a:fillRef><a:effectRef idx="2"><a:schemeClr val="accent1"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style><p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/>{paragraph_xml}</p:txBody></p:sp>"#
    ))
}

const FREEFORM_FILL_MODES: [&str; 6] = [
    "none",
    "norm",
    "lighten",
    "lightenLess",
    "darken",
    "darkenLess",
];

/// `name="value"` pairs for the present attributes, escaped, each led by a space.
fn freeform_attrs(pairs: &[(&str, Option<&str>)]) -> String {
    let mut out = String::new();
    for (name, value) in pairs {
        if let Some(value) = value {
            out.push_str(&format!(r#" {name}="{}""#, xml_attr(value)));
        }
    }
    out
}

fn freeform_pos_xml(x: &str, y: &str) -> String {
    format!(r#"<a:pos x="{}" y="{}"/>"#, xml_attr(x), xml_attr(y))
}

fn freeform_list_xml(local: &str, body: &str) -> String {
    if body.is_empty() {
        format!("<a:{local}/>")
    } else {
        format!("<a:{local}>{body}</a:{local}>")
    }
}

fn freeform_flag(value: &Option<bool>) -> Option<&'static str> {
    value.map(|flag| if flag { "1" } else { "0" })
}

/// The `a:custGeom` of a built freeform: one `a:path` holding the segment
/// operations, plus the guides, adjust handles and connection sites.
fn freeform_custom_geometry_xml(
    path_w: i64,
    path_h: i64,
    operations: &[FreeformPathOperation],
) -> Result<String, WolfPptError> {
    let path_xml = freeform_path_xml(operations)?;
    let mut adjust_values = String::new();
    let mut guides = String::new();
    let mut handles = String::new();
    let mut sites = String::new();
    let mut path_attrs: Option<(&Option<String>, &Option<bool>, &Option<bool>)> = None;
    for operation in operations {
        match operation {
            FreeformPathOperation::PathAttributes {
                fill,
                stroke,
                extrusion_ok,
            } => {
                if path_attrs.is_some() {
                    return Err(WolfPptError::InvalidInput(
                        "freeform path attributes may be set only once".to_string(),
                    ));
                }
                if let Some(mode) = fill {
                    if !FREEFORM_FILL_MODES.contains(&mode.as_str()) {
                        return Err(WolfPptError::InvalidInput(format!(
                            "freeform path fill must be one of {FREEFORM_FILL_MODES:?}, got {mode:?}"
                        )));
                    }
                }
                path_attrs = Some((fill, stroke, extrusion_ok));
            }
            FreeformPathOperation::AdjustValue { name, fmla } => {
                adjust_values.push_str(&format!(
                    r#"<a:gd name="{}" fmla="{}"/>"#,
                    xml_attr(name),
                    xml_attr(fmla)
                ));
            }
            FreeformPathOperation::Guide { name, fmla } => {
                guides.push_str(&format!(
                    r#"<a:gd name="{}" fmla="{}"/>"#,
                    xml_attr(name),
                    xml_attr(fmla)
                ));
            }
            FreeformPathOperation::AdjustHandleXy {
                x,
                y,
                gd_ref_x,
                min_x,
                max_x,
                gd_ref_y,
                min_y,
                max_y,
            } => {
                let attrs = freeform_attrs(&[
                    ("gdRefX", gd_ref_x.as_deref()),
                    ("minX", min_x.as_deref()),
                    ("maxX", max_x.as_deref()),
                    ("gdRefY", gd_ref_y.as_deref()),
                    ("minY", min_y.as_deref()),
                    ("maxY", max_y.as_deref()),
                ]);
                handles.push_str(&format!(
                    "<a:ahXY{attrs}>{}</a:ahXY>",
                    freeform_pos_xml(x, y)
                ));
            }
            FreeformPathOperation::AdjustHandlePolar {
                x,
                y,
                gd_ref_r,
                min_r,
                max_r,
                gd_ref_ang,
                min_ang,
                max_ang,
            } => {
                let attrs = freeform_attrs(&[
                    ("gdRefR", gd_ref_r.as_deref()),
                    ("minR", min_r.as_deref()),
                    ("maxR", max_r.as_deref()),
                    ("gdRefAng", gd_ref_ang.as_deref()),
                    ("minAng", min_ang.as_deref()),
                    ("maxAng", max_ang.as_deref()),
                ]);
                handles.push_str(&format!(
                    "<a:ahPolar{attrs}>{}</a:ahPolar>",
                    freeform_pos_xml(x, y)
                ));
            }
            FreeformPathOperation::ConnectionSite { ang, x, y } => {
                sites.push_str(&format!(
                    r#"<a:cxn ang="{}">{}</a:cxn>"#,
                    xml_attr(ang),
                    freeform_pos_xml(x, y)
                ));
            }
            _ => {}
        }
    }
    let path_attr_xml = match path_attrs {
        Some((fill, stroke, extrusion_ok)) => freeform_attrs(&[
            ("fill", fill.as_deref()),
            ("stroke", freeform_flag(stroke)),
            ("extrusionOk", freeform_flag(extrusion_ok)),
        ]),
        None => String::new(),
    };
    Ok(format!(
        r#"<a:custGeom>{}{}{}{}<a:rect l="l" t="t" r="r" b="b"/><a:pathLst><a:path w="{path_w}" h="{path_h}"{path_attr_xml}>{path_xml}</a:path></a:pathLst></a:custGeom>"#,
        freeform_list_xml("avLst", &adjust_values),
        freeform_list_xml("gdLst", &guides),
        freeform_list_xml("ahLst", &handles),
        freeform_list_xml("cxnLst", &sites),
    ))
}

fn freeform_path_xml(operations: &[FreeformPathOperation]) -> Result<String, WolfPptError> {
    let mut path = String::new();
    for operation in operations {
        match operation {
            FreeformPathOperation::MoveTo { x, y } => {
                path.push_str(&format!(r#"<a:moveTo><a:pt x="{x}" y="{y}"/></a:moveTo>"#));
            }
            FreeformPathOperation::LineTo { x, y } => {
                path.push_str(&format!(r#"<a:lnTo><a:pt x="{x}" y="{y}"/></a:lnTo>"#));
            }
            FreeformPathOperation::ArcTo {
                wr,
                hr,
                st_ang,
                sw_ang,
            } => {
                path.push_str(&format!(
                    r#"<a:arcTo wR="{wr}" hR="{hr}" stAng="{st_ang}" swAng="{sw_ang}"/>"#
                ));
            }
            FreeformPathOperation::QuadBezierTo { x1, y1, x, y } => {
                path.push_str(&format!(
                    r#"<a:quadBezTo><a:pt x="{x1}" y="{y1}"/><a:pt x="{x}" y="{y}"/></a:quadBezTo>"#
                ));
            }
            FreeformPathOperation::CubicBezierTo {
                x1,
                y1,
                x2,
                y2,
                x,
                y,
            } => {
                path.push_str(&format!(
                    r#"<a:cubicBezTo><a:pt x="{x1}" y="{y1}"/><a:pt x="{x2}" y="{y2}"/><a:pt x="{x}" y="{y}"/></a:cubicBezTo>"#
                ));
            }
            FreeformPathOperation::Close => path.push_str("<a:close/>"),
            _ => {}
        }
    }
    if path.is_empty() {
        return Err(WolfPptError::InvalidInput(
            "freeform shape requires at least one path operation".to_string(),
        ));
    }
    Ok(path)
}

fn c_nv_pr_names(xml: &str) -> Vec<String> {
    let mut names = Vec::new();
    let mut offset = 0;
    while let Some(relative_start) = xml[offset..].find("<p:cNvPr") {
        let start = offset + relative_start;
        let Some(relative_end) = xml[start..].find('>') else {
            break;
        };
        let tag = &xml[start..start + relative_end];
        if let Some(name) = extract_string_attribute(tag, "name") {
            names.push(name);
        }
        offset = start + relative_end + 1;
    }
    names
}

// Match table insertion's flat unsigned EMU frame instead of adding a
// serializer-only geometry wrapper or converting to the signed group frame.
#[allow(clippy::too_many_arguments)]
fn table_shape_xml(
    shape_id: u64,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    cell_texts: &[(usize, usize, String)],
) -> Result<String, WolfPptError> {
    // Match python-pptx CT_Table.new_tbl: every column and row takes the floor
    // share of the frame and the last one absorbs the division remainder.
    let col_width = cx_emu / cols as u64;
    let row_height = cy_emu / rows as u64;
    let last_col_width = cx_emu - col_width * (cols as u64 - 1);
    let last_row_height = cy_emu - row_height * (rows as u64 - 1);
    let grid_cols = (0..cols)
        .map(|col_index| {
            let width = if col_index + 1 == cols {
                last_col_width
            } else {
                col_width
            };
            format!(r#"<a:gridCol w="{width}"/>"#)
        })
        .collect::<String>();
    let mut table_rows = String::new();
    for row_index in 0..rows {
        let mut cells = String::new();
        for col_index in 0..cols {
            let paragraph_xml = match cell_texts
                .iter()
                .find(|(row, col, _text)| *row == row_index && *col == col_index)
            {
                Some((_row, _col, text)) => replacement_paragraphs_xml(text)?,
                None => r#"<a:p><a:r><a:t></a:t></a:r></a:p>"#.to_string(),
            };
            cells.push_str(&format!(
                r#"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{paragraph_xml}</a:txBody><a:tcPr/></a:tc>"#
            ));
        }
        let height = if row_index + 1 == rows {
            last_row_height
        } else {
            row_height
        };
        table_rows.push_str(&format!(r#"<a:tr h="{height}">{cells}</a:tr>"#));
    }
    Ok(format!(
        r#"<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Table {shape_id}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId></a:tblPr><a:tblGrid>{grid_cols}</a:tblGrid>{table_rows}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"#
    ))
}

fn max_cnvpr_id(xml: &str) -> u64 {
    let mut reader = quick_xml::NsReader::from_str(xml);
    let mut max_id = 0;
    while let Ok((resolved, event)) = reader.read_resolved_event() {
        let presentation_ns = matches!(
            resolved,
            quick_xml::name::ResolveResult::Bound(ns)
                if ns.0.as_bytes() == PRESENTATION_MAIN_NS || ns.0.as_bytes() == STRICT_PRESENTATION_MAIN_NS
        );
        match event {
            Event::Start(event) | Event::Empty(event)
                if presentation_ns && event.local_name().as_ref().as_bytes() == b"cNvPr" =>
            {
                for attribute in event.attributes().flatten() {
                    if attribute.key.as_ref().as_bytes() == b"id" {
                        if let Ok(value) = attribute.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                            if let Ok(id) = value.parse::<u64>() {
                                max_id = max_id.max(id);
                            }
                        }
                    }
                }
            }
            Event::Eof => break,
            _ => {}
        }
    }
    max_id
}

fn extract_string_attribute(tag: &str, name: &str) -> Option<String> {
    let needle = format!(r#"{name}=""#);
    let start = tag.find(&needle)? + needle.len();
    let end = tag[start..].find('"')?;
    Some(tag[start..start + end].to_string())
}

fn blank_slide_xml(placeholder_shapes: &str) -> String {
    format!(
        r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      {placeholder_shapes}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"#
    )
}

fn slide_layout_rels_xml(layout_target: &str) -> String {
    format!(
        r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="{layout_target}"/></Relationships>
"#
    )
}

#[cfg(test)]
mod textbox_namespace_tests {
    use super::*;

    #[test]
    fn authored_textbox_allocates_pml_ids_and_preserves_owner_bytes() {
        for pml in [PRESENTATION_MAIN_NS, STRICT_PRESENTATION_MAIN_NS] {
            let pml = std::str::from_utf8(pml).unwrap();
            for prefix in ["p:", "alias:", ""] {
                let declarations = if prefix.is_empty() {
                    format!(r#"xmlns="{pml}""#)
                } else {
                    format!(r#"xmlns:{}="{pml}""#, prefix.trim_end_matches(':'))
                };
                let highest_owner = match prefix {
                    "p:" => format!(r#"<p:cNvPr xmlns:p="{pml}" id='9200' f:id="99000"/>"#),
                    "alias:" => r#"<q:cNvPr id="92&#48;0" f:id="99000"/>"#.to_string(),
                    _ => r#"<cNvPr id='9200' f:id="99000"/>"#.to_string(),
                };
                let xml = format!(
                    r#"<{prefix}sld {declarations} xmlns:f="urn:foreign" xmlns:q="{pml}">
<{prefix}cSld><q:spTree xmlns:p="urn:rebound" xmlns:a="urn:rebound">
<q:nvGrpSpPr><q:cNvPr id='1' name="tree"/></q:nvGrpSpPr><q:grpSpPr/>
<q:grpSp><q:nvGrpSpPr><q:cNvPr id="90"/></q:nvGrpSpPr>
<sp xmlns="{pml}"><nvSpPr>{highest_owner}</nvSpPr></sp>
</q:grpSp><p:cNvPr id="99999"/><f:cNvPr id="99998"/>
<q:extLst><q:ext uri="keep"><f:spTree><f:cNvPr id='99997'/></f:spTree></q:ext></q:extLst>
</q:spTree></{prefix}cSld>
<{prefix}extLst><{prefix}ext uri="decoy"><f:spTree/></{prefix}ext></{prefix}extLst>
</{prefix}sld>"#
                );
                let id = max_cnvpr_id(&xml) + 1;
                assert_eq!(id, 9201);
                let output = add_text_box_to_slide_xml(
                    &xml, id, -10, 20, 1000000, 1000000, Some("new & owner"),
                )
                .unwrap();
                let boundary = xml.find("<q:extLst>").unwrap();
                assert!(output.starts_with(&xml[..boundary]));
                assert!(output.ends_with(&xml[boundary..]));
                let inserted = &output[boundary..output.len() - (xml.len() - boundary)];
                let mut reader = quick_xml::NsReader::from_str(inserted);
                let dml = if pml == std::str::from_utf8(STRICT_PRESENTATION_MAIN_NS).unwrap() {
                    STRICT_DRAWINGML_MAIN_NS
                } else {
                    DRAWINGML_MAIN_NS
                };
                let mut ids = Vec::new();
                loop {
                    let (namespace, event) = reader.read_resolved_event().unwrap();
                    match event {
                        Event::Start(event) | Event::Empty(event) => {
                            let expected = if event.name().as_ref().starts_with("p:") {
                                pml.as_bytes()
                            } else {
                                dml
                            };
                            assert!(matches!(
                                namespace,
                                quick_xml::name::ResolveResult::Bound(ns) if ns.0.as_bytes() == expected
                            ));
                            if event.local_name().as_ref() == "cNvPr" {
                                ids.push(
                                    event.try_get_attribute("id").unwrap().unwrap()
                                        .normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().parse::<u64>().unwrap(),
                                );
                            }
                        }
                        Event::Eof => break,
                        _ => {}
                    }
                }
                assert_eq!(ids, [9201]);
                let second_id = max_cnvpr_id(&output) + 1;
                assert_eq!(second_id, 9202);
                let second = add_text_box_to_slide_xml(
                    &output, second_id, 0, 0, 1000000, 1000000, None,
                )
                .unwrap();
                assert_eq!(max_cnvpr_id(&second), 9202);
            }
        }
    }

    #[test]
    fn authored_textbox_rejects_missing_ambiguous_or_malformed_owner() {
        let pml = std::str::from_utf8(PRESENTATION_MAIN_NS).unwrap();
        for body in [
            "<p:cSld><f:spTree/></p:cSld>",
            "<p:cSld><p:spTree></p:spTree><p:spTree></p:spTree></p:cSld>",
            "<p:cSld><p:spTree></p:spTree></p:cSld><p:cSld/>",
            "<p:cSld><p:spTree></p:cSld>",
            "<p:cSld><p:spTree><unbound:sp/></p:spTree></p:cSld>",
            "<p:cSld><p:spTree><p:sp unbound:id='7'/></p:spTree></p:cSld>",
            "<p:cSld><p:spTree><p:sp id='1' id='2'/></p:spTree></p:cSld>",
        ] {
            let xml = format!(r#"<p:sld xmlns:p="{pml}" xmlns:f="urn:foreign">{body}</p:sld>"#);
            assert!(add_text_box_to_slide_xml(&xml, 2, 0, 0, 1, 1, None).is_err());
        }
        let xml = format!(r#"<p:sld xmlns:p="{pml}"><p:cSld><p:spTree></p:spTree>"#);
        assert!(add_text_box_to_slide_xml(&xml, 2, 0, 0, 1, 1, None).is_err());
    }
}

#[cfg(test)]
mod freeform_geometry_tests {
    use super::*;

    fn text(value: &str) -> String {
        value.to_string()
    }

    fn some(value: &str) -> Option<String> {
        Some(value.to_string())
    }

    #[test]
    fn freeform_geometry_writes_curves_attributes_guides_handles_and_sites() {
        use FreeformPathOperation as Op;
        let operations = [
            Op::MoveTo { x: 0, y: 0 },
            Op::ArcTo {
                wr: 5,
                hr: 6,
                st_ang: 0,
                sw_ang: 5400000,
            },
            Op::QuadBezierTo {
                x1: 1,
                y1: 2,
                x: 3,
                y: 4,
            },
            Op::CubicBezierTo {
                x1: 1,
                y1: 2,
                x2: 3,
                y2: 4,
                x: 5,
                y: 6,
            },
            Op::Close,
            Op::PathAttributes {
                fill: some("darken"),
                stroke: Some(false),
                extrusion_ok: None,
            },
            Op::Guide {
                name: text("g0"),
                fmla: text("*/ w adj 2"),
            },
            Op::AdjustValue {
                name: text("adj"),
                fmla: text("val 5"),
            },
            Op::AdjustHandleXy {
                x: text("g0"),
                y: text("0"),
                gd_ref_x: some("adj"),
                min_x: None,
                max_x: some("9"),
                gd_ref_y: None,
                min_y: None,
                max_y: None,
            },
            Op::AdjustHandlePolar {
                x: text("1"),
                y: text("2"),
                gd_ref_r: None,
                min_r: None,
                max_r: None,
                gd_ref_ang: some("adj"),
                min_ang: None,
                max_ang: None,
            },
            Op::ConnectionSite {
                ang: text("cd4"),
                x: text("a\"<&"),
                y: text("b"),
            },
        ];
        let xml = freeform_custom_geometry_xml(10, 20, &operations).unwrap();
        assert_eq!(
            xml,
            concat!(
                r#"<a:custGeom><a:avLst><a:gd name="adj" fmla="val 5"/></a:avLst>"#,
                r#"<a:gdLst><a:gd name="g0" fmla="*/ w adj 2"/></a:gdLst>"#,
                r#"<a:ahLst><a:ahXY gdRefX="adj" maxX="9"><a:pos x="g0" y="0"/></a:ahXY>"#,
                r#"<a:ahPolar gdRefAng="adj"><a:pos x="1" y="2"/></a:ahPolar></a:ahLst>"#,
                r#"<a:cxnLst><a:cxn ang="cd4"><a:pos x="a&quot;&lt;&amp;" y="b"/></a:cxn>"#,
                r#"</a:cxnLst><a:rect l="l" t="t" r="r" b="b"/><a:pathLst>"#,
                r#"<a:path w="10" h="20" fill="darken" stroke="0">"#,
                r#"<a:moveTo><a:pt x="0" y="0"/></a:moveTo>"#,
                r#"<a:arcTo wR="5" hR="6" stAng="0" swAng="5400000"/>"#,
                r#"<a:quadBezTo><a:pt x="1" y="2"/><a:pt x="3" y="4"/></a:quadBezTo>"#,
                r#"<a:cubicBezTo><a:pt x="1" y="2"/><a:pt x="3" y="4"/>"#,
                r#"<a:pt x="5" y="6"/></a:cubicBezTo>"#,
                r#"<a:close/></a:path></a:pathLst></a:custGeom>"#,
            )
        );
    }

    #[test]
    fn freeform_geometry_refuses_bad_fill_repeated_attributes_and_no_segments() {
        use FreeformPathOperation as Op;
        let move_to = Op::MoveTo { x: 0, y: 0 };
        let glow = Op::PathAttributes {
            fill: some("glow"),
            stroke: None,
            extrusion_ok: None,
        };
        let plain = Op::PathAttributes {
            fill: None,
            stroke: None,
            extrusion_ok: None,
        };
        let guide = Op::Guide {
            name: text("g0"),
            fmla: text("val 1"),
        };
        for operations in [
            vec![move_to.clone(), glow],
            vec![move_to, plain.clone(), plain],
            vec![guide],
        ] {
            assert!(matches!(
                freeform_custom_geometry_xml(1, 1, &operations),
                Err(WolfPptError::InvalidInput(_))
            ));
        }
    }
}
