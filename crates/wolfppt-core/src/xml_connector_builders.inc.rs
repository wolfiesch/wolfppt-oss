#[allow(clippy::too_many_arguments)]
fn add_connector_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
    begin_connection: Option<ConnectorConnectionSpec>,
    end_connection: Option<ConnectorConnectionSpec>,
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
                let connector = connector_shape_xml(
                    shape_id,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                    begin_connection,
                    end_connection,
                )?;
                return Ok(format!("{}{}{}", &xml[..insert_at], connector, &xml[insert_at..]));
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
fn add_group_shape_with_connector_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    group_shape_id: u64,
    connector_shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
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
                let connector = connector_shape_xml(
                    connector_shape_id,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                    None,
                    None,
                )?;
                let group_shape = group_shape_with_child_xml(group_shape_id, &connector);
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
fn add_connected_connector_with_auto_shapes_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    begin_shape_id: u64,
    begin_display_name: &str,
    begin_preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    begin_cx_emu: u64,
    begin_cy_emu: u64,
    end_shape_id: u64,
    end_display_name: &str,
    end_preset_geometry: &str,
    end_x_emu: u64,
    end_y_emu: u64,
    end_cx_emu: u64,
    end_cy_emu: u64,
    connector_shape_id: u64,
    connector_preset_geometry: &str,
    connector_begin_x_emu: u64,
    connector_begin_y_emu: u64,
    connector_end_x_emu: u64,
    connector_end_y_emu: u64,
    begin_cxn_pt_idx: u64,
    end_cxn_pt_idx: u64,
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
                let begin_shape = auto_shape_xml(
                    begin_shape_id,
                    begin_display_name,
                    begin_preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    begin_cx_emu,
                    begin_cy_emu,
                    None,
                    &[],
                )?;
                let end_shape = auto_shape_xml(
                    end_shape_id,
                    end_display_name,
                    end_preset_geometry,
                    end_x_emu,
                    end_y_emu,
                    end_cx_emu,
                    end_cy_emu,
                    None,
                    &[],
                )?;
                let connector = connector_shape_xml(
                    connector_shape_id,
                    connector_preset_geometry,
                    connector_begin_x_emu,
                    connector_begin_y_emu,
                    connector_end_x_emu,
                    connector_end_y_emu,
                    Some(ConnectorConnectionSpec {
                        target_shape_id: begin_shape_id,
                        cxn_pt_idx: begin_cxn_pt_idx,
                    }),
                    Some(ConnectorConnectionSpec {
                        target_shape_id: end_shape_id,
                        cxn_pt_idx: end_cxn_pt_idx,
                    }),
                )?;
                return Ok(format!(
                    "{}{}{}{}{}",
                    &xml[..insert_at],
                    begin_shape,
                    end_shape,
                    connector,
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
fn add_connector_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
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
    let connector = connector_shape_xml(
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        None,
        None,
    )?;
    Ok(format!("{}{}{}", &xml[..insert_at], connector, &xml[insert_at..]))
}

#[allow(clippy::too_many_arguments)]
fn add_connector_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
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
    let connector = connector_shape_xml(
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        None,
        None,
    )?;
    Ok(format!("{}{}{}", &xml[..insert_at], connector, &xml[insert_at..]))
}

fn add_connector_to_slide_xml(
    xml: &str,
    shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let connector = connector_shape_xml(
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        None,
        None,
    )?;
    Ok(format!("{}{}{}", &xml[..end], connector, &xml[end..]))
}

#[allow(clippy::too_many_arguments)]
fn add_connected_connector_to_slide_xml(
    xml: &str,
    shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
    begin_connection: Option<ConnectorConnectionSpec>,
    end_connection: Option<ConnectorConnectionSpec>,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let connector = connector_shape_xml(
        shape_id,
        preset_geometry,
        begin_x_emu,
        begin_y_emu,
        end_x_emu,
        end_y_emu,
        begin_connection,
        end_connection,
    )?;
    Ok(format!("{}{}{}", &xml[..end], connector, &xml[end..]))
}

#[allow(clippy::too_many_arguments)]
fn add_connected_connector_with_auto_shapes_to_slide_xml(
    xml: &str,
    begin_shape_id: u64,
    begin_preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    begin_cx_emu: u64,
    begin_cy_emu: u64,
    end_shape_id: u64,
    end_preset_geometry: &str,
    end_x_emu: u64,
    end_y_emu: u64,
    end_cx_emu: u64,
    end_cy_emu: u64,
    connector_shape_id: u64,
    connector_preset_geometry: &str,
    connector_begin_x_emu: u64,
    connector_begin_y_emu: u64,
    connector_end_x_emu: u64,
    connector_end_y_emu: u64,
    begin_cxn_pt_idx: u64,
    end_cxn_pt_idx: u64,
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let begin_display_name = auto_shape_display_name(begin_preset_geometry)?;
    let end_display_name = auto_shape_display_name(end_preset_geometry)?;
    let begin_shape = auto_shape_xml(
        begin_shape_id,
        begin_display_name,
        begin_preset_geometry,
        begin_x_emu,
        begin_y_emu,
        begin_cx_emu,
        begin_cy_emu,
        None,
        &[],
    )?;
    let end_shape = auto_shape_xml(
        end_shape_id,
        end_display_name,
        end_preset_geometry,
        end_x_emu,
        end_y_emu,
        end_cx_emu,
        end_cy_emu,
        None,
        &[],
    )?;
    let connector = connector_shape_xml(
        connector_shape_id,
        connector_preset_geometry,
        connector_begin_x_emu,
        connector_begin_y_emu,
        connector_end_x_emu,
        connector_end_y_emu,
        Some(ConnectorConnectionSpec {
            target_shape_id: begin_shape_id,
            cxn_pt_idx: begin_cxn_pt_idx,
        }),
        Some(ConnectorConnectionSpec {
            target_shape_id: end_shape_id,
            cxn_pt_idx: end_cxn_pt_idx,
        }),
    )?;
    Ok(format!(
        "{}{}{}{}{}",
        &xml[..end],
        begin_shape,
        end_shape,
        connector,
        &xml[end..]
    ))
}

fn connector_preset_geometry(preset_geometry: &str) -> Result<&'static str, WolfPptError> {
    match preset_geometry {
        "line" => Ok("Connector"),
        "bentConnector3" => Ok("Connector"),
        "curvedConnector3" => Ok("Connector"),
        _ => Err(WolfPptError::InvalidInput(format!(
            "unsupported connector preset geometry: {preset_geometry}"
        ))),
    }
}

#[allow(clippy::too_many_arguments)]
fn connector_shape_xml(
    shape_id: u64,
    preset_geometry: &str,
    begin_x_emu: u64,
    begin_y_emu: u64,
    end_x_emu: u64,
    end_y_emu: u64,
    begin_connection: Option<ConnectorConnectionSpec>,
    end_connection: Option<ConnectorConnectionSpec>,
) -> Result<String, WolfPptError> {
    connector_preset_geometry(preset_geometry)?;
    let shape_number = shape_id.saturating_sub(1);
    let x_emu = begin_x_emu.min(end_x_emu);
    let y_emu = begin_y_emu.min(end_y_emu);
    let cx_emu = begin_x_emu.abs_diff(end_x_emu);
    let cy_emu = begin_y_emu.abs_diff(end_y_emu);
    let mut flip_attrs = String::new();
    if begin_x_emu > end_x_emu {
        flip_attrs.push_str(r#" flipH="1""#);
    }
    if begin_y_emu > end_y_emu {
        flip_attrs.push_str(r#" flipV="1""#);
    }
    let connection_xml = connector_connection_xml(begin_connection, end_connection);
    Ok(format!(
        r#"<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="Connector {shape_number}"/>{connection_xml}<p:nvPr/></p:nvCxnSpPr><p:spPr><a:xfrm{flip_attrs}><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="{preset_geometry}"><a:avLst/></a:prstGeom></p:spPr><p:style><a:lnRef idx="2"><a:schemeClr val="accent1"/></a:lnRef><a:fillRef idx="0"><a:schemeClr val="accent1"/></a:fillRef><a:effectRef idx="1"><a:schemeClr val="accent1"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="tx1"/></a:fontRef></p:style></p:cxnSp>"#
    ))
}

#[derive(Clone, Copy, Debug)]
struct ConnectorConnectionSpec {
    target_shape_id: u64,
    cxn_pt_idx: u64,
}

fn connector_connection_xml(
    begin_connection: Option<ConnectorConnectionSpec>,
    end_connection: Option<ConnectorConnectionSpec>,
) -> String {
    if begin_connection.is_none() && end_connection.is_none() {
        return "<p:cNvCxnSpPr/>".to_string();
    }
    let mut xml = String::from("<p:cNvCxnSpPr>");
    if let Some(connection) = begin_connection {
        xml.push_str(&format!(
            r#"<a:stCxn id="{}" idx="{}"/>"#,
            connection.target_shape_id, connection.cxn_pt_idx
        ));
    }
    if let Some(connection) = end_connection {
        xml.push_str(&format!(
            r#"<a:endCxn id="{}" idx="{}"/>"#,
            connection.target_shape_id, connection.cxn_pt_idx
        ));
    }
    xml.push_str("</p:cNvCxnSpPr>");
    xml
}
