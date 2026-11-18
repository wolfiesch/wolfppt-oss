const RUN_COLOR_DECK: &str = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";

/// A run formatting edit on global run 1 ("Fast PPTX") that only sets colour.
fn run_color_edit(color: Option<&str>, color_model: Option<DrawingColor>) -> EditOperation {
    EditOperation::SetTextRunFormatting {
        slide_index: 0,
        run_index: 1,
        set_bold: false,
        bold: None,
        set_italic: false,
        italic: None,
        set_underline: false,
        underline: None,
        set_strike: false,
        strike: None,
        set_size: false,
        size: None,
        set_name: false,
        name: None,
        set_color: true,
        color: color.map(str::to_string),
        color_model,
    }
}

/// Applies `edit` to the fixture and returns slide 1 XML plus the summary
/// colour of the "Fast PPTX" run.
fn apply_run_color(edit: EditOperation) -> Result<(String, Option<RunColorSummary>), WolfPptError> {
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-color.pptx");
    let result = apply_edit_batch(RUN_COLOR_DECK, &out, &[edit])?;
    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 1);
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let color = summary.slides[0]
        .shapes
        .iter()
        .find_map(|shape| {
            shape
                .paragraph_runs
                .iter()
                .enumerate()
                .find_map(|(paragraph, runs)| {
                    runs.iter()
                        .position(|run| run == "Fast PPTX")
                        .map(|run| shape.paragraph_run_color[paragraph][run].clone())
                })
        })
        .expect("fixture has a Fast PPTX run");
    Ok((slide_xml, color))
}

fn run_color(kind: RunColorKind) -> RunColorSummary {
    RunColorSummary {
        kind,
        value: None,
        r: None,
        g: None,
        b: None,
        last_color: None,
        rgb_hex: None,
    }
}

fn assert_refused(edit: EditOperation, fragment: &str) {
    match apply_run_color(edit) {
        Err(WolfPptError::InvalidInput(message)) => {
            assert!(message.contains(fragment), "{message}")
        }
        other => panic!("expected an invalid input refusal, got {other:?}"),
    }
}

#[test]
fn run_color_model_srgb_is_written_uppercased_and_read_back() {
    let (slide_xml, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::Srgb {
            value: "a1b2c3".to_string(),
        }),
    ))
    .unwrap();
    assert!(slide_xml.contains(
        r#"<a:rPr><a:solidFill><a:srgbClr val="A1B2C3"/></a:solidFill></a:rPr><a:t>Fast PPTX</a:t>"#
    ));
    assert_eq!(
        color,
        Some(RunColorSummary {
            value: Some("A1B2C3".to_string()),
            rgb_hex: Some("A1B2C3".to_string()),
            ..run_color(RunColorKind::Srgb)
        })
    );
}

#[test]
fn run_color_model_preset_is_written_and_read_back() {
    let (slide_xml, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::Preset {
            value: "aquamarine".to_string(),
        }),
    ))
    .unwrap();
    assert!(slide_xml.contains(
        r#"<a:rPr><a:solidFill><a:prstClr val="aquamarine"/></a:solidFill></a:rPr><a:t>Fast PPTX</a:t>"#
    ));
    assert_eq!(
        color,
        Some(RunColorSummary {
            value: Some("aquamarine".to_string()),
            ..run_color(RunColorKind::Preset)
        })
    );
}

