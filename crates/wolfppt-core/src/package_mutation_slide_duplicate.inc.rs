pub fn duplicate_slide(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    source_slide_part: &str,
) -> Result<SlideAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let mut slide_parts = slide_parts(&mut archive)?;
    if !slide_parts.iter().any(|part| part == source_slide_part) {
        return Err(WolfPptError::InvalidInput(format!(
            "source slide part {source_slide_part} was not found in the presentation"
        )));
    }

    let source_slide_xml = {
        let mut file = archive.by_name(source_slide_part)?;
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        payload
    };
    let source_rels_part = relationship_part_name(source_slide_part);
    let source_slide_rels = read_archive_text(&mut archive, &source_rels_part)?;
    let relationships = source_slide_rels
        .as_deref()
        .map(|xml| parse_relationships(xml.as_bytes()))
        .unwrap_or_default();
    let layout_relationship = relationships
        .iter()
        .find(|relationship| relationship.relationship_type.ends_with("/slideLayout"))
        .ok_or_else(|| {
            WolfPptError::InvalidInput(format!(
                "source slide part {source_slide_part} has no slide layout relationship"
            ))
        })?;
    // Slide duplication relationship copy policies:
    // - slideLayout (.../slideLayout): SHARED. Layout is a package-level presentation resource.
    // - image (.../image): SHARED. Media assets under ppt/media/ are immutable; reused by reference.
    // - audio (.../audio): SHARED. Audio media targets under ppt/media/ are immutable assets;
    //   reused by reference with unchanged rId and target; covered by [Content_Types].xml Defaults.
    // - video (.../video): SHARED. Video media targets under ppt/media/ are immutable assets;
    //   reused by reference with unchanged rId and target; partnered media and poster image rels
    //   are similarly shared; covered by [Content_Types].xml Defaults.
    // - media (.../media): SHARED. Microsoft 2007 generic media reference partnered with video/audio;
    //   reused by reference with unchanged rId and target.
    // - chart (.../chart): COPIED (OWNED). Cloned to a new ppt/charts/chartN.xml with child parts.
    // - notesSlide (.../notesSlide): COPIED (OWNED). Cloned to ppt/notesSlides/notesSlideN.xml with
    //   back-reference rewritten.
    // - oleObject / package (.../oleObject, .../package): COPIED (OWNED). Cloned to a new embedding.
    // - comments (.../comments, .../comment): COPIED (OWNED). Cloned to ppt/comments/commentN.xml
    //   with Content-Type Override and slide rel target remapped.
    // - External targets (TargetMode="External"): PASSED THROUGH VERBATIM. External targets reference
    //   resources outside the package; copied without mutation or new parts.
    // - Unknown internal relationship types: REJECTED. Explicit error raised.
    for relationship in &relationships {
        let is_external = relationship
            .target_mode
            .as_deref()
            .map(|mode| mode.eq_ignore_ascii_case("External"))
            .unwrap_or(false);
        if is_external {
            continue;
        }
        if !relationship.relationship_type.ends_with("/slideLayout")
            && !relationship.relationship_type.ends_with("/image")
            && !relationship.relationship_type.ends_with("/chart")
            && !relationship.relationship_type.ends_with("/notesSlide")
            && !relationship.relationship_type.ends_with("/oleObject")
            && !relationship.relationship_type.ends_with("/package")
            && !relationship.relationship_type.ends_with("/comments")
            && !relationship.relationship_type.ends_with("/comment")
            && !relationship.relationship_type.ends_with("/audio")
            && !relationship.relationship_type.ends_with("/video")
            && !relationship.relationship_type.ends_with("/media")
        {
            return Err(WolfPptError::InvalidInput(format!(
                "cannot duplicate slide relationship type {} without an explicit copy policy",
                relationship.relationship_type
            )));
        }
    }

    let mut existing_names = std::collections::HashSet::new();
    for index in 0..archive.len() {
        existing_names.insert(archive.by_index(index)?.name().to_string());
    }

    let next_slide_number = slide_parts
        .iter()
        .filter_map(|part| slide_number(part))
        .max()
        .unwrap_or(0)
        + 1;
    let new_slide_part = format!("ppt/slides/slide{next_slide_number}.xml");
    let new_slide_rels_part = relationship_part_name(&new_slide_part);
    slide_parts.push(new_slide_part.clone());
    existing_names.insert(new_slide_part.clone());
    existing_names.insert(new_slide_rels_part.clone());

    let mut presentation_xml = Vec::new();
    archive
        .by_name("ppt/presentation.xml")?
        .read_to_end(&mut presentation_xml)?;
    let mut presentation_rels = Vec::new();
    archive
        .by_name("ppt/_rels/presentation.xml.rels")?
        .read_to_end(&mut presentation_rels)?;
    let mut content_types_bytes = Vec::new();
    archive
        .by_name("[Content_Types].xml")?
        .read_to_end(&mut content_types_bytes)?;
    let content_types_str = String::from_utf8(content_types_bytes)
        .map_err(|err| WolfPptError::XmlText(err.to_string()))?;
    let mut new_content_types = content_types_str.clone();

    let relationship_id = next_relationship_id(&presentation_rels);
    let slide_id = next_slide_id(&presentation_xml);
    let new_presentation_xml = append_slide_id(&presentation_xml, slide_id, &relationship_id)?;
    let new_presentation_rels = append_relationship(
        &presentation_rels,
        &relationship_id,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
        &format!("slides/slide{next_slide_number}.xml"),
    )?;
    new_content_types = ensure_content_type_override(
        &new_content_types,
        &format!("/ppt/slides/slide{next_slide_number}.xml"),
        "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
    )?;

    let mut new_parts: Vec<(String, Vec<u8>)> = Vec::new();
    let mut slide_rel_replacements = BTreeMap::new();

    for relationship in &relationships {
        if relationship
            .target_mode
            .as_deref()
            .map(|mode| mode.eq_ignore_ascii_case("External"))
            .unwrap_or(false)
        {
            continue;
        }
        if relationship.relationship_type.ends_with("/chart") {
            let source_chart_part = resolve_target(source_slide_part, &relationship.target);
            let chart_xml =
                read_archive_bytes(&mut archive, &source_chart_part)?.ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "chart part {source_chart_part} was not found"
                    ))
                })?;
            let new_chart_part = next_free_numbered_part(&mut existing_names, &source_chart_part);

            let source_chart_rels_part = relationship_part_name(&source_chart_part);
            if let Some(source_chart_rels) =
                read_archive_bytes(&mut archive, &source_chart_rels_part)?
            {
                let chart_rels = parse_relationships(&source_chart_rels);
                let mut chart_rel_replacements = BTreeMap::new();
                for chart_rel in &chart_rels {
                    let source_sub_part = resolve_target(&source_chart_part, &chart_rel.target);
                    if let Some(sub_part_bytes) =
                        read_archive_bytes(&mut archive, &source_sub_part)?
                    {
                        let new_sub_part =
                            next_free_numbered_part(&mut existing_names, &source_sub_part);
                        new_parts.push((new_sub_part.clone(), sub_part_bytes));
                        let rel_target = make_relative_target(&new_chart_part, &new_sub_part);
                        chart_rel_replacements.insert(chart_rel.id.clone(), rel_target);

                        if let Some(override_ct) =
                            find_content_type_override(&content_types_str, &source_sub_part)
                        {
                            new_content_types = ensure_content_type_override(
                                &new_content_types,
                                &format!("/{new_sub_part}"),
                                &override_ct,
                            )?;
                        }
                        if new_sub_part.ends_with(".xlsx") {
                            new_content_types = ensure_default_content_type(
                                &new_content_types,
                                "xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )?;
                        }
                        // Standard Office chart relationship types are case-sensitive (.../chartColorStyle
                        // and .../chartStyle); retain lowercase variants for backward compatibility.
                        if chart_rel.relationship_type.ends_with("/chartColorStyle")
                            || chart_rel.relationship_type.ends_with("/chartcolorstyle")
                            || chart_rel.relationship_type.ends_with("/chartcolors")
                        {
                            new_content_types = ensure_content_type_override(
                                &new_content_types,
                                &format!("/{new_sub_part}"),
                                "application/vnd.ms-office.chartcolorstyle+xml",
                            )?;
                        }
                        if chart_rel.relationship_type.ends_with("/chartStyle")
                            || chart_rel.relationship_type.ends_with("/chartstyle")
                        {
                            new_content_types = ensure_content_type_override(
                                &new_content_types,
                                &format!("/{new_sub_part}"),
                                "application/vnd.ms-office.chartstyle+xml",
                            )?;
                        }
                    }
                }
                let new_chart_rels_bytes =
                    rewrite_relationship_targets(&source_chart_rels, &chart_rel_replacements)?;
                let new_chart_rels_part = relationship_part_name(&new_chart_part);
                new_parts.push((new_chart_rels_part, new_chart_rels_bytes));
            }

            new_parts.push((new_chart_part.clone(), chart_xml));
            let slide_rel_target = make_relative_target(&new_slide_part, &new_chart_part);
            slide_rel_replacements.insert(relationship.id.clone(), slide_rel_target);

            let chart_ct = find_content_type_override(&content_types_str, &source_chart_part)
                .unwrap_or_else(|| {
                    "application/vnd.openxmlformats-officedocument.drawingml.chart+xml".to_string()
                });
            new_content_types = ensure_content_type_override(
                &new_content_types,
                &format!("/{new_chart_part}"),
                &chart_ct,
            )?;
        } else if relationship.relationship_type.ends_with("/notesSlide") {
            let source_notes_part = resolve_target(source_slide_part, &relationship.target);
            let notes_xml =
                read_archive_bytes(&mut archive, &source_notes_part)?.ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "notes slide part {source_notes_part} was not found"
                    ))
                })?;
            let new_notes_part = next_free_numbered_part(&mut existing_names, &source_notes_part);

            let source_notes_rels_part = relationship_part_name(&source_notes_part);
            if let Some(source_notes_rels) =
                read_archive_bytes(&mut archive, &source_notes_rels_part)?
            {
                let notes_rels = parse_relationships(&source_notes_rels);
                let mut notes_rel_replacements = BTreeMap::new();
                for notes_rel in &notes_rels {
                    if notes_rel.relationship_type.ends_with("/slide") {
                        let back_ref = make_relative_target(&new_notes_part, &new_slide_part);
                        notes_rel_replacements.insert(notes_rel.id.clone(), back_ref);
                    }
                }
                let new_notes_rels_bytes =
                    rewrite_relationship_targets(&source_notes_rels, &notes_rel_replacements)?;
                let new_notes_rels_part = relationship_part_name(&new_notes_part);
                new_parts.push((new_notes_rels_part, new_notes_rels_bytes));
            }

            new_parts.push((new_notes_part.clone(), notes_xml));
            let slide_rel_target = make_relative_target(&new_slide_part, &new_notes_part);
            slide_rel_replacements.insert(relationship.id.clone(), slide_rel_target);

            let notes_ct = find_content_type_override(&content_types_str, &source_notes_part)
                .unwrap_or_else(|| {
                    "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
                        .to_string()
                });
            new_content_types = ensure_content_type_override(
                &new_content_types,
                &format!("/{new_notes_part}"),
                &notes_ct,
            )?;
        } else if relationship.relationship_type.ends_with("/oleObject")
            || relationship.relationship_type.ends_with("/package")
        {
            let source_ole_part = resolve_target(source_slide_part, &relationship.target);
            let ole_bytes =
                read_archive_bytes(&mut archive, &source_ole_part)?.ok_or_else(|| {
                    WolfPptError::InvalidInput(format!("OLE part {source_ole_part} was not found"))
                })?;
            let new_ole_part = next_free_numbered_part(&mut existing_names, &source_ole_part);

            new_parts.push((new_ole_part.clone(), ole_bytes));
            let slide_rel_target = make_relative_target(&new_slide_part, &new_ole_part);
            slide_rel_replacements.insert(relationship.id.clone(), slide_rel_target);

            if let Some(override_ct) =
                find_content_type_override(&content_types_str, &source_ole_part)
            {
                new_content_types = ensure_content_type_override(
                    &new_content_types,
                    &format!("/{new_ole_part}"),
                    &override_ct,
                )?;
            }
            if new_ole_part.ends_with(".bin") {
                new_content_types = ensure_default_content_type(
                    &new_content_types,
                    "bin",
                    "application/vnd.openxmlformats-officedocument.oleObject",
                )?;
            }
        } else if relationship.relationship_type.ends_with("/comments")
            || relationship.relationship_type.ends_with("/comment")
        {
            let source_comment_part = resolve_target(source_slide_part, &relationship.target);
            let comment_xml =
                read_archive_bytes(&mut archive, &source_comment_part)?.ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "comment part {source_comment_part} was not found"
                    ))
                })?;
            let new_comment_part =
                next_free_numbered_part(&mut existing_names, &source_comment_part);

            new_parts.push((new_comment_part.clone(), comment_xml));
            let slide_rel_target = make_relative_target(&new_slide_part, &new_comment_part);
            slide_rel_replacements.insert(relationship.id.clone(), slide_rel_target);

            let comment_ct = find_content_type_override(&content_types_str, &source_comment_part)
                .unwrap_or_else(|| {
                    "application/vnd.openxmlformats-officedocument.presentationml.comments+xml"
                        .to_string()
                });
            new_content_types = ensure_content_type_override(
                &new_content_types,
                &format!("/{new_comment_part}"),
                &comment_ct,
            )?;
        }
    }

    new_parts.push((new_slide_part.clone(), source_slide_xml));
    if let Some(source_slide_rels) = source_slide_rels {
        let new_slide_rels_bytes =
            rewrite_relationship_targets(source_slide_rels.as_bytes(), &slide_rel_replacements)?;
        new_parts.push((new_slide_rels_part.clone(), new_slide_rels_bytes));
    }

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut part_count = 0;
    let mut has_vba = false;
    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name().to_string();
        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
            continue;
        }
        match name.as_str() {
            "ppt/presentation.xml" => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(&new_presentation_xml), &mut writer)?
            }
            "ppt/_rels/presentation.xml.rels" => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(&new_presentation_rels), &mut writer)?
            }
            "[Content_Types].xml" => {
                writer.start_file(name, options)?;
                std::io::copy(&mut Cursor::new(new_content_types.as_bytes()), &mut writer)?
            }
            _ => {
                writer.raw_copy_file(file)?;
                0
            }
        };
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    for (part_name, content) in new_parts {
        writer.start_file(part_name.clone(), options)?;
        std::io::copy(&mut Cursor::new(&content), &mut writer)?;
        update_package_facts(&part_name, &mut part_count, &mut has_vba);
    }
    writer.finish()?;

    Ok(SlideAddSummary {
        path: output_path.to_path_buf(),
        slide_part: new_slide_part,
        relationship_id,
        layout_target: layout_relationship.target.clone(),
        slide_id,
        slide_count: slide_parts.len(),
        part_count,
        has_vba,
    })
}

fn next_free_numbered_part(
    existing: &mut std::collections::HashSet<String>,
    source_part: &str,
) -> String {
    let (dir, file) = match source_part.rfind('/') {
        Some(pos) => (&source_part[..=pos], &source_part[pos + 1..]),
        None => ("", source_part),
    };
    let (stem, ext) = match file.rfind('.') {
        Some(pos) => (&file[..pos], &file[pos..]),
        None => (file, ""),
    };
    let non_digit_len = stem.trim_end_matches(|c: char| c.is_ascii_digit()).len();
    let stem_prefix = &stem[..non_digit_len];
    for number in 1.. {
        let candidate = format!("{dir}{stem_prefix}{number}{ext}");
        if !existing.contains(&candidate) {
            existing.insert(candidate.clone());
            return candidate;
        }
    }
    unreachable!()
}

fn make_relative_target(source_part: &str, target_part: &str) -> String {
    let mut source_dir: Vec<&str> = source_part.split('/').collect();
    source_dir.pop();
    let target_parts: Vec<&str> = target_part.split('/').collect();
    let mut common = 0;
    while common < source_dir.len()
        && common < target_parts.len().saturating_sub(1)
        && source_dir[common] == target_parts[common]
    {
        common += 1;
    }
    let up_count = source_dir.len() - common;
    let mut result_parts = Vec::new();
    for _ in 0..up_count {
        result_parts.push("..");
    }
    for chunk in &target_parts[common..] {
        result_parts.push(*chunk);
    }
    result_parts.join("/")
}

