/// Check if a relationship is internal (TargetMode is absent or case-insensitively "Internal")
fn is_internal_relationship(target_mode: &Option<String>) -> bool {
    target_mode.is_none()
        || target_mode
            .as_deref()
            .map(|mode| mode.eq_ignore_ascii_case("Internal"))
            .unwrap_or(false)
}

pub fn delete_slides(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    target_slide_parts: &[&str],
    ordered_survivor_parts: Option<&[&str]>,
) -> Result<SlideDeleteSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    if target_slide_parts.is_empty() {
        return Err(WolfPptError::InvalidInput(
            "no target slide parts specified for deletion".to_string(),
        ));
    }

    let mut target_set = std::collections::HashSet::new();
    for part in target_slide_parts {
        if !target_set.insert(*part) {
            return Err(WolfPptError::InvalidInput(format!(
                "duplicate target slide part specified for deletion: {part}"
            )));
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let slide_parts = slide_parts(&mut archive)?;
    for part in target_slide_parts {
        if !slide_parts.iter().any(|p| p == *part) {
            return Err(WolfPptError::InvalidInput(format!(
                "target slide part {part} was not found in the presentation"
            )));
        }
    }

    if target_set.len() == slide_parts.len() {
        return Err(WolfPptError::InvalidInput(
            "cannot delete all slides; presentation must contain at least one slide".to_string(),
        ));
    }

    let all_survivors: Vec<&str> = slide_parts
        .iter()
        .map(|s| s.as_str())
        .filter(|s| !target_set.contains(*s))
        .collect();

    let presentation_rels_xml = {
        let mut file = archive.by_name("ppt/_rels/presentation.xml.rels")?;
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        payload
    };
    let relationships = parse_relationships(&presentation_rels_xml);
    let mut slide_rel_by_part: BTreeMap<String, String> = BTreeMap::new();
    for rel in &relationships {
        if rel.relationship_type.ends_with("/slide") {
            let resolved = resolve_target("ppt/presentation.xml", &rel.target);
            slide_rel_by_part.insert(resolved, rel.id.clone());
        }
    }

    let mut deleted_relationship_ids = std::collections::HashSet::new();
    for part in target_slide_parts {
        if let Some(rel_id) = slide_rel_by_part.get(*part) {
            deleted_relationship_ids.insert(rel_id.clone());
        } else {
            return Err(WolfPptError::InvalidInput(format!(
                "presentation relationship for slide part {part} was not found"
            )));
        }
    }

    let ordered_survivor_relationship_ids: Option<Vec<String>> =
        if let Some(order) = ordered_survivor_parts {
            if order.len() != all_survivors.len() {
                return Err(WolfPptError::InvalidInput(format!(
                    "ordered survivor parts count ({}) does not match surviving slides count ({})",
                    order.len(),
                    all_survivors.len()
                )));
            }
            let mut seen_survivors = std::collections::HashSet::new();
            let mut ids = Vec::new();
            for part in order {
                if target_set.contains(part) {
                    return Err(WolfPptError::InvalidInput(format!(
                        "deleted slide part {part} cannot be included in ordered survivors"
                    )));
                }
                if !seen_survivors.insert(*part) {
                    return Err(WolfPptError::InvalidInput(format!(
                        "duplicate survivor slide part in ordered survivors: {part}"
                    )));
                }
                let rel_id = slide_rel_by_part.get(*part).ok_or_else(|| {
                    WolfPptError::InvalidInput(format!(
                        "survivor slide part {part} was not found in the presentation"
                    ))
                })?;
                ids.push(rel_id.clone());
            }
            Some(ids)
        } else {
            None
        };

    // Reachability graph over all parts in the package
    let mut part_rels: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name()?.into_owned();
        if name.ends_with(".rels") {
            let source_part = if name == "_rels/.rels" {
                "".to_string()
            } else {
                let without_rels = name.trim_end_matches(".rels");
                let mut segments: Vec<&str> = without_rels.split('/').collect();
                if let Some(pos) = segments.iter().rposition(|&s| s == "_rels") {
                    segments.remove(pos);
                    segments.join("/")
                } else {
                    without_rels.to_string()
                }
            };

            let rels_xml = {
                let mut file = archive.by_index(index)?;
                let mut payload = Vec::new();
                file.read_to_end(&mut payload)?;
                payload
            };

            let rels = parse_relationships(&rels_xml);
            let mut targets = Vec::new();
            for rel in rels {
                if is_internal_relationship(&rel.target_mode) && !rel.target.is_empty() {
                    let resolved = if source_part.is_empty() {
                        rel.target.trim_start_matches('/').to_string()
                    } else {
                        resolve_target(&source_part, &rel.target)
                    };
                    targets.push(resolved);
                }
            }
            part_rels.insert(source_part, targets);
        }
    }

    // 1. Compute deleted slide closure: descendants reachable from target slides
    let mut deleted_closure: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut del_queue: std::collections::VecDeque<String> = std::collections::VecDeque::new();
    for target in target_slide_parts {
        let t = target.to_string();
        deleted_closure.insert(t.clone());
        del_queue.push_back(t);
    }
    while let Some(curr) = del_queue.pop_front() {
        if let Some(targets) = part_rels.get(&curr) {
            for target in targets {
                if deleted_closure.insert(target.clone()) {
                    del_queue.push_back(target.clone());
                }
            }
        }
    }

    // 2. Compute survivor reachability from package roots and surviving slides
    let mut survivor_reachable: std::collections::HashSet<String> =
        std::collections::HashSet::new();
    let mut surv_queue: std::collections::VecDeque<String> = std::collections::VecDeque::new();

    // Package roots
    for root in &["", "ppt/presentation.xml"] {
        let root_str = root.to_string();
        if survivor_reachable.insert(root_str.clone()) {
            surv_queue.push_back(root_str);
        }
    }

    // Surviving slides are roots
    for survivor in &all_survivors {
        let s = survivor.to_string();
        if survivor_reachable.insert(s.clone()) {
            surv_queue.push_back(s);
        }
    }

    while let Some(curr) = surv_queue.pop_front() {
        if let Some(targets) = part_rels.get(&curr) {
            for target in targets {
                if !target_set.contains(target.as_str())
                    && survivor_reachable.insert(target.clone())
                {
                    surv_queue.push_back(target.clone());
                }
            }
        }
    }

    let mut parts_to_remove: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut rels_parts_to_remove: std::collections::HashSet<String> =
        std::collections::HashSet::new();
    let mut deleted_content_type_overrides: std::collections::HashSet<String> =
        std::collections::HashSet::new();

    // Only target slides and their unshared descendants in the deleted closure are removed.
    // Pre-existing unreachable or unknown parts are NEVER removed.
    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name()?.into_owned();
        if name.ends_with(".rels") {
            continue;
        }
        if name == "[Content_Types].xml" {
            continue;
        }

        if (target_set.contains(name.as_str()) || deleted_closure.contains(&name))
            && !survivor_reachable.contains(&name)
        {
            parts_to_remove.insert(name.clone());
            rels_parts_to_remove.insert(relationship_part_name(&name));
            deleted_content_type_overrides.insert(format!("/{name}"));
        }
    }
    let presentation_xml = {
        let mut file = archive.by_name("ppt/presentation.xml")?;
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        payload
    };
    let rewritten_presentation_xml = rewrite_presentation_xml_for_slide_deletion(
        &presentation_xml,
        &deleted_relationship_ids,
        ordered_survivor_relationship_ids.as_deref(),
    )?;
    let rewritten_presentation_rels = rewrite_relationships_for_slide_deletion(
        &presentation_rels_xml,
        &deleted_relationship_ids,
    )?;

    let content_types_xml = {
        let mut file = archive.by_name("[Content_Types].xml")?;
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        payload
    };
    let rewritten_content_types = rewrite_content_types_for_slide_deletion(
        &content_types_xml,
        &deleted_content_type_overrides,
    )?;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut part_count = 0;
    let mut has_vba = false;

    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name()?.into_owned();

        if parts_to_remove.contains(&name) {
            continue;
        }
        if rels_parts_to_remove.contains(&name) {
            continue;
        }

        update_package_facts(&name, &mut part_count, &mut has_vba);
        let options = SimpleFileOptions::default().compression_method(file.compression());

        if name == "ppt/presentation.xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(&rewritten_presentation_xml), &mut writer)?;
        } else if name == "ppt/_rels/presentation.xml.rels" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(&rewritten_presentation_rels), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(&rewritten_content_types), &mut writer)?;
        } else {
            writer.start_file(name, options)?;
            std::io::copy(&mut file, &mut writer)?;
        }
    }
    writer.finish()?;

    let survivor_count = all_survivors.len();
    let mut deleted_parts_vec: Vec<String> =
        target_slide_parts.iter().map(|s| s.to_string()).collect();
    deleted_parts_vec.sort();
    let mut deleted_rel_ids_vec: Vec<String> = deleted_relationship_ids.into_iter().collect();
    deleted_rel_ids_vec.sort();

    Ok(SlideDeleteSummary {
        path: output_path.to_path_buf(),
        deleted_slide_parts: deleted_parts_vec,
        deleted_relationship_ids: deleted_rel_ids_vec,
        survivor_count,
        part_count,
        has_vba,
    })
}

