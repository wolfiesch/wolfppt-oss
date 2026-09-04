    #[test]
    fn classifies_known_part_kinds() {
        assert_eq!(part_kind("ppt/slides/slide1.xml"), PartKind::Xml);
        assert_eq!(
            part_kind("ppt/slides/_rels/slide1.xml.rels"),
            PartKind::Relationships
        );
        assert_eq!(part_kind("ppt/media/image1.png"), PartKind::Media);
        assert_eq!(part_kind("ppt/embeddings/file.xlsx"), PartKind::Embedding);
        assert_eq!(part_kind("ppt/vbaProject.bin"), PartKind::Vba);
    }

    #[test]
    fn extracts_paragraph_runs_without_flattening_paragraphs() {
        let xml = br#"
            <p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:txBody>
                <a:p>
                  <a:r><a:rPr b="1" i="0" u="sng" sz="2400"><a:latin typeface="Aptos"/></a:rPr><a:t>Fast</a:t></a:r>
                  <a:r><a:rPr b="0" i="1" u="none" sz="1200"><a:latin typeface="Arial"/></a:rPr><a:t> PPTX</a:t></a:r>
                </a:p>
                <a:p><a:r><a:t>Lossless first</a:t></a:r></a:p>
              </p:txBody>
            </p:sp>
        "#;

        assert_eq!(
            extract_paragraph_runs(xml),
            vec![
                vec!["Fast".to_string(), " PPTX".to_string()],
                vec!["Lossless first".to_string()],
            ]
        );
        assert_eq!(
            extract_paragraph_run_bold(xml),
            vec![vec![Some(true), Some(false)], vec![None]]
        );
        assert_eq!(
            extract_paragraph_run_italic(xml),
            vec![vec![Some(false), Some(true)], vec![None]]
        );
        assert_eq!(
            extract_paragraph_run_underline(xml),
            vec![vec![Some(true), Some(false)], vec![None]]
        );
        assert_eq!(
            extract_paragraph_run_font_size(xml),
            vec![vec![Some(304800), Some(152400)], vec![None]]
        );
        assert_eq!(
            extract_paragraph_run_font_name(xml),
            vec![
                vec![Some("Aptos".to_string()), Some("Arial".to_string())],
                vec![None],
            ]
        );
    }

    #[test]
    fn extracts_empty_paragraph_slots() {
        let xml = br#"
            <p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:txBody>
                <a:p/>
                <a:p><a:r><a:rPr b="1"><a:latin typeface="Aptos"/></a:rPr><a:t>Second</a:t></a:r></a:p>
              </p:txBody>
            </p:sp>
        "#;

        assert_eq!(
            extract_paragraph_runs(xml),
            vec![Vec::<String>::new(), vec!["Second".to_string()]]
        );
        assert_eq!(
            extract_paragraph_run_bold(xml),
            vec![vec![], vec![Some(true)]]
        );
        assert_eq!(
            extract_paragraph_run_font_name(xml),
            vec![vec![], vec![Some("Aptos".to_string())]]
        );
    }

    #[test]
    fn extracts_paragraph_line_break_slots() {
        let xml = br#"
            <p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:txBody>
                <a:p>
                  <a:r><a:t>Fast PPTX</a:t></a:r>
                  <a:br/>
                  <a:r><a:t>After</a:t></a:r>
                </a:p>
              </p:txBody>
            </p:sp>
        "#;

        assert_eq!(
            extract_paragraph_runs(xml),
            vec![vec!["Fast PPTX".to_string(), "After".to_string()]]
        );
        assert_eq!(
            extract_paragraph_texts(xml),
            vec!["Fast PPTX\u{000b}After".to_string()]
        );
        assert_eq!(extract_paragraph_line_breaks(xml), vec![vec![1]]);
    }

    #[test]
    fn inspects_fixture_package() {
        let manifest =
            inspect_package("../../fixtures/pptx/text_basic/title_body_bullets.pptx").unwrap();

        assert!(!manifest.has_vba());
        assert!(manifest.part_names().contains(&"ppt/slides/slide1.xml"));
        assert!(manifest.parts.iter().all(|part| part.sha256.len() == 64));
    }

    #[test]
    fn detects_vba_fixture() {
        let manifest =
            inspect_package("../../fixtures/pptx/package/macro_preservation.pptm").unwrap();

        assert!(manifest.has_vba());
        assert!(manifest.part_names().contains(&"ppt/vbaProject.bin"));
    }

    #[test]
    fn roundtrips_package_parts() {
        let source = "../../fixtures/pptx/package/macro_preservation.pptm";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("roundtrip.pptm");

        let original = inspect_package(source).unwrap();
        let roundtripped = roundtrip_package(source, &out).unwrap();

        assert!(out.exists());
        assert_eq!(original.parts, roundtripped.parts);
        assert!(roundtripped.has_vba());
    }

    #[test]
    fn replaces_slide_text_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("replace.pptx");

        let result = replace_slide_text(source, &out, "WolfPPT", "WolfPPT Native").unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.replacements, 1);
        assert!(summary.slides[0]
            .texts
            .contains(&"WolfPPT Native".to_string()));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn replaces_slide_text_at_index() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("replace-slide-index.pptx");

        let result =
            replace_slide_text_at_index(source, &out, 0, "WolfPPT", "WolfPPT Scoped").unwrap();
        let summary = summarize_presentation(&out).unwrap();

        assert_eq!(result.replacements, 1);
        assert!(summary.slides[0]
            .texts
            .contains(&"WolfPPT Scoped".to_string()));
    }

    #[test]
    fn replace_slide_text_at_index_rejects_missing_slide() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("replace-missing-slide.pptx");

        let err =
            replace_slide_text_at_index(source, &out, 10, "WolfPPT", "WolfPPT Scoped").unwrap_err();

        assert!(err.to_string().contains("slide index 10 was not found"));
    }

    #[test]
    fn replaces_slide_text_run_at_index_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("replace-run.pptx");

        let result = replace_slide_text_run_at_index(source, &out, 0, 1, "Fast Native").unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.replacements, 1);
        assert_eq!(summary.slides[0].texts[0], "WolfPPT");
        assert!(summary.slides[0].texts.contains(&"Fast Native".to_string()));
        assert!(summary.slides[0]
            .texts
            .contains(&"Lossless first".to_string()));
        assert!(slide_xml.contains("<a:t>Fast Native</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn sets_shape_text_at_index_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("set-shape-text.pptx");

        let result = set_slide_shape_text_at_index(source, &out, 0, 1, "Agenda\nNext").unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_index, 1);
        assert_eq!(result.replacements, 2);
        assert_eq!(summary.slides[0].texts[0], "WolfPPT");
        assert_eq!(summary.slides[0].shapes[1].text, "Agenda\nNext");
        assert_eq!(
            summary.slides[0].shapes[1].paragraphs,
            vec!["Agenda".to_string(), "Next".to_string()]
        );
        assert!(slide_xml.contains("<a:t>Agenda</a:t>"));
        assert!(slide_xml.contains("<a:t>Next</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn sets_shape_paragraph_text_at_index_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("set-paragraph-text.pptx");

        let result =
            set_slide_shape_paragraph_text_at_index(source, &out, 0, 1, 1, "Second").unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_index, 1);
        assert_eq!(result.paragraph_index, 1);
        assert_eq!(result.replacements, 1);
        assert_eq!(summary.slides[0].shapes[1].text, "Fast PPTX\nSecond");
        assert!(slide_xml.contains("<a:t>Second</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }
