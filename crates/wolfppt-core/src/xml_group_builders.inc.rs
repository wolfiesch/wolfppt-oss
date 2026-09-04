fn group_existing_group_children_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: Option<(usize, Option<usize>)>,
    child_indices: &[usize],
    shape_id: u64,
) -> Result<String, WolfPptError> {
    if child_indices.is_empty() {
        return Err(WolfPptError::InvalidInput(
            "at least one group child is required".to_string(),
        ));
    }

    let (group_start, group_end) = match nested_group_child_index {
        Some((child_index, None)) => nested_group_child_bounds(xml, group_index, child_index)?,
        Some((child_index, Some(deeper_index))) => {
            let (nested_start, nested_end) =
                nested_group_child_bounds(xml, group_index, child_index)?;
            let nested_block = &xml[nested_start..nested_end];
            let Some((deeper_start, deeper_end, deeper_tag)) =
                direct_group_child_bounds(nested_block, deeper_index)
            else {
                return Err(WolfPptError::InvalidInput(format!(
                    "deeper nested group child index {deeper_index} was not found"
                )));
            };
            if deeper_tag != "p:grpSp" {
                return Err(WolfPptError::InvalidInput(format!(
                    "deeper nested group child index {deeper_index} is not a group shape"
                )));
            }
            (nested_start + deeper_start, nested_start + deeper_end)
        }
        None => top_level_group_bounds(xml, group_index)?,
    };
    let group_block = &xml[group_start..group_end];
    let mut selected = Vec::new();
    for child_index in child_indices {
        let Some((start, end, tag)) = direct_group_child_bounds(group_block, *child_index) else {
            return Err(WolfPptError::InvalidInput(format!(
                "group child index {child_index} was not found"
            )));
        };
        let block = &group_block[start..end];
        let bounds = shape_block_bounds(block).ok_or_else(|| {
            WolfPptError::InvalidInput("selected group child is missing transform".to_string())
        })?;
        selected.push((start, end, bounds, tag));
    }

    let left = selected
        .iter()
        .map(|(_, _, bounds, _)| bounds.0)
        .min()
        .unwrap_or(0);
    let top = selected
        .iter()
        .map(|(_, _, bounds, _)| bounds.1)
        .min()
        .unwrap_or(0);
    let right = selected
        .iter()
        .map(|(_, _, bounds, _)| bounds.0 + bounds.2)
        .max()
        .unwrap_or(left);
    let bottom = selected
        .iter()
        .map(|(_, _, bounds, _)| bounds.1 + bounds.3)
        .max()
        .unwrap_or(top);

    let mut child_xml = String::new();
    for (start, end, _, _) in &selected {
        child_xml.push_str(&group_block[*start..*end]);
    }

    let mut removal_ranges = selected
        .iter()
        .map(|(start, end, _, _)| (*start, *end))
        .collect::<Vec<_>>();
    removal_ranges.sort_unstable();
    removal_ranges.dedup();

    let mut rewritten_group = String::with_capacity(group_block.len() + child_xml.len());
    let mut cursor = 0;
    for (start, end) in removal_ranges {
        if start < cursor {
            continue;
        }
        rewritten_group.push_str(&group_block[cursor..start]);
        cursor = end;
    }
    rewritten_group.push_str(&group_block[cursor..]);

    let Some(relative_end) = rewritten_group.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let nested_group =
        group_shape_with_children_xml(shape_id, left, top, right - left, bottom - top, &child_xml);
    rewritten_group.insert_str(relative_end, &nested_group);

    Ok(format!(
        "{}{}{}",
        &xml[..group_start],
        rewritten_group,
        &xml[group_end..]
    ))
}

fn add_group_shape_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    shape_id: u64,
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
    let group_shape = group_shape_xml(shape_id);
    Ok(format!(
        "{}{}{}",
        &xml[..insert_at],
        group_shape,
        &xml[insert_at..]
    ))
}
