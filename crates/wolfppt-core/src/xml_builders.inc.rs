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
    if xml.contains(&format!(r#"Extension="{extension}""#)) {
        return Ok(xml.to_string());
    }
    let Some(end) = xml.rfind("</Types>") else {
        return Err(WolfPptError::InvalidInput(
            "[Content_Types].xml is missing </Types>".to_string(),
        ));
    };
    let default = format!(
        r#"<Default Extension="{}" ContentType="{}"/>"#,
        xml_attr(extension),
        xml_attr(content_type)
    );
    Ok(format!("{}{}{}", &xml[..end], default, &xml[end..]))
}

fn ensure_content_type_override(
    xml: &str,
    part_name: &str,
    content_type: &str,
) -> Result<String, WolfPptError> {
    if xml.contains(&format!(r#"PartName="{part_name}""#)) {
        return Ok(xml.to_string());
    }
    let Some(end) = xml.rfind("</Types>") else {
        return Err(WolfPptError::InvalidInput(
            "[Content_Types].xml is missing </Types>".to_string(),
        ));
    };
    let override_xml = format!(
        r#"<Override PartName="{}" ContentType="{}"/>"#,
        xml_attr(part_name),
        xml_attr(content_type)
    );
    Ok(format!("{}{}{}", &xml[..end], override_xml, &xml[end..]))
}

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
    let table = table_shape_xml(shape_id, rows, cols, x_emu, y_emu, cx_emu, cy_emu, cell_texts)?;
    Ok(format!("{}{}{}", &xml[..end], table, &xml[end..]))
}

fn add_text_box_to_slide_xml(
    xml: &str,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
    Ok(format!("{}{}{}", &xml[..end], text_box, &xml[end..]))
}

fn add_text_box_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
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
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let text_box =
                    text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
                return Ok(format!("{}{}{}", &xml[..insert_at], text_box, &xml[insert_at..]));
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
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let Some(relative_end) = block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + relative_end;
    let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
    Ok(format!("{}{}{}", &xml[..insert_at], text_box, &xml[insert_at..]))
}

#[allow(clippy::too_many_arguments)]
fn add_text_box_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
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
    let Some(relative_end) = deeper_block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "deeper nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + deeper_start + relative_end;
    let text_box = text_box_shape_xml(shape_id, x_emu, y_emu, cx_emu, cy_emu, text)?;
    Ok(format!("{}{}{}", &xml[..insert_at], text_box, &xml[insert_at..]))
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
    let content_start =
        group_block.find("</p:grpSpPr>")? + "</p:grpSpPr>".len();
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

fn top_level_group_bounds(
    xml: &str,
    group_index: usize,
) -> Result<(usize, usize), WolfPptError> {
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
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    group_shape,
                    &xml[insert_at..]
                ));
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
    Ok(format!(
        "{}{}{}",
        &xml[..insert_at],
        group_shape,
        &xml[insert_at..]
    ))
}

#[allow(clippy::too_many_arguments)]
fn add_group_shape_with_text_box_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    group_shape_id: u64,
    text_box_id: u64,
    x_emu: u64,
    y_emu: u64,
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
                let group_shape = group_shape_with_child_xml(group_shape_id, &text_box);
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    group_shape,
                    &xml[insert_at..]
                ));
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
    x_emu: u64,
    y_emu: u64,
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
                let group_shape = group_shape_with_child_xml(group_shape_id, &auto_shape);
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    group_shape,
                    &xml[insert_at..]
                ));
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
                let group_shape = group_shape_with_child_xml(group_shape_id, &freeform);
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    group_shape,
                    &xml[insert_at..]
                ));
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
        shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations,
        text,
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
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let freeform = freeform_shape_xml(
                    shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations,
                    text,
                )?;
                return Ok(format!("{}{}{}", &xml[..insert_at], freeform, &xml[insert_at..]));
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
    let Some(relative_end) = block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + relative_end;
    let freeform = freeform_shape_xml(
        shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
    )?;
    Ok(format!("{}{}{}", &xml[..insert_at], freeform, &xml[insert_at..]))
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
    let Some(relative_end) = deeper_block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "deeper nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + deeper_start + relative_end;
    let freeform = freeform_shape_xml(
        shape_id, x_emu, y_emu, cx_emu, cy_emu, path_w, path_h, operations, text,
    )?;
    Ok(format!("{}{}{}", &xml[..insert_at], freeform, &xml[insert_at..]))
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
    x_emu: u64,
    y_emu: u64,
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

fn group_shape_with_child_xml(shape_id: u64, child_xml: &str) -> String {
    let group_number = shape_id.saturating_sub(1);
    format!(
        r#"<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{shape_id}" name="Group {group_number}"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>{child_xml}</p:grpSp>"#
    )
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
    let path_xml = freeform_path_xml(operations)?;
    let paragraph_xml = match text {
        Some(text) => replacement_paragraphs_xml(text)?,
        None => r#"<a:p><a:pPr algn="ctr"/></a:p>"#.to_string(),
    };
    Ok(format!(
        r#"<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Freeform {freeform_number}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="l" t="t" r="r" b="b"/><a:pathLst><a:path w="{path_w}" h="{path_h}">{path_xml}</a:path></a:pathLst></a:custGeom></p:spPr><p:style><a:lnRef idx="1"><a:schemeClr val="accent1"/></a:lnRef><a:fillRef idx="3"><a:schemeClr val="accent1"/></a:fillRef><a:effectRef idx="2"><a:schemeClr val="accent1"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style><p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/>{paragraph_xml}</p:txBody></p:sp>"#
    ))
}

fn freeform_path_xml(operations: &[FreeformPathOperation]) -> Result<String, WolfPptError> {
    if operations.is_empty() {
        return Err(WolfPptError::InvalidInput(
            "freeform shape requires at least one path operation".to_string(),
        ));
    }
    let mut path = String::new();
    for operation in operations {
        match operation {
            FreeformPathOperation::MoveTo { x, y } => {
                path.push_str(&format!(
                    r#"<a:moveTo><a:pt x="{x}" y="{y}"/></a:moveTo>"#
                ));
            }
            FreeformPathOperation::LineTo { x, y } => {
                path.push_str(&format!(
                    r#"<a:lnTo><a:pt x="{x}" y="{y}"/></a:lnTo>"#
                ));
            }
            FreeformPathOperation::Close => path.push_str("<a:close/>"),
        }
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
    let col_width = cx_emu / cols as u64;
    let row_height = cy_emu / rows as u64;
    let grid_cols = (0..cols)
        .map(|_| format!(r#"<a:gridCol w="{col_width}"/>"#))
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
        table_rows.push_str(&format!(r#"<a:tr h="{row_height}">{cells}</a:tr>"#));
    }
    Ok(format!(
        r#"<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Table {shape_id}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId></a:tblPr><a:tblGrid>{grid_cols}</a:tblGrid>{table_rows}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"#
    ))
}

fn max_cnvpr_id(xml: &str) -> u64 {
    let mut max_id = 0;
    let mut offset = 0;
    while let Some(relative_start) = xml[offset..].find("<p:cNvPr") {
        let start = offset + relative_start;
        let Some(relative_end) = xml[start..].find('>') else {
            break;
        };
        let tag = &xml[start..start + relative_end];
        if let Some(id) = extract_id_attribute(tag) {
            max_id = max_id.max(id);
        }
        offset = start + relative_end + 1;
    }
    max_id
}

fn extract_id_attribute(tag: &str) -> Option<u64> {
    let start = tag.find(r#"id=""#)? + r#"id=""#.len();
    let end = tag[start..].find('"')?;
    tag[start..start + end].parse().ok()
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
