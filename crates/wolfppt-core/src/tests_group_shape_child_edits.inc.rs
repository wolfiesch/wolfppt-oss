#[test]
fn sets_existing_group_child_text_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("set-group-child-text.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetGroupShapeChildText {
            slide_index: 0,
            group_index: 0,
            child_index: 0,
            replacement: "Updated Grouped Text".to_string(),
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.replacements, 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].text,
        "Updated Grouped Text"
    );
    assert!(slide_xml.contains("<a:t>Updated Grouped Text</a:t>"));
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide1.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn sets_existing_group_child_paragraph_text_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("set-group-child-paragraph-text.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetGroupShapeChildParagraphText {
            slide_index: 0,
            group_index: 0,
            child_index: 0,
            paragraph_index: 0,
            replacement: "Paragraph Grouped Text".to_string(),
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].paragraphs,
        vec!["Paragraph Grouped Text"]
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide1.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn appends_group_child_paragraph_text_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("append-group-child-paragraph-text.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetGroupShapeChildParagraphText {
            slide_index: 0,
            group_index: 0,
            child_index: 0,
            paragraph_index: 1,
            replacement: "Third".to_string(),
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].paragraphs,
        vec!["Grouped Text", "Third"]
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide1.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn sets_existing_group_child_run_text_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("set-group-child-run-text.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetGroupShapeChildRunText {
            slide_index: 0,
            group_index: 0,
            child_index: 0,
            paragraph_index: 0,
            run_index: 0,
            replacement: "Run Grouped Text".to_string(),
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].paragraph_runs,
        vec![vec!["Run Grouped Text".to_string()]]
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide1.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn appends_group_child_run_text_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("append-group-child-run-text.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetGroupShapeChildRunText {
            slide_index: 0,
            group_index: 0,
            child_index: 0,
            paragraph_index: 0,
            run_index: 1,
            replacement: " Decks".to_string(),
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].paragraph_runs,
        vec![vec!["Grouped Text".to_string(), " Decks".to_string()]]
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide1.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn appends_group_child_paragraph_then_run_text_in_one_batch() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir
        .path()
        .join("append-group-child-paragraph-run-text.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[
            EditOperation::SetGroupShapeChildParagraphText {
                slide_index: 0,
                group_index: 0,
                child_index: 0,
                paragraph_index: 1,
                replacement: "".to_string(),
            },
            EditOperation::SetGroupShapeChildRunText {
                slide_index: 0,
                group_index: 0,
                child_index: 0,
                paragraph_index: 1,
                run_index: 0,
                replacement: "Third".to_string(),
            },
        ],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();

    assert_eq!(result.replacements, 2);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].paragraph_runs,
        vec![vec!["Grouped Text".to_string()], vec!["Third".to_string()]]
    );
}

