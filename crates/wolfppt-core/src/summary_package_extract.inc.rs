fn read_relationships<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    part_name: &str,
) -> Result<Vec<RelationshipSummary>, WolfPptError> {
    let rels_part = relationship_part_name(part_name);
    let Ok(mut file) = archive.by_name(&rels_part) else {
        return Ok(Vec::new());
    };
    let mut xml = Vec::new();
    file.read_to_end(&mut xml)?;
    Ok(parse_relationships(&xml))
}

fn read_notes<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_part: &str,
    relationships: &[RelationshipSummary],
) -> Result<Vec<String>, WolfPptError> {
    let Some(notes_rel) = relationships
        .iter()
        .find(|rel| rel.relationship_type.ends_with("/notesSlide"))
    else {
        return Ok(Vec::new());
    };
    let notes_part = resolve_target(slide_part, &notes_rel.target);
    let Ok(mut file) = archive.by_name(&notes_part) else {
        return Ok(Vec::new());
    };
    let mut xml = Vec::new();
    file.read_to_end(&mut xml)?;
    Ok(extract_text_runs(&xml))
}

fn image_targets_for_relationship<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    relationship_id: &str,
) -> Result<Vec<String>, WolfPptError> {
    let mut targets = Vec::new();
    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name().to_string();
        if !is_slide_part(&name) {
            continue;
        }
        for rel in read_relationships(archive, &name)? {
            if rel.id == relationship_id && rel.relationship_type.ends_with("/image") {
                targets.push(resolve_target(&name, &rel.target));
            }
        }
    }
    targets.sort();
    targets.dedup();
    Ok(targets)
}

fn image_targets_for_relationship_at_index<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_index: usize,
    relationship_id: &str,
) -> Result<Vec<String>, WolfPptError> {
    let Some(slide_part) = slide_part_at_index(archive, slide_index)? else {
        return Ok(Vec::new());
    };
    let mut targets = Vec::new();
    for rel in read_relationships(archive, &slide_part)? {
        if rel.id == relationship_id && rel.relationship_type.ends_with("/image") {
            targets.push(resolve_target(&slide_part, &rel.target));
        }
    }
    targets.sort();
    targets.dedup();
    Ok(targets)
}

fn slide_part_at_index<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_index: usize,
) -> Result<Option<String>, WolfPptError> {
    let slides = slide_parts(archive)?;
    Ok(slides.into_iter().nth(slide_index))
}

fn slide_parts<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
) -> Result<Vec<String>, WolfPptError> {
    let mut slides = Vec::new();
    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name().to_string();
        if is_slide_part(&name) {
            slides.push(name);
        }
    }
    slides.sort_by_key(|part| natural_key(part));

    let Some(presentation_xml) = read_archive_text(archive, "ppt/presentation.xml")? else {
        return Ok(slides);
    };
    let relationship_ids = slide_relationship_ids_in_presentation(presentation_xml.as_bytes())?;
    let relationships = read_relationships(archive, "ppt/presentation.xml")?;
    let slide_relationships: BTreeMap<String, String> = relationships
        .into_iter()
        .filter(|relationship| relationship.relationship_type.ends_with("/slide"))
        .map(|relationship| {
            (
                relationship.id,
                resolve_target("ppt/presentation.xml", &relationship.target),
            )
        })
        .collect();
    let ordered: Vec<String> = relationship_ids
        .iter()
        .filter_map(|relationship_id| slide_relationships.get(relationship_id).cloned())
        .collect();
    let unique_ordered_parts: std::collections::BTreeSet<&String> =
        ordered.iter().collect();
    if ordered.len() == slides.len()
        && unique_ordered_parts.len() == slides.len()
        && ordered.iter().all(|part| slides.contains(part))
    {
        return Ok(ordered);
    }
    Ok(slides)
}

fn slide_relationship_ids_in_presentation(xml: &[u8]) -> Result<Vec<String>, WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    let mut relationship_ids = Vec::new();
    loop {
        match reader.read_event()? {
            Event::Start(event) | Event::Empty(event)
                if local_name(event.name().as_ref()) == b"sldId" =>
            {
                for attr in event.attributes().flatten() {
                    if !attr.key.as_ref().ends_with(b":id") {
                        continue;
                    }
                    relationship_ids.push(
                        attr.decode_and_unescape_value(reader.decoder())
                            .map(|value| value.into_owned())
                            .unwrap_or_default(),
                    );
                }
            }
            Event::Eof => break,
            _ => {}
        }
    }
    Ok(relationship_ids)
}

fn first_slide_layout_target<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_parts: &[String],
) -> Result<String, WolfPptError> {
    for slide_part in slide_parts {
        for rel in read_relationships(archive, slide_part)? {
            if rel.relationship_type.ends_with("/slideLayout") {
                return Ok(rel.target);
            }
        }
    }
    Err(WolfPptError::XmlText(
        "no slide layout relationship found".to_string(),
    ))
}

fn slide_layout_target_at_index<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    layout_index: usize,
) -> Result<String, WolfPptError> {
    let mut layouts = Vec::new();
    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name().to_string();
        if is_slide_layout_part(&name) {
            layouts.push(name);
        }
    }
    layouts.sort_by_key(|part| natural_key(part));
    let Some(layout_part) = layouts.get(layout_index) else {
        return Err(WolfPptError::XmlText(format!(
            "slide layout index {layout_index} was not found"
        )));
    };
    let Some(layout_name) = layout_part.rsplit('/').next() else {
        return Err(WolfPptError::XmlText(format!(
            "invalid slide layout part {layout_part}"
        )));
    };
    Ok(format!("../slideLayouts/{layout_name}"))
}

fn placeholder_shapes_from_layout<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    slide_part: &str,
    layout_target: &str,
) -> Result<String, WolfPptError> {
    let layout_part = resolve_target(slide_part, layout_target);
    let Ok(mut file) = archive.by_name(&layout_part) else {
        return Ok(String::new());
    };
    let mut payload = String::new();
    file.read_to_string(&mut payload)?;
    Ok(extract_placeholder_shape_blocks(&payload).join(""))
}

fn read_archive_text<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    part_name: &str,
) -> Result<Option<String>, WolfPptError> {
    let Ok(mut file) = archive.by_name(part_name) else {
        return Ok(None);
    };
    let mut payload = String::new();
    file.read_to_string(&mut payload)?;
    Ok(Some(payload))
}

fn extract_placeholder_shape_blocks(xml: &str) -> Vec<String> {
    let mut blocks = Vec::new();
    let mut offset = 0;
    while let Some(relative_start) = xml[offset..].find("<p:sp>") {
        let start = offset + relative_start;
        let Some(relative_end) = xml[start..].find("</p:sp>") else {
            break;
        };
        let end = start + relative_end + "</p:sp>".len();
        let block = &xml[start..end];
        if block.contains("<p:ph") && !is_non_editable_placeholder(block) {
            blocks.push(materialize_placeholder_shape(block));
        }
        offset = end;
    }
    blocks
}

fn is_non_editable_placeholder(block: &str) -> bool {
    ["type=\"dt\"", "type=\"ftr\"", "type=\"sldNum\""]
        .iter()
        .any(|needle| block.contains(needle))
}

fn materialize_placeholder_shape(block: &str) -> String {
    let block = replace_element(block, "p:spPr", "<p:spPr/>");
    replace_element(
        &block,
        "p:txBody",
        "<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>",
    )
}

fn replace_element(xml: &str, tag: &str, replacement: &str) -> String {
    let start_tag = format!("<{tag}");
    let close_tag = format!("</{tag}>");
    let Some(start) = xml.find(&start_tag) else {
        return xml.to_string();
    };
    let Some(relative_start_end) = xml[start..].find('>') else {
        return xml.to_string();
    };
    let start_end = start + relative_start_end + 1;
    let end = if xml[start..start_end].ends_with("/>") {
        start_end
    } else if let Some(relative_end) = xml[start_end..].find(&close_tag) {
        start_end + relative_end + close_tag.len()
    } else {
        return xml.to_string();
    };
    format!("{}{}{}", &xml[..start], replacement, &xml[end..])
}

fn image_extension(path: &Path) -> Result<String, WolfPptError> {
    let extension = media_extension(path, "image")?;
    Ok(match extension.as_str() {
        "jpeg" | "jpe" | "jfif" => "jpg".to_string(),
        "tif" => "tiff".to_string(),
        _ => extension,
    })
}

fn media_extension(path: &Path, label: &str) -> Result<String, WolfPptError> {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.to_ascii_lowercase())
        .ok_or_else(|| {
            WolfPptError::InvalidInput(format!(
                "{label} path has no extension: {}",
                path.display()
            ))
        })
}

fn image_content_type(extension: &str) -> Result<&'static str, WolfPptError> {
    match extension {
        "png" => Ok("image/png"),
        "jpg" | "jpeg" => Ok("image/jpeg"),
        "gif" => Ok("image/gif"),
        "bmp" => Ok("image/bmp"),
        "tif" | "tiff" => Ok("image/tiff"),
        _ => Err(WolfPptError::InvalidInput(format!(
            "unsupported image extension: {extension}"
        ))),
    }
}

fn next_media_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    extension: &str,
) -> Result<String, WolfPptError> {
    next_numbered_media_part(archive, "image", extension)
}

fn matching_image_media_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    extension: &str,
    image_payload: &[u8],
) -> Result<Option<String>, WolfPptError> {
    let wanted_hash = Sha256::digest(image_payload);
    let suffix = format!(".{extension}");
    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        if !name.starts_with("ppt/media/image") || !name.ends_with(&suffix) {
            continue;
        }
        let mut existing_payload = Vec::new();
        file.read_to_end(&mut existing_payload)?;
        if Sha256::digest(&existing_payload) == wanted_hash {
            return Ok(Some(name));
        }
    }
    Ok(None)
}

fn existing_image_relationship_id(xml: &str, target: &str) -> Option<String> {
    parse_relationships(xml.as_bytes())
        .into_iter()
        .find(|relationship| {
            relationship.relationship_type.ends_with("/image")
                && relationship.target == target
                && relationship.target_mode.is_none()
        })
        .map(|relationship| relationship.id)
}

fn next_numbered_media_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    stem: &str,
    extension: &str,
) -> Result<String, WolfPptError> {
    let mut names = Vec::new();
    for index in 0..archive.len() {
        names.push(archive.by_index(index)?.name().to_string());
    }
    for number in 1.. {
        let candidate = format!("ppt/media/{stem}{number}.{extension}");
        if !names.iter().any(|name| name == &candidate) {
            return Ok(candidate);
        }
    }
    unreachable!()
}

fn empty_relationships_xml() -> String {
    r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>
"#
    .to_string()
}
