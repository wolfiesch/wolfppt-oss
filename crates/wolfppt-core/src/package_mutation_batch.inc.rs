pub fn replace_table_cell_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    table_index: usize,
    row_index: usize,
    col_index: usize,
    replacement: &str,
) -> Result<TableCellReplacementSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let slide_part = slide_part_at_index(&mut archive, slide_index)?;
    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut replacements = 0;
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }

        let should_rewrite = Some(name.as_str()) == slide_part.as_deref();
        writer.start_file(name, options)?;
        if should_rewrite {
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            let (rewritten, count) = replace_table_cell_text_in_slide(
                &payload,
                table_index,
                row_index,
                col_index,
                replacement,
            )?;
            replacements += count;
            std::io::copy(&mut Cursor::new(rewritten), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;
    Ok(TableCellReplacementSummary {
        path: output_path.to_path_buf(),
        slide_index,
        table_index,
        row_index,
        col_index,
        replacements,
        part_count,
        has_vba,
    })
}

pub fn apply_edit_batch(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    edits: &[EditOperation],
) -> Result<EditBatchSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let slide_parts = slide_parts(&mut archive)?;
    let mut edits_by_slide: BTreeMap<String, Vec<EditOperation>> = BTreeMap::new();
    let mut slide_order = None;
    for edit in edits {
        if let EditOperation::ReorderSlides { slide_indices } = edit {
            if slide_order.replace(slide_indices.clone()).is_some() {
                return Err(WolfPptError::InvalidInput(
                    "edit batch contains more than one slide reorder".to_string(),
                ));
            }
            continue;
        }
        let slide_index = edit.slide_index().ok_or_else(|| {
            WolfPptError::InvalidInput("slide edit has no slide index".to_string())
        })?;
        let Some(slide_part) = slide_parts.get(slide_index) else {
            return Err(WolfPptError::InvalidInput(format!(
                "slide index {slide_index} was not found"
            )));
        };
        edits_by_slide
            .entry(slide_part.clone())
            .or_default()
            .push(edit.clone());
    }

    let mut rewritten_slides: BTreeMap<String, Vec<u8>> = BTreeMap::new();
    let mut relationships_to_remove: BTreeMap<String, std::collections::BTreeSet<String>> =
        BTreeMap::new();
    let mut replacements = 0;
    for (slide_part, slide_edits) in &edits_by_slide {
        let mut file = archive.by_name(slide_part)?;
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        drop(file);
        let (rewritten, count, orphan_relationship_ids) =
            apply_slide_edit_operations(&payload, slide_edits)?;
        replacements += count;
        rewritten_slides.insert(slide_part.clone(), rewritten);
        if !orphan_relationship_ids.is_empty() {
            relationships_to_remove
                .entry(relationship_part_name(slide_part))
                .or_default()
                .extend(orphan_relationship_ids);
        }
    }

    let rewritten_presentation = if let Some(slide_indices) = slide_order {
        let mut file = archive.by_name("ppt/presentation.xml")?;
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        drop(file);
        let (rewritten, count) = reorder_slide_ids(&payload, &slide_indices)?;
        replacements += count;
        Some(rewritten)
    } else {
        None
    };

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);

        if let Some(payload) = rewritten_slides.get(&name) {
            let options = SimpleFileOptions::default().compression_method(file.compression());
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(payload), &mut writer)?;
        } else if name == "ppt/presentation.xml" && rewritten_presentation.is_some() {
            let options = SimpleFileOptions::default().compression_method(file.compression());
            writer.start_file(name, options)?;
            std::io::copy(
                &mut Cursor::new(rewritten_presentation.as_ref().unwrap()),
                &mut writer,
            )?;
        } else if let Some(relationship_ids) = relationships_to_remove.get(&name) {
            let options = SimpleFileOptions::default().compression_method(file.compression());
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            let (rewritten, count) = remove_relationships_by_id(&payload, relationship_ids)?;
            replacements += count;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rewritten), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }
    writer.finish()?;

    Ok(EditBatchSummary {
        path: output_path.to_path_buf(),
        edits: edits.len(),
        replacements,
        part_count,
        has_vba,
    })
}

