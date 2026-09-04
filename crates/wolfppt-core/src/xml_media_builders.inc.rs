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
    x_emu: u64,
    y_emu: u64,
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

fn add_picture_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    relationship_id: &str,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
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
                let picture =
                    picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    picture,
                    &xml[insert_at..]
                ));
            }
            current_group_index += 1;
        }
        offset = end;
    }

    Err(WolfPptError::InvalidInput(format!(
        "group shape index {group_index} was not found"
    )))
}

fn add_picture_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    relationship_id: &str,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let Some(relative_end) = block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + relative_end;
    let picture = picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
    Ok(format!("{}{}{}", &xml[..insert_at], picture, &xml[insert_at..]))
}

#[allow(clippy::too_many_arguments)]
fn add_picture_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    relationship_id: &str,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
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
    let Some(relative_end) = deeper_block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "deeper nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + deeper_start + relative_end;
    let picture = picture_shape_xml(relationship_id, shape_id, x_emu, y_emu, cx_emu, cy_emu);
    Ok(format!("{}{}{}", &xml[..insert_at], picture, &xml[insert_at..]))
}

#[allow(clippy::too_many_arguments)]
fn add_picture_to_new_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    relationship_id: &str,
    group_shape_id: u64,
    picture_shape_id: u64,
    x_emu: u64,
    y_emu: u64,
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
                let group_shape = group_shape_with_child_xml(group_shape_id, &picture);
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    group_shape,
                    &xml[insert_at..]
                ));
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
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
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
    )
}

#[allow(clippy::too_many_arguments)]
fn add_ole_object_to_slide_xml(
    xml: &str,
    ole_relationship_id: &str,
    icon_relationship_id: &str,
    shape_id: u64,
    prog_id: &str,
    x_emu: u64,
    y_emu: u64,
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
    x_emu: u64,
    y_emu: u64,
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
                    shape_id,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon_cx_emu,
                    icon_cy_emu,
                );
                return Ok(format!("{}{}{}", &xml[..insert_at], ole, &xml[insert_at..]));
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
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> Result<String, WolfPptError> {
    let (nested_start, nested_end) =
        nested_group_child_bounds(xml, group_index, nested_group_child_index)?;
    let block = &xml[nested_start..nested_end];
    let Some(relative_end) = block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + relative_end;
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
    Ok(format!("{}{}{}", &xml[..insert_at], ole, &xml[insert_at..]))
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
    x_emu: u64,
    y_emu: u64,
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
    let Some(relative_end) = deeper_block.rfind("</p:grpSp>") else {
        return Err(WolfPptError::InvalidInput(
            "deeper nested group shape XML is missing </p:grpSp>".to_string(),
        ));
    };
    let insert_at = nested_start + deeper_start + relative_end;
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
    Ok(format!("{}{}{}", &xml[..insert_at], ole, &xml[insert_at..]))
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
    x_emu: u64,
    y_emu: u64,
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
                let group_shape = group_shape_with_child_xml(group_shape_id, &ole);
                return Ok(format!(
                    "{}{}{}",
                    &xml[..insert_at],
                    group_shape,
                    &xml[insert_at..]
                ));
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
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> String {
    format!(
        r#"<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="{movie_name}"><a:hlinkClick r:id="" action="ppaction://media"/></p:cNvPr><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr><a:videoFile r:link="{video_relationship_id}"/><p:extLst><p:ext uri="{{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}}"><p14:media xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" r:embed="{media_relationship_id}"/></p:ext></p:extLst></p:nvPr></p:nvPicPr><p:blipFill><a:blip r:embed="{poster_relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>"#,
        movie_name = xml_attr(movie_name),
        video_relationship_id = xml_attr(video_relationship_id),
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
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    icon_cx_emu: u64,
    icon_cy_emu: u64,
) -> String {
    let name = format!("Object {}", shape_id.saturating_sub(1));
    format!(
        r#"<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/presentationml/2006/ole"><p:oleObj showAsIcon="1" r:id="{ole_relationship_id}" imgW="{icon_cx_emu}" imgH="{icon_cy_emu}" progId="{prog_id}"><p:embed/><p:pic><p:nvPicPr><p:cNvPr id="0" name=""/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{icon_relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic></p:oleObj></a:graphicData></a:graphic></p:graphicFrame>"#,
        name = xml_attr(&name),
        prog_id = xml_attr(prog_id),
        ole_relationship_id = xml_attr(ole_relationship_id),
        icon_relationship_id = xml_attr(icon_relationship_id),
    )
}

fn picture_shape_xml(
    relationship_id: &str,
    shape_id: u64,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> String {
    let picture_number = shape_id.saturating_sub(1);
    format!(
        r#"<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="Picture {picture_number}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>"#
    )
}

fn add_movie_timing_to_slide_xml(xml: &str, shape_id: u64) -> Result<String, WolfPptError> {
    if let Some(timing_start) = xml.find("<p:timing") {
        if let Some(relative_end) = xml[timing_start..].find("</p:childTnLst>") {
            let end = timing_start + relative_end;
            let timing_id = max_timing_id(xml) + 1;
            let video = movie_timing_child_xml(shape_id, timing_id);
            return Ok(format!("{}{}{}", &xml[..end], video, &xml[end..]));
        }
        return Ok(xml.to_string());
    }
    let Some(end) = xml.rfind("</p:sld>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:sld>".to_string(),
        ));
    };
    let timing = format!(
        r#"<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>{}</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"#,
        movie_timing_child_xml(shape_id, 2)
    );
    Ok(format!("{}{}{}", &xml[..end], timing, &xml[end..]))
}

fn movie_timing_child_xml(shape_id: u64, timing_id: u64) -> String {
    format!(
        r#"<p:video><p:cMediaNode vol="80000"><p:cTn id="{timing_id}" fill="hold" display="0"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl></p:cMediaNode></p:video>"#
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
