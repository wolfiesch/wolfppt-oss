pub fn inspect_package(path: impl AsRef<Path>) -> Result<PackageManifest, WolfPptError> {
    let path = path.as_ref();
    let file = File::open(path)?;
    let mut archive = ZipArchive::new(file)?;
    inspect_archive(path.to_path_buf(), &mut archive)
}

pub fn roundtrip_package(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
) -> Result<PackageManifest, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    std::fs::copy(input_path, output_path)?;
    let mut manifest = inspect_package(input_path)?;
    manifest.path = output_path.to_path_buf();
    Ok(manifest)
}

pub fn replace_slide_text(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    search: &str,
    replacement: &str,
) -> Result<TextReplacementSummary, WolfPptError> {
    replace_slide_text_inner(input_path, output_path, None, search, replacement)
}

pub fn replace_slide_text_at_index(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    search: &str,
    replacement: &str,
) -> Result<TextReplacementSummary, WolfPptError> {
    replace_slide_text_inner(
        input_path,
        output_path,
        Some(slide_index),
        search,
        replacement,
    )
}

pub fn replace_slide_text_run_at_index(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    run_index: usize,
    replacement: &str,
) -> Result<TextRunReplacementSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
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

        let should_rewrite = name == slide_part;
        writer.start_file(name, options)?;
        if should_rewrite {
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            let (rewritten, count) =
                replace_text_run_at_index_in_slide(&payload, run_index, replacement)?;
            replacements += count;
            std::io::copy(&mut Cursor::new(rewritten), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;
    Ok(TextRunReplacementSummary {
        path: output_path.to_path_buf(),
        slide_index,
        run_index,
        replacements,
        part_count,
        has_vba,
    })
}

pub fn set_slide_shape_text_at_index(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    shape_index: usize,
    replacement: &str,
) -> Result<ShapeTextSetSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
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

        let should_rewrite = name == slide_part;
        writer.start_file(name, options)?;
        if should_rewrite {
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            let (rewritten, count) =
                set_shape_text_at_index_in_slide(&payload, shape_index, replacement)?;
            replacements += count;
            std::io::copy(&mut Cursor::new(rewritten), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;
    Ok(ShapeTextSetSummary {
        path: output_path.to_path_buf(),
        slide_index,
        shape_index,
        replacements,
        part_count,
        has_vba,
    })
}

pub fn set_slide_shape_paragraph_text_at_index(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    shape_index: usize,
    paragraph_index: usize,
    replacement: &str,
) -> Result<ParagraphTextSetSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
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

        let should_rewrite = name == slide_part;
        writer.start_file(name, options)?;
        if should_rewrite {
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            let (rewritten, count) = set_shape_paragraph_text_at_index_in_slide(
                &payload,
                shape_index,
                paragraph_index,
                replacement,
            )?;
            replacements += count;
            std::io::copy(&mut Cursor::new(rewritten), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;
    Ok(ParagraphTextSetSummary {
        path: output_path.to_path_buf(),
        slide_index,
        shape_index,
        paragraph_index,
        replacements,
        part_count,
        has_vba,
    })
}

fn replace_slide_text_inner(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: Option<usize>,
    search: &str,
    replacement: &str,
) -> Result<TextReplacementSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let target_slide_part = match slide_index {
        Some(index) => Some(slide_part_at_index(&mut archive, index)?.ok_or_else(|| {
            WolfPptError::InvalidInput(format!("slide index {index} was not found"))
        })?),
        None => None,
    };
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

        let should_rewrite = if let Some(target) = target_slide_part.as_deref() {
            name == target
        } else {
            is_slide_part(&name)
        };
        writer.start_file(name, options)?;
        if should_rewrite && !search.is_empty() {
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            let (rewritten, count) = replace_text_nodes(&payload, search, replacement)?;
            replacements += count;
            std::io::copy(&mut Cursor::new(rewritten), &mut writer)?;
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;
    Ok(TextReplacementSummary {
        path: output_path.to_path_buf(),
        replacements,
        part_count,
        has_vba,
    })
}

pub fn replace_slide_image(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    relationship_id: &str,
    image_path: impl AsRef<Path>,
) -> Result<ImageReplacementSummary, WolfPptError> {
    replace_slide_image_inner(input_path, output_path, None, relationship_id, image_path)
}

pub fn replace_slide_image_at_index(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    relationship_id: &str,
    image_path: impl AsRef<Path>,
) -> Result<ImageReplacementSummary, WolfPptError> {
    replace_slide_image_inner(
        input_path,
        output_path,
        Some(slide_index),
        relationship_id,
        image_path,
    )
}

fn replace_slide_image_inner(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: Option<usize>,
    relationship_id: &str,
    image_path: impl AsRef<Path>,
) -> Result<ImageReplacementSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let image_path = image_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let replacement_image = std::fs::read(image_path)?;
    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let target_parts = match slide_index {
        Some(index) => {
            image_targets_for_relationship_at_index(&mut archive, index, relationship_id)?
        }
        None => image_targets_for_relationship(&mut archive, relationship_id)?,
    };
    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut replaced_parts = Vec::new();
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

        writer.start_file(name.clone(), options)?;
        if target_parts.contains(&name) {
            std::io::copy(&mut Cursor::new(replacement_image.as_slice()), &mut writer)?;
            replaced_parts.push(name);
        } else {
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;
    Ok(ImageReplacementSummary {
        path: output_path.to_path_buf(),
        relationship_id: relationship_id.to_string(),
        replacements: replaced_parts.len(),
        replaced_parts,
        part_count,
        has_vba,
    })
}

pub fn summarize_presentation(path: impl AsRef<Path>) -> Result<PresentationSummary, WolfPptError> {
    let path = path.as_ref();
    let file = File::open(path)?;
    let mut archive = ZipArchive::new(file)?;
    let (slide_parts, has_vba) = presentation_part_facts(&mut archive)?;
    let mut slides = Vec::new();

    for part in slide_parts {
        let mut xml = Vec::new();
        archive.by_name(&part)?.read_to_end(&mut xml)?;
        let relationships = read_relationships(&mut archive, &part)?;
        let notes = read_notes(&mut archive, &part, &relationships)?;
        let image_relationships = relationships_by_type(&relationships, &["/image"]);
        let chart_relationships = relationships_by_type(&relationships, &["/chart"]);
        let comment_relationships =
            relationships_by_type(&relationships, &["/comments", "/comment"]);
        let media_relationships =
            relationships_by_type(&relationships, &["/audio", "/media", "/video"]);
        let ole_relationships = relationships_by_type(&relationships, &["/oleObject", "/package"]);
        let shapes = extract_shapes(&xml);
        slides.push(SlideSummary {
            part,
            texts: extract_text_runs(&xml),
            tables: extract_tables(&xml),
            shapes,
            notes,
            relationships,
            image_relationships,
            chart_relationships,
            comment_relationships,
            media_relationships,
            ole_relationships,
            has_transition: has_element(&xml, b"transition"),
            has_timing: has_element(&xml, b"timing"),
        });
    }

    Ok(PresentationSummary {
        path: path.to_path_buf(),
        slide_count: slides.len(),
        slides,
        has_vba,
    })
}

pub fn summarize_slide_at_index(
    path: impl AsRef<Path>,
    slide_index: usize,
) -> Result<SlideSummary, WolfPptError> {
    let path = path.as_ref();
    let file = File::open(path)?;
    let mut archive = ZipArchive::new(file)?;
    let Some(part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let mut xml = Vec::new();
    archive.by_name(&part)?.read_to_end(&mut xml)?;
    let relationships = read_relationships(&mut archive, &part)?;
    let notes = read_notes(&mut archive, &part, &relationships)?;
    let image_relationships = relationships_by_type(&relationships, &["/image"]);
    let chart_relationships = relationships_by_type(&relationships, &["/chart"]);
    let comment_relationships = relationships_by_type(&relationships, &["/comments", "/comment"]);
    let media_relationships =
        relationships_by_type(&relationships, &["/audio", "/media", "/video"]);
    let ole_relationships = relationships_by_type(&relationships, &["/oleObject", "/package"]);
    Ok(SlideSummary {
        part,
        texts: extract_text_runs(&xml),
        tables: extract_tables(&xml),
        shapes: extract_shapes(&xml),
        notes,
        relationships,
        image_relationships,
        chart_relationships,
        comment_relationships,
        media_relationships,
        ole_relationships,
        has_transition: has_element(&xml, b"transition"),
        has_timing: has_element(&xml, b"timing"),
    })
}

impl EditOperation {
    fn slide_index(&self) -> Option<usize> {
        match self {
            EditOperation::ReorderSlides { .. } => None,
            EditOperation::DeleteShape { slide_index, .. }
            | EditOperation::DeleteGroupShapeChild { slide_index, .. }
            | EditOperation::SetShapeText { slide_index, .. }
            | EditOperation::SetGroupShapeChildText { slide_index, .. }
            | EditOperation::SetGroupShapeChildParagraphText { slide_index, .. }
            | EditOperation::SetGroupShapeChildRunText { slide_index, .. }
            | EditOperation::SetParagraphText { slide_index, .. }
            | EditOperation::ReplaceTextRun { slide_index, .. }
            | EditOperation::SetTextRunBold { slide_index, .. }
            | EditOperation::SetTextRunItalic { slide_index, .. }
            | EditOperation::SetTextRunUnderline { slide_index, .. }
            | EditOperation::SetTextRunFontSize { slide_index, .. }
            | EditOperation::SetTextRunFontName { slide_index, .. }
            | EditOperation::SetTextRunFormatting { slide_index, .. }
            | EditOperation::AppendParagraphText { slide_index, .. }
            | EditOperation::AppendTextRun { slide_index, .. }
            | EditOperation::InsertParagraphLineBreak { slide_index, .. }
            | EditOperation::SetParagraphProperties { slide_index, .. }
            | EditOperation::SetParagraphFontProperties { slide_index, .. }
            | EditOperation::SetShapeGeometry { slide_index, .. }
            | EditOperation::SetGroupShapeChildGeometry { slide_index, .. }
            | EditOperation::SetTextFrameProperties { slide_index, .. }
            | EditOperation::ReplaceTableCellText { slide_index, .. }
            | EditOperation::SetTableCellMerge { slide_index, .. }
            | EditOperation::SetTableStyleFlags { slide_index, .. }
            | EditOperation::InsertTableRow { slide_index, .. }
            | EditOperation::DeleteTableRow { slide_index, .. }
            | EditOperation::InsertTableColumn { slide_index, .. }
            | EditOperation::DeleteTableColumn { slide_index, .. } => Some(*slide_index),
        }
    }

    fn apply_to_slide(&self, payload: &[u8]) -> Result<(Vec<u8>, usize), WolfPptError> {
        match self {
            EditOperation::ReorderSlides { .. }
            | EditOperation::DeleteShape { .. }
            | EditOperation::DeleteGroupShapeChild { .. } => Err(WolfPptError::InvalidInput(
                "package-level edit reached the slide edit loop".to_string(),
            )),
            EditOperation::SetShapeText {
                shape_index,
                replacement,
                ..
            } => set_shape_text_at_index_in_slide(payload, *shape_index, replacement),
            EditOperation::SetGroupShapeChildText {
                group_index,
                child_index,
                replacement,
                ..
            } => set_group_shape_child_text_in_slide(
                payload,
                *group_index,
                *child_index,
                replacement,
            ),
            EditOperation::SetGroupShapeChildParagraphText {
                group_index,
                child_index,
                paragraph_index,
                replacement,
                ..
            } => set_group_shape_child_paragraph_text_in_slide(
                payload,
                *group_index,
                *child_index,
                *paragraph_index,
                replacement,
            ),
            EditOperation::SetGroupShapeChildRunText {
                group_index,
                child_index,
                paragraph_index,
                run_index,
                replacement,
                ..
            } => set_group_shape_child_run_text_in_slide(
                payload,
                *group_index,
                *child_index,
                *paragraph_index,
                *run_index,
                replacement,
            ),
            EditOperation::SetParagraphText {
                shape_index,
                paragraph_index,
                replacement,
                ..
            } => set_shape_paragraph_text_at_index_in_slide(
                payload,
                *shape_index,
                *paragraph_index,
                replacement,
            ),
            EditOperation::ReplaceTextRun {
                run_index,
                replacement,
                ..
            } => replace_text_run_at_index_in_slide(payload, *run_index, replacement),
            EditOperation::SetTextRunBold {
                run_index, bold, ..
            } => set_text_run_bold_at_index_in_slide(payload, *run_index, *bold),
            EditOperation::SetTextRunItalic {
                run_index, italic, ..
            } => set_text_run_italic_at_index_in_slide(payload, *run_index, *italic),
            EditOperation::SetTextRunUnderline {
                run_index,
                underline,
                ..
            } => set_text_run_underline_at_index_in_slide(payload, *run_index, *underline),
            EditOperation::SetTextRunFontSize {
                run_index, size, ..
            } => set_text_run_font_size_at_index_in_slide(payload, *run_index, *size),
            EditOperation::SetTextRunFontName {
                run_index, name, ..
            } => set_text_run_font_name_at_index_in_slide(payload, *run_index, name.as_deref()),
            EditOperation::SetTextRunFormatting {
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
            } => set_text_run_formatting_at_index_in_slide(
                payload,
                *run_index,
                &TextRunFormattingPatch {
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
            ),
            EditOperation::AppendParagraphText {
                shape_index, text, ..
            } => append_shape_paragraph_text_in_slide(payload, *shape_index, text),
            EditOperation::AppendTextRun {
                shape_index,
                paragraph_index,
                text,
                ..
            } => append_shape_text_run_in_slide(payload, *shape_index, *paragraph_index, text),
            EditOperation::InsertParagraphLineBreak {
                shape_index,
                paragraph_index,
                run_slot,
                ..
            } => insert_shape_paragraph_line_break_in_slide(
                payload,
                *shape_index,
                *paragraph_index,
                *run_slot,
            ),
            EditOperation::SetParagraphProperties {
                shape_index,
                paragraph_index,
                set_alignment,
                alignment,
                set_level,
                level,
                spacing,
                ..
            } => set_shape_paragraph_properties_in_slide(
                payload,
                *shape_index,
                *paragraph_index,
                if *set_alignment {
                    Some(alignment.as_deref())
                } else {
                    None
                },
                if *set_level { Some(*level) } else { None },
                spacing,
            ),
            EditOperation::SetParagraphFontProperties {
                shape_index,
                paragraph_index,
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
                set_fill_type,
                fill_type,
                set_language,
                language_id,
                ..
            } => set_shape_paragraph_font_properties_in_slide(
                payload,
                *shape_index,
                *paragraph_index,
                &ParagraphFontPatch {
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
                    fill_type: if *set_fill_type {
                        Some(fill_type.as_deref())
                    } else {
                        None
                    },
                    language_id: if *set_language {
                        Some(language_id.as_deref())
                    } else {
                        None
                    },
                },
            ),
            EditOperation::SetShapeGeometry {
                shape_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                ..
            } => set_shape_geometry_at_index_in_slide(
                payload,
                *shape_index,
                *x_emu,
                *y_emu,
                *cx_emu,
                *cy_emu,
            ),
            EditOperation::SetGroupShapeChildGeometry {
                group_index,
                child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                ..
            } => set_group_shape_child_geometry_in_slide(
                payload,
                *group_index,
                *child_index,
                *x_emu,
                *y_emu,
                *cx_emu,
                *cy_emu,
            ),
            EditOperation::SetTextFrameProperties {
                shape_index,
                properties,
                ..
            } => set_text_frame_properties_in_slide(payload, *shape_index, properties),
            EditOperation::ReplaceTableCellText {
                table_index,
                row_index,
                col_index,
                replacement,
                ..
            } => replace_table_cell_text_in_slide(
                payload,
                *table_index,
                *row_index,
                *col_index,
                replacement,
            ),
            EditOperation::SetTableCellMerge {
                table_index,
                row_min,
                row_max,
                col_min,
                col_max,
                kind,
                paragraphs,
                ..
            } => set_table_cell_merge_in_slide(
                payload,
                *table_index,
                *row_min,
                *row_max,
                *col_min,
                *col_max,
                kind,
                paragraphs,
            ),
            EditOperation::SetTableStyleFlags {
                table_index, flags, ..
            } => set_table_style_flags_in_slide(payload, *table_index, flags),
            EditOperation::InsertTableRow {
                table_index,
                row_index,
                ..
            } => insert_table_row_in_slide(payload, *table_index, *row_index),
            EditOperation::DeleteTableRow {
                table_index,
                row_index,
                ..
            } => delete_table_row_in_slide(payload, *table_index, *row_index),
            EditOperation::InsertTableColumn {
                table_index,
                col_index,
                ..
            } => insert_table_column_in_slide(payload, *table_index, *col_index),
            EditOperation::DeleteTableColumn {
                table_index,
                col_index,
                ..
            } => delete_table_column_in_slide(payload, *table_index, *col_index),
        }
    }
}