pub fn delete_slide(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    target_slide_part: &str,
) -> Result<SlideDeleteSummary, WolfPptError> {
    delete_slides(input_path, output_path, &[target_slide_part], None)
}

/// Rewrite `ppt/presentation.xml` after deleting slides.
///
/// Only the root `p:presentation/p:sldIdLst` names slides by relationship and is
/// filtered and reordered here. Every other `sldIdLst` (the `p14:section`
/// membership lists inside `p:extLst`) names slides by presentation slide id;
/// those keep every section and every surviving member and drop only the ids of
/// the deleted slides.
fn rewrite_presentation_xml_for_slide_deletion(
    xml: &[u8],
    deleted_relationship_ids: &std::collections::HashSet<String>,
    ordered_survivor_relationship_ids: Option<&[String]>,
) -> Result<Vec<u8>, WolfPptError> {
    let deleted_slide_ids = deleted_presentation_slide_ids(xml, deleted_relationship_ids)?;
    let mut reader = Reader::from_reader(xml);
    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(xml.len())));
    // Depth of the innermost open element; the document element is depth 1.
    let mut depth: usize = 0;
    let mut in_root_list = false;
    let mut member_list_depth: Option<usize> = None;
    let mut survivor_entries: Vec<(String, Vec<Event<'static>>)> = Vec::new();
    loop {
        match reader.read_event()? {
            Event::Start(start) => {
                depth += 1;
                let qname = start.name();
                let name = local_name(qname.as_ref().as_bytes());
                if name == b"sldIdLst" {
                    if depth == 2 {
                        in_root_list = true;
                    } else {
                        member_list_depth = Some(depth);
                    }
                } else if name == b"sldId" && in_root_list && depth == 3 {
                    let rel_id = extract_rel_id_from_attributes(&start);
                    let mut events = vec![Event::Start(start.into_owned())];
                    read_element_body(&mut reader, Some(&mut events))?;
                    depth -= 1;
                    if !deleted_relationship_ids.contains(&rel_id) {
                        survivor_entries.push((rel_id, events));
                    }
                    continue;
                } else if name == b"sldId"
                    && member_list_depth == Some(depth - 1)
                    && is_deleted_member(&start, &deleted_slide_ids)
                {
                    read_element_body(&mut reader, None)?;
                    depth -= 1;
                    continue;
                }
                writer.write_event(Event::Start(start.into_owned()))?;
            }
            Event::Empty(empty) => {
                let qname = empty.name();
                let name = local_name(qname.as_ref().as_bytes());
                if name == b"sldId" && in_root_list && depth == 2 {
                    let rel_id = extract_rel_id_from_attributes(&empty);
                    if !deleted_relationship_ids.contains(&rel_id) {
                        survivor_entries.push((rel_id, vec![Event::Empty(empty.into_owned())]));
                    }
                    continue;
                }
                if name == b"sldId"
                    && member_list_depth == Some(depth)
                    && is_deleted_member(&empty, &deleted_slide_ids)
                {
                    continue;
                }
                writer.write_event(Event::Empty(empty.into_owned()))?;
            }
            Event::End(end) => {
                if in_root_list && depth == 2 {
                    let survivors = std::mem::take(&mut survivor_entries);
                    if let Some(ordered_ids) = ordered_survivor_relationship_ids {
                        let mut entries_by_id: BTreeMap<String, Vec<Event<'static>>> =
                            survivors.into_iter().collect();
                        for id in ordered_ids {
                            if let Some(events) = entries_by_id.remove(id) {
                                for ev in events {
                                    writer.write_event(ev)?;
                                }
                            }
                        }
                    } else {
                        for (_, events) in survivors {
                            for ev in events {
                                writer.write_event(ev)?;
                            }
                        }
                    }
                    in_root_list = false;
                }
                if member_list_depth == Some(depth) {
                    member_list_depth = None;
                }
                depth = depth.saturating_sub(1);
                writer.write_event(Event::End(end.into_owned()))?;
            }
            Event::Eof => break,
            other => writer.write_event(other.into_owned())?,
        }
    }
    Ok(writer.into_inner().into_inner())
}

/// Presentation slide ids (`p:sldId/@id`) of the slides whose relationships are deleted.
fn deleted_presentation_slide_ids(
    xml: &[u8],
    deleted_relationship_ids: &std::collections::HashSet<String>,
) -> Result<std::collections::HashSet<String>, WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    let mut depth: usize = 0;
    let mut in_root_list = false;
    let mut ids = std::collections::HashSet::new();
    loop {
        let (start, element_depth, has_children) = match reader.read_event()? {
            Event::Start(start) => {
                depth += 1;
                (start, depth, true)
            }
            Event::Empty(empty) => (empty, depth + 1, false),
            Event::End(_) => {
                if depth == 2 {
                    in_root_list = false;
                }
                depth = depth.saturating_sub(1);
                continue;
            }
            Event::Eof => break,
            _ => continue,
        };
        let qname = start.name();
        let name = local_name(qname.as_ref().as_bytes());
        if name == b"sldIdLst" && element_depth == 2 {
            in_root_list = has_children;
        } else if name == b"sldId" && in_root_list && element_depth == 3 {
            let rel_id = extract_rel_id_from_attributes(&start);
            if deleted_relationship_ids.contains(&rel_id) {
                if let Some(id) = slide_id_attribute(&start) {
                    ids.insert(id);
                }
            }
        }
    }
    Ok(ids)
}

