    // quick-xml skips a leading UTF-8 byte order mark without counting it in
    // `buffer_position()`. Every splice must still index the part's own bytes.
    const UTF8_BOM: &str = "\u{feff}";
    const BOM_PML_NAMESPACES: &str = concat!(
        "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" ",
        "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" ",
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"",
    );

    fn with_bom(xml: &str) -> String {
        format!("{UTF8_BOM}{xml}")
    }

    fn with_bom_bytes(xml: &[u8]) -> Vec<u8> {
        [UTF8_BOM.as_bytes(), xml].concat()
    }

    fn package_with_parts(source: &str, output: &Path, parts: &[(&str, &[u8])]) {
        let mut archive = ZipArchive::new(File::open(source).unwrap()).unwrap();
        let mut writer = zip::ZipWriter::new(File::create(output).unwrap());
        for index in 0..archive.len() {
            let file = archive.by_index(index).unwrap();
            let name = file.name().unwrap().into_owned();
            if let Some((_, bytes)) = parts.iter().find(|(part, _)| *part == name) {
                writer
                    .start_file(name, SimpleFileOptions::default())
                    .unwrap();
                std::io::Write::write_all(&mut writer, bytes).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.finish().unwrap();
    }

    #[test]
    fn utf8_bom_text_node_replacement_matches_unmarked_slide() {
        let slide = format!(
            "<p:sld {BOM_PML_NAMESPACES}><p:cSld><p:spTree><p:sp><p:txBody><a:p>\
             <a:r><a:t>Keep me</a:t></a:r><a:r><a:t>Old text</a:t></a:r>\
             </a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
        );
        let (plain, plain_count) = replace_text_nodes(slide.as_bytes(), "Old", "New").unwrap();
        let (marked, marked_count) =
            replace_text_nodes(with_bom(&slide).as_bytes(), "Old", "New").unwrap();
        // The writer re-serializes parser events, so the skipped mark is not written.
        assert_eq!(
            String::from_utf8(marked).unwrap(),
            String::from_utf8(plain).unwrap()
        );
        assert_eq!(marked_count, plain_count);
    }

    #[test]
    fn utf8_bom_text_run_replacement_matches_unmarked_slide() {
        let slide = format!(
            "<p:sld {BOM_PML_NAMESPACES}><p:cSld><p:spTree><p:sp><p:txBody><a:p>\
             <a:r><a:t>First</a:t></a:r><a:r><a:t>Second</a:t></a:r>\
             </a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
        );
        let (plain, plain_count) =
            replace_text_run_at_index_in_slide(slide.as_bytes(), 1, "Changed").unwrap();
        let (marked, marked_count) =
            replace_text_run_at_index_in_slide(with_bom(&slide).as_bytes(), 1, "Changed").unwrap();
        assert_eq!(
            String::from_utf8(marked).unwrap(),
            String::from_utf8(plain).unwrap()
        );
        assert_eq!(marked_count, plain_count);
    }

    #[test]
    fn utf8_bom_text_box_insertion_preserves_marked_slide_bytes() {
        let slide = format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n\
             <p:sld {BOM_PML_NAMESPACES}><p:cSld><p:spTree><p:nvGrpSpPr>\
             <p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\
             <p:grpSpPr/></p:spTree></p:cSld></p:sld>"
        );
        let plain = add_text_box_to_slide_xml(&slide, 2, 0, 0, 100, 100, Some("Hi")).unwrap();
        let marked =
            add_text_box_to_slide_xml(&with_bom(&slide), 2, 0, 0, 100, 100, Some("Hi")).unwrap();
        assert_eq!(marked, with_bom(&plain));
    }

    #[test]
    fn utf8_bom_self_closing_master_list_append_preserves_marked_presentation() {
        let presentation = format!(
            "<p:presentation {BOM_PML_NAMESPACES}><p:sldMasterIdLst/>\
             <p:sldSz cx=\"9144000\" cy=\"6858000\"/></p:presentation>"
        );
        let plain = append_master_id(presentation.as_bytes(), 2147483648, "rId9").unwrap();
        let marked =
            append_master_id(with_bom(&presentation).as_bytes(), 2147483648, "rId9").unwrap();
        assert_eq!(marked, with_bom_bytes(&plain));
    }

    #[test]
    fn utf8_bom_self_closing_slide_list_append_preserves_marked_presentation() {
        let presentation = format!(
            "<p:presentation {BOM_PML_NAMESPACES}><p:sldIdLst/>\
             <p:sldSz cx=\"9144000\" cy=\"6858000\"/></p:presentation>"
        );
        let plain = append_slide_id(presentation.as_bytes(), 256, "rId9").unwrap();
        let marked = append_slide_id(with_bom(&presentation).as_bytes(), 256, "rId9").unwrap();
        assert_eq!(marked, with_bom_bytes(&plain));
    }

    #[test]
    fn utf8_bom_content_type_append_preserves_marked_content_types() {
        let attributes = r#"Extension="xml" ContentType="application/xml""#;
        for types in [
            concat!(
                r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"#,
                r#"<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">"#,
                r#"<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>"#,
                r#"</Types>"#,
            ),
            concat!(
                r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"#,
                r#"<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>"#,
            ),
        ] {
            let plain =
                append_content_type_element(types.as_bytes(), "Default", attributes).unwrap();
            let marked =
                append_content_type_element(with_bom(types).as_bytes(), "Default", attributes)
                    .unwrap();
            assert_eq!(marked, with_bom_bytes(&plain), "{types}");
        }
    }

    #[test]
    fn utf8_bom_media_control_nodes_index_the_marked_slide() {
        let slide =
            add_movie_timing_to_slide_xml(&format!("{MEDIA_SLIDE_HEAD}</p:sld>"), 5, None).unwrap();
        let spans = |xml: &str| -> Vec<(String, String)> {
            media_control_nodes(xml)
                .unwrap()
                .iter()
                .map(|node| {
                    (
                        xml[node.start..node.open_end].to_string(),
                        xml[node.close_start..node.end].to_string(),
                    )
                })
                .collect()
        };
        assert_eq!(spans(&with_bom(&slide)), spans(&slide));
    }

    #[test]
    fn utf8_bom_set_slide_media_controls_preserves_marked_slide() {
        let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
        let slide = format!("{MEDIA_SLIDE_HEAD}</p:sld>");
        let relationships = concat!(
            r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"#,
            r#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">"#,
            r#"<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout7.xml"/>"#,
            r#"<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/video" Target="clip.mp4" TargetMode="External"/>"#,
            r#"</Relationships>"#,
        );
        let controls = MediaControls {
            volume: Some(40),
            ..MediaControls::default()
        };
        let dir = tempfile::tempdir().unwrap();
        let mut outputs = Vec::new();
        for (label, xml) in [("plain", slide.clone()), ("marked", with_bom(&slide))] {
            let input = dir.path().join(format!("{label}.pptx"));
            let output = dir.path().join(format!("{label}-out.pptx"));
            package_with_parts(
                source,
                &input,
                &[
                    ("ppt/slides/slide1.xml", xml.as_bytes()),
                    ("ppt/slides/_rels/slide1.xml.rels", relationships.as_bytes()),
                ],
            );
            set_slide_media_controls(&input, &output, 0, 5, &controls).unwrap();
            outputs.push(read_zip_text(&output, "ppt/slides/slide1.xml"));
        }
        assert!(outputs[0].contains(r#"vol="40000""#), "{}", outputs[0]);
        assert_eq!(outputs[1], with_bom(&outputs[0]));
    }

    #[test]
    fn utf8_bom_unbalanced_slide_shape_names_match_unmarked_slide() {
        // An unclosed root makes MC resolution fall back to the raw part bytes.
        let slide = concat!(
            r#"<pml:sld xmlns:pml="http://schemas.openxmlformats.org/presentationml/2006/main" "#,
            r#"xmlns:dml="http://schemas.openxmlformats.org/drawingml/2006/main">"#,
            r#"<pml:cSld><pml:spTree><pml:sp><pml:nvSpPr><pml:cNvPr id="2" name="Title"/>"#,
            r#"<pml:cNvSpPr/><pml:nvPr/></pml:nvSpPr><pml:spPr/><pml:txBody><dml:bodyPr/>"#,
            r#"<dml:p><dml:r><dml:t>Hello</dml:t></dml:r></dml:p></pml:txBody></pml:sp>"#,
            r#"</pml:spTree></pml:cSld>"#,
        );
        let plain = extract_shapes(slide.as_bytes());
        assert_eq!(plain.len(), 1);
        assert_eq!(extract_shapes(with_bom(slide).as_bytes()), plain);
    }
