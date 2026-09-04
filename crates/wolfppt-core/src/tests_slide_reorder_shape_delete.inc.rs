    #[test]
    fn reorders_slides_without_changing_slide_parts_or_relationships() {
        let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("reordered.pptx");
        let original = inspect_package(source).unwrap();

        let result = apply_edit_batch(
            source,
            &out,
            &[EditOperation::ReorderSlides {
                slide_indices: vec![1, 0],
            }],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let rewritten = inspect_package(&out).unwrap();
        let original_presentation = read_zip_text(source, "ppt/presentation.xml");
        let rewritten_presentation = read_zip_text(&out, "ppt/presentation.xml");
        let original_relationship_ids = slide_relationship_ids_in_presentation(
            original_presentation.as_bytes(),
        )
        .unwrap();
        let rewritten_relationship_ids = slide_relationship_ids_in_presentation(
            rewritten_presentation.as_bytes(),
        )
        .unwrap();

        assert_eq!(result.edits, 1);
        assert_eq!(summary.slides[0].part, "ppt/slides/slide2.xml");
        assert_eq!(summary.slides[1].part, "ppt/slides/slide1.xml");
        assert_eq!(
            rewritten_relationship_ids,
            vec![
                original_relationship_ids[1].clone(),
                original_relationship_ids[0].clone(),
            ]
        );
        for slide_id in ["256", "257"] {
            assert_eq!(
                rewritten_presentation.matches(&format!("id=\"{slide_id}\"")).count(),
                original_presentation.matches(&format!("id=\"{slide_id}\"")).count(),
            );
        }
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original.parts.iter().all(|part| {
            part.name == "ppt/presentation.xml" || rewritten.parts.contains(part)
        }));
    }

    #[test]
    fn deletes_one_shape_without_changing_unrelated_package_parts() {
        let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("shape-deleted.pptx");
        let original = inspect_package(source).unwrap();

        apply_edit_batch(
            source,
            &out,
            &[EditOperation::DeleteShape {
                slide_index: 0,
                shape_index: 0,
            }],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();
        let rewritten = inspect_package(&out).unwrap();

        assert!(summary.slides[0].shapes.is_empty());
        assert_eq!(summary.slides[1].shapes.len(), 1);
        assert_eq!(original.parts.len(), rewritten.parts.len());
        assert!(original.parts.iter().all(|part| {
            part.name == "ppt/slides/slide1.xml" || rewritten.parts.contains(part)
        }));
    }

    #[test]
    fn applies_slide_local_edits_before_delete_and_reorder() {
        let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("mixed-structural-edit.pptx");

        apply_edit_batch(
            source,
            &out,
            &[
                EditOperation::SetShapeText {
                    slide_index: 1,
                    shape_index: 0,
                    replacement: "Moved and edited".to_string(),
                },
                EditOperation::DeleteShape {
                    slide_index: 0,
                    shape_index: 0,
                },
                EditOperation::ReorderSlides {
                    slide_indices: vec![1, 0],
                },
            ],
        )
        .unwrap();
        let summary = summarize_presentation(&out).unwrap();

        assert_eq!(summary.slides[0].part, "ppt/slides/slide2.xml");
        assert_eq!(summary.slides[0].shapes[0].text, "Moved and edited");
        assert_eq!(summary.slides[1].part, "ppt/slides/slide1.xml");
        assert!(summary.slides[1].shapes.is_empty());
    }

    #[test]
    fn removes_a_deleted_picture_relationship_but_preserves_its_media_part() {
        let source = "../../fixtures/pptx/media/png_picture.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("picture-deleted.pptx");
        let original = inspect_package(source).unwrap();

        apply_edit_batch(
            source,
            &out,
            &[EditOperation::DeleteShape {
                slide_index: 0,
                shape_index: 0,
            }],
        )
        .unwrap();
        let relationships = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");
        let rewritten = inspect_package(&out).unwrap();

        assert!(!relationships.contains("/image"));
        assert!(relationships.contains("/slideLayout"));
        assert!(original
            .parts
            .iter()
            .filter(|part| part.name.starts_with("ppt/media/"))
            .all(|part| rewritten.parts.contains(part)));
    }

    #[test]
    fn keeps_a_deleted_shapes_relationship_when_a_survivor_still_references_it() {
        let xml = br#"<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/><p:pic><p:blipFill><p:blip r:embed="rId2"/></p:blipFill></p:pic><p:pic><p:blipFill><p:blip r:embed="rId2"/></p:blipFill></p:pic></p:spTree></p:cSld></p:sld>"#;

        let (rewritten, count, orphan_relationship_ids) =
            delete_shape_at_index_in_slide(xml, 0).unwrap();
        let rewritten = String::from_utf8(rewritten).unwrap();

        assert_eq!(count, 1);
        assert_eq!(rewritten.matches("<p:pic>").count(), 1);
        assert!(rewritten.contains("r:embed=\"rId2\""));
        assert!(orphan_relationship_ids.is_empty());
    }
