#[test]
fn applies_text_edit_batch_without_rewriting_package_parts_repeatedly() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("edit-batch.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[
            EditOperation::SetShapeText {
                slide_index: 0,
                shape_index: 0,
                replacement: "WolfPPT Native".to_string(),
            },
            EditOperation::ReplaceTextRun {
                slide_index: 0,
                run_index: 1,
                replacement: "Fast Native".to_string(),
            },
            EditOperation::SetParagraphText {
                slide_index: 0,
                shape_index: 1,
                paragraph_index: 1,
                replacement: "Second".to_string(),
            },
            EditOperation::AppendParagraphText {
                slide_index: 0,
                shape_index: 1,
                text: "Appended".to_string(),
            },
            EditOperation::AppendTextRun {
                slide_index: 0,
                shape_index: 1,
                paragraph_index: 0,
                text: " Decks".to_string(),
            },
            EditOperation::SetShapeGeometry {
                slide_index: 0,
                shape_index: 0,
                x_emu: 914400,
                y_emu: 1828800,
                cx_emu: 2743200,
                cy_emu: 914400,
            },
        ],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.edits, 6);
    assert_eq!(result.replacements, 6);
    assert_eq!(
        summary.slides[0].shapes[0].transform,
        Some(TransformSummary {
            x: 914400,
            y: 1828800,
            cx: 2743200,
            cy: 914400,
        })
    );
    assert_eq!(summary.slides[0].shapes[0].text, "WolfPPT Native");
    assert_eq!(
        summary.slides[0].shapes[1].text,
        "Fast Native Decks\nSecond\nAppended"
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn appends_text_run_in_empty_text_box_paragraph() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let text_box = dir.path().join("empty-text-box.pptx");
    let out = dir.path().join("appended-text-run.pptx");

    add_slide_text_box(source, &text_box, 0, 914400, 2743200, 3657600, 914400).unwrap();
    apply_edit_batch(
        &text_box,
        &out,
        &[EditOperation::AppendTextRun {
            slide_index: 0,
            shape_index: 2,
            paragraph_index: 0,
            text: "controlled font asset".to_string(),
        }],
    )
    .unwrap();

    let summary = summarize_presentation(&out).unwrap();
    assert_eq!(summary.slides[0].shapes[2].text, "controlled font asset");
}

