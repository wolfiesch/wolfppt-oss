    #[test]
    fn applies_table_cell_edit_batch() {
        let source = "../../fixtures/pptx/tables/simple_table.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("edit-table-batch.pptx");

        let result = apply_edit_batch(
            source,
            &out,
            &[
                EditOperation::ReplaceTableCellText {
                    slide_index: 0,
                    table_index: 0,
                    row_index: 1,
                    col_index: 0,
                    replacement: "Rows".to_string(),
                },
                EditOperation::ReplaceTableCellText {
                    slide_index: 0,
                    table_index: 0,
                    row_index: 1,
                    col_index: 1,
                    replacement: "2".to_string(),
                },
            ],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();

        assert_eq!(result.edits, 2);
        assert_eq!(result.replacements, 2);
        assert_eq!(summary.slides[0].tables[0].rows[1], vec!["Rows", "2"]);
    }

    #[test]
    fn applies_table_cell_merge_batch() {
        let source = "../../fixtures/pptx/tables/simple_table.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("merge-table-batch.pptx");

        let result = apply_edit_batch(
            source,
            &out,
            &[EditOperation::SetTableCellMerge {
                slide_index: 0,
                table_index: 0,
                row_min: 0,
                row_max: 1,
                col_min: 0,
                col_max: 1,
                kind: "merge".to_string(),
                paragraphs: vec![
                    "Metric".to_string(),
                    "Value".to_string(),
                    "Slides".to_string(),
                    "1".to_string(),
                ],
            }],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.edits, 1);
        assert_eq!(summary.slides[0].tables[0].rows[0][0], "Metric\nValue\nSlides\n1");
        assert_eq!(summary.slides[0].tables[0].rows[0][1], "");
        assert!(slide_xml.contains(r#"<a:tc rowSpan="2" gridSpan="2">"#));
        assert!(slide_xml.contains(r#"<a:tc rowSpan="2" hMerge="1">"#));
        assert!(slide_xml.contains(r#"<a:tc gridSpan="2" vMerge="1">"#));
        assert!(slide_xml.contains(r#"<a:tc hMerge="1" vMerge="1">"#));
    }

    #[test]
    fn applies_table_style_flag_batch() {
        let source = "../../fixtures/pptx/tables/simple_table.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("table-style-flags-batch.pptx");

        let result = apply_edit_batch(
            source,
            &out,
            &[EditOperation::SetTableStyleFlags {
                slide_index: 0,
                table_index: 0,
                flags: std::collections::BTreeMap::from([
                    ("firstCol".to_string(), true),
                    ("firstRow".to_string(), false),
                    ("bandRow".to_string(), false),
                    ("lastCol".to_string(), true),
                    ("lastRow".to_string(), true),
                    ("bandCol".to_string(), true),
                ]),
            }],
        )
        .unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.edits, 1);
        assert_eq!(result.replacements, 1);
        assert!(slide_xml.contains(
            r#"<a:tblPr firstCol="1" lastCol="1" lastRow="1" bandCol="1">"#
        ));
        assert!(!slide_xml.contains(r#"firstRow="1""#));
        assert!(!slide_xml.contains(r#"bandRow="1""#));
    }

    #[test]
    fn replaces_slide_image_payload_by_relationship_id() {
        let source = "../../fixtures/pptx/media/png_picture.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let out = dir.path().join("replace-image.pptx");
        std::fs::write(&image, b"replacement image bytes").unwrap();

        let result = replace_slide_image(source, &out, "rId2", &image).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.replacements, 1);
        assert_eq!(
            result.replaced_parts,
            vec!["ppt/media/image1.png".to_string()]
        );
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/media/image1.png")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn replaces_slide_image_payload_by_slide_index() {
        let source = "../../fixtures/pptx/media/png_picture.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let out = dir.path().join("replace-image-index.pptx");
        std::fs::write(&image, b"replacement image bytes").unwrap();

        let result = replace_slide_image_at_index(source, &out, 0, "rId2", &image).unwrap();

        assert_eq!(result.replacements, 1);
        assert_eq!(
            result.replaced_parts,
            vec!["ppt/media/image1.png".to_string()]
        );
    }

    #[test]
    fn adds_slide_image_shape_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let out = dir.path().join("add-image.pptx");
        let image_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&image, image_payload).unwrap();

        let result = add_slide_image(source, &out, 0, &image, 0, 0, 914400, 914400).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");
        let content_types_xml = read_zip_text(&out, "[Content_Types].xml");

        assert_eq!(result.slide_part, "ppt/slides/slide1.xml");
        assert_eq!(result.relationship_id, "rId2");
        assert_eq!(result.image_part, "ppt/media/image1.png");
        assert_eq!(summary.slides[0].image_relationships.len(), 1);
        assert_eq!(
            summary.slides[0].image_relationships[0].target,
            "../media/image1.png"
        );
        assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
        assert_eq!(rewritten.parts.len(), original.parts.len() + 1);
        assert!(slide_xml.contains(r#"<p:pic>"#));
        assert!(slide_xml.contains(r#"<p:cNvPr id="4" name="Picture 3"/>"#));
        assert!(slide_xml.contains(r#"r:embed="rId2""#));
        assert!(slide_xml.contains(r#"<a:ext cx="914400" cy="914400"/>"#));
        assert!(rels_xml.contains(r#"Target="../media/image1.png""#));
        assert!(content_types_xml.contains(r#"Extension="png" ContentType="image/png""#));
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
    fn reuses_matching_slide_image_media_part() {
        let source = "../../fixtures/pptx/workloads/mixed_real_world_deck.pptx";
        let dir = tempfile::tempdir().unwrap();
        let image = dir.path().join("image.png");
        let out = dir.path().join("reuse-image.pptx");
        let image_payload = read_zip_bytes(source, "ppt/media/image1.png");
        std::fs::write(&image, image_payload).unwrap();

        let result = add_slide_image(source, &out, 0, &image, 0, 0, 914400, 914400).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original_rels_xml = read_zip_text(source, "ppt/slides/_rels/slide1.xml.rels");
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");

        assert_eq!(result.slide_part, "ppt/slides/slide1.xml");
        assert_eq!(result.image_part, "ppt/media/image1.png");
        assert_eq!(rewritten.parts.len(), original.parts.len());
        assert!(!rewritten.part_names().contains(&"ppt/media/image2.png"));
        assert_eq!(rels_xml, original_rels_xml);
        assert_eq!(summary.slides[0].image_relationships.len(), 1);
        assert_eq!(
            summary.slides[0].image_relationships[0].target,
            "../media/image1.png"
        );
        assert!(slide_xml.contains(&format!(r#"r:embed="{}""#, result.relationship_id)));
        assert!(rels_xml.contains(&format!(r#"Id="{}""#, result.relationship_id)));
        assert!(original
            .parts
            .iter()
            .filter(|part| {
                !matches!(
                    part.name.as_str(),
                    "ppt/slides/slide1.xml" | "ppt/slides/_rels/slide1.xml.rels"
                )
            })
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_slide_movie_shape_with_media_relationships() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let movie = dir.path().join("movie.mp4");
        let poster = dir.path().join("poster.png");
        let out = dir.path().join("add-movie.pptx");
        let poster_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&movie, b"fake movie bytes").unwrap();
        std::fs::write(&poster, poster_payload).unwrap();

        let result = add_slide_movie(
            source,
            &out,
            0,
            &movie,
            Some(poster.as_path()),
            914400,
            1828800,
            2743200,
            1828800,
            "video/mp4",
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");
        let content_types_xml = read_zip_text(&out, "[Content_Types].xml");

        assert_eq!(result.slide_part, "ppt/slides/slide1.xml");
        assert_eq!(result.media_relationship_id, "rId2");
        assert_eq!(result.video_relationship_id, "rId3");
        assert_eq!(result.poster_relationship_id, "rId4");
        assert_eq!(result.media_part, "ppt/media/media1.mp4");
        assert_eq!(result.poster_part, "ppt/media/image1.png");
        assert_eq!(summary.slides[0].media_relationships.len(), 2);
        assert_eq!(summary.slides[0].shapes.last().unwrap().kind, "movie");
        assert!(!summary.slides[0].shapes.last().unwrap().has_picture);
        assert!(rewritten.part_names().contains(&"ppt/media/media1.mp4"));
        assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
        assert_eq!(rewritten.parts.len(), original.parts.len() + 2);
        assert!(slide_xml.contains(r#"<a:videoFile r:link="rId3"/>"#));
        assert!(slide_xml.contains(r#"r:embed="rId2""#));
        assert!(slide_xml.contains(r#"<a:blip r:embed="rId4"/>"#));
        assert!(slide_xml.contains(r#"<p:video>"#));
        assert!(rels_xml.contains(r#"Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/media1.mp4""#));
        assert!(rels_xml.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/video" Target="../media/media1.mp4""#));
        assert!(rels_xml.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png""#));
        assert!(content_types_xml.contains(r#"Extension="mp4" ContentType="video/mp4""#));
        assert!(content_types_xml.contains(r#"Extension="png" ContentType="image/png""#));
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
    fn adds_slide_ole_object_shape_with_embedding_relationships() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let object = dir.path().join("object.bin");
        let icon = dir.path().join("icon.png");
        let out = dir.path().join("add-ole-object.pptx");
        let icon_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&object, b"fake embedded object bytes").unwrap();
        std::fs::write(&icon, icon_payload).unwrap();

        let result = add_slide_ole_object(
            source,
            &out,
            0,
            &object,
            "Package",
            914400,
            1828800,
            2743200,
            914400,
            Some(icon.as_path()),
            914400,
            914400,
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");
        let content_types_xml = read_zip_text(&out, "[Content_Types].xml");

        assert_eq!(result.slide_part, "ppt/slides/slide1.xml");
        assert_eq!(result.ole_relationship_id, "rId2");
        assert_eq!(result.icon_relationship_id, "rId3");
        assert_eq!(result.ole_part, "ppt/embeddings/oleObject1.bin");
        assert_eq!(result.icon_part, "ppt/media/image1.png");
        assert_eq!(summary.slides[0].ole_relationships.len(), 1);
        assert_eq!(summary.slides[0].shapes.last().unwrap().kind, "ole_object");
        assert!(rewritten
            .part_names()
            .contains(&"ppt/embeddings/oleObject1.bin"));
        assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
        assert_eq!(rewritten.parts.len(), original.parts.len() + 2);
        assert!(slide_xml.contains(r#"<p:oleObj showAsIcon="1" r:id="rId2""#));
        assert!(slide_xml.contains(r#"progId="Package""#));
        assert!(slide_xml.contains(r#"<a:blip r:embed="rId3"/>"#));
        assert!(rels_xml.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="../embeddings/oleObject1.bin""#));
        assert!(rels_xml.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png""#));
        assert!(content_types_xml.contains(r#"PartName="/ppt/embeddings/oleObject1.bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject""#));
        assert!(content_types_xml.contains(r#"Extension="png" ContentType="image/png""#));
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
    fn adds_ole_object_inside_existing_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let object = dir.path().join("object.bin");
        let icon = dir.path().join("icon.png");
        let out = dir.path().join("add-group-ole-object.pptx");
        let icon_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&object, b"fake embedded object bytes").unwrap();
        std::fs::write(&icon, icon_payload).unwrap();

        let result = add_slide_group_ole_object(
            source,
            &out,
            0,
            0,
            &object,
            "Package",
            91440,
            182880,
            731520,
            457200,
            Some(icon.as_path()),
            365760,
            274320,
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");

        assert_eq!(result.ole_relationship_id, "rId2");
        assert_eq!(result.icon_relationship_id, "rId3");
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        assert_eq!(
            summary.slides[0].shapes[0].children[1].kind,
            "ole_object"
        );
        assert_eq!(rewritten.parts.len(), original.parts.len() + 2);
        assert!(slide_xml.contains(r#"<p:oleObj showAsIcon="1" r:id="rId2""#));
        assert!(rels_xml.contains(r#"Target="../embeddings/oleObject1.bin""#));
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
    fn adds_ole_object_inside_new_nested_group_shape() {
        let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
        let dir = tempfile::tempdir().unwrap();
        let object = dir.path().join("object.bin");
        let icon = dir.path().join("icon.png");
        let out = dir.path().join("add-new-nested-group-ole-object.pptx");
        let icon_payload = read_zip_bytes(
            "../../fixtures/pptx/media/png_picture.pptx",
            "ppt/media/image1.png",
        );
        std::fs::write(&object, b"fake embedded object bytes").unwrap();
        std::fs::write(&icon, icon_payload).unwrap();

        let result = add_slide_nested_group_ole_object_in_new_group(
            source,
            &out,
            0,
            0,
            &object,
            "Package",
            91440,
            182880,
            731520,
            457200,
            Some(icon.as_path()),
            365760,
            274320,
        )
        .unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
        let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");

        assert_eq!(result.shape_id, 5);
        assert_eq!(result.ole_relationship_id, "rId2");
        assert_eq!(result.icon_relationship_id, "rId3");
        assert_eq!(summary.slides[0].shapes[0].children.len(), 2);
        let nested_group = &summary.slides[0].shapes[0].children[1];
        assert_eq!(nested_group.kind, "group");
        assert_eq!(nested_group.children.len(), 1);
        assert_eq!(nested_group.children[0].kind, "ole_object");
        assert_eq!(
            nested_group.children[0].transform,
            Some(TransformSummary {
                x: 91440,
                y: 182880,
                cx: 731520,
                cy: 457200,
            })
        );
        assert_eq!(rewritten.parts.len(), original.parts.len() + 2);
        assert!(slide_xml.contains(r#"<p:oleObj showAsIcon="1" r:id="rId2""#));
        assert!(rels_xml.contains(r#"Target="../embeddings/oleObject1.bin""#));
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
    fn replaces_table_cell_text_without_losing_package_parts() {
        let source = "../../fixtures/pptx/tables/simple_table.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("replace-table.pptx");

        let result = replace_table_cell_text(source, &out, 0, 0, 1, 1, "2").unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.replacements, 1);
        assert_eq!(summary.slides[0].tables[0].rows[1][1], "2");
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_slide_table_without_losing_package_parts() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-table.pptx");

        let result = add_slide_table(source, &out, 0, 2, 3, 0, 0, 2743200, 914400).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_part, "ppt/slides/slide1.xml");
        assert_eq!(result.table_index, 0);
        assert_eq!(result.rows, 2);
        assert_eq!(result.cols, 3);
        assert_eq!(summary.slides[0].tables.len(), 1);
        assert_eq!(summary.slides[0].tables[0].row_count, 2);
        assert_eq!(summary.slides[0].tables[0].col_count, 3);
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(slide_xml.contains(r#"<p:graphicFrame>"#));
        assert!(slide_xml.contains(
            r#"<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">"#
        ));
        assert!(slide_xml.contains(r#"<a:ext cx="2743200" cy="914400"/>"#));
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn edits_newly_added_empty_table_cell() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let table_out = dir.path().join("add-table.pptx");
        let edit_out = dir.path().join("edit-table.pptx");

        add_slide_table(source, &table_out, 0, 2, 3, 0, 0, 2743200, 914400).unwrap();
        let result = replace_table_cell_text(&table_out, &edit_out, 0, 0, 0, 0, "Metric").unwrap();
        let summary = summarize_presentation(&edit_out).unwrap();

        assert_eq!(result.replacements, 1);
        assert_eq!(summary.slides[0].tables[0].rows[0][0], "Metric");
    }

    #[test]
    fn adds_table_with_cell_text_without_second_rewrite() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-table-with-text.pptx");

        let result = add_slide_table_with_cell_texts(
            source,
            &out,
            0,
            2,
            3,
            914400,
            2743200,
            3657600,
            914400,
            &[(0, 0, "Metric".to_string())],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

        assert_eq!(result.slide_index, 0);
        assert_eq!(result.table_index, 0);
        assert_eq!(summary.slides[0].tables[0].rows[0][0], "Metric");
        assert!(slide_xml.contains("<a:t>Metric</a:t>"));
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name != "ppt/slides/slide1.xml")
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_blank_slide_from_existing_layout() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-slide.pptx");

        let result = add_blank_slide_from_existing_layout(source, &out).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let original = inspect_package(source).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert_eq!(result.slide_part, "ppt/slides/slide2.xml");
        assert_eq!(result.relationship_id, "rId8");
        assert_eq!(result.layout_target, "../slideLayouts/slideLayout7.xml");
        assert_eq!(result.slide_count, 2);
        assert_eq!(result.part_count, rewritten.parts.len());
        assert_eq!(summary.slide_count, 2);
        assert_eq!(summary.slides[1].part, "ppt/slides/slide2.xml");
        assert!(summary.slides[1].texts.is_empty());
        assert!(summary.slides[1]
            .relationships
            .iter()
            .any(|rel| rel.relationship_type.ends_with("/slideLayout")));
        assert!(rewritten
            .part_names()
            .contains(&"ppt/slides/_rels/slide2.xml.rels"));
        assert_eq!(rewritten.parts.len(), original.parts.len() + 2);
        assert!(original
            .parts
            .iter()
            .filter(|part| {
                !matches!(
                    part.name.as_str(),
                    "[Content_Types].xml"
                        | "ppt/presentation.xml"
                        | "ppt/_rels/presentation.xml.rels"
                )
            })
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn adds_blank_slide_from_selected_layout_index() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-slide-layout.pptx");

        let result = add_blank_slide_from_layout_index(source, &out, 0).unwrap();
        let summary = summarize_presentation(&out).unwrap();

        assert_eq!(result.layout_target, "../slideLayouts/slideLayout1.xml");
        assert_eq!(summary.slides[1].texts, Vec::<String>::new());
        assert_eq!(summary.slides[1].tables, Vec::<TableSummary>::new());
        assert!(summary.slides[1].relationships.iter().any(|rel| {
            rel.relationship_type.ends_with("/slideLayout")
                && rel.target == "../slideLayouts/slideLayout1.xml"
        }));
    }

    #[test]
    fn appends_first_slide_id_list_for_zero_slide_presentation() {
        let xml = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldSz cx="9144000" cy="6858000" type="screen4x3"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>"#;

        let rewritten = append_slide_id(xml, 256, "rId2").unwrap();
        let rewritten = String::from_utf8(rewritten).unwrap();

        assert!(rewritten.contains(
            r#"</p:sldMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst><p:sldSz"#
        ));
    }

    #[test]
    fn materializes_editable_layout_placeholders_without_prompt_text() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("add-slide-placeholders.pptx");

        add_blank_slide_from_layout_index(source, &out, 0).unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let slide_xml = read_zip_text(&out, "ppt/slides/slide2.xml");

        assert_eq!(summary.slides[1].texts, Vec::<String>::new());
        assert_eq!(summary.slides[1].relationships.len(), 1);
        assert_eq!(slide_xml.matches("<p:ph").count(), 2);
        assert!(slide_xml.contains("Title 1"));
        assert!(slide_xml.contains("Subtitle 2"));
        assert!(slide_xml.contains("<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>"));
        assert!(!slide_xml.contains("<a:t>"));
        assert!(!slide_xml.contains("Click to edit Master title style"));
    }

    #[test]
    fn summarizes_slide_text() {
        let summary =
            summarize_presentation("../../fixtures/pptx/text_basic/title_body_bullets.pptx")
                .unwrap();

        assert_eq!(summary.slide_count, 1);
        assert_eq!(summary.slides[0].part, "ppt/slides/slide1.xml");
        assert_eq!(
            summary.slides[0].texts,
            vec![
                "WolfPPT".to_string(),
                "Fast PPTX".to_string(),
                "Lossless first".to_string()
            ]
        );
    }

    #[test]
    fn summarizes_tables() {
        let summary =
            summarize_presentation("../../fixtures/pptx/tables/simple_table.pptx").unwrap();

        let table = &summary.slides[0].tables[0];
        assert_eq!(table.row_count, 2);
        assert_eq!(table.col_count, 2);
        assert_eq!(
            table.rows[0],
            vec!["Metric".to_string(), "Value".to_string()]
        );
    }

    #[test]
    fn summarizes_table_cells_with_run_spacing_and_paragraph_breaks() {
        let xml = br#"
            <p:spTree xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                      xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:graphicFrame>
                <a:graphic>
                  <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
                    <a:tbl>
                      <a:tr>
                        <a:tc>
                          <a:txBody>
                            <a:p>
                              <a:r><a:t>  Leading </a:t></a:r>
                              <a:r><a:t>and trailing  </a:t></a:r>
                            </a:p>
                            <a:p><a:r><a:t>Second paragraph</a:t></a:r></a:p>
                          </a:txBody>
                        </a:tc>
                        <a:tc>
                          <a:txBody>
                            <a:p><a:r><a:t>Before</a:t></a:r><a:br/><a:r><a:t>After</a:t></a:r></a:p>
                          </a:txBody>
                        </a:tc>
                      </a:tr>
                    </a:tbl>
                  </a:graphicData>
                </a:graphic>
              </p:graphicFrame>
            </p:spTree>
        "#;

        let tables = extract_tables(xml);

        assert_eq!(
            tables[0].rows[0],
            vec![
                "  Leading and trailing  \nSecond paragraph".to_string(),
                "Before\u{000b}After".to_string(),
            ]
        );
    }

    #[test]
    fn skips_alternate_content_choice_and_fallback_shapes() {
        let xml = br#"
            <p:spTree xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                      xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                      xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
              <p:sp>
                <p:nvSpPr><p:cNvPr id="1" name="Title 1"/></p:nvSpPr>
                <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Title</a:t></a:r></a:p></p:txBody>
              </p:sp>
              <mc:AlternateContent>
                <mc:Choice Requires="cx4">
                  <p:graphicFrame>
                    <p:nvGraphicFramePr><p:cNvPr id="2" name="Content Placeholder 5"/></p:nvGraphicFramePr>
                    <a:graphic><a:graphicData><c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"/></a:graphicData></a:graphic>
                  </p:graphicFrame>
                </mc:Choice>
                <mc:Fallback>
                  <p:pic>
                    <p:nvPicPr><p:cNvPr id="2" name="Content Placeholder 5"/></p:nvPicPr>
                  </p:pic>
                </mc:Fallback>
              </mc:AlternateContent>
              <p:sp>
                <p:nvSpPr><p:cNvPr id="3" name="Body 2"/></p:nvSpPr>
                <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Body</a:t></a:r></a:p></p:txBody>
              </p:sp>
            </p:spTree>
        "#;

        let shapes = extract_shapes(xml);

        assert_eq!(shapes.len(), 2);
        assert_eq!(shapes[0].name.as_deref(), Some("Title 1"));
        assert_eq!(shapes[1].name.as_deref(), Some("Body 2"));
    }

    #[test]
    fn summarizes_grouped_shape_tree_with_effective_transforms() {
        let summary =
            summarize_presentation("../../fixtures/pptx/shapes/grouped_shapes.pptx").unwrap();

        let group = &summary.slides[0].shapes[0];
        let child = &group.children[0];
        assert_eq!(group.kind, "group");
        assert_eq!(group.text, "Grouped Text");
        assert_eq!(
            group.effective_transform,
            Some(TransformSummary {
                x: 1000,
                y: 2000,
                cx: 4000,
                cy: 4000
            })
        );
        assert_eq!(child.kind, "shape");
        assert_eq!(child.text, "Grouped Text");
        assert_eq!(
            child.effective_transform,
            Some(TransformSummary {
                x: 1500,
                y: 2600,
                cx: 1000,
                cy: 800
            })
        );
    }

    #[test]
    fn summarizes_notes_relationship_and_text() {
        let summary =
            summarize_presentation("../../fixtures/pptx/notes/speaker_notes.pptx").unwrap();

        assert!(summary.slides[0]
            .relationships
            .iter()
            .any(|rel| rel.relationship_type.ends_with("/notesSlide")));
        assert_eq!(
            summary.slides[0].notes,
            vec!["Remember to mention preservation before rendering.".to_string()]
        );
    }

    #[test]
    fn summarizes_xml_entity_text_inside_runs_notes_and_tables() {
        let summary =
            summarize_presentation("../../fixtures/pptx/workloads/management_reporting_deck.pptx")
                .unwrap();

        assert_eq!(
            summary.slides[3].notes,
            vec!["Revenue Bridge owner is FP&A; preserve chart workbook and notes.".to_string()]
        );
        assert!(summary.slides[7]
            .texts
            .contains(&"Segment P&L".to_string()));
        assert!(summary.slides[7].texts.contains(&"FP&A".to_string()));

        let table = &summary.slides[7].tables[0];
        assert_eq!(table.rows[2][0], "Segment P&L");
        assert_eq!(table.rows[2][2], "FP&A");
    }

    #[test]
    fn summarizes_image_relationships() {
        let summary = summarize_presentation("../../fixtures/pptx/media/png_picture.pptx").unwrap();

        assert_eq!(summary.slides[0].image_relationships.len(), 1);
        assert!(summary.slides[0].image_relationships[0]
            .relationship_type
            .ends_with("/image"));
        assert_eq!(
            summary.slides[0].image_relationships[0].target,
            "../media/image1.png"
        );
    }

    #[test]
    fn classifies_rich_slide_relationship_types() {
        let rels = vec![
            RelationshipSummary {
                id: "rId1".to_string(),
                relationship_type:
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
                        .to_string(),
                target: "../charts/chart1.xml".to_string(),
                target_mode: None,
            },
            RelationshipSummary {
                id: "rId2".to_string(),
                relationship_type:
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video"
                        .to_string(),
                target: "../media/media1.mp4".to_string(),
                target_mode: None,
            },
            RelationshipSummary {
                id: "rId3".to_string(),
                relationship_type:
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject"
                        .to_string(),
                target: "../embeddings/oleObject1.bin".to_string(),
                target_mode: None,
            },
        ];

        assert_eq!(relationships_by_type(&rels, &["/chart"]).len(), 1);
        assert_eq!(relationships_by_type(&rels, &["/video", "/audio"]).len(), 1);
        assert_eq!(
            relationships_by_type(&rels, &["/oleObject", "/package"]).len(),
            1
        );
    }

    #[test]
    fn detects_transition_and_timing_markers() {
        let xml = br#"
            <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
              <p:transition/>
              <p:timing/>
            </p:sld>
        "#;

        assert!(has_element(xml, b"transition"));
        assert!(has_element(xml, b"timing"));
        assert!(!has_element(xml, b"notHere"));
    }