#[test]
fn run_color_model_system_is_written_with_optional_last_color() {
    let (slide_xml, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::System {
            value: "captionText".to_string(),
            last_color: None,
        }),
    ))
    .unwrap();
    assert!(slide_xml.contains(
        r#"<a:rPr><a:solidFill><a:sysClr val="captionText"/></a:solidFill></a:rPr><a:t>Fast PPTX</a:t>"#
    ));
    assert_eq!(
        color,
        Some(RunColorSummary {
            value: Some("captionText".to_string()),
            ..run_color(RunColorKind::System)
        })
    );

    let (slide_xml, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::System {
            value: "windowText".to_string(),
            last_color: Some("0a0b0c".to_string()),
        }),
    ))
    .unwrap();
    assert!(slide_xml
        .contains(r#"<a:solidFill><a:sysClr val="windowText" lastClr="0A0B0C"/></a:solidFill>"#));
    assert_eq!(
        color,
        Some(RunColorSummary {
            value: Some("windowText".to_string()),
            last_color: Some("0A0B0C".to_string()),
            rgb_hex: Some("0A0B0C".to_string()),
            ..run_color(RunColorKind::System)
        })
    );
}

#[test]
fn run_color_model_scrgb_channels_are_clamped_and_companded() {
    let (slide_xml, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::Scrgb {
            r: -1,
            g: -1,
            b: -1,
        }),
    ))
    .unwrap();
    assert!(slide_xml.contains(
        r#"<a:rPr><a:solidFill><a:scrgbClr r="0" g="0" b="0"/></a:solidFill></a:rPr><a:t>Fast PPTX</a:t>"#
    ));
    assert_eq!(
        color,
        Some(RunColorSummary {
            r: Some(0),
            g: Some(0),
            b: Some(0),
            rgb_hex: Some("000000".to_string()),
            ..run_color(RunColorKind::Scrgb)
        })
    );

    let (slide_xml, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::Scrgb {
            r: 654321,
            g: 654321,
            b: 654321,
        }),
    ))
    .unwrap();
    assert!(slide_xml
        .contains(r#"<a:solidFill><a:scrgbClr r="100000" g="100000" b="100000"/></a:solidFill>"#));
    assert_eq!(
        color,
        Some(RunColorSummary {
            r: Some(100000),
            g: Some(100000),
            b: Some(100000),
            rgb_hex: Some("FFFFFF".to_string()),
            ..run_color(RunColorKind::Scrgb)
        })
    );

    // 50% linear light companded to sRGB is 188 (0xBC).
    let (_, color) = apply_run_color(run_color_edit(
        None,
        Some(DrawingColor::Scrgb {
            r: 50000,
            g: 0,
            b: 100000,
        }),
    ))
    .unwrap();
    assert_eq!(
        color.and_then(|color| color.rgb_hex),
        Some("BC00FF".to_string())
    );
}

#[test]
fn run_color_model_refuses_unknown_tokens_malformed_hex_and_both_colors() {
    let preset = |value: &str| {
        run_color_edit(
            None,
            Some(DrawingColor::Preset {
                value: value.to_string(),
            }),
        )
    };
    assert_refused(preset("notAColor"), "ST_PresetColorVal");
    // Tokens are case-sensitive, as in the schema.
    assert_refused(preset("Aquamarine"), "ST_PresetColorVal");
    assert_refused(
        run_color_edit(
            None,
            Some(DrawingColor::System {
                value: "captiontext".to_string(),
                last_color: None,
            }),
        ),
        "ST_SystemColorVal",
    );
    assert_refused(
        run_color_edit(
            None,
            Some(DrawingColor::System {
                value: "captionText".to_string(),
                last_color: Some("12345".to_string()),
            }),
        ),
        "last_color",
    );
    for value in ["12345", "1234567", "GGGGGG", "#12345"] {
        assert_refused(
            run_color_edit(
                None,
                Some(DrawingColor::Srgb {
                    value: value.to_string(),
                }),
            ),
            "six hex digits",
        );
    }
    assert_refused(
        run_color_edit(
            Some("123456"),
            Some(DrawingColor::Preset {
                value: "aquamarine".to_string(),
            }),
        ),
        "not both",
    );
}

#[test]
fn legacy_run_color_hex_path_is_unchanged() {
    let (slide_xml, color) = apply_run_color(run_color_edit(Some("abcdef"), None)).unwrap();
    // The legacy string is written verbatim, as before color_model existed.
    assert!(slide_xml.contains(
        r#"<a:rPr><a:solidFill><a:srgbClr val="abcdef"/></a:solidFill></a:rPr><a:t>Fast PPTX</a:t>"#
    ));
    assert_eq!(
        color,
        Some(RunColorSummary {
            value: Some("ABCDEF".to_string()),
            rgb_hex: Some("ABCDEF".to_string()),
            ..run_color(RunColorKind::Srgb)
        })
    );
}

#[test]
fn run_color_model_replaces_and_removes_an_existing_fill() {
    let source = br#"<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:rPr b="1"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>first</a:t></a:r></a:p>"#;
    let model = run_color_edit(
        None,
        Some(DrawingColor::Preset {
            value: "dkSlateGray".to_string(),
        }),
    );
    let mut replace = text_run_formatting_edit(&model).unwrap().unwrap();
    replace.0 = 0;
    let (replaced, count) = set_text_run_formatting_batch_in_slide(source, &[replace]).unwrap();
    assert_eq!(count, 1);
    assert_eq!(
        String::from_utf8(replaced.clone()).unwrap(),
        r#"<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:rPr b="1"><a:solidFill><a:prstClr val="dkSlateGray"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>first</a:t></a:r></a:p>"#
    );

    let removal = run_color_edit(None, None);
    let mut remove = text_run_formatting_edit(&removal).unwrap().unwrap();
    remove.0 = 0;
    let (removed, count) = set_text_run_formatting_batch_in_slide(&replaced, &[remove]).unwrap();
    assert_eq!(count, 1);
    assert_eq!(
        String::from_utf8(removed.clone()).unwrap(),
        r#"<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:rPr b="1"><a:latin typeface="Aptos"/></a:rPr><a:t>first</a:t></a:r></a:p>"#
    );
    assert_eq!(extract_paragraph_run_color(&removed), vec![vec![None]]);
}

#[test]
fn run_color_summary_reads_only_the_direct_rpr_solid_fill_child() {
    let xml = br#"<a:txBody xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:rPr><a:solidFill><a:schemeClr val="accent1"><a:lumMod val="75000"/></a:schemeClr></a:solidFill></a:rPr><a:t>scheme</a:t></a:r><a:r><a:rPr><a:solidFill><a:hslClr hue="0" sat="100000" lum="50000"/></a:solidFill></a:rPr><a:t>hsl</a:t></a:r><a:r><a:rPr><a:ln><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:ln><a:highlight><a:srgbClr val="00FF00"/></a:highlight></a:rPr><a:t>outline</a:t></a:r><a:r><a:rPr b="1"/><a:t>plain</a:t></a:r><a:r><a:rPr><a:solidFill><a:sysClr val="window" lastClr="ffffff"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>sys</a:t></a:r><a:r><a:rPr><a:solidFill><a:scrgbClr r="-5" g="250000" b="0"/></a:solidFill></a:rPr><a:t>raw</a:t></a:r></a:p></a:txBody>"#;
    assert_eq!(
        extract_paragraph_run_color(xml),
        vec![vec![
            Some(RunColorSummary {
                value: Some("accent1".to_string()),
                ..run_color(RunColorKind::Scheme)
            }),
            Some(run_color(RunColorKind::Hsl)),
            None,
            None,
            Some(RunColorSummary {
                value: Some("window".to_string()),
                last_color: Some("FFFFFF".to_string()),
                rgb_hex: Some("FFFFFF".to_string()),
                ..run_color(RunColorKind::System)
            }),
            // Stored channels are reported as written; only rgb_hex clamps.
            Some(RunColorSummary {
                r: Some(-5),
                g: Some(250000),
                b: Some(0),
                rgb_hex: Some("00FF00".to_string()),
                ..run_color(RunColorKind::Scrgb)
            }),
        ]]
    );
    assert_eq!(
        extract_paragraph_run_font_name(xml)[0][4],
        Some("Aptos".to_string())
    );
}
