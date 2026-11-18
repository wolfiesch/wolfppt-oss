const DEFAULT_MOVIE_POSTER_PNG: &[u8] = &[
    137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0,
    0, 0, 31, 21, 196, 137, 0, 0, 0, 10, 73, 68, 65, 84, 120, 156, 99, 96, 0, 0, 2, 0, 1, 0, 255,
    255, 3, 0, 0, 6, 0, 5, 87, 191, 171, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130,
];

/// Longest side, in pixels, of the generated default audio icon.
const AUDIO_ICON_LONG_SIDE_PX: u64 = 256;

/// Render the default audio poster: a dark speaker glyph with sound waves,
/// centred on a transparent canvas whose aspect ratio matches the audio
/// shape, so the icon is not distorted when PowerPoint stretches the poster
/// over the shape frame.
fn default_audio_icon_png(cx_emu: u64, cy_emu: u64) -> Vec<u8> {
    let (width, height) = if cx_emu == 0 || cy_emu == 0 {
        (AUDIO_ICON_LONG_SIDE_PX, AUDIO_ICON_LONG_SIDE_PX)
    } else if cx_emu >= cy_emu {
        let short = (AUDIO_ICON_LONG_SIDE_PX * cy_emu + cx_emu / 2) / cx_emu;
        (AUDIO_ICON_LONG_SIDE_PX, short.max(16))
    } else {
        let short = (AUDIO_ICON_LONG_SIDE_PX * cx_emu + cy_emu / 2) / cy_emu;
        (short.max(16), AUDIO_ICON_LONG_SIDE_PX)
    };
    let (width, height) = (width as usize, height as usize);
    let side = width.min(height) as f64 * 0.9;
    let left = (width as f64 - side) / 2.0;
    let top = (height as f64 - side) / 2.0;
    const SAMPLES: usize = 4;
    let mut rows = Vec::with_capacity(height * (width * 4 + 1));
    for y in 0..height {
        rows.push(0); // PNG filter type: None
        for x in 0..width {
            let mut covered = 0u32;
            for sy in 0..SAMPLES {
                for sx in 0..SAMPLES {
                    let u = (x as f64 + (sx as f64 + 0.5) / SAMPLES as f64 - left) / side;
                    let v = (y as f64 + (sy as f64 + 0.5) / SAMPLES as f64 - top) / side;
                    covered += u32::from(audio_icon_covers(u, v));
                }
            }
            let alpha = (covered * 255 / (SAMPLES * SAMPLES) as u32) as u8;
            rows.extend_from_slice(&[0x40, 0x40, 0x40, alpha]);
        }
    }
    let mut header = Vec::with_capacity(13);
    header.extend_from_slice(&(width as u32).to_be_bytes());
    header.extend_from_slice(&(height as u32).to_be_bytes());
    header.extend_from_slice(&[8, 6, 0, 0, 0]); // 8-bit RGBA, no interlace
    let mut png = vec![137, 80, 78, 71, 13, 10, 26, 10];
    push_png_chunk(&mut png, b"IHDR", &header);
    push_png_chunk(&mut png, b"IDAT", &zlib_stored(&rows));
    push_png_chunk(&mut png, b"IEND", &[]);
    png
}

/// Whether the unit-square point (u, v) lies on the speaker glyph.
fn audio_icon_covers(u: f64, v: f64) -> bool {
    let dv = (v - 0.5).abs();
    let body = (0.08..=0.30).contains(&u) && dv <= 0.13;
    let cone = (0.30..=0.52).contains(&u) && dv <= 0.13 + (u - 0.30) / 0.22 * 0.23;
    let radius = ((u - 0.50).powi(2) + (v - 0.5).powi(2)).sqrt();
    let in_wave_sector = u > 0.56 && dv <= (u - 0.50) * 1.2;
    let wave = in_wave_sector
        && ((0.13..=0.19).contains(&radius)
            || (0.26..=0.32).contains(&radius)
            || (0.39..=0.45).contains(&radius));
    body || cone || wave
}

fn push_png_chunk(png: &mut Vec<u8>, kind: &[u8; 4], data: &[u8]) {
    png.extend_from_slice(&(data.len() as u32).to_be_bytes());
    let start = png.len();
    png.extend_from_slice(kind);
    png.extend_from_slice(data);
    let crc = crc32(&png[start..]);
    png.extend_from_slice(&crc.to_be_bytes());
}

/// Wrap `data` in a zlib stream of stored (uncompressed) deflate blocks; the
/// package writer deflates the part itself.
fn zlib_stored(data: &[u8]) -> Vec<u8> {
    let mut out = vec![0x78, 0x01];
    let mut chunks = data.chunks(65_535).peekable();
    if chunks.peek().is_none() {
        out.extend_from_slice(&[1, 0, 0, 0xff, 0xff]);
    }
    while let Some(chunk) = chunks.next() {
        out.push(u8::from(chunks.peek().is_none()));
        let len = chunk.len() as u16;
        out.extend_from_slice(&len.to_le_bytes());
        out.extend_from_slice(&(!len).to_le_bytes());
        out.extend_from_slice(chunk);
    }
    let (mut a, mut b) = (1u32, 0u32);
    for byte in data {
        a = (a + u32::from(*byte)) % 65_521;
        b = (b + a) % 65_521;
    }
    out.extend_from_slice(&((b << 16) | a).to_be_bytes());
    out
}

fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xffff_ffffu32;
    for byte in data {
        crc ^= u32::from(*byte);
        for _ in 0..8 {
            crc = if crc & 1 == 1 {
                (crc >> 1) ^ 0xedb8_8320
            } else {
                crc >> 1
            };
        }
    }
    !crc
}

fn read_media_source(path: &Path, role: &str) -> Result<Vec<u8>, WolfPptError> {
    std::fs::read(path).map_err(|err| {
        WolfPptError::Io(std::io::Error::new(
            err.kind(),
            format!("{role} file {} could not be read: {err}", path.display()),
        ))
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_movie(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    movie_path: impl AsRef<Path>,
    poster_frame_path: Option<&Path>,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    mime_type: &str,
    minimum_timing_id: Option<u64>,
) -> Result<MovieAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let movie_path = movie_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let movie_extension = media_extension(movie_path, "movie")?;
    let movie_payload = read_media_source(movie_path, "movie")?;
    let (poster_extension, poster_content_type, poster_payload) = match poster_frame_path {
        Some(path) => {
            let extension = image_extension(path)?;
            let content_type = image_content_type(&extension)?.to_string();
            (
                extension,
                content_type,
                read_media_source(path, "poster frame")?,
            )
        }
        None => (
            "png".to_string(),
            "image/png".to_string(),
            DEFAULT_MOVIE_POSTER_PNG.to_vec(),
        ),
    };

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let media_part = next_numbered_media_part(&mut archive, "media", &movie_extension)?;
    let poster_part = next_numbered_media_part(&mut archive, "image", &poster_extension)?;
    let rels_part = relationship_part_name(&slide_part);
    let media_target = format!("../media/{}", media_part.rsplit('/').next().unwrap_or(""));
    let poster_target = format!("../media/{}", poster_part.rsplit('/').next().unwrap_or(""));
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let rels_xml =
        read_archive_text(&mut archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let content_types_xml =
        read_archive_text(&mut archive, "[Content_Types].xml")?.ok_or_else(|| {
            WolfPptError::InvalidInput("[Content_Types].xml was not found".to_string())
        })?;

    let media_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &media_relationship_id,
        "http://schemas.microsoft.com/office/2007/relationships/media",
        &media_target,
    )?;
    let video_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &video_relationship_id,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video",
        &media_target,
    )?;
    let poster_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_image_relationship(&rels_xml, &poster_relationship_id, &poster_target)?;

    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let movie_name = movie_path
        .file_name()
        .and_then(|value| value.to_str())
        .map(str::to_string)
        .unwrap_or_else(|| format!("Movie {shape_id}"));
    slide_xml = add_movie_to_slide_xml(
        &slide_xml,
        &video_relationship_id,
        &media_relationship_id,
        &poster_relationship_id,
        shape_id,
        &movie_name,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        minimum_timing_id,
    )?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &movie_extension, mime_type)?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &poster_extension, &poster_content_type)?;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
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
        if name == media_part || name == poster_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    update_package_facts(&media_part, &mut part_count, &mut has_vba);
    writer.start_file(media_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(movie_payload), &mut writer)?;
    update_package_facts(&poster_part, &mut part_count, &mut has_vba);
    writer.start_file(poster_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(poster_payload), &mut writer)?;
    writer.finish()?;

    Ok(MovieAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        media_relationship_id,
        video_relationship_id,
        poster_relationship_id,
        media_part,
        poster_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_audio(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    audio_path: impl AsRef<Path>,
    poster_frame_path: Option<&Path>,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    mime_type: &str,
    minimum_timing_id: Option<u64>,
) -> Result<AudioAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let audio_path = audio_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let audio_extension = media_extension(audio_path, "audio")?;
    let audio_payload = read_media_source(audio_path, "audio")?;
    let (poster_extension, poster_content_type, poster_payload) = match poster_frame_path {
        Some(path) => {
            let extension = image_extension(path)?;
            let content_type = image_content_type(&extension)?.to_string();
            (
                extension,
                content_type,
                read_media_source(path, "poster frame")?,
            )
        }
        None => (
            "png".to_string(),
            "image/png".to_string(),
            default_audio_icon_png(cx_emu, cy_emu),
        ),
    };

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let media_part = next_numbered_media_part(&mut archive, "media", &audio_extension)?;
    let poster_part = next_numbered_media_part(&mut archive, "image", &poster_extension)?;
    let rels_part = relationship_part_name(&slide_part);
    let media_target = format!("../media/{}", media_part.rsplit('/').next().unwrap_or(""));
    let poster_target = format!("../media/{}", poster_part.rsplit('/').next().unwrap_or(""));
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let rels_xml =
        read_archive_text(&mut archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let content_types_xml =
        read_archive_text(&mut archive, "[Content_Types].xml")?.ok_or_else(|| {
            WolfPptError::InvalidInput("[Content_Types].xml was not found".to_string())
        })?;

    let media_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &media_relationship_id,
        "http://schemas.microsoft.com/office/2007/relationships/media",
        &media_target,
    )?;
    let audio_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &audio_relationship_id,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio",
        &media_target,
    )?;
    let poster_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_image_relationship(&rels_xml, &poster_relationship_id, &poster_target)?;

    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let audio_name = audio_path
        .file_name()
        .and_then(|value| value.to_str())
        .map(str::to_string)
        .unwrap_or_else(|| format!("Audio {shape_id}"));
    slide_xml = add_audio_to_slide_xml(
        &slide_xml,
        &audio_relationship_id,
        &media_relationship_id,
        &poster_relationship_id,
        shape_id,
        &audio_name,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        minimum_timing_id,
    )?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &audio_extension, mime_type)?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &poster_extension, &poster_content_type)?;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
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
        if name == media_part || name == poster_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part.clone(), options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    update_package_facts(&media_part, &mut part_count, &mut has_vba);
    writer.start_file(media_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(audio_payload), &mut writer)?;
    update_package_facts(&poster_part, &mut part_count, &mut has_vba);
    writer.start_file(poster_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(poster_payload), &mut writer)?;
    writer.finish()?;

    Ok(AudioAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        media_relationship_id,
        audio_relationship_id,
        poster_relationship_id,
        media_part,
        poster_part,
        shape_id,
        part_count,
        has_vba,
    })
}

#[allow(clippy::too_many_arguments)]
pub fn set_slide_media_playback(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    shape_id: u64,
    loop_playback: bool,
    play_across_slides: bool,
    volume: u8,
    auto_play: bool,
) -> Result<(), WolfPptError> {
    if volume > 100 {
        return Err(WolfPptError::InvalidInput(
            "media volume must be between 0 and 100".to_string(),
        ));
    }

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
    let slide_count = slide_parts(&mut archive)?.len();
    let slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let rewritten_slide_xml = set_media_playback_in_slide_xml(
        &slide_xml,
        shape_id,
        loop_playback,
        play_across_slides,
        volume,
        auto_play,
        slide_count.saturating_sub(slide_index),
    )?;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name()?.into_owned();
        let options = SimpleFileOptions::default().compression_method(file.compression());
        if file.is_dir() {
            writer.add_directory(name, options)?;
        } else if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(
                &mut Cursor::new(rewritten_slide_xml.as_bytes()),
                &mut writer,
            )?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }
    writer.finish()?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::Slide,
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_group_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::Group { group_index },
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::NestedGroup {
            group_index,
            nested_group_child_index,
        },
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_deeper_nested_group_ole_object(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::DeeperNestedGroup {
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        },
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn add_slide_nested_group_ole_object_in_new_group(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    group_index: usize,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    add_slide_ole_object_with_target(
        input_path,
        output_path,
        slide_index,
        OleObjectInsertTarget::NewNestedGroup { group_index },
        object_path,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_path,
        icon_cx_emu,
        icon_cy_emu,
    )
}

enum OleObjectInsertTarget {
    Slide,
    Group {
        group_index: usize,
    },
    NestedGroup {
        group_index: usize,
        nested_group_child_index: usize,
    },
    DeeperNestedGroup {
        group_index: usize,
        nested_group_child_index: usize,
        deeper_group_child_index: usize,
    },
    NewNestedGroup {
        group_index: usize,
    },
}

#[allow(clippy::too_many_arguments)]
fn add_slide_ole_object_with_target(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    target: OleObjectInsertTarget,
    object_path: impl AsRef<Path>,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_path: Option<&Path>,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<OleObjectAddSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    let object_path = object_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let object_payload = std::fs::read(object_path)?;
    let (object_extension, object_content_type, object_relationship_type) =
        ole_embedding_format(&object_payload);
    let (icon_extension, icon_content_type, icon_payload) = match icon_path {
        Some(path) => {
            let extension = image_extension(path)?;
            let content_type = image_content_type(&extension)?.to_string();
            (extension, content_type, std::fs::read(path)?)
        }
        None => (
            "png".to_string(),
            "image/png".to_string(),
            DEFAULT_MOVIE_POSTER_PNG.to_vec(),
        ),
    };

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let ole_part = next_embedding_part(&mut archive, object_extension)?;
    let icon_part = next_numbered_media_part(&mut archive, "image", &icon_extension)?;
    let rels_part = relationship_part_name(&slide_part);
    let ole_target = format!(
        "../embeddings/{}",
        ole_part.rsplit('/').next().unwrap_or("")
    );
    let icon_target = format!("../media/{}", icon_part.rsplit('/').next().unwrap_or(""));
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let rels_xml =
        read_archive_text(&mut archive, &rels_part)?.unwrap_or_else(empty_relationships_xml);
    let content_types_xml =
        read_archive_text(&mut archive, "[Content_Types].xml")?.ok_or_else(|| {
            WolfPptError::InvalidInput("[Content_Types].xml was not found".to_string())
        })?;

    let ole_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_relationship(
        &rels_xml,
        &ole_relationship_id,
        object_relationship_type,
        &ole_target,
    )?;
    let icon_relationship_id = next_relationship_id(rels_xml.as_bytes());
    let rels_xml = add_image_relationship(&rels_xml, &icon_relationship_id, &icon_target)?;

    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    let mut inserted_shape_id = shape_id;
    slide_xml = match target {
        OleObjectInsertTarget::Slide => add_ole_object_to_slide_xml(
            &slide_xml,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::Group { group_index } => add_ole_object_to_group_shape_xml(
            &slide_xml,
            group_index,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::NestedGroup {
            group_index,
            nested_group_child_index,
        } => add_ole_object_to_nested_group_shape_xml(
            &slide_xml,
            group_index,
            nested_group_child_index,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::DeeperNestedGroup {
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        } => add_ole_object_to_deeper_nested_group_shape_xml(
            &slide_xml,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            &ole_relationship_id,
            &icon_relationship_id,
            shape_id,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_cx_emu,
            icon_cy_emu,
        )?,
        OleObjectInsertTarget::NewNestedGroup { group_index } => {
            inserted_shape_id = shape_id + 1;
            add_ole_object_to_new_nested_group_shape_xml(
                &slide_xml,
                group_index,
                &ole_relationship_id,
                &icon_relationship_id,
                shape_id,
                inserted_shape_id,
                prog_id,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                icon_cx_emu,
                icon_cy_emu,
            )?
        }
    };
    let content_types_xml = ensure_content_type_override(
        &content_types_xml,
        &format!("/{}", ole_part),
        object_content_type,
    )?;
    let content_types_xml =
        ensure_default_content_type(&content_types_xml, &icon_extension, &icon_content_type)?;

    let output = File::create(output_path)?;
    let mut writer = zip::ZipWriter::new(output);
    let mut wrote_rels = false;
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
        if name == ole_part || name == icon_part {
            part_count -= 1;
            continue;
        }
        if name == slide_part {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(slide_xml.as_bytes()), &mut writer)?;
        } else if name == rels_part {
            wrote_rels = true;
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
        } else if name == "[Content_Types].xml" {
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(content_types_xml.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }

    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    if !wrote_rels {
        update_package_facts(&rels_part, &mut part_count, &mut has_vba);
        writer.start_file(rels_part, options)?;
        std::io::copy(&mut Cursor::new(rels_xml.as_bytes()), &mut writer)?;
    }
    update_package_facts(&ole_part, &mut part_count, &mut has_vba);
    writer.start_file(ole_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(object_payload), &mut writer)?;
    update_package_facts(&icon_part, &mut part_count, &mut has_vba);
    writer.start_file(icon_part.clone(), options)?;
    std::io::copy(&mut Cursor::new(icon_payload), &mut writer)?;
    writer.finish()?;

    Ok(OleObjectAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        ole_relationship_id,
        icon_relationship_id,
        ole_part,
        icon_part,
        shape_id: inserted_shape_id,
        part_count,
        has_vba,
    })
}

// Inspect bytes rather than the filename or ProgID: file-like inputs materialize
// as object.bin, and legacy compound files may carry an OOXML ProgID.
// Unrecognized bytes retain the existing opaque OLE insertion contract.
fn ole_embedding_format(payload: &[u8]) -> (&'static str, &'static str, &'static str) {
    const OLE: (&str, &str, &str) = (
        "bin",
        "application/vnd.openxmlformats-officedocument.oleObject",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
    );
    const PACKAGE: &str =
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package";
    if payload.starts_with(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") {
        return OLE;
    }
    let Ok(mut package) = ZipArchive::new(Cursor::new(payload)) else {
        return OLE;
    };
    // Match the established native package signatures, including the minimal
    // workbook accepted by the public API. Never unpack or activate the object.
    for (main, extension, content_type, macro_extension, macro_content_type) in [
        (
            "xl/workbook.xml",
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsm",
            "application/vnd.ms-excel.sheet.macroEnabled.12",
        ),
        (
            "word/document.xml",
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docm",
            "application/vnd.ms-word.document.macroEnabled.12",
        ),
        (
            "ppt/presentation.xml",
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "pptm",
            "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
        ),
    ] {
        if package.by_name(main).is_ok() {
            let main_type = read_archive_text(&mut package, "[Content_Types].xml")
                .ok()
                .flatten()
                .and_then(|xml| find_content_type_override(&xml, main));
            if main_type
                .as_deref()
                .is_some_and(|value| value.ends_with(".macroEnabled.main+xml"))
            {
                return (macro_extension, macro_content_type, PACKAGE);
            }
            return (extension, content_type, PACKAGE);
        }
    }
    OLE
}

fn next_embedding_part<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    extension: &str,
) -> Result<String, WolfPptError> {
    let mut names = Vec::new();
    for index in 0..archive.len() {
        names.push(archive.by_index(index)?.name()?.into_owned());
    }
    for number in 1.. {
        let candidate = format!("ppt/embeddings/oleObject{number}.{extension}");
        if !names.iter().any(|name| name == &candidate) {
            return Ok(candidate);
        }
    }
    unreachable!()
}
