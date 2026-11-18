use std::collections::{HashMap, HashSet};

struct MasterLayoutInfo {
    output_layout_part: String,
    layout_bytes_for_cmp: Vec<u8>,
}

struct MasterInfo {
    output_master_part: String,
    master_bytes_for_cmp: Vec<u8>,
    theme_bytes_for_cmp: Option<Vec<u8>>,
    layouts: Vec<MasterLayoutInfo>,
}

struct AssemblyState {
    existing_names: HashSet<String>,
    media_cache: HashMap<[u8; 32], String>,
    known_masters: Vec<MasterInfo>,
    new_parts: Vec<(String, Vec<u8>)>,
    content_types: String,
    presentation_xml: Vec<u8>,
    presentation_rels: Vec<u8>,
    max_slide_id: u64,
    max_master_or_layout_id: u64,
    max_rel_id: u64,
    next_slide_number: u64,
    summary: DeckAssemblySummary,
}

pub fn assemble_deck(
    base_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    selections: &[DeckSlideSelection],
) -> Result<DeckAssemblySummary, WolfPptError> {
    let base_path = base_path.as_ref();
    let output_path = output_path.as_ref();

    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let base_file = File::open(base_path)?;
    let mut base_archive = ZipArchive::new(base_file)?;

    let mut existing_names = HashSet::new();
    for index in 0..base_archive.len() {
        existing_names.insert(base_archive.by_index(index)?.name()?.into_owned());
    }

    let mut presentation_xml = Vec::new();
    base_archive
        .by_name("ppt/presentation.xml")?
        .read_to_end(&mut presentation_xml)?;

    let mut presentation_rels = Vec::new();
    base_archive
        .by_name("ppt/_rels/presentation.xml.rels")?
        .read_to_end(&mut presentation_rels)?;

    let mut content_types_bytes = Vec::new();
    base_archive
        .by_name("[Content_Types].xml")?
        .read_to_end(&mut content_types_bytes)?;
    let content_types = String::from_utf8(content_types_bytes)
        .map_err(|err| WolfPptError::XmlText(err.to_string()))?;

    // Pre-populate media cache with SHA-256 hashes of all existing base media
    let mut media_cache = HashMap::new();
    for name in &existing_names {
        if name.starts_with("ppt/media/") {
            if let Some(bytes) = read_archive_bytes(&mut base_archive, name)? {
                let mut hasher = Sha256::new();
                hasher.update(&bytes);
                let hash: [u8; 32] = hasher.finalize().into();
                media_cache.insert(hash, name.clone());
            }
        }
    }

    // Index base presentation masters and layouts
    let mut known_masters = Vec::new();
    let base_pres_rels = parse_relationships(&presentation_rels);
    for rel in &base_pres_rels {
        if rel.relationship_type.ends_with("/slideMaster") {
            let output_master_part = resolve_target("ppt/presentation.xml", &rel.target);
            if let Some(master_bytes) = read_archive_bytes(&mut base_archive, &output_master_part)? {
                let master_rels_part = relationship_part_name(&output_master_part);
                let mut theme_bytes_for_cmp = None;
                let mut layouts = Vec::new();
                if let Some(master_rels_bytes) = read_archive_bytes(&mut base_archive, &master_rels_part)? {
                    let master_rels = parse_relationships(&master_rels_bytes);
                    for mrel in &master_rels {
                        if mrel.relationship_type.ends_with("/theme") {
                            let theme_part = resolve_target(&output_master_part, &mrel.target);
                            theme_bytes_for_cmp = read_archive_bytes(&mut base_archive, &theme_part)?;
                        } else if mrel.relationship_type.ends_with("/slideLayout") {
                            let layout_part = resolve_target(&output_master_part, &mrel.target);
                            if let Some(layout_bytes) = read_archive_bytes(&mut base_archive, &layout_part)? {
                                layouts.push(MasterLayoutInfo {
                                    output_layout_part: layout_part,
                                    layout_bytes_for_cmp: layout_bytes,
                                });
                            }
                        }
                    }
                }
                known_masters.push(MasterInfo {
                    output_master_part,
                    master_bytes_for_cmp: master_bytes,
                    theme_bytes_for_cmp,
                    layouts,
                });
            }
        }
    }

    let max_slide_id = find_max_slide_id(&presentation_xml);
    let max_master_or_layout_id = find_max_master_or_layout_id(&mut base_archive, &presentation_xml)?;
    let max_rel_id = find_max_rel_id(&presentation_rels);

    let next_slide_number = existing_names
        .iter()
        .filter_map(|name| slide_number(name))
        .max()
        .unwrap_or(0)
        + 1;

    let summary = DeckAssemblySummary {
        path: output_path.to_path_buf(),
        slides_added: 0,
        masters_added: 0,
        masters_reused: 0,
        layouts_added: 0,
        media_added: 0,
        media_reused: 0,
        slide_parts: Vec::new(),
    };

    let mut state = AssemblyState {
        existing_names,
        media_cache,
        known_masters,
        new_parts: Vec::new(),
        content_types,
        presentation_xml,
        presentation_rels,
        max_slide_id,
        max_master_or_layout_id,
        max_rel_id,
        next_slide_number,
        summary,
    };

    // Cache opened source archives to avoid repeatedly re-opening and re-parsing
    let mut source_archives: HashMap<PathBuf, ZipArchive<File>> = HashMap::new();

    for selection in selections {
        if !source_archives.contains_key(&selection.source_path) {
            let file = File::open(&selection.source_path)?;
            let archive = ZipArchive::new(file)?;
            source_archives.insert(selection.source_path.clone(), archive);
        }
        let src_archive = source_archives.get_mut(&selection.source_path).unwrap();

        // 1. Validate slide exists in source
        let source_slide_xml = match read_archive_bytes(src_archive, &selection.slide_part)? {
            Some(xml) => xml,
            None => {
                return Err(WolfPptError::InvalidInput(format!(
                    "source slide part {} was not found in {:?}",
                    selection.slide_part, selection.source_path
                )));
            }
        };

        // Read source Content_Types.xml
        let src_content_types_str = read_archive_text(src_archive, "[Content_Types].xml")?
            .unwrap_or_default();

        // Read slide relationships
        let source_slide_rels_part = relationship_part_name(&selection.slide_part);
        let source_slide_rels_raw = read_archive_bytes(src_archive, &source_slide_rels_part)?
            .unwrap_or_default();
        let relationships = parse_relationships(&source_slide_rels_raw);

        // Find slide layout rel
        let layout_relationship = relationships
            .iter()
            .find(|r| r.relationship_type.ends_with("/slideLayout"))
            .ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "source slide part {} in {:?} has no slide layout relationship",
                    selection.slide_part, selection.source_path
                ))
            })?;

        let source_layout_part = resolve_target(&selection.slide_part, &layout_relationship.target);
        let source_layout_bytes = read_archive_bytes(src_archive, &source_layout_part)?
            .ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "source layout part {source_layout_part} was not found in {:?}",
                    selection.source_path
                ))
            })?;

        // Find master for this layout
        let source_layout_rels_part = relationship_part_name(&source_layout_part);
        let source_layout_rels_raw = read_archive_bytes(src_archive, &source_layout_rels_part)?
            .ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "layout rels part {source_layout_rels_part} was not found in {:?}",
                    selection.source_path
                ))
            })?;
        let layout_rels = parse_relationships(&source_layout_rels_raw);
        let master_relationship = layout_rels
            .iter()
            .find(|r| r.relationship_type.ends_with("/slideMaster"))
            .ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "layout part {source_layout_part} has no slide master relationship in {:?}",
                    selection.source_path
                ))
            })?;

        let source_master_part = resolve_target(&source_layout_part, &master_relationship.target);
        let source_master_bytes = read_archive_bytes(src_archive, &source_master_part)?
            .ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "source master part {source_master_part} was not found in {:?}",
                    selection.source_path
                ))
            })?;

        let source_master_rels_part = relationship_part_name(&source_master_part);
        let source_master_rels_raw = read_archive_bytes(src_archive, &source_master_rels_part)?
            .unwrap_or_default();
        let master_rels = parse_relationships(&source_master_rels_raw);

        // Find theme for this master
        let theme_relationship = master_rels
            .iter()
            .find(|r| r.relationship_type.ends_with("/theme"));
        let source_theme_part = theme_relationship
            .map(|r| resolve_target(&source_master_part, &r.target));
        let source_theme_bytes = match &source_theme_part {
            Some(part) => read_archive_bytes(src_archive, part)?,
            None => None,
        };

        // 2. Master deduplication check
        let matching_master_idx = state.known_masters.iter().position(|m| {
            m.master_bytes_for_cmp == source_master_bytes && m.theme_bytes_for_cmp == source_theme_bytes
        });

        let assigned_layout_part = if let Some(m_idx) = matching_master_idx {
            // Master reused!
            state.summary.masters_reused += 1;

            // Look for matching layout XML in this master
            let layout_match = state.known_masters[m_idx]
                .layouts
                .iter()
                .find(|l| l.layout_bytes_for_cmp == source_layout_bytes)
                .map(|l| l.output_layout_part.clone());

            if let Some(output_part) = layout_match {
                output_part
            } else {
                // Layout not in master's existing layouts; add it to this reused master
                let output_master_part = state.known_masters[m_idx].output_master_part.clone();
                let new_layout_part = next_free_numbered_part(&mut state.existing_names, &source_layout_part);
                state.summary.layouts_added += 1;

                // Rewrite layout rels to point to reused master
                let mut layout_rel_replacements = BTreeMap::new();
                for lr in &layout_rels {
                    if lr.relationship_type.ends_with("/slideMaster") {
                        layout_rel_replacements.insert(
                            lr.id.clone(),
                            make_relative_target(&new_layout_part, &output_master_part),
                        );
                    } else if is_media_rel_type(&lr.relationship_type) && !is_external_rel(lr) {
                        let target = process_media_relationship(
                            &source_layout_part,
                            &new_layout_part,
                            lr,
                            src_archive,
                            &mut state,
                        )?;
                        layout_rel_replacements.insert(lr.id.clone(), target);
                    }
                }

                let new_layout_rels = rewrite_relationship_targets(&source_layout_rels_raw, &layout_rel_replacements)?;
                state.new_parts.push((relationship_part_name(&new_layout_part), new_layout_rels));
                state.new_parts.push((new_layout_part.clone(), source_layout_bytes.clone()));
                state.content_types = ensure_content_type_override(
                    &state.content_types,
                    &format!("/{new_layout_part}"),
                    "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml",
                )?;

                state.known_masters[m_idx].layouts.push(MasterLayoutInfo {
                    output_layout_part: new_layout_part.clone(),
                    layout_bytes_for_cmp: source_layout_bytes.clone(),
                });

                new_layout_part
            }
        } else {
            // New master needed!
            state.summary.masters_added += 1;
            let new_master_part = next_free_numbered_part(&mut state.existing_names, &source_master_part);

            state.max_master_or_layout_id += 1;
            let master_id = state.max_master_or_layout_id;
            state.max_rel_id += 1;
            let master_rid = format!("rId{}", state.max_rel_id);

            state.presentation_xml = append_master_id(&state.presentation_xml, master_id, &master_rid)?;
            let rel_target = make_relative_target("ppt/presentation.xml", &new_master_part);
            state.presentation_rels = append_relationship(
                &state.presentation_rels,
                &master_rid,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
                &rel_target,
            )?;
            state.content_types = ensure_content_type_override(
                &state.content_types,
                &format!("/{new_master_part}"),
                "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml",
            )?;

            let mut master_rel_replacements = BTreeMap::new();

            // Copy theme if present
            if let Some(src_theme_part) = &source_theme_part {
                if let Some(theme_bytes) = &source_theme_bytes {
                    let new_theme_part = next_free_numbered_part(&mut state.existing_names, src_theme_part);
                    state.new_parts.push((new_theme_part.clone(), theme_bytes.clone()));
                    state.content_types = ensure_content_type_override(
                        &state.content_types,
                        &format!("/{new_theme_part}"),
                        "application/vnd.openxmlformats-officedocument.theme+xml",
                    )?;
                    if let Some(t_rel) = &theme_relationship {
                        master_rel_replacements.insert(
                            t_rel.id.clone(),
                            make_relative_target(&new_master_part, &new_theme_part),
                        );
                    }
                }
            }

            // Copy layouts for this master
            let mut this_master_layouts = Vec::new();
            let mut rid_to_bumped_layout_id = BTreeMap::new();
            let mut current_assigned_layout = None;

            for mrel in &master_rels {
                if mrel.relationship_type.ends_with("/slideLayout") {
                    let sub_layout_part = resolve_target(&source_master_part, &mrel.target);
                    let sub_layout_bytes = read_archive_bytes(src_archive, &sub_layout_part)?
                        .ok_or_else(|| {
                            WolfPptError::InvalidInput(format!(
                                "layout part {sub_layout_part} referenced by master was not found in {:?}",
                                selection.source_path
                            ))
                        })?;
                    let new_layout_part = next_free_numbered_part(&mut state.existing_names, &sub_layout_part);
                    state.summary.layouts_added += 1;

                    state.max_master_or_layout_id += 1;
                    let layout_id = state.max_master_or_layout_id;
                    rid_to_bumped_layout_id.insert(mrel.id.clone(), layout_id);
                    master_rel_replacements.insert(
                        mrel.id.clone(),
                        make_relative_target(&new_master_part, &new_layout_part),
                    );

                    // Copy sub_layout rels
                    let sub_layout_rels_part = relationship_part_name(&sub_layout_part);
                    let mut sub_layout_rel_replacements = BTreeMap::new();
                    if let Some(sub_layout_rels_bytes) = read_archive_bytes(src_archive, &sub_layout_rels_part)? {
                        let parsed_sub_rels = parse_relationships(&sub_layout_rels_bytes);
                        for slr in &parsed_sub_rels {
                            if slr.relationship_type.ends_with("/slideMaster") {
                                sub_layout_rel_replacements.insert(
                                    slr.id.clone(),
                                    make_relative_target(&new_layout_part, &new_master_part),
                                );
                            } else if is_media_rel_type(&slr.relationship_type) && !is_external_rel(slr) {
                                let media_target = process_media_relationship(
                                    &sub_layout_part,
                                    &new_layout_part,
                                    slr,
                                    src_archive,
                                    &mut state,
                                )?;
                                sub_layout_rel_replacements.insert(slr.id.clone(), media_target);
                            }
                        }
                        let new_sub_layout_rels = rewrite_relationship_targets(&sub_layout_rels_bytes, &sub_layout_rel_replacements)?;
                        state.new_parts.push((relationship_part_name(&new_layout_part), new_sub_layout_rels));
                    }

                    state.new_parts.push((new_layout_part.clone(), sub_layout_bytes.clone()));
                    state.content_types = ensure_content_type_override(
                        &state.content_types,
                        &format!("/{new_layout_part}"),
                        "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml",
                    )?;

                    this_master_layouts.push(MasterLayoutInfo {
                        output_layout_part: new_layout_part.clone(),
                        layout_bytes_for_cmp: sub_layout_bytes,
                    });

                    if sub_layout_part == source_layout_part {
                        current_assigned_layout = Some(new_layout_part);
                    }
                } else if is_media_rel_type(&mrel.relationship_type) && !is_external_rel(mrel) {
                    let media_target = process_media_relationship(
                        &source_master_part,
                        &new_master_part,
                        mrel,
                        src_archive,
                        &mut state,
                    )?;
                    master_rel_replacements.insert(mrel.id.clone(), media_target);
                }
            }

            // Rewrite master XML layout IDs with bumped unique IDs
            let new_master_xml = rewrite_master_layout_ids(&source_master_bytes, &rid_to_bumped_layout_id)?;
            state.new_parts.push((new_master_part.clone(), new_master_xml));

            // Rewrite master relationships
            let new_master_rels = rewrite_relationship_targets(&source_master_rels_raw, &master_rel_replacements)?;
            state.new_parts.push((relationship_part_name(&new_master_part), new_master_rels));

            state.known_masters.push(MasterInfo {
                output_master_part: new_master_part,
                master_bytes_for_cmp: source_master_bytes,
                theme_bytes_for_cmp: source_theme_bytes,
                layouts: this_master_layouts,
            });

            current_assigned_layout.ok_or_else(|| {
                WolfPptError::InvalidInput(format!(
                    "layout {source_layout_part} was not found among the master's layouts in {:?}",
                    selection.source_path
                ))
            })?
        };

        // 3. Setup the new slide
        let new_slide_part = format!("ppt/slides/slide{}.xml", state.next_slide_number);
        let new_slide_rels_part = relationship_part_name(&new_slide_part);
        state.next_slide_number += 1;
        state.existing_names.insert(new_slide_part.clone());
        state.existing_names.insert(new_slide_rels_part.clone());

        state.max_slide_id += 1;
        let slide_id = state.max_slide_id;
        state.max_rel_id += 1;
        let slide_rid = format!("rId{}", state.max_rel_id);

        state.presentation_xml = append_slide_id(&state.presentation_xml, slide_id, &slide_rid)?;
        let rel_target = format!("slides/slide{}.xml", state.next_slide_number - 1);
        state.presentation_rels = append_relationship(
            &state.presentation_rels,
            &slide_rid,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
            &rel_target,
        )?;
        state.content_types = ensure_content_type_override(
            &state.content_types,
            &format!("/{new_slide_part}"),
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        )?;

        // 4. Process slide relationships
        let mut slide_rel_replacements = BTreeMap::new();
        let mut drop_rel_ids = HashSet::new();

        for rel in &relationships {
            if is_external_rel(rel) {
                continue;
            }

            if rel.relationship_type.ends_with("/slideLayout") {
                let target = make_relative_target(&new_slide_part, &assigned_layout_part);
                slide_rel_replacements.insert(rel.id.clone(), target);
            } else if is_media_rel_type(&rel.relationship_type) {
                let target = process_media_relationship(
                    &selection.slide_part,
                    &new_slide_part,
                    rel,
                    src_archive,
                    &mut state,
                )?;
                slide_rel_replacements.insert(rel.id.clone(), target);
            } else if rel.relationship_type.ends_with("/chart") {
                let source_chart_part = resolve_target(&selection.slide_part, &rel.target);
                let chart_xml = read_archive_bytes(src_archive, &source_chart_part)?
                    .ok_or_else(|| {
                        WolfPptError::InvalidInput(format!("chart part {source_chart_part} was not found"))
                    })?;
                let new_chart_part = next_free_numbered_part(&mut state.existing_names, &source_chart_part);

                let source_chart_rels_part = relationship_part_name(&source_chart_part);
                if let Some(source_chart_rels) = read_archive_bytes(src_archive, &source_chart_rels_part)? {
                    let chart_rels = parse_relationships(&source_chart_rels);
                    let mut chart_rel_replacements = BTreeMap::new();
                    for chart_rel in &chart_rels {
                        let source_sub_part = resolve_target(&source_chart_part, &chart_rel.target);
                        if let Some(sub_part_bytes) = read_archive_bytes(src_archive, &source_sub_part)? {
                            let new_sub_part = next_free_numbered_part(&mut state.existing_names, &source_sub_part);
                            state.new_parts.push((new_sub_part.clone(), sub_part_bytes));
                            let sub_rel_target = make_relative_target(&new_chart_part, &new_sub_part);
                            chart_rel_replacements.insert(chart_rel.id.clone(), sub_rel_target);

                            if let Some(override_ct) = find_content_type_override(&src_content_types_str, &source_sub_part) {
                                state.content_types = ensure_content_type_override(
                                    &state.content_types,
                                    &format!("/{new_sub_part}"),
                                    &override_ct,
                                )?;
                            }
                            if new_sub_part.ends_with(".xlsx") {
                                state.content_types = ensure_default_content_type(
                                    &state.content_types,
                                    "xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                )?;
                            }
                            if chart_rel.relationship_type.ends_with("/chartColorStyle")
                                || chart_rel.relationship_type.ends_with("/chartcolorstyle")
                                || chart_rel.relationship_type.ends_with("/chartcolors")
                            {
                                state.content_types = ensure_content_type_override(
                                    &state.content_types,
                                    &format!("/{new_sub_part}"),
                                    "application/vnd.ms-office.chartcolorstyle+xml",
                                )?;
                            }
                            if chart_rel.relationship_type.ends_with("/chartStyle")
                                || chart_rel.relationship_type.ends_with("/chartstyle")
                            {
                                state.content_types = ensure_content_type_override(
                                    &state.content_types,
                                    &format!("/{new_sub_part}"),
                                    "application/vnd.ms-office.chartstyle+xml",
                                )?;
                            }
                        }
                    }
                    let new_chart_rels_bytes = rewrite_relationship_targets(&source_chart_rels, &chart_rel_replacements)?;
                    let new_chart_rels_part = relationship_part_name(&new_chart_part);
                    state.new_parts.push((new_chart_rels_part, new_chart_rels_bytes));
                }

                state.new_parts.push((new_chart_part.clone(), chart_xml));
                let slide_rel_target = make_relative_target(&new_slide_part, &new_chart_part);
                slide_rel_replacements.insert(rel.id.clone(), slide_rel_target);

                let chart_ct = find_content_type_override(&src_content_types_str, &source_chart_part)
                    .unwrap_or_else(|| {
                        "application/vnd.openxmlformats-officedocument.drawingml.chart+xml".to_string()
                    });
                state.content_types = ensure_content_type_override(
                    &state.content_types,
                    &format!("/{new_chart_part}"),
                    &chart_ct,
                )?;
            } else if rel.relationship_type.ends_with("/notesSlide") {
                // If output has a notes master, copy notes slide; otherwise drop the notesSlide relationship
                let has_notes_master = state.existing_names.contains("ppt/notesMasters/notesMaster1.xml");
                if has_notes_master {
                    let source_notes_part = resolve_target(&selection.slide_part, &rel.target);
                    if let Some(notes_xml) = read_archive_bytes(src_archive, &source_notes_part)? {
                        let new_notes_part = next_free_numbered_part(&mut state.existing_names, &source_notes_part);
                        let source_notes_rels_part = relationship_part_name(&source_notes_part);
                        if let Some(source_notes_rels) = read_archive_bytes(src_archive, &source_notes_rels_part)? {
                            let notes_rels = parse_relationships(&source_notes_rels);
                            let mut notes_rel_replacements = BTreeMap::new();
                            for nr in &notes_rels {
                                if nr.relationship_type.ends_with("/slide") {
                                    let back_ref = make_relative_target(&new_notes_part, &new_slide_part);
                                    notes_rel_replacements.insert(nr.id.clone(), back_ref);
                                } else if nr.relationship_type.ends_with("/notesMaster") {
                                    let master_ref = make_relative_target(&new_notes_part, "ppt/notesMasters/notesMaster1.xml");
                                    notes_rel_replacements.insert(nr.id.clone(), master_ref);
                                }
                            }
                            let new_notes_rels_bytes = rewrite_relationship_targets(&source_notes_rels, &notes_rel_replacements)?;
                            state.new_parts.push((relationship_part_name(&new_notes_part), new_notes_rels_bytes));
                        }
                        state.new_parts.push((new_notes_part.clone(), notes_xml));
                        let slide_target = make_relative_target(&new_slide_part, &new_notes_part);
                        slide_rel_replacements.insert(rel.id.clone(), slide_target);

                        let notes_ct = find_content_type_override(&src_content_types_str, &source_notes_part)
                            .unwrap_or_else(|| {
                                "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml".to_string()
                            });
                        state.content_types = ensure_content_type_override(
                            &state.content_types,
                            &format!("/{new_notes_part}"),
                            &notes_ct,
                        )?;
                    } else {
                        drop_rel_ids.insert(rel.id.clone());
                    }
                } else {
                    // Notes master is absent in output package; drop relationship to avoid dangling target
                    drop_rel_ids.insert(rel.id.clone());
                }
            } else if rel.relationship_type.ends_with("/oleObject") || rel.relationship_type.ends_with("/package") {
                let source_ole_part = resolve_target(&selection.slide_part, &rel.target);
                let ole_bytes = read_archive_bytes(src_archive, &source_ole_part)?
                    .ok_or_else(|| {
                        WolfPptError::InvalidInput(format!("OLE part {source_ole_part} was not found"))
                    })?;
                let new_ole_part = next_free_numbered_part(&mut state.existing_names, &source_ole_part);
                state.new_parts.push((new_ole_part.clone(), ole_bytes));
                let slide_rel_target = make_relative_target(&new_slide_part, &new_ole_part);
                slide_rel_replacements.insert(rel.id.clone(), slide_rel_target);

                if let Some(override_ct) = find_content_type_override(&src_content_types_str, &source_ole_part) {
                    state.content_types = ensure_content_type_override(
                        &state.content_types,
                        &format!("/{new_ole_part}"),
                        &override_ct,
                    )?;
                }
                if new_ole_part.ends_with(".bin") {
                    state.content_types = ensure_default_content_type(
                        &state.content_types,
                        "bin",
                        "application/vnd.openxmlformats-officedocument.oleObject",
                    )?;
                }
            } else if rel.relationship_type.ends_with("/comments") || rel.relationship_type.ends_with("/comment") {
                let source_comment_part = resolve_target(&selection.slide_part, &rel.target);
                let comment_xml = read_archive_bytes(src_archive, &source_comment_part)?
                    .ok_or_else(|| {
                        WolfPptError::InvalidInput(format!("comment part {source_comment_part} was not found"))
                    })?;
                let new_comment_part = next_free_numbered_part(&mut state.existing_names, &source_comment_part);
                state.new_parts.push((new_comment_part.clone(), comment_xml));
                let slide_rel_target = make_relative_target(&new_slide_part, &new_comment_part);
                slide_rel_replacements.insert(rel.id.clone(), slide_rel_target);

                let comment_ct = find_content_type_override(&src_content_types_str, &source_comment_part)
                    .unwrap_or_else(|| {
                        "application/vnd.openxmlformats-officedocument.presentationml.comments+xml".to_string()
                    });
                state.content_types = ensure_content_type_override(
                    &state.content_types,
                    &format!("/{new_comment_part}"),
                    &comment_ct,
                )?;
            } else if rel.relationship_type.ends_with("/slide") {
                // Internal hyperlink: pass through as-is
            } else {
                return Err(WolfPptError::InvalidInput(format!(
                    "cannot import slide relationship type {} without an explicit copy policy",
                    rel.relationship_type
                )));
            }
        }

        let new_slide_rels_bytes = rewrite_and_filter_relationships(
            &source_slide_rels_raw,
            &slide_rel_replacements,
            &drop_rel_ids,
        )?;

        state.new_parts.push((new_slide_part.clone(), source_slide_xml));
        state.new_parts.push((new_slide_rels_part, new_slide_rels_bytes));
        state.summary.slides_added += 1;
        state.summary.slide_parts.push(new_slide_part);
    }

    // 5. Write the assembled package atomically
    #[cfg(not(target_os = "wasi"))]
    let temp_output_path = match output_path.parent() {
        Some(parent) if !parent.as_os_str().is_empty() => {
            parent.join(format!(".tmp_assemble_{}.pptx", std::process::id()))
        }
        _ => PathBuf::from(format!(".tmp_assemble_{}.pptx", std::process::id())),
    };
    // WASI preview 1 has no process ids: a draw from std's randomly keyed hasher (seeded from
    // the host's `random_get`) keeps concurrent assemblies apart instead.
    #[cfg(target_os = "wasi")]
    let temp_output_path = {
        use std::hash::BuildHasher;
        let token = std::collections::hash_map::RandomState::new().hash_one(output_path) as u32;
        match output_path.parent() {
            Some(parent) if !parent.as_os_str().is_empty() => {
                parent.join(format!(".tmp_assemble_{token}.pptx"))
            }
            _ => PathBuf::from(format!(".tmp_assemble_{token}.pptx")),
        }
    };

    {
        let output_file = File::create(&temp_output_path)?;
        let mut writer = zip::ZipWriter::new(output_file);

        for index in 0..base_archive.len() {
            let file = base_archive.by_index(index)?;
            let name = file.name()?.into_owned();
            let options = SimpleFileOptions::default().compression_method(file.compression());
            if file.is_dir() {
                writer.add_directory(name, options)?;
                continue;
            }
            match name.as_str() {
                "ppt/presentation.xml" => {
                    writer.start_file(name, options)?;
                    std::io::copy(&mut Cursor::new(&state.presentation_xml), &mut writer)?;
                }
                "ppt/_rels/presentation.xml.rels" => {
                    writer.start_file(name, options)?;
                    std::io::copy(&mut Cursor::new(&state.presentation_rels), &mut writer)?;
                }
                "[Content_Types].xml" => {
                    writer.start_file(name, options)?;
                    std::io::copy(&mut Cursor::new(state.content_types.as_bytes()), &mut writer)?;
                }
                _ => {
                    writer.raw_copy_file(file)?;
                }
            }
        }

        let deflated_options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
        for (part_name, content) in state.new_parts {
            writer.start_file(part_name, deflated_options)?;
            std::io::copy(&mut Cursor::new(&content), &mut writer)?;
        }

        writer.finish()?;
    }

    std::fs::rename(&temp_output_path, output_path)?;

    Ok(state.summary)
}

fn is_media_rel_type(rel_type: &str) -> bool {
    rel_type.ends_with("/image")
        || rel_type.ends_with("/audio")
        || rel_type.ends_with("/video")
        || rel_type.ends_with("/media")
}

fn is_external_rel(rel: &RelationshipSummary) -> bool {
    rel.target_mode
        .as_deref()
        .map(|m| m.eq_ignore_ascii_case("External"))
        .unwrap_or(false)
}

fn process_media_relationship<R: Read + std::io::Seek>(
    referring_source_part: &str,
    referring_new_part: &str,
    rel: &RelationshipSummary,
    src_archive: &mut ZipArchive<R>,
    state: &mut AssemblyState,
) -> Result<String, WolfPptError> {
    let source_media_part = resolve_target(referring_source_part, &rel.target);
    let media_bytes = read_archive_bytes(src_archive, &source_media_part)?
        .ok_or_else(|| WolfPptError::InvalidInput(format!("media part {source_media_part} was not found")))?;

    let mut hasher = Sha256::new();
    hasher.update(&media_bytes);
    let hash: [u8; 32] = hasher.finalize().into();

    let target_part = if let Some(existing_part) = state.media_cache.get(&hash) {
        state.summary.media_reused += 1;
        existing_part.clone()
    } else {
        state.summary.media_added += 1;
        let new_part = next_free_numbered_part(&mut state.existing_names, &source_media_part);
        state.media_cache.insert(hash, new_part.clone());
        state.new_parts.push((new_part.clone(), media_bytes));

        if let Some(pos) = new_part.rfind('.') {
            let ext = &new_part[pos + 1..];
            state.content_types = ensure_default_for_media_ext(&state.content_types, ext)?;
        }
        new_part
    };

    Ok(make_relative_target(referring_new_part, &target_part))
}

fn ensure_default_for_media_ext(content_types: &str, ext: &str) -> Result<String, WolfPptError> {
    let ext_lower = ext.to_ascii_lowercase();
    let default_ct = match ext_lower.as_str() {
        "png" => "image/png",
        "jpeg" | "jpg" => "image/jpeg",
        "gif" => "image/gif",
        "bmp" => "image/bmp",
        "svg" => "image/svg+xml",
        "tiff" | "tif" => "image/tiff",
        "emf" => "image/x-emf",
        "wmf" => "image/x-wmf",
        "mp4" => "video/mp4",
        "mp3" => "audio/mpeg",
        "wav" => "audio/wav",
        "m4a" => "audio/mp4",
        "avi" => "video/x-msvideo",
        "wmv" => "video/x-ms-wmv",
        "wma" => "audio/x-ms-wma",
        _ => "application/octet-stream",
    };
    ensure_default_content_type(content_types, &ext_lower, default_ct)
}

fn append_master_id(
    xml: &[u8],
    master_id: u64,
    relationship_id: &str,
) -> Result<Vec<u8>, WolfPptError> {
    let entry = format!(r#"<p:sldMasterId id="{master_id}" r:id="{relationship_id}"/>"#);
    let text = String::from_utf8_lossy(xml);
    if text.contains("</p:sldMasterIdLst>") {
        return insert_before(xml, "</p:sldMasterIdLst>", &entry);
    }
    if let Some((start, end)) = self_closing_master_id_list_span(xml)? {
        let mut output = Vec::with_capacity(xml.len() + entry.len() + b"</p:sldMasterIdLst>".len() - 1);
        output.extend_from_slice(&xml[..start]);
        output.extend_from_slice(&xml[start..end - 2]);
        output.push(b'>');
        output.extend_from_slice(entry.as_bytes());
        output.extend_from_slice(b"</p:sldMasterIdLst>");
        output.extend_from_slice(&xml[end..]);
        return Ok(output);
    }
    let list = format!(r#"<p:sldMasterIdLst>{entry}</p:sldMasterIdLst>"#);
    if text.contains("<p:sldIdLst") {
        return insert_before(xml, "<p:sldIdLst", &list);
    }
    for marker in ["<p:sldSz", "<p:notesSz", "<p:defaultTextStyle"] {
        if text.contains(marker) {
            return insert_before(xml, marker, &list);
        }
    }
    insert_before(xml, "</p:presentation>", &list)
}

fn self_closing_master_id_list_span(xml: &[u8]) -> Result<Option<(usize, usize)>, WolfPptError> {
    let bom = utf8_bom_offset(xml);
    let mut reader = Reader::from_reader(xml);
    loop {
        let start = bom + reader.buffer_position() as usize;
        match reader.read_event()? {
            Event::Empty(event) if event.name().as_ref().as_bytes() == b"p:sldMasterIdLst" => {
                let end = bom + reader.buffer_position() as usize;
                return Ok(Some((start, end)));
            }
            Event::Eof => return Ok(None),
            _ => {}
        }
    }
}

fn rewrite_master_layout_ids(
    master_xml: &[u8],
    rid_to_layout_id: &BTreeMap<String, u64>,
) -> Result<Vec<u8>, WolfPptError> {
    let mut reader = Reader::from_reader(master_xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(master_xml.len())));
    loop {
        match reader.read_event()? {
            Event::Eof => break,
            Event::Empty(event) if local_name(event.name().as_ref().as_bytes()) == b"sldLayoutId" => {
                let rid = event
                    .attributes()
                    .flatten()
                    .find(|attr| {
                        let key = attr.key.as_ref().as_bytes();
                        key == b"r:id" || (key.ends_with(b":id") && key != b"id")
                    })
                    .and_then(|attr| attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).ok())
                    .map(|v| v.into_owned())
                    .unwrap_or_default();
                if let Some(&new_id) = rid_to_layout_id.get(&rid) {
                    let rewritten = rewrite_event_attributes(&event, &[("id", new_id.to_string())]);
                    writer.write_event(Event::Empty(rewritten))?;
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::Start(event) if local_name(event.name().as_ref().as_bytes()) == b"sldLayoutId" => {
                let rid = event
                    .attributes()
                    .flatten()
                    .find(|attr| {
                        let key = attr.key.as_ref().as_bytes();
                        key == b"r:id" || (key.ends_with(b":id") && key != b"id")
                    })
                    .and_then(|attr| attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).ok())
                    .map(|v| v.into_owned())
                    .unwrap_or_default();
                if let Some(&new_id) = rid_to_layout_id.get(&rid) {
                    let rewritten = rewrite_event_attributes(&event, &[("id", new_id.to_string())]);
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

fn rewrite_and_filter_relationships(
    rels_xml: &[u8],
    replacements: &BTreeMap<String, String>,
    drop_ids: &HashSet<String>,
) -> Result<Vec<u8>, WolfPptError> {
    if replacements.is_empty() && drop_ids.is_empty() {
        return Ok(rels_xml.to_vec());
    }
    let mut reader = Reader::from_reader(rels_xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(rels_xml.len())));
    loop {
        match reader.read_event()? {
            Event::Eof => break,
            Event::Empty(event) if local_name(event.name().as_ref().as_bytes()) == b"Relationship" => {
                let id = event
                    .attributes()
                    .flatten()
                    .find(|attr| local_name(attr.key.as_ref().as_bytes()) == b"Id")
                    .and_then(|attr| attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).ok())
                    .map(|v| v.into_owned())
                    .unwrap_or_default();
                if drop_ids.contains(&id) {
                    continue;
                }
                if let Some(new_target) = replacements.get(&id) {
                    let rewritten =
                        rewrite_event_attributes(&event, &[("Target", new_target.clone())]);
                    writer.write_event(Event::Empty(rewritten))?;
                } else {
                    writer.write_event(Event::Empty(event))?;
                }
            }
            Event::Start(event) if local_name(event.name().as_ref().as_bytes()) == b"Relationship" => {
                let id = event
                    .attributes()
                    .flatten()
                    .find(|attr| local_name(attr.key.as_ref().as_bytes()) == b"Id")
                    .and_then(|attr| attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).ok())
                    .map(|v| v.into_owned())
                    .unwrap_or_default();
                if drop_ids.contains(&id) {
                    let mut depth = 1usize;
                    loop {
                        match reader.read_event()? {
                            Event::Start(_) => depth += 1,
                            Event::End(_) => {
                                depth -= 1;
                                if depth == 0 {
                                    break;
                                }
                            }
                            Event::Eof => break,
                            _ => {}
                        }
                    }
                    continue;
                }
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

fn find_max_slide_id(xml: &[u8]) -> u64 {
    let mut max_id: u64 = 255;
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    loop {
        match reader.read_event() {
            Ok(Event::Empty(event)) | Ok(Event::Start(event))
                if local_name(event.name().as_ref().as_bytes()) == b"sldId" =>
            {
                for attr in event.attributes().flatten() {
                    if local_name(attr.key.as_ref().as_bytes()) == b"id" {
                        if let Ok(v) = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                            if let Ok(id) = v.parse::<u64>() {
                                max_id = max_id.max(id);
                            }
                        }
                    }
                }
            }
            Ok(Event::Eof) | Err(_) => break,
            _ => {}
        }
    }
    max_id
}

fn find_max_master_or_layout_id<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    presentation_xml: &[u8],
) -> Result<u64, WolfPptError> {
    let mut max_id: u64 = 2147483647;

    let mut reader = Reader::from_reader(presentation_xml);
    reader.config_mut().trim_text(true);
    loop {
        match reader.read_event() {
            Ok(Event::Empty(e)) | Ok(Event::Start(e))
                if local_name(e.name().as_ref().as_bytes()) == b"sldMasterId" =>
            {
                for attr in e.attributes().flatten() {
                    if local_name(attr.key.as_ref().as_bytes()) == b"id" {
                        if let Ok(v) = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                            if let Ok(id) = v.parse::<u64>() {
                                max_id = max_id.max(id);
                            }
                        }
                    }
                }
            }
            Ok(Event::Eof) | Err(_) => break,
            _ => {}
        }
    }

    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name()?.into_owned();
        if name.starts_with("ppt/slideMasters/slideMaster") && name.ends_with(".xml") {
            if let Some(master_bytes) = read_archive_bytes(archive, &name)? {
                let mut reader = Reader::from_reader(master_bytes.as_slice());
                reader.config_mut().trim_text(true);
                loop {
                    match reader.read_event() {
                        Ok(Event::Empty(e)) | Ok(Event::Start(e))
                            if local_name(e.name().as_ref().as_bytes()) == b"sldLayoutId" =>
                        {
                            for attr in e.attributes().flatten() {
                                if attr.key.as_ref().as_bytes() == b"id" {
                                    if let Ok(v) = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                                        if let Ok(id) = v.parse::<u64>() {
                                            max_id = max_id.max(id);
                                        }
                                    }
                                }
                            }
                        }
                        Ok(Event::Eof) | Err(_) => break,
                        _ => {}
                    }
                }
            }
        }
    }

    Ok(max_id)
}

fn find_max_rel_id(xml: &[u8]) -> u64 {
    let relationships = parse_relationships(xml);
    relationships
        .iter()
        .filter_map(|rel| rel.id.strip_prefix("rId")?.parse::<u64>().ok())
        .max()
        .unwrap_or(0)
}