#[test]
fn sets_existing_group_child_geometry_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("set-group-child-geometry.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::SetGroupShapeChildGeometry {
            slide_index: 0,
            group_index: 0,
            child_index: 0,
            x_emu: 91440,
            y_emu: 182880,
            cx_emu: 914400,
            cy_emu: 365760,
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].transform,
        Some(TransformSummary {
            x: 91440,
            y: 182880,
            cx: 914400,
            cy: 365760,
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
fn deletes_existing_group_child_shape_without_losing_package_parts() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("delete-group-child.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::DeleteGroupShapeChild {
            slide_index: 0,
            group_shape_id: 2,
            child_shape_id: 3,
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    assert_eq!(summary.slides[0].shapes[0].children.len(), 0);
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide1.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn deletes_group_child_from_multi_child_group_preserving_siblings() {
    let source = "../../fixtures/pptx/workloads/customer_success_review_pack.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("delete-group-child-multi.pptx");

    let result = apply_edit_batch(
        source,
        &out,
        &[EditOperation::DeleteGroupShapeChild {
            slide_index: 4,
            group_shape_id: 3,
            child_shape_id: 5,
        }],
    )
    .unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let original = inspect_package(source).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 1);
    // Slide 4 group had 4 children, now 3
    assert_eq!(summary.slides[4].shapes[1].children.len(), 3);
    assert_eq!(
        summary.slides[4].shapes[1].children[0].name.as_deref(),
        Some("Rounded Rectangle 3")
    );
    assert_eq!(
        summary.slides[4].shapes[1].children[1].name.as_deref(),
        Some("Rounded Rectangle 5")
    );
    assert_eq!(
        summary.slides[4].shapes[1].children[2].name.as_deref(),
        Some("Rounded Rectangle 6")
    );
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .filter(|part| part.name != "ppt/slides/slide5.xml")
        .all(|part| rewritten.parts.contains(part)));
}

#[test]
fn deletes_group_child_picture_cleans_relationship_but_preserves_media_part() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let image_file = dir.path().join("image.png");
    let with_pic = dir.path().join("group-with-pic.pptx");
    let image = read_zip_bytes(
        "../../fixtures/pptx/media/png_picture.pptx",
        "ppt/media/image1.png",
    );
    std::fs::write(&image_file, image).unwrap();

    let add_res = add_slide_group_image(
        source,
        &with_pic,
        0,
        0,
        &image_file,
        91440,
        182880,
        822960,
        822960,
    )
    .unwrap();
    assert_eq!(add_res.shape_id, 4);
    assert_eq!(add_res.relationship_id, "rId2");

    let out = dir.path().join("deleted-pic-child.pptx");
    let result = apply_edit_batch(
        &with_pic,
        &out,
        &[EditOperation::DeleteGroupShapeChild {
            slide_index: 0,
            group_shape_id: 2,
            child_shape_id: 4,
        }],
    )
    .unwrap();

    let summary = summarize_presentation(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
    let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");
    let original = inspect_package(&with_pic).unwrap();
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 2); // 1 in slide1.xml + 1 in slide1.xml.rels
    assert_eq!(summary.slides[0].shapes[0].children.len(), 1);
    assert_eq!(
        summary.slides[0].shapes[0].children[0].name.as_deref(),
        Some("Grouped Text 1")
    );
    assert!(!slide_xml.contains("rId2"));
    assert!(!slide_xml.contains("<p:pic>"));
    assert!(!rels_xml.contains(r#"Id="rId2""#));
    assert!(rels_xml.contains("/slideLayout"));
    assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
    assert_eq!(
        read_zip_bytes(&out, "ppt/media/image1.png"),
        read_zip_bytes(&with_pic, "ppt/media/image1.png")
    );
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
fn deletes_child_shape_in_nested_group_preserving_siblings() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let nested = dir.path().join("nested.pptx");
    let first = dir.path().join("first.pptx");
    let second = dir.path().join("second.pptx");

    let nested_res = add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
    let nested_group_id = nested_res.shape_id as usize;

    let first_res = add_slide_nested_group_auto_shape_with_text(
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
        "First Nested Child",
    )
    .unwrap();
    let first_child_id = first_res.shape_id as usize;

    let second_res = add_slide_nested_group_auto_shape_with_text(
        &first,
        &second,
        0,
        0,
        1,
        "ellipse",
        182880,
        182880,
        914400,
        457200,
        "Second Nested Child",
    )
    .unwrap();
    let _second_child_id = second_res.shape_id as usize;

    let out = dir.path().join("out.pptx");
    let result = apply_edit_batch(
        &second,
        &out,
        &[EditOperation::DeleteGroupShapeChild {
            slide_index: 0,
            group_shape_id: nested_group_id,
            child_shape_id: first_child_id,
        }],
    )
    .unwrap();

    let summary = summarize_presentation(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.replacements, 1);
    assert!(!slide_xml.contains("First Nested Child"));
    assert!(slide_xml.contains("Second Nested Child"));
    assert!(slide_xml.contains("Grouped Text 1"));

    // Verify that the nested group now has 1 child (Second Nested Child)
    let outer_group = &summary.slides[0].shapes[0];
    assert_eq!(outer_group.children.len(), 2); // original text + nested group
    let nested_group = &outer_group.children[1];
    assert_eq!(nested_group.children.len(), 1);
    assert_eq!(nested_group.children[0].text, "Second Nested Child");
}

#[test]
fn deletes_entire_nested_subgroup_from_outer_group() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let nested = dir.path().join("nested.pptx");
    let populated = dir.path().join("populated.pptx");

    let nested_res = add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
    let nested_group_id = nested_res.shape_id as usize;

    add_slide_nested_group_auto_shape_with_text(
        &nested,
        &populated,
        0,
        0,
        1,
        "rect",
        91440,
        91440,
        914400,
        457200,
        "Child in Nested Subgroup",
    )
    .unwrap();

    let out = dir.path().join("out.pptx");
    let result = apply_edit_batch(
        &populated,
        &out,
        &[EditOperation::DeleteGroupShapeChild {
            slide_index: 0,
            group_shape_id: 2, // outer group id
            child_shape_id: nested_group_id,
        }],
    )
    .unwrap();

    let summary = summarize_presentation(&out).unwrap();
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");

    assert_eq!(result.replacements, 1);
    assert!(!slide_xml.contains("Child in Nested Subgroup"));
    assert!(slide_xml.contains("Grouped Text 1"));

    let outer_group = &summary.slides[0].shapes[0];
    assert_eq!(outer_group.children.len(), 1);
    assert_eq!(
        outer_group.children[0].name.as_deref(),
        Some("Grouped Text 1")
    );
}

#[test]
fn deletes_nested_group_child_picture_cleans_relationship() {
    let source = "../../fixtures/pptx/shapes/grouped_shapes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let nested = dir.path().join("nested.pptx");
    let image_file = dir.path().join("image.png");
    let with_pic = dir.path().join("nested-with-pic.pptx");

    let image = read_zip_bytes(
        "../../fixtures/pptx/media/png_picture.pptx",
        "ppt/media/image1.png",
    );
    std::fs::write(&image_file, &image).unwrap();

    let nested_res = add_slide_nested_group_shape(source, &nested, 0, 0).unwrap();
    let nested_group_id = nested_res.shape_id as usize;

    let pic_res = add_slide_nested_group_image(
        &nested,
        &with_pic,
        0,
        0,
        1,
        &image_file,
        91440,
        182880,
        822960,
        822960,
    )
    .unwrap();
    let pic_child_id = pic_res.shape_id as usize;
    let pic_rel_id = pic_res.relationship_id;

    let out = dir.path().join("out.pptx");
    let result = apply_edit_batch(
        &with_pic,
        &out,
        &[EditOperation::DeleteGroupShapeChild {
            slide_index: 0,
            group_shape_id: nested_group_id,
            child_shape_id: pic_child_id,
        }],
    )
    .unwrap();

    let rels_xml = read_zip_text(&out, "ppt/slides/_rels/slide1.xml.rels");
    let slide_xml = read_zip_text(&out, "ppt/slides/slide1.xml");
    let rewritten = inspect_package(&out).unwrap();

    assert_eq!(result.replacements, 2); // 1 in slide1.xml + 1 in slide1.xml.rels
    assert!(!slide_xml.contains(&pic_rel_id));
    assert!(!slide_xml.contains("<p:pic>"));
    assert!(!rels_xml.contains(&format!(r#"Id="{pic_rel_id}""#)));
    assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
}
