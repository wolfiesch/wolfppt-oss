fn add_image_relationship(
    xml: &str,
    relationship_id: &str,
    target: &str,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</Relationships>") else {
        return Err(WolfPptError::InvalidInput(
            "relationships part is missing </Relationships>".to_string(),
        ));
    };
    let relationship = format!(
        r#"<Relationship Id="{relationship_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>"#
    );
    Ok(format!("{}{}{}", &xml[..end], relationship, &xml[end..]))
}

fn add_picture_to_slide_xml(
    xml: &str,
    relationship_id: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let picture = picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
    Ok(format!("{}{}{}", &xml[..end], picture, &xml[end..]))
}

// Match the sibling picture builders' flat signed-offset/unsigned-extent
// contract instead of introducing a geometry wrapper only for group insertion.
#[allow(clippy::too_many_arguments)]
fn add_picture_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    relationship_id: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let picture =
                    picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
                let rewritten_group = append_group_children_xml(block, &picture)?;
                return replace_group_subtree_xml(xml, start, end, &rewritten_group);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

// Match top-level and deeper-group picture builders instead of adding a
// nested-only geometry wrapper; the extra child index selects the owner.
#[allow(clippy::too_many_arguments)]
fn add_picture_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    relationship_id: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let picture = picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
    let rewritten_group = append_group_children_xml(block, &picture)?;
    replace_group_subtree_xml(xml, nested_start, nested_end, &rewritten_group)
}

#[allow(clippy::too_many_arguments)]
fn add_picture_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    relationship_id: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
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
    let picture = picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
    let rewritten_group = append_group_children_xml(deeper_block, &picture)?;
    let deeper_absolute_start = nested_start + deeper_start;
    let deeper_absolute_end = nested_start + deeper_end;
    replace_group_subtree_xml(xml, deeper_absolute_start, deeper_absolute_end, &rewritten_group)
}

#[allow(clippy::too_many_arguments)]
fn add_picture_to_new_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    relationship_id: &str,
    group_shape_id: u64,
    picture_shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let picture = picture_shape_xml(
                    relationship_id,
                    picture_shape_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                );
                let group_shape =
                    group_shape_with_child_xml(group_shape_id, &picture)?;
                return replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_movie_to_slide_xml(
    xml: &str,
    video_relationship_id: &str,
    media_relationship_id: &str,
    poster_relationship_id: &str,
    shape_id: u64,
    movie_name: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    minimum_timing_id: Option<u64>,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let movie = movie_shape_xml(
        video_relationship_id,
        media_relationship_id,
        poster_relationship_id,
        shape_id,
        movie_name,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    );
    add_movie_timing_to_slide_xml(
        &format!("{}{}{}", &xml[..end], movie, &xml[end..]),
        shape_id,
        minimum_timing_id,
    )
}

#[allow(clippy::too_many_arguments)]
fn add_audio_to_slide_xml(
    xml: &str,
    audio_relationship_id: &str,
    media_relationship_id: &str,
    poster_relationship_id: &str,
    shape_id: u64,
    audio_name: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    minimum_timing_id: Option<u64>,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let audio = audio_shape_xml(
        audio_relationship_id,
        media_relationship_id,
        poster_relationship_id,
        shape_id,
        audio_name,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
    );
    add_media_timing_to_slide_xml(
        &format!("{}{}{}", &xml[..end], audio, &xml[end..]),
        shape_id,
        "audio",
        false,
        false,
        80,
        1,
        minimum_timing_id,
    )
}

#[allow(clippy::too_many_arguments)]
fn add_ole_object_to_slide_xml(
    xml: &str,
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    shape_id: u64,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let ole = ole_object_shape_xml(
        ole_relationship_id,
        icon_relationship_id,
        shape_id,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_cx_emu,
        icon_cy_emu,
    );
    Ok(format!("{}{}{}", &xml[..end], ole, &xml[end..]))
}

#[allow(clippy::too_many_arguments)]
fn add_ole_object_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    shape_id: u64,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let ole = ole_object_shape_xml(
                    ole_relationship_id,
                    icon_relationship_id,
                    shape_id,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon_cx_emu,
                    icon_cy_emu,
                );
                let rewritten_group = append_group_children_xml(block, &ole)?;
                return replace_group_subtree_xml(xml, start, end, &rewritten_group);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn add_ole_object_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    shape_id: u64,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let ole = ole_object_shape_xml(
        ole_relationship_id,
        icon_relationship_id,
        shape_id,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_cx_emu,
        icon_cy_emu,
    );
    let rewritten_group = append_group_children_xml(block, &ole)?;
    replace_group_subtree_xml(xml, nested_start, nested_end, &rewritten_group)
}

#[allow(clippy::too_many_arguments)]
fn add_ole_object_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    shape_id: u64,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
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
    let ole = ole_object_shape_xml(
        ole_relationship_id,
        icon_relationship_id,
        shape_id,
        prog_id,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        icon_cx_emu,
        icon_cy_emu,
    );
    let rewritten_group = append_group_children_xml(deeper_block, &ole)?;
    let deeper_absolute_start = nested_start + deeper_start;
    let deeper_absolute_end = nested_start + deeper_end;
    replace_group_subtree_xml(xml, deeper_absolute_start, deeper_absolute_end, &rewritten_group)
}

#[allow(clippy::too_many_arguments)]
fn add_ole_object_to_new_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    group_shape_id: u64,
    ole_shape_id: u64,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<String, WolfPptError> {
    let mut offset = 0;
    let mut current_group_index = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let Some(end) = find_element_end(xml, start, tag) else {
            break;
        };
        if tag == "p:grpSp" {
            if current_group_index == group_index {
                let block = &xml[start..end];
                let Some(relative_end) = block.rfind("</p:grpSp>") else {
                    return Err(WolfPptError::InvalidInput(
                        "group shape XML is missing </p:grpSp>".to_string(),
                    ));
                };
                let insert_at = start + relative_end;
                let ole = ole_object_shape_xml(
                    ole_relationship_id,
                    icon_relationship_id,
                    ole_shape_id,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon_cx_emu,
                    icon_cy_emu,
                );
                let group_shape =
                    group_shape_with_child_xml(group_shape_id, &ole)?;
                return replace_group_subtree_xml(xml, insert_at, insert_at, &group_shape);
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

#[allow(clippy::too_many_arguments)]
fn movie_shape_xml(
    video_relationship_id: &str,
    media_relationship_id: &str,
    poster_relationship_id: &str,
    shape_id: u64,
    movie_name: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> String {
    format!(
        r#"<p:pic><p:nvPicPr xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cNvPr id="{shape_id}" name="{movie_name}"><a:hlinkClick r:id="" action="ppaction://media"/></p:cNvPr><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr><a:videoFile r:link="{video_relationship_id}"/><p:extLst><p:ext uri="{{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}}"><p14:media xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" r:embed="{media_relationship_id}"/></p:ext></p:extLst></p:nvPr></p:nvPicPr><p:blipFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><a:blip r:embed="{poster_relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>"#,
        movie_name = xml_attr(movie_name),
        video_relationship_id = xml_attr(video_relationship_id),
        media_relationship_id = xml_attr(media_relationship_id),
        poster_relationship_id = xml_attr(poster_relationship_id),
    )
}

#[allow(clippy::too_many_arguments)]
fn audio_shape_xml(
    audio_relationship_id: &str,
    media_relationship_id: &str,
    poster_relationship_id: &str,
    shape_id: u64,
    audio_name: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> String {
    format!(
        r#"<p:pic><p:nvPicPr xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cNvPr id="{shape_id}" name="{audio_name}"><a:hlinkClick r:id="" action="ppaction://media"/></p:cNvPr><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr><a:audioFile r:link="{audio_relationship_id}"/><p:extLst><p:ext uri="{{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}}"><p14:media xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" r:embed="{media_relationship_id}"/></p:ext></p:extLst></p:nvPr></p:nvPicPr><p:blipFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><a:blip r:embed="{poster_relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>"#,
        audio_name = xml_attr(audio_name),
        audio_relationship_id = xml_attr(audio_relationship_id),
        media_relationship_id = xml_attr(media_relationship_id),
        poster_relationship_id = xml_attr(poster_relationship_id),
    )
}

#[allow(clippy::too_many_arguments)]
fn ole_object_shape_xml(
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    shape_id: u64,
    prog_id: &str,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> String {
    let name = format!("Object {}", shape_id.saturating_sub(1));
    format!(
        r#"<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></p:xfrm><a:graphic><a:graphicData xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" uri="http://schemas.openxmlformats.org/presentationml/2006/ole"><p:oleObj showAsIcon="1" r:id="{ole_relationship_id}" imgW="{icon_cx_emu}" imgH="{icon_cy_emu}" progId="{prog_id}"><p:embed/><p:pic><p:nvPicPr><p:cNvPr id="0" name=""/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{icon_relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic></p:oleObj></a:graphicData></a:graphic></p:graphicFrame>"#,
        name = xml_attr(&name),
        prog_id = xml_attr(prog_id),
        ole_relationship_id = xml_attr(ole_relationship_id),
        icon_relationship_id = xml_attr(icon_relationship_id),
    )
}

fn picture_shape_xml(
    relationship_id: &str,
    shape_id: u64,
    x_emu: i64,
    y_emu: i64,
    cx_emu: u64,
    cy_emu: u64,
) -> String {
    let picture_number = shape_id.saturating_sub(1);
    format!(
        r#"<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="Picture {picture_number}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>"#
    )
}

fn add_movie_timing_to_slide_xml(
    xml: &str,
    shape_id: u64,
    minimum_timing_id: Option<u64>,
) -> Result<String, WolfPptError> {
    add_media_timing_to_slide_xml(
        xml,
        shape_id,
        "video",
        false,
        false,
        80,
        1,
        minimum_timing_id,
    )
}

#[allow(clippy::too_many_arguments)]
fn add_media_timing_to_slide_xml(
    xml: &str,
    shape_id: u64,
    media_kind: &str,
    loop_playback: bool,
    play_across_slides: bool,
    volume: u8,
    across_slide_count: usize,
    minimum_timing_id: Option<u64>,
) -> Result<String, WolfPptError> {
    let root_child_list = timing_root_child_list_bounds(xml);
    if root_child_list.is_none() && xml.contains("<p:timing") {
        return Ok(xml.to_string());
    }
    // A newly created timing tree assigns id 1 to its tmRoot node, so the media node
    // must start above it.
    let reserved_root_id = u64::from(root_child_list.is_none());
    let timing_id = max_timing_id(xml)
        .max(minimum_timing_id.unwrap_or(0))
        .max(reserved_root_id)
        + 1;
    let media = media_timing_child_xml(
        shape_id,
        timing_id,
        media_kind,
        loop_playback,
        play_across_slides,
        volume,
        across_slide_count,
    );
    if let Some((_start, end)) = root_child_list {
        let insert_at = end - "</p:childTnLst>".len();
        return Ok(format!("{}{}{}", &xml[..insert_at], media, &xml[insert_at..]));
    }
    let Some(end) = xml.rfind("</p:sld>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:sld>".to_string(),
        ));
    };
    let timing = format!(
        r#"<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>{media}</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"#,
    );
    Ok(format!("{}{}{}", &xml[..end], timing, &xml[end..]))
}

#[allow(clippy::too_many_arguments)]
fn set_media_playback_in_slide_xml(
    xml: &str,
    shape_id: u64,
    loop_playback: bool,
    play_across_slides: bool,
    volume: u8,
    auto_play: bool,
    across_slide_count: usize,
) -> Result<String, WolfPptError> {
    let Some(media_kind) = media_timing_kind_for_shape(xml, shape_id) else {
        return Err(WolfPptError::InvalidInput(format!(
            "shape {shape_id} is not an audio or video shape"
        )));
    };
    if media_kind == "video" && play_across_slides {
        return Err(WolfPptError::InvalidInput(format!(
            "shape {shape_id} is a video: PowerPoint does not support play across slides \
             for video (it will not play a video whose media node sets numSld); use \
             play_across_slides only on audio shapes"
        )));
    }
    let with_media_node = match timing_root_child_list_bounds(xml).and_then(
        |(list_start, list_end)| {
            direct_media_timing_bounds(xml, list_start, list_end, media_kind, shape_id)
        },
    ) {
        Some((start, end)) => {
            let replacement = media_timing_child_xml(
                shape_id,
                max_timing_id(xml) + 1,
                media_kind,
                loop_playback,
                play_across_slides,
                volume,
                across_slide_count,
            );
            format!("{}{}{}", &xml[..start], replacement, &xml[end..])
        }
        None => add_media_timing_to_slide_xml(
            xml,
            shape_id,
            media_kind,
            loop_playback,
            play_across_slides,
            volume,
            across_slide_count,
            None,
        )?,
    };
    Ok(set_media_auto_play_in_slide_xml(
        &with_media_node,
        &shape_id.to_string(),
        auto_play,
    ))
}

/// PowerPoint's Playback > Start "Automatically" is not a media-node property:
/// it is a main-sequence media-call effect (`presetClass="mediacall"`, a
/// `playFrom` command, `afterEffect` or `withEffect` node type) in the slide's
/// automatic first click group. Click-triggered media calls are left alone.
fn set_media_auto_play_in_slide_xml(xml: &str, shape_id: &str, auto_play: bool) -> String {
    let effects = media_play_call_effects(xml, shape_id);
    let has_auto_call = effects
        .iter()
        .any(|(_, _, node_type)| is_auto_media_call_node_type(node_type.as_deref()));
    if auto_play {
        if has_auto_call {
            return xml.to_string();
        }
        let mut xml = xml.to_string();
        for (start, end, _) in effects.into_iter().rev() {
            xml = remove_timing_effect(&xml, start, end);
        }
        return insert_media_auto_play_call(&xml, shape_id).unwrap_or(xml);
    }
    let mut xml = xml.to_string();
    for (start, end, node_type) in effects.into_iter().rev() {
        if is_auto_media_call_node_type(node_type.as_deref()) {
            xml = remove_timing_effect(&xml, start, end);
        }
    }
    xml
}

fn is_auto_media_call_node_type(node_type: Option<&str>) -> bool {
    matches!(node_type, Some("afterEffect" | "withEffect"))
}

/// Span and node type of every media-call effect `p:par` that plays `shape_id`.
fn media_play_call_effects(xml: &str, shape_id: &str) -> Vec<(usize, usize, Option<String>)> {
    let mut effects = Vec::new();
    let Some(timing_start) = find_tag_start(xml, 0, "p:timing") else {
        return effects;
    };
    let Some(timing_end) = find_element_end(xml, timing_start, "p:timing") else {
        return effects;
    };
    let target = format!(r#"spid="{shape_id}""#);
    let mut offset = timing_start;
    while let Some(c_tn_start) = find_tag_start(&xml[..timing_end], offset, "p:cTn") {
        let Some(tag_end) = xml[c_tn_start..].find('>').map(|end| c_tn_start + end + 1) else {
            break;
        };
        offset = tag_end;
        let tag = &xml[c_tn_start..tag_end];
        if extract_string_attribute(tag, "presetClass").as_deref() != Some("mediacall") {
            continue;
        }
        let Some(par_start) = owning_par_start(xml, c_tn_start) else {
            continue;
        };
        let Some(par_end) = find_element_end(xml, par_start, "p:par") else {
            continue;
        };
        let block = &xml[par_start..par_end];
        if block.contains(r#"cmd="playFrom("#) && block.contains(&target) {
            effects.push((par_start, par_end, extract_string_attribute(tag, "nodeType")));
            offset = par_end;
        }
    }
    effects
}

/// Start of the `p:par` whose first child is the `p:cTn` starting at `c_tn_start`.
fn owning_par_start(xml: &str, c_tn_start: usize) -> Option<usize> {
    let par_start = xml[..c_tn_start].rfind("<p:par")?;
    let par_tag_end = xml[par_start..].find('>')? + par_start + 1;
    (is_tag_boundary(xml, par_start + "<p:par".len())
        && par_tag_end <= c_tn_start
        && xml[par_tag_end..c_tn_start].trim().is_empty())
    .then_some(par_start)
}

/// Cut one effect `p:par`, then every grouping `p:par` it leaves empty; an
/// emptied main sequence is removed whole, because a time-node list must not
/// be empty.
fn remove_timing_effect(xml: &str, start: usize, end: usize) -> String {
    let mut xml = format!("{}{}", &xml[..start], &xml[end..]);
    let mut position = start;
    loop {
        let head = xml[..position].trim_end();
        if !head.ends_with("<p:childTnLst>")
            || !xml[position..].trim_start().starts_with("</p:childTnLst>")
        {
            return xml;
        }
        let list_start = head.len() - "<p:childTnLst>".len();
        let Some(c_tn_start) = xml[..list_start].rfind("<p:cTn") else {
            return xml;
        };
        let Some(c_tn_tag_end) = xml[c_tn_start..].find('>').map(|end| c_tn_start + end + 1)
        else {
            return xml;
        };
        let node_type = extract_string_attribute(&xml[c_tn_start..c_tn_tag_end], "nodeType");
        let (owner_start, owner_tag) = match node_type.as_deref() {
            Some("mainSeq") => match xml[..c_tn_start].rfind("<p:seq") {
                Some(seq_start) => (seq_start, "p:seq"),
                None => return xml,
            },
            Some("tmRoot") => return xml,
            _ => match owning_par_start(&xml, c_tn_start) {
                Some(par_start) => (par_start, "p:par"),
                None => return xml,
            },
        };
        let Some(owner_end) = find_element_end(&xml, owner_start, owner_tag) else {
            return xml;
        };
        xml = format!("{}{}", &xml[..owner_start], &xml[owner_end..]);
        if owner_tag == "p:seq" {
            return xml;
        }
        position = owner_start;
    }
}

/// Add an automatic `playFrom(0.0)` media call for `shape_id` to the start of
/// the main sequence, laid out as PowerPoint writes it: main sequence > click
/// group started by the sequence's `onBegin` > sub-group > effect. The call
/// joins an existing automatic first group as a `withEffect`; otherwise it
/// becomes a new automatic first group. Returns None when the slide has no
/// timing root to extend.
fn insert_media_auto_play_call(xml: &str, shape_id: &str) -> Option<String> {
    let (list_start, list_end) = timing_root_child_list_bounds(xml)?;
    let mut next_id = max_timing_id(xml) + 1;
    let mut alloc = || {
        next_id += 1;
        next_id - 1
    };
    let root_content_start = xml[list_start..].find('>')? + list_start + 1;
    let Some((seq_c_tn_start, seq_c_tn_end)) =
        main_sequence_time_node(xml, root_content_start, list_end)
    else {
        let seq_id = alloc();
        let group = media_call_click_group_xml(seq_id, shape_id, &mut alloc);
        let seq = format!(
            r#"<p:seq concurrent="1" nextAc="seek"><p:cTn id="{seq_id}" dur="indefinite" nodeType="mainSeq"><p:childTnLst>{group}</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>"#
        );
        return Some(splice(xml, root_content_start, &seq));
    };
    let seq_tag_end = xml[seq_c_tn_start..].find('>')? + seq_c_tn_start + 1;
    let seq_id = extract_string_attribute(&xml[seq_c_tn_start..seq_tag_end], "id")?;
    let seq_id: u64 = seq_id.parse().ok()?;
    let Some(list) = find_tag_start(&xml[..seq_c_tn_end], seq_tag_end, "p:childTnLst") else {
        let group = media_call_click_group_xml(seq_id, shape_id, &mut alloc);
        let children = format!("<p:childTnLst>{group}</p:childTnLst>");
        if xml[seq_c_tn_start..seq_tag_end].trim_end().ends_with("/>") {
            let open_tag = xml[seq_c_tn_start..seq_tag_end]
                .trim_end()
                .trim_end_matches("/>")
                .trim_end();
            let node = format!("{open_tag}>{children}</p:cTn>");
            return Some(format!("{}{}{}", &xml[..seq_c_tn_start], node, &xml[seq_tag_end..]));
        }
        let insert_at = find_tag_start(&xml[..seq_c_tn_end], seq_tag_end, "p:subTnLst")
            .unwrap_or(seq_c_tn_end - "</p:cTn>".len());
        return Some(splice(xml, insert_at, &children));
    };
    let list_content_start = xml[list..].find('>')? + list + 1;
    if let Some(insert_at) = auto_start_first_sub_group_end(xml, list_content_start) {
        let effect = media_call_effect_xml(shape_id, "withEffect", &mut alloc);
        return Some(splice(xml, insert_at, &effect));
    }
    let group = media_call_click_group_xml(seq_id, shape_id, &mut alloc);
    Some(splice(xml, list_content_start, &group))
}

fn splice(xml: &str, at: usize, insert: &str) -> String {
    format!("{}{}{}", &xml[..at], insert, &xml[at..])
}

/// Span of the `nodeType="mainSeq"` time node among the timing root children.
fn main_sequence_time_node(xml: &str, start: usize, end: usize) -> Option<(usize, usize)> {
    let mut offset = start;
    while let Some(c_tn_start) = find_tag_start(&xml[..end], offset, "p:cTn") {
        let tag_end = xml[c_tn_start..].find('>')? + c_tn_start + 1;
        if extract_string_attribute(&xml[c_tn_start..tag_end], "nodeType").as_deref()
            == Some("mainSeq")
        {
            return Some((c_tn_start, find_element_end(xml, c_tn_start, "p:cTn")?));
        }
        offset = tag_end;
    }
    None
}

/// Insertion point at the end of the first sub-group of the main sequence's
/// first click group, when that group starts automatically (`onBegin`).
fn auto_start_first_sub_group_end(xml: &str, list_content_start: usize) -> Option<usize> {
    let group_start = list_content_start + (xml[list_content_start..].len()
        - xml[list_content_start..].trim_start().len());
    if !xml[group_start..].starts_with("<p:par") {
        return None;
    }
    let group_end = find_element_end(xml, group_start, "p:par")?;
    let group_c_tn = find_tag_start(&xml[..group_end], group_start, "p:cTn")?;
    let group_list = find_tag_start(&xml[..group_end], group_c_tn, "p:childTnLst")?;
    let group_tag_end = xml[group_c_tn..].find('>')? + group_c_tn + 1;
    if extract_string_attribute(&xml[group_c_tn..group_tag_end], "presetClass").is_some()
        || !xml[group_tag_end..group_list].contains(r#"evt="onBegin""#)
    {
        return None;
    }
    let sub_start = xml[group_list..].find('>')? + group_list + 1;
    let sub_start = sub_start + (xml[sub_start..].len() - xml[sub_start..].trim_start().len());
    if !xml[sub_start..].starts_with("<p:par") {
        return None;
    }
    let sub_end = find_element_end(xml, sub_start, "p:par")?;
    let sub_c_tn = find_tag_start(&xml[..sub_end], sub_start, "p:cTn")?;
    let sub_tag_end = xml[sub_c_tn..].find('>')? + sub_c_tn + 1;
    let sub_tag = &xml[sub_c_tn..sub_tag_end];
    if extract_string_attribute(sub_tag, "presetClass").is_some()
        || !matches!(
            extract_string_attribute(sub_tag, "nodeType").as_deref(),
            None | Some("withGroup" | "afterGroup")
        )
    {
        return None;
    }
    let sub_list = find_tag_start(&xml[..sub_end], sub_tag_end, "p:childTnLst")?;
    Some(find_element_end(xml, sub_list, "p:childTnLst")? - "</p:childTnLst>".len())
}

fn media_call_click_group_xml(
    main_sequence_id: u64,
    shape_id: &str,
    alloc: &mut impl FnMut() -> u64,
) -> String {
    let group_id = alloc();
    let sub_group_id = alloc();
    let effect = media_call_effect_xml(shape_id, "afterEffect", alloc);
    format!(
        r#"<p:par><p:cTn id="{group_id}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="{main_sequence_id}"/></p:cond></p:stCondLst><p:childTnLst><p:par><p:cTn id="{sub_group_id}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>{effect}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"#
    )
}

fn media_call_effect_xml(
    shape_id: &str,
    node_type: &str,
    alloc: &mut impl FnMut() -> u64,
) -> String {
    let effect_id = alloc();
    let behavior_id = alloc();
    format!(
        r#"<p:par><p:cTn id="{effect_id}" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" nodeType="{node_type}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="{behavior_id}" dur="1" fill="hold"/><p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl></p:cBhvr></p:cmd></p:childTnLst></p:cTn></p:par>"#
    )
}

fn timing_root_child_list_bounds(xml: &str) -> Option<(usize, usize)> {
    let timing_start = find_tag_start(xml, 0, "p:timing")?;
    let timing_end = find_element_end(xml, timing_start, "p:timing")?;
    let mut offset = timing_start;
    while let Some(c_tn_start) = find_tag_start(xml, offset, "p:cTn") {
        if c_tn_start >= timing_end {
            return None;
        }
        let c_tn_tag = element_start_tag(&xml[c_tn_start..], "p:cTn")?;
        if extract_string_attribute(c_tn_tag, "nodeType").as_deref() == Some("tmRoot") {
            let c_tn_end = find_element_end(xml, c_tn_start, "p:cTn")?;
            let c_tn_start_end = xml[c_tn_start..].find('>')? + c_tn_start + 1;
            let c_tn_end_start = c_tn_end - "</p:cTn>".len();
            let mut child_offset = c_tn_start_end;
            while child_offset < c_tn_end_start {
                let relative_start = xml[child_offset..c_tn_end_start].find('<')?;
                let child_start = child_offset + relative_start;
                if xml[child_start..].starts_with("</") {
                    break;
                }
                let tag_name_start = child_start + 1;
                let tag_name_end = xml[tag_name_start..]
                    .find(|ch: char| ch == '>' || ch == '/' || ch.is_whitespace())
                    .map(|end| tag_name_start + end)?;
                let child_tag = &xml[tag_name_start..tag_name_end];
                let child_start_end = xml[child_start..].find('>')? + child_start + 1;
                let child_end = if xml[child_start..child_start_end]
                    .trim_end()
                    .ends_with("/>")
                {
                    child_start_end
                } else {
                    find_element_end(xml, child_start, child_tag)?
                };
                if child_end > c_tn_end {
                    return None;
                }
                if child_tag == "p:childTnLst" {
                    return Some((child_start, child_end));
                }
                child_offset = child_end;
            }
            return None;
        }
        offset = c_tn_start + "<p:cTn".len();
    }
    None
}

fn direct_media_timing_bounds(
    xml: &str,
    list_start: usize,
    list_end: usize,
    media_kind: &str,
    shape_id: u64,
) -> Option<(usize, usize)> {
    let parent_start_end = xml[list_start..].find('>')? + list_start + 1;
    let parent_end_start = list_end - "</p:childTnLst>".len();
    let wanted_tag = match media_kind {
        "audio" => "p:audio",
        "video" => "p:video",
        _ => return None,
    };
    let target = format!(r#"spid="{shape_id}""#);
    let mut offset = parent_start_end;
    while let Some(relative_start) = xml[offset..parent_end_start].find('<') {
        let child_start = offset + relative_start;
        if xml[child_start..].starts_with("</") {
            break;
        }
        let tag_name_start = child_start + 1;
        let tag_name_end = xml[tag_name_start..]
            .find(|ch: char| ch == '>' || ch == '/' || ch.is_whitespace())
            .map(|end| tag_name_start + end)?;
        let tag = &xml[tag_name_start..tag_name_end];
        let child_end = find_element_end(xml, child_start, tag)?;
        if tag == wanted_tag && xml[child_start..child_end].contains(&target) {
            return Some((child_start, child_end));
        }
        offset = child_end;
    }
    None
}

fn media_timing_kind_for_shape(xml: &str, shape_id: u64) -> Option<&'static str> {
    let mut offset = 0;
    while let Some((start, tag)) = find_next_shape_start(xml, offset) {
        let end = find_element_end(xml, start, tag)?;
        let block = &xml[start..end];
        let shape_tag = element_start_tag(block, "p:cNvPr")?;
        if extract_string_attribute(shape_tag, "id").as_deref() == Some(&shape_id.to_string()) {
            if block.contains("<a:audioFile") {
                return Some("audio");
            }
            if block.contains("<a:videoFile") {
                return Some("video");
            }
            return None;
        }
        offset = end;
    }
    None
}

#[allow(clippy::too_many_arguments)]
fn media_timing_child_xml(
    shape_id: u64,
    timing_id: u64,
    media_kind: &str,
    loop_playback: bool,
    play_across_slides: bool,
    volume: u8,
    across_slide_count: usize,
) -> String {
    let repeat_count = if loop_playback {
        r#" repeatCount="indefinite""#
    } else {
        ""
    };
    // Play Across Slides is an audio-only PowerPoint option. PowerPoint will not
    // start or play a video whose media node carries numSld, and it omits the
    // attribute (default 1) whenever the option is off.
    let number_of_slides = if play_across_slides && media_kind == "audio" {
        format!(r#" numSld="{}""#, across_slide_count.max(2))
    } else {
        String::new()
    };
    format!(
        r#"<p:{media_kind}><p:cMediaNode vol="{}"{number_of_slides}><p:cTn id="{timing_id}" fill="hold" display="0"{repeat_count}><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl></p:cMediaNode></p:{media_kind}>"#,
        u32::from(volume) * 1000,
    )
}

fn max_timing_id(xml: &str) -> u64 {
    let mut max_id = 0;
    let mut offset = 0;
    while let Some(relative_start) = xml[offset..].find("<p:cTn") {
        let start = offset + relative_start;
        let Some(relative_end) = xml[start..].find('>') else {
            break;
        };
        let tag = &xml[start..start + relative_end];
        if let Some(value) = extract_string_attribute(tag, "id") {
            if let Ok(parsed) = value.parse::<u64>() {
                max_id = max_id.max(parsed);
            }
        }
        offset = start + relative_end;
    }
    max_id
}