fn rewrite_relationship_targets(
    rels_xml: &[u8],
    replacements: &BTreeMap<String, String>,
) -> Result<Vec<u8>, WolfPptError> {
    if replacements.is_empty() {
        return Ok(rels_xml.to_vec());
    }
    let mut reader = Reader::from_reader(rels_xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(rels_xml.len())));
    loop {
        match reader.read_event()? {
            Event::Eof => break,
            Event::Empty(event) if local_name(event.name().as_ref()) == b"Relationship" => {
                let id = event
                    .attributes()
                    .flatten()
                    .find(|attr| local_name(attr.key.as_ref()) == b"Id")
                    .and_then(|attr| attr.decode_and_unescape_value(reader.decoder()).ok())
                    .map(|v| v.into_owned())
                    .unwrap_or_default();
                if let Some(new_target) = replacements.get(&id) {
                    let rewritten =
                        rewrite_event_attributes(&event, &[("Target", new_target.clone())]);
                    writer.write_event(Event::Empty(rewritten))?;
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::Start(event) if local_name(event.name().as_ref()) == b"Relationship" => {
                let id = event
                    .attributes()
                    .flatten()
                    .find(|attr| local_name(attr.key.as_ref()) == b"Id")
                    .and_then(|attr| attr.decode_and_unescape_value(reader.decoder()).ok())
                    .map(|v| v.into_owned())
                    .unwrap_or_default();
                if let Some(new_target) = replacements.get(&id) {
                    let rewritten =
                        rewrite_event_attributes(&event, &[("Target", new_target.clone())]);
                    writer.write_event(Event::Start(rewritten))?;
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            other => {
                writer.write_event(other)?;
            }
        }
    }
    Ok(writer.into_inner().into_inner())
}

fn read_archive_bytes<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    part_name: &str,
) -> Result<Option<Vec<u8>>, WolfPptError> {
    match archive.by_name(part_name) {
        Ok(mut file) => {
            let mut payload = Vec::new();
            file.read_to_end(&mut payload)?;
            Ok(Some(payload))
        }
        Err(zip::result::ZipError::FileNotFound) => Ok(None),
        Err(err) => Err(WolfPptError::from(err)),
    }
}

fn find_content_type_override(content_types_xml: &str, part_name: &str) -> Option<String> {
    let mut reader = Reader::from_str(content_types_xml);
    reader.config_mut().trim_text(true);
    let target_part = if part_name.starts_with('/') {
        part_name.to_string()
    } else {
        format!("/{part_name}")
    };
    loop {
        match reader.read_event() {
            Ok(Event::Empty(event)) | Ok(Event::Start(event))
                if local_name(event.name().as_ref()) == b"Override" =>
            {
                let mut current_part = String::new();
                let mut content_type = String::new();
                for attr in event.attributes().flatten() {
                    let key = local_name(attr.key.as_ref());
                    let value = attr
                        .decode_and_unescape_value(reader.decoder())
                        .map(|v| v.into_owned())
                        .unwrap_or_default();
                    if key == b"PartName" {
                        current_part = value;
                    } else if key == b"ContentType" {
                        content_type = value;
                    }
                }
                if current_part == target_part {
                    return Some(content_type);
                }
            }
            Ok(Event::Eof) | Err(_) => break,
            _ => {}
        }
    }
    None
}