fn apply_slide_edit_operations(
    original_payload: &[u8],
    slide_edits: &[EditOperation],
) -> Result<(Vec<u8>, usize, std::collections::BTreeSet<String>), WolfPptError> {
    let mut regular_edits = Vec::new();
    let mut delete_indices = Vec::new();
    let mut group_child_deletes = Vec::new();
    for edit in slide_edits {
        match edit {
            EditOperation::DeleteShape { shape_index, .. } => delete_indices.push(*shape_index),
            EditOperation::DeleteGroupShapeChild {
                group_shape_id,
                child_shape_id,
                ..
            } => group_child_deletes.push((*group_shape_id, *child_shape_id)),
            EditOperation::ReorderSlides { .. } => {
                return Err(WolfPptError::InvalidInput(
                    "slide reorder reached the slide edit loop".to_string(),
                ));
            }
            _ => regular_edits.push(edit.clone()),
        }
    }

    let mut payload = original_payload.to_vec();
    let mut replacements = 0;
    let mut edit_index = 0;
    while edit_index < regular_edits.len() {
        if matches!(
            regular_edits[edit_index],
            EditOperation::SetTextRunFormatting { .. }
        ) {
            let mut formatting_edits = Vec::new();
            while let Some(EditOperation::SetTextRunFormatting {
                run_index,
                set_bold,
                bold,
                set_italic,
                italic,
                set_underline,
                underline,
                set_size,
                size,
                set_name,
                name,
                set_color,
                color,
                ..
            }) = regular_edits.get(edit_index)
            {
                formatting_edits.push((
                    *run_index,
                    TextRunFormattingPatch {
                        bold: if *set_bold { Some(*bold) } else { None },
                        italic: if *set_italic { Some(*italic) } else { None },
                        underline: if *set_underline {
                            Some(*underline)
                        } else {
                            None
                        },
                        size: if *set_size { Some(*size) } else { None },
                        name: if *set_name {
                            Some(name.as_deref())
                        } else {
                            None
                        },
                        color: if *set_color {
                            Some(color.as_deref())
                        } else {
                            None
                        },
                    },
                ));
                edit_index += 1;
            }
            let (rewritten, count) =
                set_text_run_formatting_batch_in_slide(&payload, &formatting_edits)?;
            payload = rewritten;
            replacements += count;
            continue;
        }
        if matches!(
            regular_edits[edit_index],
            EditOperation::ReplaceTableCellText { .. }
        ) {
            let mut table_edits = Vec::new();
            let mut seen_targets: BTreeMap<(usize, usize, usize), ()> = BTreeMap::new();
            while let Some(EditOperation::ReplaceTableCellText {
                table_index,
                row_index,
                col_index,
                replacement,
                ..
            }) = regular_edits.get(edit_index)
            {
                let target = (*table_index, *row_index, *col_index);
                if seen_targets.contains_key(&target) {
                    break;
                }
                seen_targets.insert(target, ());
                table_edits.push((*table_index, *row_index, *col_index, replacement.as_str()));
                edit_index += 1;
            }
            let (rewritten, count) =
                replace_table_cell_text_batch_in_slide(&payload, &table_edits)?;
            payload = rewritten;
            replacements += count;
            continue;
        }
        let (rewritten, count) = regular_edits[edit_index].apply_to_slide(&payload)?;
        payload = rewritten;
        replacements += count;
        edit_index += 1;
    }

    let mut seen_group_child_deletes = std::collections::BTreeSet::new();
    for edit in &group_child_deletes {
        if !seen_group_child_deletes.insert((edit.0, edit.1)) {
            return Err(WolfPptError::InvalidInput(format!(
                "group child shape id {} in group {} is deleted more than once",
                edit.1, edit.0
            )));
        }
    }
    let mut orphan_relationship_ids = std::collections::BTreeSet::new();
    for (group_shape_id, child_shape_id) in group_child_deletes {
        let (rewritten, count, orphaned) =
            delete_group_shape_child_in_slide(&payload, group_shape_id, child_shape_id)?;
        payload = rewritten;
        replacements += count;
        orphan_relationship_ids.extend(orphaned);
    }

    let mut seen_delete_indices = std::collections::BTreeSet::new();
    for shape_index in &delete_indices {
        if !seen_delete_indices.insert(*shape_index) {
            return Err(WolfPptError::InvalidInput(format!(
                "shape index {shape_index} is deleted more than once"
            )));
        }
    }
    delete_indices.sort_unstable_by(|left, right| right.cmp(left));
    for shape_index in delete_indices {
        let (rewritten, count, orphaned) = delete_shape_at_index_in_slide(&payload, shape_index)?;
        payload = rewritten;
        replacements += count;
        orphan_relationship_ids.extend(orphaned);
    }
    Ok((payload, replacements, orphan_relationship_ids))
}
