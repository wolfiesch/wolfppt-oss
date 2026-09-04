#[allow(clippy::too_many_arguments)]
fn add_auto_shape_to_group_shape_xml(
    xml: &str,
    group_index: usize,
    shape_id: u64,
    display_name: &str,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides: &[(String, i64)],
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
                let auto_shape = auto_shape_xml(
                    shape_id,
                    display_name,
                    preset_geometry,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    text,
                    adjustment_guides,
                )?;
                return Ok(format!("{}{}{}", &xml[..insert_at], auto_shape, &xml[insert_at..]));
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
fn add_auto_shape_to_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    shape_id: u64,
    display_name: &str,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides: &[(String, i64)],
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
    let auto_shape = auto_shape_xml(
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
        adjustment_guides,
    )?;
    Ok(format!("{}{}{}", &xml[..insert_at], auto_shape, &xml[insert_at..]))
}

#[allow(clippy::too_many_arguments)]
fn add_auto_shape_to_deeper_nested_group_shape_xml(
    xml: &str,
    group_index: usize,
    nested_group_child_index: usize,
    deeper_group_child_index: usize,
    shape_id: u64,
    display_name: &str,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides: &[(String, i64)],
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
    let auto_shape = auto_shape_xml(
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
        adjustment_guides,
    )?;
    Ok(format!("{}{}{}", &xml[..insert_at], auto_shape, &xml[insert_at..]))
}

#[allow(clippy::too_many_arguments)]
fn add_auto_shape_to_slide_xml(
    xml: &str,
    shape_id: u64,
    display_name: &str,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides: &[(String, i64)],
) -> Result<String, WolfPptError> {
    let Some(end) = xml.rfind("</p:spTree>") else {
        return Err(WolfPptError::InvalidInput(
            "slide XML is missing </p:spTree>".to_string(),
        ));
    };
    let auto_shape = auto_shape_xml(
        shape_id,
        display_name,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        text,
        adjustment_guides,
    )?;
    Ok(format!("{}{}{}", &xml[..end], auto_shape, &xml[end..]))
}

fn auto_shape_display_name(preset_geometry: &str) -> Result<&'static str, WolfPptError> {
    match preset_geometry {
        "rect" => Ok("Rectangle"),
        "parallelogram" => Ok("Parallelogram"),
        "trapezoid" => Ok("Trapezoid"),
        "ellipse" => Ok("Oval"),
        "roundRect" => Ok("Rounded Rectangle"),
        "triangle" => Ok("Triangle"),
        "rtTriangle" => Ok("Right Triangle"),
        "diamond" => Ok("Diamond"),
        "hexagon" => Ok("Hexagon"),
        "octagon" => Ok("Octagon"),
        "plus" => Ok("Cross"),
        "can" => Ok("Can"),
        "cube" => Ok("Cube"),
        "smileyFace" => Ok("Smiley Face"),
        "donut" => Ok("Donut"),
        "noSmoking" => Ok("No Symbol"),
        "blockArc" => Ok("Block Arc"),
        "heart" => Ok("Heart"),
        "arc" => Ok("Arc"),
        "plaque" => Ok("Plaque"),
        "rightArrow" => Ok("Right Arrow"),
        "leftArrow" => Ok("Left Arrow"),
        "upArrow" => Ok("Up Arrow"),
        "downArrow" => Ok("Down Arrow"),
        "homePlate" => Ok("Pentagon"),
        "chevron" => Ok("Chevron"),
        "flowChartProcess" => Ok("Flowchart Process"),
        "flowChartDecision" => Ok("Flowchart Decision"),
        "flowChartInputOutput" => Ok("Flowchart Data"),
        "flowChartDocument" => Ok("Flowchart Document"),
        "flowChartOfflineStorage" => Ok("Flowchart Offline Storage"),
        "star5" => Ok("5-Point Star"),
        "leftRightRibbon" => Ok("Left Right Ribbon"),
        "borderCallout2" => Ok("Line Callout 2"),
        "cloud" => Ok("Cloud"),
        "pentagon" | "bevel" | "foldedCorner" | "lightningBolt" | "sun" | "moon"
        | "bracketPair" | "bracePair" | "leftBracket" | "rightBracket"
        | "leftBrace" | "rightBrace" | "leftRightArrow" | "upDownArrow"
        | "quadArrow" | "leftRightUpArrow" | "bentArrow" | "uturnArrow"
        | "leftUpArrow" | "bentUpArrow" | "curvedRightArrow" | "curvedLeftArrow"
        | "curvedUpArrow" | "curvedDownArrow" | "stripedRightArrow"
        | "notchedRightArrow" | "rightArrowCallout" | "leftArrowCallout"
        | "upArrowCallout" | "downArrowCallout" | "leftRightArrowCallout"
        | "upDownArrowCallout" | "quadArrowCallout" | "circularArrow"
        | "flowChartAlternateProcess" | "flowChartPredefinedProcess"
        | "flowChartInternalStorage" | "flowChartMultidocument"
        | "flowChartTerminator" | "flowChartPreparation" | "flowChartManualInput"
        | "flowChartManualOperation" | "flowChartConnector"
        | "flowChartOffpageConnector" | "flowChartPunchedCard"
        | "flowChartPunchedTape" | "flowChartSummingJunction" | "flowChartOr"
        | "flowChartCollate" | "flowChartSort" | "flowChartExtract"
        | "flowChartMerge" | "flowChartOnlineStorage" | "flowChartDelay"
        | "flowChartMagneticTape" | "flowChartMagneticDisk" | "flowChartMagneticDrum"
        | "flowChartDisplay" | "irregularSeal1" | "irregularSeal2" | "star4"
        | "star8" | "star16" | "star24" | "star32" | "ribbon2" | "ribbon"
        | "ellipseRibbon2" | "ellipseRibbon" | "verticalScroll" | "horizontalScroll"
        | "wave" | "doubleWave" | "wedgeRectCallout" | "wedgeRoundRectCallout"
        | "wedgeEllipseCallout" | "cloudCallout" | "borderCallout1"
        | "borderCallout3" | "accentCallout1" | "accentCallout2"
        | "accentCallout3" | "callout1" | "callout2" | "callout3"
        | "accentBorderCallout1" | "accentBorderCallout2" | "accentBorderCallout3"
        | "actionButtonBlank" | "actionButtonHome" | "actionButtonHelp"
        | "actionButtonInformation" | "actionButtonBackPrevious"
        | "actionButtonForwardNext" | "actionButtonBeginning" | "actionButtonEnd"
        | "actionButtonReturn" | "actionButtonDocument" | "actionButtonSound"
        | "actionButtonMovie"
        | "diagStripe" | "pie" | "nonIsoscelesTrapezoid" | "decagon" | "heptagon"
        | "dodecagon" | "star6" | "star7" | "star10" | "star12" | "round1Rect"
        | "round2SameRect" | "round2DiagRect" | "snipRoundRect" | "snip1Rect"
        | "snip2SameRect" | "snip2DiagRect" | "frame" | "halfFrame" | "teardrop"
        | "chord" | "corner" | "mathPlus" | "mathMinus" | "mathMultiply"
        | "mathDivide" | "mathEqual" | "mathNotEqual" | "cornerTabs" | "squareTabs"
        | "plaqueTabs" | "gear6" | "gear9" | "funnel" | "pieWedge"
        | "leftCircularArrow" | "leftRightCircularArrow" | "swooshArrow" | "chartX"
        | "chartStar" | "chartPlus" | "lineInv" => Ok("Auto Shape"),
        _ => Err(WolfPptError::InvalidInput(format!(
            "unsupported auto shape preset geometry: {preset_geometry}"
        ))),
    }
}

#[allow(clippy::too_many_arguments)]
fn auto_shape_xml(
    shape_id: u64,
    display_name: &str,
    preset_geometry: &str,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    text: Option<&str>,
    adjustment_guides: &[(String, i64)],
) -> Result<String, WolfPptError> {
    auto_shape_display_name(preset_geometry)?;
    let shape_number = shape_id.saturating_sub(1);
    let paragraph_xml = match text {
        Some(text) => replacement_paragraphs_xml(text)?,
        None => r#"<a:p><a:pPr algn="ctr"/></a:p>"#.to_string(),
    };
    let adjustment_xml = adjustment_guides_xml(adjustment_guides);
    Ok(format!(
        r#"<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{display_name} {shape_number}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm><a:prstGeom prst="{preset_geometry}"><a:avLst>{adjustment_xml}</a:avLst></a:prstGeom></p:spPr><p:style><a:lnRef idx="1"><a:schemeClr val="accent1"/></a:lnRef><a:fillRef idx="3"><a:schemeClr val="accent1"/></a:fillRef><a:effectRef idx="2"><a:schemeClr val="accent1"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style><p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/>{paragraph_xml}</p:txBody></p:sp>"#
    ))
}

fn adjustment_guides_xml(adjustment_guides: &[(String, i64)]) -> String {
    adjustment_guides
        .iter()
        .map(|(name, value)| format!(r#"<a:gd name="{name}" fmla="val {value}"/>"#))
        .collect::<String>()
}
