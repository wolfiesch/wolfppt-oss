    #[test]
    fn adds_text_box_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-group-textbox.pptx");

        let result = add_slide_group_text_box_with_text(
            source,
            &out,
            0,
            0,
            91440,
            182880,
            914400,
            365760,
            "Nested Box",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.shape_id, 4);
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[1].text, "Nested Box");
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_auto_shape_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-group-autoshape.pptx");

        let result = add_slide_group_auto_shape_with_text(
            source,
            &out,
            0,
            0,
            "rect",
            91440,
            182880,
            914400,
            365760,
            "Grouped Shape",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 4);
        assert_eq!(result.preset_geometry, "rect");
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[1].text, "Grouped Shape");
        assert!(slide_xml.contains(r#"<a:prstGeom prst="rect">"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connector_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-group-connector.pptx");

        let result = add_slide_group_connector(
            source,
            &out,
            0,
            0,
            "line",
            91440,
            182880,
            1097280,
            640080,
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 4);
        assert_eq!(result.preset_geometry, "line");
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[1].kind, "connector");
        assert_eq!(
            summary.slides[0].shapes[0].children[1].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 1005840,
                cy: 457200,
            })
        );
        assert!(slide_xml.contains("<p:grpSp>"));
        assert!(slide_xml.contains("<p:cxnSp>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connected_connector_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-connected-group-connector.pptx");

        let result = add_slide_connected_group_connector(
            source,
            &out,
            0,
            0,
            "line",
            91440,
            182880,
            1097280,
            640080,
            Some(3),
            Some(3),
            Some(3),
            Some(1),
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 4);
        assert!(slide_xml.contains(r#"<a:stCxn id="3" idx="3"/>"#));
        assert!(slide_xml.contains(r#"<a:endCxn id="3" idx="1"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connected_group_connector_with_auto_shapes_in_one_slide_rewrite() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir
            .path()
            .join("add-connected-group-connector-with-shapes.pptx");

        let result = add_slide_connected_group_connector_with_auto_shapes(
            source, &out, 0, 0, "roundRect", 914400, 1828800, 1371600, 685800,
            "diamond", 3657600, 1828800, 1143000, 685800, "line", 914400,
            914400, 3657600, 1828800, 3, 1,
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 6);
        assert_eq!(result.preset_geometry, "line");
        assert_eq!(summary.slides[0].shapes[0].children.len(), 4);
        assert_eq!(summary.slides[0].shapes[0].children[1].kind, "shape");
        assert_eq!(summary.slides[0].shapes[0].children[2].kind, "shape");
        assert_eq!(summary.slides[0].shapes[0].children[3].kind, "connector");
        assert!(slide_xml.contains(r#"<a:prstGeom prst="roundRect">"#));
        assert!(slide_xml.contains(r#"<a:prstGeom prst="diamond">"#));
        assert!(slide_xml.contains(r#"<a:stCxn id="4" idx="3"/>"#));
        assert!(slide_xml.contains(r#"<a:endCxn id="5" idx="1"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connected_connector_with_auto_shapes_in_one_slide_rewrite() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-connected-connector-with-shapes.pptx");

        let result = add_slide_connected_connector_with_auto_shapes(
            source,
            &out,
            0,
            "roundRect",
            914400,
            914400,
            1371600,
            685800,
            "diamond",
            2743200,
            1143000,
            914400,
            685800,
            "line",
            914400,
            914400,
            3657600,
            1828800,
            3,
            1,
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 6);
        assert_eq!(result.preset_geometry, "line");
        assert_eq!(summary.slides[0].shapes.len(), 5);
        assert_eq!(summary.slides[0].shapes[2].kind, "shape");
        assert_eq!(summary.slides[0].shapes[3].kind, "shape");
        assert_eq!(summary.slides[0].shapes[4].kind, "connector");
        assert!(slide_xml.contains(r#"<a:prstGeom prst="roundRect">"#));
        assert!(slide_xml.contains(r#"<a:prstGeom prst="diamond">"#));
        assert!(slide_xml.contains(r#"<a:stCxn id="4" idx="3"/>"#));
        assert!(slide_xml.contains(r#"<a:endCxn id="5" idx="1"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_picture_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let out = dir.path().join("add-group-picture.pptx");
        let image_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&image, image_payload).unwrap();

        let result =
            add_slide_group_image(source, &out, 0, 0, &image, 91440, 182880, 822960, 822960)
                .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");

        assert_eq!(result.shape_id, 4);
        assert_eq!(result.relationship_id, "rId2");
        assert_eq!(result.image_part, "ppt/media/image1.png");
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[1].kind, "picture");
        assert_eq!(
            summary.slides[0].shapes[0].children[1].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 822960,
                cy: 822960,
            })
        );
        assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
        assert_eq!(rewritten.parts.len(), original.parts.len() + 1);
        assert!(slide_xml.contains("<p:grpSp>"));
        assert!(slide_xml.contains("<p:pic>"));
        assert!(slide_xml.contains(r#"<p:cNvPr id="4" name="Picture 3"/>"#));
        assert!(slide_xml.contains(r#"r:embed="rId2""#));
        assert!(rels_xml.contains(r#"Target="../media/image1.png""#));
        assert!(original
            .parts
            .iter()
            .filter(|part| {
                !matches!(
                    part.name.as_str(),
                    "[Content_Types].xml"
                        | "ppt/slides/slide1.xml"
                        | "ppt/slides/_rels/slide1.xml.rels"
                )
            })
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn reuses_matching_group_picture_media_and_relationship() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let first = dir.path().join("add-group-picture-first.pptx");
        let second = dir.path().join("add-group-picture-second.pptx");
        let image_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&image, image_payload).unwrap();

        let first_result =
            add_slide_group_image(source, &first, 0, 0, &image, 91440, 182880, 822960, 822960)
                .unwrap();
        let first_rels_xml = read_zip_text(&first, "ppt/slides/_rels/slide1.xml.rels");
        let second_result =
            add_slide_group_image(&first, &second, 0, 0, &image, 182880, 274320, 731520, 731520)
                .unwrap();
        let first_manifest = inspect_package(&first).unwrap();
        let second_manifest = inspect_package(&second).unwrap();
        let second_summary = summarize_presentation(&second).unwrap();
        let second_slide_xml = read_zip_text(&second, "ppt/slides/slide1.xml");
        let second_rels_xml = read_zip_text(&second, "ppt/slides/_rels/slide1.xml.rels");

        assert_eq!(first_result.relationship_id, "rId2");
        assert_eq!(second_result.relationship_id, "rId2");
        assert_eq!(second_result.image_part, "ppt/media/image1.png");
        assert_eq!(second_rels_xml, first_rels_xml);
        assert_eq!(second_manifest.parts.len(), first_manifest.parts.len());
        assert!(!second_manifest.part_names().contains(&"ppt/media/image2.png"));
        assert_eq!(second_summary.slides[0].shapes[0].children.len(), 3);
        assert!(second_slide_xml.contains(r#"r:embed="rId2""#));
        assert!(first_manifest
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| second_manifest.parts.contains(part)));
    }
