fn placeholder_shape_xml(
    slide_xml: &str,
    shape_id: u64,
    placeholder_type: Option<&str>,
    placeholder_orient: Option<&str>,
    placeholder_size: Option<&str>,
    placeholder_idx: Option<&str>,
) -> String {
    let name = placeholder_name(slide_xml, shape_id, placeholder_type, placeholder_orient);
    let ph_attrs =
        placeholder_attrs(placeholder_type, placeholder_orient, placeholder_size, placeholder_idx);
    format!(
        r#"<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph{ph_attrs}/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"#
    )
}

fn placeholder_attrs(
    placeholder_type: Option<&str>,
    placeholder_orient: Option<&str>,
    placeholder_size: Option<&str>,
    placeholder_idx: Option<&str>,
) -> String {
    let mut attrs = String::new();
    if let Some(value) = placeholder_type {
        if !value.is_empty() && value != "obj" {
            attrs.push_str(&format!(r#" type="{}""#, xml_attr(value)));
        }
    }
    if let Some(value) = placeholder_orient {
        if !value.is_empty() && value != "horz" {
            attrs.push_str(&format!(r#" orient="{}""#, xml_attr(value)));
        }
    }
    if let Some(value) = placeholder_size {
        if !value.is_empty() && value != "full" {
            attrs.push_str(&format!(r#" sz="{}""#, xml_attr(value)));
        }
    }
    if let Some(value) = placeholder_idx {
        if !value.is_empty() && value != "0" {
            attrs.push_str(&format!(r#" idx="{}""#, xml_attr(value)));
        }
    }
    attrs
}

fn placeholder_name(
    slide_xml: &str,
    shape_id: u64,
    placeholder_type: Option<&str>,
    placeholder_orient: Option<&str>,
) -> String {
    let mut basename = placeholder_basename(placeholder_type).to_string();
    if matches!(placeholder_orient, Some("vert")) {
        basename = format!("Vertical {basename}");
    }
    let names = c_nv_pr_names(slide_xml);
    let mut suffix = shape_id.saturating_sub(1);
    loop {
        let candidate = format!("{basename} {suffix}");
        if !names.iter().any(|name| name == &candidate) {
            return xml_attr(&candidate);
        }
        suffix += 1;
    }
}

fn placeholder_basename(placeholder_type: Option<&str>) -> &'static str {
    match placeholder_type.unwrap_or("obj") {
        "body" => "Text Placeholder",
        "chart" => "Chart Placeholder",
        "clipArt" => "ClipArt Placeholder",
        "ctrTitle" | "title" => "Title",
        "dgm" => "SmartArt Placeholder",
        "dt" => "Date Placeholder",
        "ftr" => "Footer Placeholder",
        "media" => "Media Placeholder",
        "pic" => "Picture Placeholder",
        "sldImg" => "Image Placeholder",
        "sldNum" => "Slide Number Placeholder",
        "subTitle" => "Subtitle",
        "tbl" => "Table Placeholder",
        _ => "Content Placeholder",
    }
}

fn placeholder_specs_from_layout_xml(xml: &str) -> Vec<PlaceholderShapeSpec> {
    let mut placeholders = Vec::new();
    let mut offset = 0;
    while let Some(relative_start) = xml[offset..].find("<p:sp>") {
        let start = offset + relative_start;
        let Some(relative_end) = xml[start..].find("</p:sp>") else {
            break;
        };
        let end = start + relative_end + "</p:sp>".len();
        let block = &xml[start..end];
        if let Some(ph_tag) = placeholder_tag(block) {
            let placeholder_type = extract_string_attribute(ph_tag, "type");
            if matches!(
                placeholder_type.as_deref(),
                Some("dt" | "ftr" | "sldNum")
            ) {
                offset = end;
                continue;
            }
            placeholders.push(PlaceholderShapeSpec {
                placeholder_type,
                placeholder_orient: extract_string_attribute(ph_tag, "orient"),
                placeholder_size: extract_string_attribute(ph_tag, "sz"),
                placeholder_idx: extract_string_attribute(ph_tag, "idx"),
            });
        }
        offset = end;
    }
    placeholders
}

fn placeholder_tag(block: &str) -> Option<&str> {
    let start = block.find("<p:ph")?;
    let end = block[start..].find('>')?;
    Some(&block[start..start + end])
}

