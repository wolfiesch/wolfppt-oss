    #[test]
    fn adds_freeform_shape_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-group-freeform-shape.pptx");
        let operations = vec![
            FreeformPathOperation::MoveTo { x: 0, y: 0 },
            FreeformPathOperation::LineTo { x: 914400, y: 0 },
            FreeformPathOperation::LineTo {
                x: 914400,
                y: 457200,
            },
            FreeformPathOperation::Close,
        ];

        let result = add_slide_group_freeform_shape_with_text(
            source,
            &out,
            0,
            0,
            91440,
            182880,
            914400,
            457200,
            914400,
            457200,
            &operations,
            "Grouped Freeform",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 4);
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(
            summary.slides[0].shapes[0].children[1].text,
            "Grouped Freeform"
        );
        assert_eq!(
            summary.slides[0].shapes[0].children[1].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 914400,
                cy: 457200,
            })
        );
        assert!(slide_xml.contains("<p:grpSp>"));
        assert!(slide_xml.contains(r#"<a:custGeom>"#));
        assert!(slide_xml.contains("<a:t>Grouped Freeform</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_nested_group_shape_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-nested-group-shape.pptx");

        let result = add_slide_nested_group_shape(source, &out, 0, 0).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 4);
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[1].kind, "group");
        assert_eq!(
            summary.slides[0].shapes[0].children[1].name.as_deref(),
            Some("Group 3")
        );
        assert_eq!(summary.slides[0].shapes[0].children[1].children.len(), 0);
        assert_eq!(
            summary.slides[0].shapes[0].children[1].transform,
            Some(TransformSummary {
                x: 0,
                y: 0,
                cx: 0,
                cy: 0,
            })
        );
        assert!(slide_xml.contains(r#"<p:cNvPr id="4" name="Group 3"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_group_shape_inside_existing_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let out = dir.path().join("add-deeper-nested-group-shape.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        let result = add_slide_group_shape_to_nested_group(&nested, &out, 0, 0, 1).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&nested).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 5);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "group");
        assert_eq!(nested_group.children[0].name.as_deref(), Some("Group 4"));
        assert_eq!(nested_group.children[0].children.len(), 0);
        assert!(slide_xml.contains(r#"<p:cNvPr id="5" name="Group 4"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_group_shape_inside_existing_deeper_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let deeper = dir.path().join("add-deeper-nested-group-shape.pptx");
        let out = dir.path().join("add-group-in-deeper-nested-group-shape.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        add_slide_group_shape_to_nested_group(&nested, &deeper, 0, 0, 1).unwrap();
        let result =
            add_slide_group_shape_to_deeper_nested_group(&deeper, &out, 0, 0, 1, 0).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&deeper).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 6);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        let deeper_group = &nested_group.children[0];
        assert_eq!(deeper_group.kind, "group");
        assert_eq!(deeper_group.children.len(), 1);
        assert_eq!(deeper_group.children[0].kind, "group");
        assert_eq!(deeper_group.children[0].name.as_deref(), Some("Group 5"));
        assert_eq!(deeper_group.children[0].children.len(), 0);
        assert!(slide_xml.contains(r#"<p:cNvPr id="6" name="Group 5"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_text_box_inside_existing_deeper_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let deeper = dir.path().join("add-deeper-nested-group-shape.pptx");
        let out = dir.path().join("add-deeper-nested-group-text-box.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        add_slide_group_shape_to_nested_group(&nested, &deeper, 0, 0, 1).unwrap();
        let result = add_slide_deeper_nested_group_text_box_with_text(
            &deeper,
            &out,
            0,
            0,
            1,
            0,
            91440,
            182880,
            914400,
            365760,
            "Deep Nested Box",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&deeper).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 6);
        let deeper_group = &summary.slides[0].shapes[0].children[1].children[0];
        assert_eq!(deeper_group.kind, "group");
        assert_eq!(deeper_group.children.len(), 1);
        assert_eq!(deeper_group.children[0].text, "Deep Nested Box");
        assert_eq!(
            deeper_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 914400,
                cy: 365760,
            })
        );
        assert!(slide_xml.contains("<a:t>Deep Nested Box</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_auto_shape_inside_existing_deeper_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let deeper = dir.path().join("add-deeper-nested-group-shape.pptx");
        let out = dir.path().join("add-deeper-nested-group-auto-shape.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        add_slide_group_shape_to_nested_group(&nested, &deeper, 0, 0, 1).unwrap();
        let result = add_slide_deeper_nested_group_auto_shape_with_text(
            &deeper,
            &out,
            0,
            0,
            1,
            0,
            "rect",
            91440,
            182880,
            914400,
            365760,
            "Deep Nested Shape",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&deeper).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 6);
        let deeper_group = &summary.slides[0].shapes[0].children[1].children[0];
        assert_eq!(deeper_group.kind, "group");
        assert_eq!(deeper_group.children.len(), 1);
        assert_eq!(deeper_group.children[0].kind, "shape");
        assert_eq!(deeper_group.children[0].text, "Deep Nested Shape");
        assert_eq!(
            deeper_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 914400,
                cy: 365760,
            })
        );
        assert!(slide_xml.contains(r#"<a:prstGeom prst="rect">"#));
        assert!(slide_xml.contains("<a:t>Deep Nested Shape</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn groups_existing_group_children_without_losing_package_parts() {
        let source = "../../fixtures/pptx/workloads/customer_success_review_pack.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("group-existing-children.pptx");

        let result = group_slide_existing_group_children(source, &out, 4, 0, &[1, 0]).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide5.xml");

        assert_eq!(result.slide_part, "ppt/slides/slide5.xml");
        assert_eq!(result.shape_id, 8);
        let parent_group = &summary.slides[4].shapes[1];
        assert_eq!(parent_group.children.len(), 3);
        assert_eq!(
            parent_group.children[0].name.as_deref(),
            Some("Rounded Rectangle 5")
        );
        assert_eq!(
            parent_group.children[1].name.as_deref(),
            Some("Rounded Rectangle 6")
        );
        let nested_group = &parent_group.children[2];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.name.as_deref(), Some("Group 7"));
        assert_eq!(nested_group.children.len(), 2);
        assert_eq!(
            nested_group.children[0].name.as_deref(),
            Some("Rounded Rectangle 4")
        );
        assert_eq!(
            nested_group.children[1].name.as_deref(),
            Some("Rounded Rectangle 3")
        );
        assert!(slide_xml.contains(r#"<p:cNvPr id="8" name="Group 7"/>"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide5.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn groups_existing_nested_group_children_without_losing_package_parts() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("nested-group.pptx");
        let first = dir.path().join("nested-child-1.pptx");
        let second = dir.path().join("nested-child-2.pptx");
        let out = dir.path().join("group-existing-nested-children.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        add_slide_nested_group_auto_shape_with_text(
            &nested,
            &first,
            0,
            0,
            1,
            "rect",
            91440,
            91440,
            914400,
            457200,
            "First",
        )
        .unwrap();
        add_slide_nested_group_auto_shape_with_text(
            &first,
            &second,
            0,
            0,
            1,
            "ellipse",
            1097280,
            91440,
            914400,
            457200,
            "Second",
        )
        .unwrap();

        let result =
            group_slide_existing_nested_group_children(&second, &out, 0, 0, 1, &[1, 0]).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&second).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.slide_part, "ppt/slides/slide1.xml");
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.children.len(), 1);
        let grouped = &nested_group.children[0];
        assert_eq!(grouped.kind, "group");
        assert_eq!(grouped.children.len(), 2);
        assert_eq!(grouped.children[0].text, "Second");
        assert_eq!(grouped.children[1].text, "First");
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn groups_existing_deeper_nested_group_children_without_losing_package_parts() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("nested-group.pptx");
        let deeper = dir.path().join("deeper-group.pptx");
        let first = dir.path().join("deeper-child-1.pptx");
        let second = dir.path().join("deeper-child-2.pptx");
        let out = dir.path().join("group-existing-deeper-children.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        add_slide_group_shape_to_nested_group(&nested, &deeper, 0, 0, 1).unwrap();
        add_slide_deeper_nested_group_auto_shape_with_text(
            &deeper, &first, 0, 0, 1, 0, "rect", 91440, 91440, 914400, 457200, "First",
        )
        .unwrap();
        add_slide_deeper_nested_group_auto_shape_with_text(
            &first, &second, 0, 0, 1, 0, "ellipse", 1097280, 91440, 914400, 457200,
            "Second",
        )
        .unwrap();

        group_slide_existing_deeper_nested_group_children(&second, &out, 0, 0, 1, 0, &[1, 0])
            .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&second).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        let deeper_group = &summary.slides[0].shapes[0].children[1].children[0];
        assert_eq!(deeper_group.children.len(), 1);
        let grouped = &deeper_group.children[0];
        assert_eq!(grouped.kind, "group");
        assert_eq!(grouped.children.len(), 2);
        assert_eq!(grouped.children[0].text, "Second");
        assert_eq!(grouped.children[1].text, "First");
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_text_box_inside_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let out = dir.path().join("add-nested-group-textbox.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        let result = add_slide_nested_group_text_box_with_text(
            &nested,
            &out,
            0,
            0,
            1,
            91440,
            182880,
            914400,
            365760,
            "Nested child",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.shape_id, 5);
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[0].text, "Grouped Text");
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].text, "Nested child");
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_text_box_inside_new_nested_group_shape_without_second_rewrite() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-new-nested-group-textbox.pptx");

        let result = add_slide_nested_group_text_box_in_new_group_with_text(
            source,
            &out,
            0,
            0,
            91440,
            182880,
            914400,
            365760,
            "Nested child",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.shape_id, 5);
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(summary.slides[0].shapes[0].children[0].text, "Grouped Text");
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].text, "Nested child");
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_auto_shape_inside_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let out = dir.path().join("add-nested-group-auto-shape.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        let result = add_slide_nested_group_auto_shape_with_text(
            &nested,
            &out,
            0,
            0,
            1,
            "rect",
            91440,
            182880,
            914400,
            365760,
            "Nested shape",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 5);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "shape");
        assert_eq!(nested_group.children[0].text, "Nested shape");
        assert!(slide_xml.contains(r#"<a:prstGeom prst="rect">"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connector_inside_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let out = dir.path().join("add-nested-group-connector.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        let result = add_slide_nested_group_connector(
            &nested, &out, 0, 0, 1, "line", 91440, 182880, 1097280, 640080,
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 5);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "connector");
        assert_eq!(
            nested_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 1005840,
                cy: 457200,
            })
        );
        assert!(slide_xml.contains(r#"<p:cxnSp>"#));
        assert!(slide_xml.contains(r#"<a:prstGeom prst="line">"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connector_inside_existing_deeper_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let deeper = dir.path().join("add-deeper-nested-group-shape.pptx");
        let out = dir.path().join("add-deeper-nested-group-connector.pptx");

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        add_slide_group_shape_to_nested_group(&nested, &deeper, 0, 0, 1).unwrap();
        let result = add_slide_deeper_nested_group_connector(
            &deeper, &out, 0, 0, 1, 0, "line", 91440, 182880, 1097280, 640080,
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(&deeper).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 6);
        let deeper_group = &summary.slides[0].shapes[0].children[1].children[0];
        assert_eq!(deeper_group.kind, "group");
        assert_eq!(deeper_group.children.len(), 1);
        assert_eq!(deeper_group.children[0].kind, "connector");
        assert_eq!(
            deeper_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 1005840,
                cy: 457200,
            })
        );
        assert!(slide_xml.contains(r#"<p:cxnSp>"#));
        assert!(slide_xml.contains(r#"<a:prstGeom prst="line">"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_connector_inside_new_nested_group_shape_without_second_rewrite() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-new-nested-group-connector.pptx");

        let result = add_slide_nested_group_connector_in_new_group(
            source, &out, 0, 0, "line", 91440, 182880, 1097280, 640080,
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 5);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "connector");
        assert_eq!(
            nested_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 1005840,
                cy: 457200,
            })
        );
        assert!(slide_xml.contains(r#"<p:cxnSp>"#));
        assert!(slide_xml.contains(r#"<a:prstGeom prst="line">"#));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_picture_inside_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let image = dir.path().join("image.png");
        let out = dir.path().join("add-nested-group-picture.pptx");
        let image_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&image, image_payload).unwrap();

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        let result =
            add_slide_nested_group_image(&nested, &out, 0, 0, 1, &image, 91440, 182880, 822960, 822960)
                .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");

        assert_eq!(result.shape_id, 5);
        assert_eq!(result.relationship_id, "rId2");
        assert_eq!(result.image_part, "ppt/media/image1.png");
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "picture");
        assert_eq!(
            nested_group.children[0].transform,
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
    fn adds_picture_inside_new_nested_group_shape_without_second_rewrite() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let out = dir.path().join("add-nested-group-picture-one-rewrite.pptx");
        let image_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&image, image_payload).unwrap();

        let result = add_slide_nested_group_image_in_new_group(
            source, &out, 0, 0, &image, 91440, 182880, 822960, 822960,
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.shape_id, 5);
        assert_eq!(result.relationship_id, "rId2");
        assert_eq!(result.image_part, "ppt/media/image1.png");
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "picture");
        assert_eq!(
            nested_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 822960,
                cy: 822960,
            })
        );
        assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
        assert_eq!(rewritten.parts.len(), original.parts.len() + 1);
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
    fn adds_freeform_inside_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("add-nested-group-shape.pptx");
        let out = dir.path().join("add-nested-group-freeform.pptx");
        let operations = vec![
            FreeformPathOperation::MoveTo { x: 0, y: 0 },
            FreeformPathOperation::LineTo { x: 914400, y: 0 },
            FreeformPathOperation::LineTo {
                x: 914400,
                y: 914400,
            },
            FreeformPathOperation::Close,
        ];

        add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
        let result = add_slide_nested_group_freeform_shape_with_text(
            &nested,
            &out,
            0,
            0,
            1,
            91440,
            182880,
            914400,
            914400,
            914400,
            914400,
            &operations,
            "Nested Freeform",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 5);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "shape");
        assert_eq!(nested_group.children[0].text, "Nested Freeform");
        assert_eq!(
            nested_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 914400,
                cy: 914400,
            })
        );
        assert!(slide_xml.contains("<p:grpSp>"));
        assert!(slide_xml.contains("<a:custGeom>"));
        assert!(slide_xml.contains("<a:t>Nested Freeform</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_freeform_inside_new_nested_group_shape_in_one_rewrite() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-nested-group-freeform-one-rewrite.pptx");
        let operations = vec![
            FreeformPathOperation::MoveTo { x: 0, y: 0 },
            FreeformPathOperation::LineTo { x: 914400, y: 0 },
            FreeformPathOperation::LineTo {
                x: 914400,
                y: 914400,
            },
            FreeformPathOperation::Close,
        ];

        let result = add_slide_nested_group_freeform_shape_in_new_group_with_text(
            source,
            &out,
            0,
            0,
            91440,
            182880,
            914400,
            914400,
            914400,
            914400,
            &operations,
            "Nested Freeform",
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.shape_id, 5);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "shape");
        assert_eq!(nested_group.children[0].text, "Nested Freeform");
        assert_eq!(
            nested_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 914400,
                cy: 914400,
            })
        );
        assert!(slide_xml.contains("<p:grpSp>"));
        assert!(slide_xml.contains("<a:custGeom>"));
        assert!(slide_xml.contains("<a:t>Nested Freeform</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }
