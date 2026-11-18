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
        assert_eq!(
            summary.slides[0].tables[0].rows[0][0],
            "Metric\nValue\nSlides\n1"
        );
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
        assert!(slide_xml.contains(r#"<a:tblPr firstCol="1" lastCol="1" lastRow="1" bandCol="1">"#));
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
            None,
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
        assert_eq!(summary.slides[0].shapes[0].children[1].kind, "ole_object");
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
    fn adds_blank_slide_with_prefixed_content_types() {
        let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
        let dir = tempfile::tempdir().unwrap();
        let prefixed = dir.path().join("prefixed-content-types.pptx");
        let out = dir.path().join("add-slide.pptx");

        {
            let input = File::open(source).unwrap();
            let mut archive = ZipArchive::new(input).unwrap();
            let output = File::create(&prefixed).unwrap();
            let mut writer = zip::ZipWriter::new(output);
            let options = SimpleFileOptions::default();
            for i in 0..archive.len() {
                let mut file = archive.by_index(i).unwrap();
                let name = file.name().unwrap().into_owned();
                if name == "[Content_Types].xml" {
                    let mut content = String::new();
                    file.read_to_string(&mut content).unwrap();
                    let prefixed_content = prefixed_content_types(&content);
                    writer.start_file(name, options).unwrap();
                    std::io::copy(&mut Cursor::new(prefixed_content.as_bytes()), &mut writer)
                        .unwrap();
                } else {
                    writer.raw_copy_file(file).unwrap();
                }
            }
            writer.finish().unwrap();
        }

        let result = add_blank_slide_from_existing_layout(&prefixed, &out).unwrap();
        assert_eq!(result.slide_part, "ppt/slides/slide2.xml");
        let content_types = read_zip_text(&out, "[Content_Types].xml");
        assert!(content_types.contains(
            r#"<ct:Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>"#
        ));
        assert!(content_types.contains("</ct:Types>"));
    }

    #[test]
    fn appends_content_types_children_to_prefixed_self_closing_root() {
        let xml = br#"<?xml version="1.0" encoding="UTF-8"?><ct:Types xmlns:ct="http://schemas.openxmlformats.org/package/2006/content-types"/>"#;
        let with_default =
            ensure_default_content_type(std::str::from_utf8(xml).unwrap(), "png", "image/png")
                .unwrap();
        let rewritten = append_content_type_override(
            with_default.as_bytes(),
            "/ppt/slides/slide1.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        )
        .unwrap();
        let rewritten = String::from_utf8(rewritten).unwrap();
        assert_eq!(
            rewritten,
            r#"<?xml version="1.0" encoding="UTF-8"?><ct:Types xmlns:ct="http://schemas.openxmlformats.org/package/2006/content-types"><ct:Default Extension="png" ContentType="image/png"/><ct:Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></ct:Types>"#
        );
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
    fn expands_self_closing_slide_id_list_preserving_start_tag_attributes() {
        let xml = br#"<p:presentation xmlns:p="urn:p" xmlns:r="urn:r"><p:sldIdLst xmlns:custom="urn:custom" data="quoted > value" custom:flag="keep"/></p:presentation>"#;

        let rewritten = String::from_utf8(append_slide_id(xml, 256, "rId2").unwrap()).unwrap();

        assert_eq!(rewritten.matches("<p:sldIdLst").count(), 1);
        assert!(rewritten.contains(
            r#"<p:sldIdLst xmlns:custom="urn:custom" data="quoted > value" custom:flag="keep"><p:sldId id="256" r:id="rId2"/></p:sldIdLst>"#
        ));
    }

    #[test]
    fn appends_to_expanded_empty_slide_id_list_without_duplicating_it() {
        let xml = br#"<p:presentation xmlns:p="urn:p" xmlns:r="urn:r"><p:sldIdLst custom="preserved"></p:sldIdLst></p:presentation>"#;

        let rewritten = String::from_utf8(append_slide_id(xml, 256, "rId2").unwrap()).unwrap();

        assert_eq!(rewritten.matches("<p:sldIdLst").count(), 1);
        assert!(rewritten.contains(
            r#"<p:sldIdLst custom="preserved"><p:sldId id="256" r:id="rId2"/></p:sldIdLst>"#
        ));
    }

    #[test]
    fn appends_to_populated_slide_id_list_without_duplicating_it() {
        let xml = br#"<p:presentation xmlns:p="urn:p" xmlns:r="urn:r"><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst></p:presentation>"#;

        let rewritten = String::from_utf8(append_slide_id(xml, 257, "rId3").unwrap()).unwrap();

        assert_eq!(rewritten.matches("<p:sldIdLst").count(), 1);
        assert!(
            rewritten.contains(r#"<p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId3"/>"#)
        );
    }

    #[test]
    fn adds_slide_to_project_authored_blank_with_one_slide_id_list() {
        let source = "../../src/wolfppt/templates/blank.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("project-authored-blank-add-slide.pptx");

        add_blank_slide_from_layout_index(source, &out, 6).unwrap();
        let presentation_xml = read_zip_text(&out, "ppt/presentation.xml");

        assert_eq!(presentation_xml.matches("<p:sldIdLst").count(), 1);
        assert_eq!(presentation_xml.matches("<p:sldId ").count(), 1);
        assert!(presentation_xml
            .contains(r#"<p:sldIdLst><p:sldId id="256" r:id="rId4"/></p:sldIdLst>"#));
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
        assert!(summary.slides[7].texts.contains(&"Segment P&L".to_string()));
        assert!(summary.slides[7].texts.contains(&"FP&A".to_string()));

        let table = &summary.slides[7].tables[0];
        assert_eq!(table.rows[2][0], "Segment P&L");
        assert_eq!(table.rows[2][2], "FP&A");
    }

    #[test]
    fn xml_text_entities_remain_complete_across_event_boundaries() {
        let xml = br#"<p:sld><a:p><a:r><a:rPr b="1"/><a:t>A&amp;&lt;&gt;&quot;&apos;&#65;&#x1F642;B</a:t></a:r><a:r><a:t><![CDATA[C&D]]></a:t></a:r></a:p></p:sld>"#;
        let first = "A&<>\"'A🙂B";
        assert_eq!(extract_text_runs(xml), vec![first, "C&D"]);
        assert_eq!(extract_paragraph_runs(xml), vec![vec![first, "C&D"]]);
        assert_eq!(extract_paragraph_texts(xml), vec![format!("{first}C&D")]);
        assert_eq!(extract_paragraph_run_bold(xml), vec![vec![Some(true), None]]);
    }

    #[test]
    fn text_search_replaces_a_logical_node_across_entities_and_cdata() {
        let xml = br#"<p:sld><a:t>pre&amp;&#65;<![CDATA[B]]>&#x43;post</a:t><a:t>&unknown;</a:t></p:sld>"#;
        let (rewritten, replacements) = replace_text_nodes(xml, "&ABC", "<new&>").unwrap();
        assert_eq!(replacements, 1);
        assert_eq!(extract_text_runs(&rewritten), vec!["pre<new&>post", "&unknown;"]);
        assert_eq!(
            String::from_utf8(rewritten).unwrap(),
            r#"<p:sld><a:t>pre&lt;new&amp;&gt;post</a:t><a:t>&unknown;</a:t></p:sld>"#
        );
        let (unchanged, replacements) = replace_text_nodes(xml, "absent", "unused").unwrap();
        assert_eq!(replacements, 0);
        assert_eq!(unchanged, xml);
    }

    #[test]
    fn indexed_text_replacement_counts_nodes_not_entity_events() {
        let xml = br#"<p:sld><a:t></a:t><a:t>A&amp;&#65;B</a:t><a:t>&lt;&#x43;</a:t><a:t>last</a:t></p:sld>"#;
        let (rewritten, replacements) = replace_text_run_at_index_in_slide(xml, 1, "new&").unwrap();
        assert_eq!(replacements, 1);
        assert_eq!(extract_text_runs(&rewritten), vec!["A&AB", "new&", "last"]);
        assert!(String::from_utf8(rewritten).unwrap().contains("<a:t>A&amp;&#65;B</a:t>"));
    }

    #[test]
    fn table_text_replacement_removes_all_original_entity_events() {
        let xml = br#"<p:sld><a:tbl><a:tr><a:tc><a:p><a:r><a:t>&amp;&#65;<![CDATA[B]]>tail</a:t></a:r></a:p></a:tc><a:tc><a:p><a:r><a:t>keep&lt;</a:t></a:r></a:p></a:tc></a:tr></a:tbl></p:sld>"#;
        let (single, count) = replace_table_cell_text_in_slide(xml, 0, 0, 0, "new&").unwrap();
        assert_eq!(count, 1);
        assert_eq!(extract_text_runs(&single), vec!["new&", "keep<"]);
        let (batch, count) =
            replace_table_cell_text_batch_in_slide(xml, &[(0, 0, 0, "new&")]).unwrap();
        assert_eq!(count, 1);
        assert_eq!(extract_text_runs(&batch), vec!["new&", "keep<"]);
    }

    #[test]
    fn group_text_replacement_removes_entities_without_affecting_other_runs() {
        let xml = br#"<p:sld><p:grpSp><p:sp><p:txBody><a:p><a:r><a:t>&amp;&#65;<![CDATA[B]]>tail</a:t></a:r><a:r><a:t>keep&lt;</a:t></a:r></a:p></p:txBody></p:sp></p:grpSp></p:sld>"#;
        let (run, count) = set_group_shape_child_run_text_in_slide(xml, 0, 0, 0, 0, "new&").unwrap();
        assert_eq!(extract_text_runs(&run), vec!["new&", "keep<"]);
        assert_eq!(count, 1);
        let (paragraph, count) =
            set_group_shape_child_paragraph_text_in_slide(xml, 0, 0, 0, "new&").unwrap();
        assert_eq!(extract_text_runs(&paragraph), vec!["new&"]);
        assert_eq!(count, 1);
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
    fn finds_only_direct_tm_root_child_list_across_self_closing_timing_nodes() {
        let valid = concat!(
            "<p:timing><p:tnLst><p:par><p:cTn id=\"1\" nodeType=\"tmRoot\">",
            "<p:childTnLst><p:seq><p:cTn id=\"2\" nodeType=\"mainSeq\">",
            "<p:childTnLst><p:par><p:cTn id=\"3\"/></p:par></p:childTnLst>",
            "</p:cTn></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>",
        );
        let (start, end) = timing_root_child_list_bounds(valid).unwrap();
        assert!(valid[start..end].starts_with("<p:childTnLst><p:seq>"));

        let missing_direct_list = concat!(
            "<p:timing><p:tnLst><p:par><p:cTn id=\"1\" nodeType=\"tmRoot\">",
            "<p:seq><p:cTn id=\"2\" nodeType=\"mainSeq\"><p:childTnLst>",
            "<p:par><p:cTn id=\"3\"/></p:par></p:childTnLst></p:cTn></p:seq>",
            "</p:cTn></p:par></p:tnLst></p:timing>",
        );
        assert!(timing_root_child_list_bounds(missing_direct_list).is_none());
    }

    #[test]
    fn summarizes_audio_playback_and_preserves_across_slide_intent() {
        let xml = concat!(
            "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" ",
            "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" ",
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">",
            "<p:cSld><p:spTree><p:pic><p:nvPicPr>",
            "<p:cNvPr id=\"5\" name=\"audio.wav\"/><p:cNvPicPr/><p:nvPr>",
            "<a:audioFile r:link=\"rId2\"/></p:nvPr></p:nvPicPr>",
            "<p:blipFill/><p:spPr/></p:pic></p:spTree></p:cSld>",
            "<p:timing><p:tnLst><p:par><p:cTn id=\"1\" nodeType=\"tmRoot\">",
            "<p:childTnLst><p:audio><p:cMediaNode vol=\"35000\" numSld=\"2\">",
            "<p:cTn id=\"7\" repeatCount=\"indefinite\"><p:stCondLst>",
            "<p:cond delay=\"0\"/></p:stCondLst></p:cTn><p:tgtEl>",
            "<p:spTgt spid=\"5\"/></p:tgtEl></p:cMediaNode></p:audio>",
            "</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing></p:sld>",
        );
        let shapes = extract_shapes(xml.as_bytes());
        assert_eq!(shapes[0].kind, "audio");
        assert_eq!(
            shapes[0].media_playback,
            Some(MediaPlaybackSummary {
                r#loop: true,
                play_across_slides: true,
                volume: 35,
                auto_play: true,
            })
        );

        let timing = media_timing_child_xml(5, 7, "audio", true, true, 35, 1);
        assert!(timing.contains(r#"<p:cMediaNode vol="35000" numSld="2">"#));
        let timing = media_timing_child_xml(5, 7, "audio", true, false, 35, 1);
        assert!(
            timing.contains(r#"<p:cMediaNode vol="35000">"#),
            "PowerPoint omits numSld when play across slides is off: {timing}"
        );
    }

    #[test]
    fn video_media_node_never_carries_num_sld() {
        // PowerPoint 16 will not start or play a video whose cMediaNode sets
        // numSld, and offers Play Across Slides for audio only.
        let slide = format!("{MEDIA_SLIDE_HEAD}</p:sld>");
        let slide = add_movie_timing_to_slide_xml(&slide, 5, None).unwrap();
        assert!(!slide.contains("numSld"), "{slide}");

        let auto = set_media_playback_in_slide_xml(&slide, 5, true, false, 35, true, 3).unwrap();
        assert!(!auto.contains("numSld"), "{auto}");
        let video = &auto[auto.find("<p:video>").unwrap()..];
        assert!(video.starts_with(r#"<p:video><p:cMediaNode vol="35000"><p:cTn id=""#));
        assert!(video.contains(
            r#"" fill="hold" display="0" repeatCount="indefinite"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="5"/></p:tgtEl></p:cMediaNode></p:video>"#
        ));

        let error = set_media_playback_in_slide_xml(&slide, 5, true, true, 35, true, 3)
            .unwrap_err()
            .to_string();
        assert!(error.contains("play across slides"), "{error}");
        assert!(error.contains("video"), "{error}");

        // A source video node that already carries numSld still reads, and any
        // playback rewrite of it drops the attribute.
        let legacy = auto.replace(
            r#"<p:cMediaNode vol="35000">"#,
            r#"<p:cMediaNode vol="35000" numSld="2">"#,
        );
        let legacy_playback = extract_shapes(legacy.as_bytes())
            .into_iter()
            .find(|shape| shape.kind == "movie")
            .and_then(|shape| shape.media_playback)
            .unwrap();
        assert!(legacy_playback.play_across_slides);
        let rewritten =
            set_media_playback_in_slide_xml(&legacy, 5, true, false, 35, true, 3).unwrap();
        assert!(!rewritten.contains("numSld"), "{rewritten}");
    }

    const MEDIA_SLIDE_HEAD: &str = concat!(
        "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" ",
        "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" ",
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">",
        "<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"Title\"/><p:cNvSpPr/>",
        "<p:nvPr/></p:nvSpPr><p:spPr/></p:sp><p:pic><p:nvPicPr>",
        "<p:cNvPr id=\"5\" name=\"clip.mp4\"/><p:cNvPicPr/><p:nvPr>",
        "<a:videoFile r:link=\"rId2\"/></p:nvPr></p:nvPicPr>",
        "<p:blipFill/><p:spPr/></p:pic></p:spTree></p:cSld>",
    );

    fn media_call_count(xml: &str) -> usize {
        xml.matches(r#"presetClass="mediacall""#).count()
    }

    fn summarized_auto_play(xml: &str) -> bool {
        extract_shapes(xml.as_bytes())
            .into_iter()
            .find(|shape| shape.kind == "movie")
            .and_then(|shape| shape.media_playback)
            .map(|playback| playback.auto_play)
            .unwrap()
    }

    #[test]
    fn auto_play_is_an_automatic_main_sequence_media_call() {
        let slide = format!("{MEDIA_SLIDE_HEAD}</p:sld>");
        let slide = add_movie_timing_to_slide_xml(&slide, 5, None).unwrap();
        assert!(!summarized_auto_play(&slide));

        let auto = set_media_playback_in_slide_xml(&slide, 5, false, false, 80, true, 1).unwrap();
        let seq = auto.find(r#"nodeType="mainSeq""#).unwrap();
        let video = auto.find("<p:video>").unwrap();
        assert!(seq < video, "main sequence precedes the media node");
        let seq_id = extract_string_attribute(&auto[auto[..seq].rfind("<p:cTn").unwrap()..], "id")
            .unwrap();
        assert!(auto.contains(&format!(
            r#"<p:cond evt="onBegin" delay="0"><p:tn val="{seq_id}"/></p:cond>"#
        )));
        assert!(auto.contains(r#"nodeType="afterEffect""#));
        assert!(auto.contains(r#"<p:cmd type="call" cmd="playFrom(0.0)">"#));
        assert!(auto[video..].contains(r#"<p:cond delay="indefinite"/>"#));
        assert_eq!(media_call_count(&auto), 1);
        assert!(summarized_auto_play(&auto));
        let ids: Vec<u64> = auto
            .match_indices("<p:cTn ")
            .filter_map(|(at, _)| extract_string_attribute(&auto[at..], "id"))
            .map(|id| id.parse().unwrap())
            .collect();
        let mut unique = ids.clone();
        unique.sort_unstable();
        unique.dedup();
        assert_eq!(ids.len(), unique.len(), "timing ids stay unique");

        let again = set_media_playback_in_slide_xml(&auto, 5, true, false, 50, true, 1).unwrap();
        assert_eq!(media_call_count(&again), 1, "re-applying auto_play keeps one call");

        let manual = set_media_playback_in_slide_xml(&again, 5, true, false, 50, false, 1).unwrap();
        assert_eq!(media_call_count(&manual), 0);
        assert!(!manual.contains("mainSeq"), "an emptied main sequence is removed");
        assert!(!summarized_auto_play(&manual));
    }

    #[test]
    fn auto_play_joins_an_existing_automatic_first_click_group() {
        let animated = format!(
            "{MEDIA_SLIDE_HEAD}{}</p:sld>",
            concat!(
                "<p:timing><p:tnLst><p:par><p:cTn id=\"1\" dur=\"indefinite\" restart=\"never\" ",
                "nodeType=\"tmRoot\"><p:childTnLst><p:seq concurrent=\"1\" nextAc=\"seek\">",
                "<p:cTn id=\"2\" dur=\"indefinite\" nodeType=\"mainSeq\"><p:childTnLst>",
                "<p:par><p:cTn id=\"3\" fill=\"hold\"><p:stCondLst><p:cond delay=\"indefinite\"/>",
                "<p:cond evt=\"onBegin\" delay=\"0\"><p:tn val=\"2\"/></p:cond></p:stCondLst>",
                "<p:childTnLst><p:par><p:cTn id=\"4\" fill=\"hold\"><p:stCondLst>",
                "<p:cond delay=\"0\"/></p:stCondLst><p:childTnLst><p:par>",
                "<p:cTn id=\"5\" presetID=\"10\" presetClass=\"entr\" presetSubtype=\"0\" ",
                "fill=\"hold\" nodeType=\"afterEffect\"><p:stCondLst><p:cond delay=\"0\"/>",
                "</p:stCondLst><p:childTnLst><p:set><p:cBhvr><p:cTn id=\"6\" dur=\"1\" ",
                "fill=\"hold\"/><p:tgtEl><p:spTgt spid=\"2\"/></p:tgtEl></p:cBhvr>",
                "<p:to><p:strVal val=\"visible\"/></p:to></p:set></p:childTnLst></p:cTn>",
                "</p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>",
                "</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt=\"onPrev\" delay=\"0\">",
                "<p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst>",
                "<p:cond evt=\"onNext\" delay=\"0\"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>",
                "</p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>",
            )
        );
        let slide = add_movie_timing_to_slide_xml(&animated, 5, None).unwrap();
        let auto = set_media_playback_in_slide_xml(&slide, 5, false, false, 80, true, 1).unwrap();
        assert_eq!(auto.matches(r#"evt="onBegin""#).count(), 1);
        assert_eq!(auto.matches("nodeType=\"mainSeq\"").count(), 1);
        let entrance = auto.find(r#"presetClass="entr""#).unwrap();
        let call = auto.find(r#"presetClass="mediacall""#).unwrap();
        assert!(entrance < call);
        assert!(auto[call..].starts_with(r#"presetClass="mediacall" presetSubtype="0" fill="hold" nodeType="withEffect""#));
        assert!(summarized_auto_play(&auto));

        let manual = set_media_playback_in_slide_xml(&auto, 5, false, false, 80, false, 1).unwrap();
        let main_sequence = |xml: &str| {
            let start = xml.find("<p:seq").unwrap();
            xml[start..find_element_end(xml, start, "p:seq").unwrap()].to_string()
        };
        assert_eq!(
            main_sequence(&manual),
            main_sequence(&slide),
            "removing the call restores the animation sequence"
        );
        assert!(!summarized_auto_play(&manual));
    }

    #[test]
    fn default_audio_icon_is_a_visible_png_shaped_like_the_audio_frame() {
        let png = default_audio_icon_png(1_828_800, 914_400);
        assert_eq!(&png[..8], &[137, 80, 78, 71, 13, 10, 26, 10]);
        assert_eq!(&png[12..16], b"IHDR");
        let width = u32::from_be_bytes(png[16..20].try_into().unwrap());
        let height = u32::from_be_bytes(png[20..24].try_into().unwrap());
        assert_eq!((width, height), (256, 128));
        assert!(audio_icon_covers(0.2, 0.5), "speaker body");
        assert!(audio_icon_covers(0.5, 0.5), "speaker cone");
        assert!(!audio_icon_covers(0.02, 0.02), "transparent corner");
        let square = default_audio_icon_png(914_400, 914_400);
        let side = u32::from_be_bytes(square[16..20].try_into().unwrap());
        assert_eq!(side, u32::from_be_bytes(square[20..24].try_into().unwrap()));
    }

    #[test]
    fn detects_transition_and_timing_markers() {
        let xml = br#"
            <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
              <p:transition/>
              <p:timing/>
            </p:sld>
        "#;

        assert_eq!(
            extract_text_runs_and_elements(xml, [b"transition", b"timing", b"notHere"]).1,
            [true, true, false]
        );
        assert_eq!(extract_text_runs_and_elements(xml, [b"timing"]).1, [true]);
        // A read error ends the search; markers before it still count.
        assert_eq!(
            extract_text_runs_and_elements(
                b"<a><transition/></b><timing/>",
                [b"transition", b"timing"]
            ).1,
            [true, false]
        );
    }