#[test]
fn applies_text_frame_property_batch() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("text-frame-properties-batch.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextFrameProperties {
            slide_index: 0,
            shape_index: 0,
            properties: TextFramePropertiesPatch {
                margins: std::collections::BTreeMap::from([
                    ("lIns".to_string(), Some(228600)),
                    ("rIns".to_string(), Some(114300)),
                    ("tIns".to_string(), Some(12345)),
                    ("bIns".to_string(), Some(0)),
                ]),
                set_word_wrap: true,
                word_wrap: Some("square".to_string()),
                set_vertical_anchor: true,
                vertical_anchor: Some("ctr".to_string()),
                set_auto_size: true,
                auto_size: Some("normAutofit".to_string()),
                set_autofit_scale: false,
                font_scale: None,
                line_spacing_reduction: None,
            },
        }],
    )
    .unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 7);
    assert!(slide_xml.contains(r#"lIns="228600""#));
    assert!(slide_xml.contains(r#"rIns="114300""#));
    assert!(slide_xml.contains(r#"tIns="12345""#));
    assert!(slide_xml.contains(r#"bIns="0""#));
    assert!(slide_xml.contains(r#"wrap="square""#));
    assert!(slide_xml.contains(r#"anchor="ctr""#));
    assert!(slide_xml.contains("<a:normAutofit/>"));
}

#[test]
fn clears_text_frame_margins_set_to_none() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let authored = dir.path().join("text-frame-margins-authored.pptx");
    let cleared = dir.path().join("text-frame-margins-cleared.pptx");
    let edit = |margins: &[(&str, Option<i64>)]| EditOperation::SetTextFrameProperties {
        slide_index: 0,
        shape_index: 0,
        properties: TextFramePropertiesPatch {
            margins: margins
                .iter()
                .map(|(attribute, value)| (attribute.to_string(), *value))
                .collect(),
            ..TextFramePropertiesPatch::default()
        },
    };

    let explicit = edit(&[
        ("lIns", Some(228600)),
        ("rIns", Some(114300)),
        ("tIns", Some(12345)),
        ("bIns", Some(0)),
    ]);
    apply_edit_batch(source, &authored, &[explicit]).unwrap();
    let clear = edit(&[("lIns", None), ("bIns", None)]);
    apply_edit_batch(&authored, &cleared, &[clear]).unwrap();
    let slide_xml = read_zip_text(&cleared, "ppt/slides/slide1.xml");

    assert!(!slide_xml.contains("lIns="));
    assert!(!slide_xml.contains("bIns="));
    assert!(slide_xml.contains(r#"rIns="114300""#));
    assert!(slide_xml.contains(r#"tIns="12345""#));
}

#[test]
fn applies_paragraph_line_break_in_text_edit_batch() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("line-break-batch.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[
            EditOperation::AppendTextRun {
                slide_index: 0,
                shape_index: 1,
                paragraph_index: 0,
                text: "After".to_string(),
            },
            EditOperation::InsertParagraphLineBreak {
                slide_index: 0,
                shape_index: 1,
                paragraph_index: 0,
                run_slot: 1,
            },
        ],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.edits, 2);
    assert_eq!(result.replacements, 2);
    assert_eq!(
        summary.slides[0].shapes[1].paragraphs,
        vec![
            "Fast PPTX\u{000b}After".to_string(),
            "Lossless first".to_string(),
        ]
    );
    assert!(slide_xml.contains("<a:br/><a:r><a:t>After</a:t></a:r>"));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_paragraph_properties_in_text_edit_batch() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("paragraph-properties-batch.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[
            EditOperation::AppendParagraphText {
                slide_index: 0,
                shape_index: 1,
                text: "Third".to_string(),
            },
            EditOperation::SetParagraphProperties {
                slide_index: 0,
                shape_index: 1,
                paragraph_index: 2,
                set_alignment: true,
                alignment: Some("ctr".to_string()),
                set_level: true,
                level: 1,
                spacing: ParagraphSpacingPatch {
                    line_spacing: Some(ParagraphSpacingValue::Multiple { value: 1.25 }),
                    space_before: Some(ParagraphSpacingValue::Emu { value: 152400 }),
                    space_after: Some(ParagraphSpacingValue::Emu { value: 76200 }),
                },
            },
        ],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.edits, 2);
    assert_eq!(result.replacements, 6);
    assert_eq!(
        summary.slides[0].shapes[1].paragraphs,
        vec![
            "Fast PPTX".to_string(),
            "Lossless first".to_string(),
            "Third".to_string(),
        ]
    );
    assert!(slide_xml.contains(
            r#"<a:pPr algn="ctr" lvl="1"><a:lnSpc><a:spcPct val="125000"/></a:lnSpc><a:spcBef><a:spcPts val="1200"/></a:spcBef><a:spcAft><a:spcPts val="600"/></a:spcAft></a:pPr><a:r><a:t>Third</a:t></a:r>"#
        ));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_paragraph_font_properties_in_text_edit_batch() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("paragraph-font-batch.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetParagraphFontProperties {
            slide_index: 0,
            shape_index: 1,
            paragraph_index: 0,
            set_bold: true,
            bold: Some(true),
            set_italic: true,
            italic: Some(true),
            set_underline: true,
            underline: Some(true.into()),
            set_strike: false,
            strike: None,
            set_size: true,
            size: Some(228600),
            set_name: true,
            name: Some("Aptos".to_string()),
            set_color: true,
            color: Some("0C2238".to_string()),
            set_fill_type: false,
            fill_type: None,
            set_language: true,
            language_id: Some("de-DE".to_string()),
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 7);
    assert_eq!(
        summary.slides[0].shapes[1].paragraphs,
        vec!["Fast PPTX".to_string(), "Lossless first".to_string()]
    );
    assert!(slide_xml.contains(
            r#"<a:defRPr b="1" i="1" u="sng" sz="1800" lang="de-DE"><a:solidFill><a:srgbClr val="0C2238"/></a:solidFill><a:latin typeface="Aptos"/></a:defRPr>"#
        ));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_text_run_bold_batch_edit_without_losing_package_parts() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-bold.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextRunBold {
            slide_index: 0,
            run_index: 1,
            bold: Some(true),
        }],
    )
    .unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 1);
    assert!(slide_xml.contains(r#"<a:rPr b="1"/><a:t>Fast PPTX</a:t>"#));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_text_run_italic_batch_edit_without_losing_package_parts() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-italic.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextRunItalic {
            slide_index: 0,
            run_index: 1,
            italic: Some(true),
        }],
    )
    .unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 1);
    assert!(slide_xml.contains(r#"<a:rPr i="1"/><a:t>Fast PPTX</a:t>"#));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_text_run_underline_batch_edit_without_losing_package_parts() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-underline.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextRunUnderline {
            slide_index: 0,
            run_index: 1,
            underline: Some(true.into()),
        }],
    )
    .unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 1);
    assert!(slide_xml.contains(r#"<a:rPr u="sng"/><a:t>Fast PPTX</a:t>"#));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_text_run_font_size_batch_edit_without_losing_package_parts() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-size.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextRunFontSize {
            slide_index: 0,
            run_index: 1,
            size: Some(304800),
        }],
    )
    .unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 1);
    assert!(slide_xml.contains(r#"<a:rPr sz="2400"/><a:t>Fast PPTX</a:t>"#));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_text_run_font_name_batch_edit_without_losing_package_parts() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-name.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextRunFontName {
            slide_index: 0,
            run_index: 1,
            name: Some("Aptos".to_string()),
        }],
    )
    .unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 1);
    assert!(
        slide_xml.contains(r#"<a:rPr><a:latin typeface="Aptos"/></a:rPr><a:t>Fast PPTX</a:t>"#)
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_text_run_formatting_batch_edit_without_losing_package_parts() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-formatting.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetTextRunFormatting {
            slide_index: 0,
            run_index: 1,
            set_bold: true,
            bold: Some(true),
            set_italic: true,
            italic: Some(true),
            set_underline: true,
            underline: Some(true.into()),
            set_strike: false,
            strike: None,
            set_size: true,
            size: Some(304800),
            set_name: true,
            name: Some("Aptos".to_string()),
            set_color: true,
            color: Some("123456".to_string()),
            color_model: None,
        }],
    )
    .unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 1);
    assert_eq!(result.replacements, 6);
    assert!(slide_xml.contains(
            r#"<a:rPr b="1" i="1" u="sng" sz="2400"><a:solidFill><a:srgbClr val="123456"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>Fast PPTX</a:t>"#
        ));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(
        original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part))
    );
}

#[test]
fn applies_multiple_text_run_formatting_edits_in_one_batch() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-formatting-multi.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[
            EditOperation::SetTextRunFormatting {
                slide_index: 0,
                run_index: 1,
                set_bold: true,
                bold: Some(true),
                set_italic: true,
                italic: Some(true),
                set_underline: true,
                underline: Some(true.into()),
                set_strike: false,
                strike: None,
                set_size: true,
                size: Some(304800),
                set_name: true,
                name: Some("Aptos".to_string()),
                set_color: true,
                color: Some("123456".to_string()),
                color_model: None,
            },
            EditOperation::SetTextRunFormatting {
                slide_index: 0,
                run_index: 2,
                set_bold: true,
                bold: Some(true),
                set_italic: true,
                italic: Some(true),
                set_underline: true,
                underline: Some(true.into()),
                set_strike: false,
                strike: None,
                set_size: true,
                size: Some(304800),
                set_name: true,
                name: Some("Aptos".to_string()),
                set_color: true,
                color: Some("654321".to_string()),
                color_model: None,
            },
        ],
    )
    .unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 2);
    assert_eq!(result.replacements, 12);
    assert!(slide_xml.contains(
            r#"<a:rPr b="1" i="1" u="sng" sz="2400"><a:solidFill><a:srgbClr val="123456"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>Fast PPTX</a:t>"#
        ));
    assert!(slide_xml.contains(
            r#"<a:rPr b="1" i="1" u="sng" sz="2400"><a:solidFill><a:srgbClr val="654321"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>Lossless first</a:t>"#
        ));
}

