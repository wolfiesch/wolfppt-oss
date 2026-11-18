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

    let mut source_slide_xml = {
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
    // - tags (.../tags): COPIED (OWNED). Slide and shape tag sets get independent parts.
    // - diagramData / diagramLayout / diagramQuickStyle / diagramColors (.../diagram*): COPIED
    //   (OWNED). The complete internal relationship closure of every root is cloned with one
    //   shared old->new map (aliases preserved, cycles terminate); XML/binary bytes, external
    //   relationships, rIds and fragments are preserved, internal targets are rewritten, content
    //   type overrides are registered. Missing parts, or closure references to slide parts or
    //   the presentation root, are rejected before any output is created.
    // - customXml (.../customXml): SHARED only for package-level customXml/ datastore items.
    //   The copy keeps the p:custData binding's rId and target, so no ds:itemID is duplicated.
    //   Other targets, including ppt/ink/ content parts, are REJECTED without a copy policy.
    //   Resolve dot segments before checking the package-root directory.
    // - vmlDrawing (.../vmlDrawing): COPIED (OWNED). Cloned to a new ppt/drawings/vmlDrawingN.vml
    //   with its relationship part copied verbatim (targets are drawing-relative and shared).
    //   A drawing that declares an o:signatureline is REJECTED: a signature line carries a
    //   signature identity that has no copy policy.
    // - slide (.../slide): SHARED. Internal hyperlinks reference existing slides; passed through
    //   with unchanged rId and target.
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
        let is_shared_custom_xml = relationship.relationship_type.ends_with("/customXml") && {
            let target = if relationship.target.starts_with('/') {
                resolve_target("", relationship.target.trim_start_matches('/'))
            } else {
                resolve_target(source_slide_part, &relationship.target)
            };
            target.starts_with("customXml/")
        };

        if !relationship.relationship_type.ends_with("/slideLayout")
            && !relationship.relationship_type.ends_with("/image")
            && !relationship.relationship_type.ends_with("/chart")
            && !relationship.relationship_type.ends_with("/notesSlide")
            && !relationship.relationship_type.ends_with("/oleObject")
            && !relationship.relationship_type.ends_with("/package")
            && !relationship.relationship_type.ends_with("/comments")
            && !relationship.relationship_type.ends_with("/comment")
            && !relationship.relationship_type.ends_with("/tags")
            && !relationship.relationship_type.ends_with("/audio")
            && !relationship.relationship_type.ends_with("/video")
            && !relationship.relationship_type.ends_with("/media")
            && !relationship.relationship_type.ends_with("/slide")
            && !is_shared_custom_xml
            && !relationship.relationship_type.ends_with("/vmlDrawing")
            && !is_diagram_root_relationship_type(&relationship.relationship_type)
        {
            return Err(WolfPptError::InvalidInput(format!(
                "cannot duplicate slide relationship type {} without an explicit copy policy",
                relationship.relationship_type
            )));
        }
        if relationship.relationship_type.ends_with("/vmlDrawing") {
            let source_vml_part = resolve_target(source_slide_part, &relationship.target);
            let vml = read_archive_bytes(&mut archive, &source_vml_part)?.ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "vml drawing part {source_vml_part} was not found"
                ))
            })?;
            if vml_declares_signature_line(&vml) {
                return Err(WolfPptError::InvalidInput(format!(
                    "cannot duplicate slide relationship type {} without an explicit copy policy",
                    relationship.relationship_type
                )));
            }
        }
    }

    let mut existing_names = std::collections::HashSet::new();
    for index in 0..archive.len() {
        existing_names.insert(archive.by_index(index)?.name()?.into_owned());
    }

    refresh_duplicate_creation_id(&mut archive, &slide_parts, &mut source_slide_xml)?;
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
    // One old->new map across all SmartArt roots preserves aliases and ends cycles.
    let mut diagram_part_map: BTreeMap<String, String> = BTreeMap::new();

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
            let mut comment_xml = read_archive_bytes(&mut archive, &source_comment_part)?
                .ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "comment part {source_comment_part} was not found"
                    ))
                })?;
            let new_comment_part =
                next_free_numbered_part(&mut existing_names, &source_comment_part);

            if relationship.relationship_type
                == "http://schemas.microsoft.com/office/2018/10/relationships/comments"
            {
                rebind_duplicate_comment_anchors(&mut comment_xml, slide_id)?;
            }
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
        } else if relationship.relationship_type.ends_with("/tags") {
            let source_tags_part = resolve_target(source_slide_part, &relationship.target);
            let tags_xml =
                read_archive_bytes(&mut archive, &source_tags_part)?.ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "tags part {source_tags_part} was not found"
                    ))
                })?;
            let new_tags_part = next_free_numbered_part(&mut existing_names, &source_tags_part);
            let tags_ct = find_content_type_override(&content_types_str, &source_tags_part)
                .unwrap_or_else(|| {
                    "application/vnd.openxmlformats-officedocument.presentationml.tags+xml"
                        .to_string()
                });
            new_content_types = ensure_content_type_override(
                &new_content_types,
                &format!("/{new_tags_part}"),
                &tags_ct,
            )?;
            let slide_rel_target = make_relative_target(&new_slide_part, &new_tags_part);
            slide_rel_replacements.insert(relationship.id.clone(), slide_rel_target);
            new_parts.push((new_tags_part, tags_xml));
        } else if relationship.relationship_type.ends_with("/vmlDrawing") {
            let source_vml_part = resolve_target(source_slide_part, &relationship.target);
            let vml_bytes =
                read_archive_bytes(&mut archive, &source_vml_part)?.ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "vml drawing part {source_vml_part} was not found"
                    ))
                })?;
            let new_vml_part = next_free_numbered_part(&mut existing_names, &source_vml_part);
            if let Some(vml_rels) =
                read_archive_bytes(&mut archive, &relationship_part_name(&source_vml_part))?
            {
                new_parts.push((relationship_part_name(&new_vml_part), vml_rels));
            }
            new_parts.push((new_vml_part.clone(), vml_bytes));
            let slide_rel_target = make_relative_target(&new_slide_part, &new_vml_part);
            slide_rel_replacements.insert(relationship.id.clone(), slide_rel_target);
            if let Some(override_ct) =
                find_content_type_override(&content_types_str, &source_vml_part)
            {
                new_content_types = ensure_content_type_override(
                    &new_content_types,
                    &format!("/{new_vml_part}"),
                    &override_ct,
                )?;
            }
        } else if is_diagram_root_relationship_type(&relationship.relationship_type) {
            let (root_path, _) = split_target_fragment(&relationship.target);
            let source_root = resolve_target(source_slide_part, root_path);
            let new_root = clone_diagram_closure(
                &mut archive,
                &mut existing_names,
                &content_types_str,
                &mut new_content_types,
                &mut new_parts,
                &mut diagram_part_map,
                &slide_parts,
                &source_root,
            )?;
            slide_rel_replacements.insert(
                relationship.id.clone(),
                diagram_rewritten_target(&new_slide_part, &new_root, &relationship.target),
            );
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
        let name = file.name()?.into_owned();
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

/// Replace only namespace-resolved moniker attribute values, keeping opaque XML bytes.
fn rebind_duplicate_comment_anchors(xml: &mut Vec<u8>, slide_id: u64) -> Result<(), WolfPptError> {
    let invalid = || WolfPptError::InvalidInput("invalid modern comment slide anchor".to_string());
    let mut ranges = Vec::new();
    let mut reader = quick_xml::NsReader::from_reader(xml.as_slice());
    loop {
        let (namespace, event) = reader
            .read_resolved_event()
            .map_err(|error| WolfPptError::XmlText(error.to_string()))?;
        let is_command = matches!(
            namespace,
            quick_xml::name::ResolveResult::Bound(namespace)
                if namespace.0.as_bytes()
                    == b"http://schemas.microsoft.com/office/powerpoint/2013/main/command"
        );
        match event {
            Event::Start(element) | Event::Empty(element)
                if is_command && element.local_name().as_ref().as_bytes() == b"sldMk" =>
            {
                for attribute in element.attributes() {
                    let attribute = attribute.map_err(|_| invalid())?;
                    if attribute.key.as_ref().as_bytes() != b"sldId" {
                        continue;
                    }
                    let std::borrow::Cow::Borrowed(raw) = attribute.value else {
                        return Err(invalid());
                    };
                    raw.parse::<u32>().map_err(|_| invalid())?;
                    let start = (raw.as_ptr() as usize)
                        .checked_sub(xml.as_ptr() as usize)
                        .ok_or_else(invalid)?;
                    if start + raw.len() > xml.len() {
                        return Err(invalid());
                    }
                    ranges.push(start..start + raw.len());
                }
            }
            Event::DocType(_) => return Err(invalid()),
            Event::Eof => break,
            _ => {}
        }
    }
    if !ranges.is_empty() {
        let replacement = slide_id.to_string();
        for range in ranges.into_iter().rev() {
            xml.splice(range, replacement.bytes());
        }
    }
    Ok(())
}

/// Locate only the slide-level p14 identity; shape identities and opaque payloads
/// remain untouched. Borrowed attribute offsets retain all original XML bytes.
fn duplicate_creation_id_attribute(
    xml: &[u8],
) -> Result<Option<(std::ops::Range<usize>, u32)>, WolfPptError> {
    let invalid = || WolfPptError::InvalidInput("invalid slide creationId".to_string());
    let mut reader = quick_xml::NsReader::from_reader(xml);
    let mut depth = 0;
    let mut in_list = false;
    let mut in_extension = false;
    let mut found = None;
    loop {
        let (namespace, event) = reader
            .read_resolved_event()
            .map_err(|error| WolfPptError::XmlText(error.to_string()))?;
        let namespace = match namespace {
            quick_xml::name::ResolveResult::Bound(namespace) => namespace.0.as_bytes(),
            _ => b"",
        };
        let presentation = matches!(
            namespace,
            b"http://schemas.openxmlformats.org/presentationml/2006/main"
                | b"http://purl.oclc.org/ooxml/presentationml/main"
        );
        let empty = matches!(event, Event::Empty(_));
        match event {
            Event::Start(element) | Event::Empty(element) => {
                let local = element.local_name();
                if depth == 1 {
                    in_list = presentation && local.as_ref().as_bytes() == b"extLst";
                }
                if depth == 2 {
                    in_extension = false;
                    if in_list && presentation && local.as_ref().as_bytes() == b"ext" {
                        for attribute in element.attributes() {
                            let attribute = attribute.map_err(|_| invalid())?;
                            if attribute.key.as_ref().as_bytes() == b"uri" {
                                in_extension = attribute
                                    .value
                                    .as_ref()
                                    .eq_ignore_ascii_case("{BB962C8B-B14F-4D97-AF65-F5344CB8AC3E}");
                            }
                        }
                    }
                }
                if depth == 3
                    && in_extension
                    && namespace == b"http://schemas.microsoft.com/office/powerpoint/2010/main"
                    && local.as_ref().as_bytes() == b"creationId"
                {
                    if found.is_some() {
                        return Err(invalid());
                    }
                    let mut value = None;
                    for attribute in element.attributes() {
                        let attribute = attribute.map_err(|_| invalid())?;
                        if attribute.key.as_ref().as_bytes() != b"val" {
                            continue;
                        }
                        let std::borrow::Cow::Borrowed(raw) = attribute.value else {
                            return Err(invalid());
                        };
                        let start = (raw.as_ptr() as usize)
                            .checked_sub(xml.as_ptr() as usize)
                            .ok_or_else(invalid)?;
                        if start + raw.len() > xml.len() || value.is_some() {
                            return Err(invalid());
                        }
                        let id = raw.parse::<u32>().map_err(|_| invalid())?;
                        value = Some((start..start + raw.len(), id));
                    }
                    found = Some(value.ok_or_else(invalid)?);
                }
                if !empty {
                    depth += 1;
                }
            }
            Event::End(_) => depth -= 1,
            Event::DocType(_) => return Err(invalid()),
            Event::Eof => return Ok(found),
            _ => {}
        }
    }
}

fn refresh_duplicate_creation_id(
    archive: &mut ZipArchive<File>,
    slide_parts: &[String],
    source: &mut Vec<u8>,
) -> Result<(), WolfPptError> {
    let Some((span, _)) = duplicate_creation_id_attribute(source)? else {
        return Ok(());
    };
    let mut used = std::collections::HashSet::new();
    for part in slide_parts {
        if let Some(xml) = read_archive_bytes(archive, part)? {
            if let Some((_, id)) = duplicate_creation_id_attribute(&xml)? {
                used.insert(id);
            }
        }
    }
    let mut candidate = 1_u32;
    while used.contains(&candidate) {
        candidate = candidate.checked_add(1).ok_or_else(|| {
            WolfPptError::InvalidInput("slide creationId space is exhausted".to_string())
        })?;
    }
    source.splice(span, candidate.to_string().bytes());
    Ok(())
}

/// True when a legacy VML drawing declares an `o:signatureline`. UTF-16 drawings (byte-order
/// mark) are decoded; anything else is read as lossy UTF-8.
fn vml_declares_signature_line(vml: &[u8]) -> bool {
    let text = match vml {
        [0xFF, 0xFE, rest @ ..] => String::from_utf16_lossy(
            &rest
                .as_chunks::<2>()
                .0
                .iter()
                .map(|&pair| u16::from_le_bytes(pair))
                .collect::<Vec<_>>(),
        ),
        [0xFE, 0xFF, rest @ ..] => String::from_utf16_lossy(
            &rest
                .as_chunks::<2>()
                .0
                .iter()
                .map(|&pair| u16::from_be_bytes(pair))
                .collect::<Vec<_>>(),
        ),
        _ => String::from_utf8_lossy(vml).into_owned(),
    };
    text.to_ascii_lowercase().contains("signatureline")
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
    let mut result_parts = Vec::with_capacity(up_count + target_parts.len() - common);
    result_parts.resize(up_count, "..");
    for chunk in &target_parts[common..] {
        result_parts.push(*chunk);
    }
    result_parts.join("/")
}

fn is_diagram_root_relationship_type(relationship_type: &str) -> bool {
    relationship_type.ends_with("/diagramData")
        || relationship_type.ends_with("/diagramLayout")
        || relationship_type.ends_with("/diagramQuickStyle")
        || relationship_type.ends_with("/diagramColors")
}

/// Split a relationship target into its part path and optional fragment.
fn split_target_fragment(target: &str) -> (&str, Option<&str>) {
    match target.split_once('#') {
        Some((path, fragment)) => (path, Some(fragment)),
        None => (target, None),
    }
}

/// Build the rewritten relationship target for a cloned diagram part, keeping the
/// original absolute/relative style and any fragment.
fn diagram_rewritten_target(from_part: &str, to_part: &str, original_target: &str) -> String {
    let mut target = if original_target.starts_with('/') {
        format!("/{to_part}")
    } else {
        make_relative_target(from_part, to_part)
    };
    if let (_, Some(fragment)) = split_target_fragment(original_target) {
        target.push('#');
        target.push_str(fragment);
    }
    target
}

/// Allocate a numbered part name whose relationship part name is also unused.
fn allocate_diagram_part(
    existing: &mut std::collections::HashSet<String>,
    source_part: &str,
) -> String {
    loop {
        let candidate = next_free_numbered_part(existing, source_part);
        let rels_part = relationship_part_name(&candidate);
        if existing.insert(rels_part) {
            return candidate;
        }
    }
}

/// Clone the complete internal relationship closure of one SmartArt root part.
/// `closure_map` is shared by every diagram root of the slide so aliases map to a
/// single clone and cyclic relationships terminate. Returns the cloned root part.
/// Every failure happens before any output file is created.
#[allow(clippy::too_many_arguments)]
fn clone_diagram_closure(
    archive: &mut ZipArchive<File>,
    existing_names: &mut std::collections::HashSet<String>,
    content_types_str: &str,
    new_content_types: &mut String,
    new_parts: &mut Vec<(String, Vec<u8>)>,
    closure_map: &mut BTreeMap<String, String>,
    slide_parts: &[String],
    source_root: &str,
) -> Result<String, WolfPptError> {
    let forbidden = |part: &str| {
        part == "ppt/presentation.xml"
            || slide_parts.iter().any(|slide| slide == part)
            || slide_number(part).is_some()
    };
    if forbidden(source_root) {
        return Err(WolfPptError::InvalidInput(format!(
            "SmartArt part {source_root} cannot be a slide or presentation part"
        )));
    }
    if let Some(existing) = closure_map.get(source_root) {
        return Ok(existing.clone());
    }
    let new_root = allocate_diagram_part(existing_names, source_root);
    closure_map.insert(source_root.to_string(), new_root.clone());
    let mut pending = vec![source_root.to_string()];
    while let Some(source_part) = pending.pop() {
        let new_part = closure_map[&source_part].clone();
        let part_bytes = read_archive_bytes(archive, &source_part)?.ok_or_else(|| {
            WolfPptError::InvalidInput(format!("SmartArt part {source_part} was not found"))
        })?;
        let source_rels_part = relationship_part_name(&source_part);
        if let Some(source_rels) = read_archive_bytes(archive, &source_rels_part)? {
            let mut replacements = BTreeMap::new();
            for relationship in parse_relationships(&source_rels) {
                let is_external = relationship
                    .target_mode
                    .as_deref()
                    .map(|mode| mode.eq_ignore_ascii_case("External"))
                    .unwrap_or(false);
                if is_external {
                    continue;
                }
                let (target_path, _) = split_target_fragment(&relationship.target);
                let target_part = resolve_target(&source_part, target_path);
                if relationship.relationship_type.ends_with("/slide")
                    || relationship.relationship_type.ends_with("/officeDocument")
                    || forbidden(&target_part)
                {
                    return Err(WolfPptError::InvalidInput(format!(
                        "SmartArt part {source_part} references slide or presentation part {target_part}; cannot duplicate"
                    )));
                }
                let new_target = match closure_map.get(&target_part) {
                    Some(existing) => existing.clone(),
                    None => {
                        let allocated = allocate_diagram_part(existing_names, &target_part);
                        closure_map.insert(target_part.clone(), allocated.clone());
                        pending.push(target_part);
                        allocated
                    }
                };
                replacements.insert(
                    relationship.id.clone(),
                    diagram_rewritten_target(&new_part, &new_target, &relationship.target),
                );
            }
            let new_rels = rewrite_relationship_targets(&source_rels, &replacements)?;
            new_parts.push((relationship_part_name(&new_part), new_rels));
        }
        if let Some(override_ct) = find_content_type_override(content_types_str, &source_part) {
            *new_content_types = ensure_content_type_override(
                new_content_types,
                &format!("/{new_part}"),
                &override_ct,
            )?;
        }
        new_parts.push((new_part, part_bytes));
    }
    Ok(new_root)
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
            Event::Empty(event)
                if local_name(event.name().as_ref().as_bytes()) == b"Relationship" =>
            {
                let id = event
                    .attributes()
                    .flatten()
                    .find(|attr| local_name(attr.key.as_ref().as_bytes()) == b"Id")
                    .and_then(|attr| {
                        attr.normalized_value(quick_xml::XmlVersion::Implicit1_0)
                            .ok()
                    })
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
            Event::Start(event)
                if local_name(event.name().as_ref().as_bytes()) == b"Relationship" =>
            {
                let id = event
                    .attributes()
                    .flatten()
                    .find(|attr| local_name(attr.key.as_ref().as_bytes()) == b"Id")
                    .and_then(|attr| {
                        attr.normalized_value(quick_xml::XmlVersion::Implicit1_0)
                            .ok()
                    })
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
                if local_name(event.name().as_ref().as_bytes()) == b"Override" =>
            {
                let mut current_part = String::new();
                let mut content_type = String::new();
                for attr in event.attributes().flatten() {
                    let key = local_name(attr.key.as_ref().as_bytes());
                    let value = attr
                        .normalized_value(quick_xml::XmlVersion::Implicit1_0)
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

#[cfg(test)]
mod duplicate_tags_tests {
    use super::*;

    #[test]
    fn duplicate_slide_owns_tag_parts_and_refuses_missing_tags_atomically() {
        use std::io::Write;

        for namespace in [
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "http://purl.oclc.org/ooxml/officeDocument/relationships",
        ] {
            for missing in [false, true] {
                let dir = tempfile::tempdir().unwrap();
                let input = dir.path().join("tags.pptx");
                let output = dir.path().join("duplicate.pptx");
                let mut original = ZipArchive::new(
                    File::open("../../fixtures/pptx/slides/two_slide_text.pptx").unwrap(),
                )
                .unwrap();
                let source_part = "ppt/slides/slide1.xml";
                let rels_part = relationship_part_name(source_part);
                let rels = read_archive_bytes(&mut original, &rels_part)
                    .unwrap()
                    .unwrap();
                let rels = append_relationship(
                    &rels,
                    "rIdTagsSlide",
                    &format!("{namespace}/tags"),
                    "../tags/tag1.xml",
                )
                .unwrap();
                let rels = append_relationship(
                    &rels,
                    "rIdTagsShape",
                    &format!("{namespace}/tags"),
                    "../tags/tag2.xml",
                )
                .unwrap();
                let types = read_archive_text(&mut original, "[Content_Types].xml")
                    .unwrap()
                    .unwrap();
                let mut types = types;
                for number in 1..=2 {
                    types = ensure_content_type_override(
                        &types,
                        &format!("/ppt/tags/tag{number}.xml"),
                        "application/vnd.openxmlformats-officedocument.presentationml.tags+xml",
                    )
                    .unwrap();
                }
                let mut writer = zip::ZipWriter::new(File::create(&input).unwrap());
                let options = SimpleFileOptions::default();
                for index in 0..original.len() {
                    let entry = original.by_index(index).unwrap();
                    let name = entry.name().unwrap().into_owned();
                    if name == rels_part || name == "[Content_Types].xml" {
                        writer.start_file(&name, options).unwrap();
                        writer
                            .write_all(if name == rels_part {
                                &rels
                            } else {
                                types.as_bytes()
                            })
                            .unwrap();
                    } else {
                        writer.raw_copy_file(entry).unwrap();
                    }
                }
                let tags = [
                    b"<p:tagLst xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"><p:tag name=\"SLIDE\" val=\"source\"/></p:tagLst>".as_slice(),
                    b"<p:tagLst xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"><p:tag name=\"SHAPE\" val=\"source\"/></p:tagLst>".as_slice(),
                ];
                for (index, bytes) in tags.iter().enumerate() {
                    if missing && index == 1 {
                        continue;
                    }
                    writer
                        .start_file(format!("ppt/tags/tag{}.xml", index + 1), options)
                        .unwrap();
                    writer.write_all(bytes).unwrap();
                }
                writer.finish().unwrap();
                std::fs::write(&output, b"existing destination").unwrap();
                let result = duplicate_slide(&input, &output, source_part);
                if missing {
                    assert!(result
                        .unwrap_err()
                        .to_string()
                        .contains("tags part ppt/tags/tag2.xml was not found"));
                    assert_eq!(std::fs::read(&output).unwrap(), b"existing destination");
                    continue;
                }
                let summary = result.unwrap();
                let mut duplicated = ZipArchive::new(File::open(&output).unwrap()).unwrap();
                let copied_rels = read_archive_bytes(
                    &mut duplicated,
                    &relationship_part_name(&summary.slide_part),
                )
                .unwrap()
                .unwrap();
                let copied_rels = parse_relationships(&copied_rels);
                let content_types = read_archive_text(&mut duplicated, "[Content_Types].xml")
                    .unwrap()
                    .unwrap();
                for (index, bytes) in tags.iter().enumerate() {
                    let rel = copied_rels
                        .iter()
                        .find(|rel| {
                            rel.id
                                == if index == 0 {
                                    "rIdTagsSlide"
                                } else {
                                    "rIdTagsShape"
                                }
                        })
                        .unwrap();
                    let target = resolve_target(&summary.slide_part, &rel.target);
                    assert_ne!(target, format!("ppt/tags/tag{}.xml", index + 1));
                    assert_eq!(
                        read_archive_bytes(&mut duplicated, &target)
                            .unwrap()
                            .unwrap(),
                        *bytes
                    );
                    assert_eq!(
                        read_archive_bytes(
                            &mut duplicated,
                            &format!("ppt/tags/tag{}.xml", index + 1)
                        )
                        .unwrap()
                        .unwrap(),
                        *bytes
                    );
                    assert_eq!(
                        find_content_type_override(&content_types, &target).as_deref(),
                        Some(
                            "application/vnd.openxmlformats-officedocument.presentationml.tags+xml"
                        )
                    );
                    assert_eq!(rel.relationship_type, format!("{namespace}/tags"));
                }
                assert_ne!(
                    copied_rels
                        .iter()
                        .find(|r| r.id == "rIdTagsSlide")
                        .unwrap()
                        .target,
                    copied_rels
                        .iter()
                        .find(|r| r.id == "rIdTagsShape")
                        .unwrap()
                        .target
                );
            }
        }
    }
}