fn slide_id_attribute(
    event: &quick_xml::events::BytesStart<'_>,
) -> Option<String> {
    event
        .attributes()
        .flatten()
        .find(|attr| attr.key.as_ref().as_bytes() == b"id")
        .and_then(|attr| attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).ok())
        .map(|value| value.trim().to_string())
}

fn is_deleted_member(
    event: &quick_xml::events::BytesStart<'_>,
    deleted_slide_ids: &std::collections::HashSet<String>,
) -> bool {
    slide_id_attribute(event).is_some_and(|id| deleted_slide_ids.contains(&id))
}

/// Consume the rest of an element whose start tag was just read, optionally
/// capturing its events (through the matching end tag).
fn read_element_body(
    reader: &mut Reader<&[u8]>,
    mut captured: Option<&mut Vec<Event<'static>>>,
) -> Result<(), WolfPptError> {
    let mut depth = 1;
    loop {
        let event = reader.read_event()?;
        match &event {
            Event::Start(_) => depth += 1,
            Event::End(_) => depth -= 1,
            Event::Eof => return Ok(()),
            _ => {}
        }
        if let Some(events) = captured.as_deref_mut() {
            events.push(event.into_owned());
        }
        if depth == 0 {
            return Ok(());
        }
    }
}

fn extract_rel_id_from_attributes(
    event: &quick_xml::events::BytesStart<'_>,
) -> String {
    for attr in event.attributes().flatten() {
        let key = attr.key.as_ref().as_bytes();
        if key == b"r:id" || (key.ends_with(b":id") && key != b"id") {
            if let Ok(val) = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0) {
                return val.into_owned();
            }
        }
    }
    String::new()
}