#[test]
fn merges_duplicate_text_run_formatting_edits_in_one_batch() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("run-formatting-duplicate.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[
            EditOperation::SetTextRunFormatting {
                slide_index: 0,
                run_index: 1,
                set_bold: true,
                bold: Some(true),
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
                set_color: false,
                color: None,
                color_model: None,
            },
            EditOperation::SetTextRunFormatting {
                slide_index: 0,
                run_index: 1,
                set_bold: false,
                bold: None,
                set_italic: true,
                italic: Some(true),
                set_underline: false,
                underline: None,
                set_strike: false,
                strike: None,
                set_size: false,
                size: None,
                set_name: false,
                name: None,
                set_color: false,
                color: None,
                color_model: None,
            },
        ],
    )
    .unwrap();
    let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
    let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
        .unwrap()
        .unwrap();

    assert_eq!(result.edits, 2);
    assert_eq!(result.replacements, 2);
    assert!(slide_xml.contains(r#"<a:rPr b="1" i="1"/><a:t>Fast PPTX</a:t>"#));
}

#[test]
fn text_run_replacements_keep_indices_after_emptying_a_run() {
    let source = br#"<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:rPr b="1" i="0" u="sng" strike="noStrike" sz="1800"><a:latin typeface="Aptos"/></a:rPr><a:t>first</a:t></a:r><a:br/><a:r><a:rPr b="0" i="1"/><a:t>second</a:t></a:r><a:r><a:t>third</a:t></a:r></a:p>"#;
    let (empty, count) = replace_text_run_at_index_in_slide(source, 0, "").unwrap();
    assert_eq!(count, 1);
    let (replaced, count) = replace_text_run_at_index_in_slide(&empty, 2, "last").unwrap();
    assert_eq!(count, 1);
    assert_eq!(
        extract_paragraph_runs(&replaced),
        vec![vec!["", "second", "last"]]
    );
    assert_eq!(extract_paragraph_line_breaks(&replaced), vec![vec![1]]);
    assert_eq!(
        extract_paragraph_run_bold(&replaced),
        vec![vec![Some(true), Some(false), None]]
    );
    assert_eq!(
        extract_paragraph_run_italic(&replaced),
        vec![vec![Some(false), Some(true), None]]
    );
    assert_eq!(
        extract_paragraph_run_underline(&replaced),
        vec![vec![Some(true), None, None]]
    );
    assert_eq!(
        extract_paragraph_run_strike(&replaced),
        vec![vec![Some(false), None, None]]
    );
    assert_eq!(
        extract_paragraph_run_font_size(&replaced),
        vec![vec![Some(228600), None, None]]
    );
    assert_eq!(
        extract_paragraph_run_font_name(&replaced),
        vec![vec![Some("Aptos".to_owned()), None, None]]
    );
}

#[test]
fn text_run_replacement_handles_self_closing_nodes_and_entities() {
    let source = br#"<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:rPr b="1"><a:latin typeface="Aptos"/></a:rPr><a:t/></a:r><a:br/><a:r><a:rPr b="0"/><a:t>A &amp; B<![CDATA[<C>]]></a:t></a:r></a:p>"#;
    assert_eq!(extract_paragraph_runs(source)[0].len(), 2);
    assert_eq!(extract_paragraph_runs(source)[0][0], "");
    assert_eq!(extract_paragraph_line_breaks(source), vec![vec![1]]);
    assert_eq!(
        extract_paragraph_run_bold(source),
        vec![vec![Some(true), Some(false)]]
    );
    assert_eq!(
        extract_paragraph_run_font_name(source),
        vec![vec![Some("Aptos".to_owned()), None]]
    );
    let (filled, count) = replace_text_run_at_index_in_slide(source, 0, "filled").unwrap();
    assert_eq!(count, 1);
    let (replaced, count) = replace_text_run_at_index_in_slide(&filled, 1, "new <&>").unwrap();
    assert_eq!(count, 1);
    assert_eq!(
        extract_paragraph_runs(&replaced),
        vec![vec!["filled", "new <&>"]]
    );
    let rewritten = String::from_utf8(replaced).unwrap();
    assert!(rewritten.contains("new &lt;&amp;&gt;"));
    assert!(!rewritten.contains("CDATA"));
}
