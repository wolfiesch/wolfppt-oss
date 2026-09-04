fn inspect_archive<R: Read + std::io::Seek>(
    path: PathBuf,
    archive: &mut ZipArchive<R>,
) -> Result<PackageManifest, WolfPptError> {
    let mut parts = Vec::with_capacity(archive.len());
    for index in 0..archive.len() {
        let mut file = archive.by_index(index)?;
        let name = file.name().to_string();
        let mut payload = Vec::new();
        file.read_to_end(&mut payload)?;
        let sha256 = format!("{:x}", Sha256::digest(&payload));
        parts.push(PartRecord {
            kind: part_kind(&name),
            name,
            size: payload.len() as u64,
            sha256,
        });
    }
    parts.sort_by(|left, right| left.name.cmp(&right.name));
    Ok(PackageManifest { path, parts })
}

fn update_package_facts(name: &str, part_count: &mut usize, has_vba: &mut bool) {
    *part_count += 1;
    if part_kind(name) == PartKind::Vba {
        *has_vba = true;
    }
}

fn presentation_part_facts<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
) -> Result<(Vec<String>, bool), WolfPptError> {
    let slides = slide_parts(archive)?;
    let mut has_vba = false;
    for index in 0..archive.len() {
        let name = archive.by_index(index)?.name().to_string();
        if part_kind(&name) == PartKind::Vba {
            has_vba = true;
        }
    }
    Ok((slides, has_vba))
}

pub fn inspect_bytes(payload: &[u8]) -> Result<PackageManifest, WolfPptError> {
    let cursor = Cursor::new(payload);
    let mut archive = ZipArchive::new(cursor)?;
    inspect_archive(PathBuf::from("<bytes>"), &mut archive)
}

pub fn part_kind(name: &str) -> PartKind {
    if name.ends_with(".rels") {
        PartKind::Relationships
    } else if name.ends_with("vbaProject.bin") {
        PartKind::Vba
    } else if name.ends_with(".xml") {
        PartKind::Xml
    } else if name.starts_with("ppt/media/") {
        PartKind::Media
    } else if name.starts_with("ppt/embeddings/") {
        PartKind::Embedding
    } else {
        PartKind::Binary
    }
}