fn rewrite_relationships_for_slide_deletion(
    xml: &[u8],
    deleted_relationship_ids: &std::collections::HashSet<String>,
) -> Result<Vec<u8>, WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(xml.len())));
    let mut skipping = false;
    let mut skip_depth = 0;

    loop {
        let event = reader.read_event()?;
        if skipping {
            match event {
                Event::Start(_) => skip_depth += 1,
                Event::End(_) => {
                    skip_depth -= 1;
                    if skip_depth == 0 {
                        skipping = false;
                    }
                }
                _ => {}
            }
            continue;
        }

        match event {
            Event::Start(start) => {
                let qname = start.name();
                let name = local_name(qname.as_ref().as_bytes());
                if name == b"Relationship" {
                    let mut id = String::new();
                    for attr in start.attributes().flatten() {
                        if local_name(attr.key.as_ref().as_bytes()) == b"Id" {
                            id = attr
                                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                                .map(|v| v.into_owned())
                                .unwrap_or_default();
                            break;
                        }
                    }
                    if deleted_relationship_ids.contains(&id) {
                        skipping = true;
                        skip_depth = 1;
                        continue;
                    }
                }
                writer.write_event(Event::Start(start.into_owned()))?;
            }
            Event::Empty(empty) => {
                let qname = empty.name();
                let name = local_name(qname.as_ref().as_bytes());
                if name == b"Relationship" {
                    let mut id = String::new();
                    for attr in empty.attributes().flatten() {
                        if local_name(attr.key.as_ref().as_bytes()) == b"Id" {
                            id = attr
                                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                                .map(|v| v.into_owned())
                                .unwrap_or_default();
                            break;
                        }
                    }
                    if deleted_relationship_ids.contains(&id) {
                        continue;
                    }
                }
                writer.write_event(Event::Empty(empty.into_owned()))?;
            }
            Event::Eof => break,
            other => writer.write_event(other.into_owned())?,
        }
    }
    Ok(writer.into_inner().into_inner())
}

fn rewrite_content_types_for_slide_deletion(
    xml: &[u8],
    deleted_content_type_overrides: &std::collections::HashSet<String>,
) -> Result<Vec<u8>, WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(xml.len())));
    let mut skipping_depth: usize = 0;

    loop {
        let event = reader.read_event()?;
        if skipping_depth > 0 {
            match &event {
                Event::Start(_) => skipping_depth += 1,
                Event::End(_) => skipping_depth = skipping_depth.saturating_sub(1),
                _ => {}
            }
            continue;
        }

        match event {
            Event::Start(start) => {
                let qname = start.name();
                let name = local_name(qname.as_ref().as_bytes());
                if name == b"Override" {
                    let mut part_name = String::new();
                    for attr in start.attributes().flatten() {
                        if local_name(attr.key.as_ref().as_bytes()) == b"PartName" {
                            part_name = attr
                                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                                .map(|v| v.into_owned())
                                .unwrap_or_default();
                            break;
                        }
                    }
                    if deleted_content_type_overrides.contains(&part_name) {
                        skipping_depth = 1;
                        continue;
                    }
                }
                writer.write_event(Event::Start(start.into_owned()))?;
            }
            Event::Empty(empty) => {
                let qname = empty.name();
                let name = local_name(qname.as_ref().as_bytes());
                if name == b"Override" {
                    let mut part_name = String::new();
                    for attr in empty.attributes().flatten() {
                        if local_name(attr.key.as_ref().as_bytes()) == b"PartName" {
                            part_name = attr
                                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                                .map(|v| v.into_owned())
                                .unwrap_or_default();
                            break;
                        }
                    }
                    if deleted_content_type_overrides.contains(&part_name) {
                        continue;
                    }
                }
                writer.write_event(Event::Empty(empty.into_owned()))?;
            }
            Event::Eof => break,
            other => writer.write_event(other.into_owned())?,
        }
    }
    Ok(writer.into_inner().into_inner())
}
