    #[test]
    fn adds_text_box_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-text-box.pptx");

        let result = add_slide_text_box(source, &out, 0, 914400, 2743200, 3657600, 914400).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "shape");
        assert_eq!(summary.slides[0].shapes[2].text, "");
        assert_eq!(
            summary.slides[0].shapes[2].transform,
            Some(TransformSummary {
                x: 914400,
                y: 2743200,
                cx: 3657600,
                cy: 914400,
            })
        );
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_text_box_with_text_without_second_rewrite() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-text-box-with-text.pptx");

        let result = add_slide_text_box_with_text(
            source, &out, 0, 914400, 2743200, 3657600, 914400, "Fast Box",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "shape");
        assert_eq!(summary.slides[0].shapes[2].text, "Fast Box");
        assert!(slide_xml.contains("<a:t>Fast Box</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_group_shape_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-group-shape.pptx");

        let result = add_slide_group_shape(source, &out, 0).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert!(slide_xml.contains(r#"<p:grpSp>"#));
        assert!(slide_xml.contains(r#"name="Group 3""#));
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "group");
        assert_eq!(summary.slides[0].shapes[2].children, vec![]);
        assert_eq!(
            summary.slides[0].shapes[2].transform,
            Some(TransformSummary {
                x: 0,
                y: 0,
                cx: 0,
                cy: 0,
            })
        );
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_freeform_shape_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-freeform-shape.pptx");
        let operations = vec![
            FreeformPathOperation::MoveTo { x: 0, y: 0 },
            FreeformPathOperation::LineTo { x: 914400, y: 0 },
            FreeformPathOperation::LineTo {
                x: 914400,
                y: 914400,
            },
            FreeformPathOperation::Close,
        ];

        let result = add_slide_freeform_shape(
            source,
            &out,
            0,
            914400,
            1828800,
            914400,
            914400,
            914400,
            914400,
            &operations,
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert!(slide_xml.contains(r#"<a:custGeom>"#));
        assert!(slide_xml.contains(r#"<a:path w="914400" h="914400">"#));
        assert!(slide_xml.contains(r#"name="Freeform 3""#));
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "shape");
        assert_eq!(
            summary.slides[0].shapes[2].transform,
            Some(TransformSummary {
                x: 914400,
                y: 1828800,
                cx: 914400,
                cy: 914400,
            })
        );
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_auto_shape_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-auto-shape.pptx");

        let result =
            add_slide_auto_shape(source, &out, 0, "rect", 914400, 2743200, 3657600, 914400)
                .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
        let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
            .unwrap()
            .unwrap();

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert_eq!(result.preset_geometry, "rect");
        assert!(slide_xml.contains(r#"<a:prstGeom prst="rect">"#));
        assert!(slide_xml.contains(r#"name="Rectangle 3""#));
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "shape");
        assert_eq!(summary.slides[0].shapes[2].text, "");
        assert_eq!(
            summary.slides[0].shapes[2].transform,
            Some(TransformSummary {
                x: 914400,
                y: 2743200,
                cx: 3657600,
                cy: 914400,
            })
        );
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_auto_shape_with_text_without_second_rewrite() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-auto-shape-text.pptx");

        let result = add_slide_auto_shape_with_text(
            source,
            &out,
            0,
            "roundRect",
            914400,
            2743200,
            3657600,
            914400,
            "New Shape",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert_eq!(result.preset_geometry, "roundRect");
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "shape");
        assert_eq!(summary.slides[0].shapes[2].text, "New Shape");
        assert!(slide_xml.contains(r#"<a:prstGeom prst="roundRect">"#));
        assert!(slide_xml.contains(r#"<a:r><a:t>New Shape</a:t></a:r>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_auto_shape_with_adjustments_without_second_rewrite() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-auto-shape-adjustments.pptx");

        let result = add_slide_auto_shape_with_text_and_adjustments(
            source,
            &out,
            0,
            "roundRect",
            914400,
            2743200,
            3657600,
            914400,
            None,
            &[("adj".to_string(), 33000)],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert_eq!(result.preset_geometry, "roundRect");
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert!(slide_xml.contains(r#"<a:prstGeom prst="roundRect">"#));
        assert!(slide_xml.contains(r#"<a:gd name="adj" fmla="val 33000"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connector_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-connector.pptx");

        let result =
            add_slide_connector(source, &out, 0, "line", 914400, 914400, 3657600, 1828800).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let mut archive = ZipArchive::new(File::open(&out).unwrap()).unwrap();
        let slide_xml = read_archive_text(&mut archive, "ppt/slides/slide1.xml")
            .unwrap()
            .unwrap();

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.shape_id, 4);
        assert_eq!(result.preset_geometry, "line");
        assert!(slide_xml.contains(r#"<p:cxnSp>"#));
        assert!(slide_xml.contains(r#"<a:prstGeom prst="line">"#));
        assert!(slide_xml.contains(r#"name="Connector 3""#));
        assert_eq!(summary.slides[0].shapes.len(), 3);
        assert_eq!(summary.slides[0].shapes[2].kind, "connector");
        assert_eq!(
            summary.slides[0].shapes[2].transform,
            Some(TransformSummary {
                x: 914400,
                y: 914400,
                cx: 2743200,
                cy: 914400,
            })
        );
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }
