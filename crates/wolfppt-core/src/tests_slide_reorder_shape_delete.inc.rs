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
    let original_relationship_ids =
        slide_relationship_ids_in_presentation(original_presentation.as_bytes()).unwrap();
    let rewritten_relationship_ids =
        slide_relationship_ids_in_presentation(rewritten_presentation.as_bytes()).unwrap();

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
            rewritten_presentation
                .matches(&format!("id=\"{slide_id}\""))
                .count(),
            original_presentation
                .matches(&format!("id=\"{slide_id}\""))
                .count(),
        );
    }
    assert_eq!(original.parts.len(), rewritten.parts.len());
    assert!(original
        .parts
        .iter()
        .all(|part| { part.name == "ppt/presentation.xml" || rewritten.parts.contains(part) }));
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
    assert!(original
        .parts
        .iter()
        .all(|part| { part.name == "ppt/slides/slide1.xml" || rewritten.parts.contains(part) }));
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

#[test]
fn reorders_only_the_root_presentation_slide_id_list_around_sections() {
    // Exercises the p14:sectionLst collision: the section extension
    // carries its own sldIdLst/sldId entries in the p14 namespace, plus a
    // presentation-namespace sldIdLst behind a locally declared prefix
    // that is NOT a direct child of the presentation root. Only the
    // root's own list may be collected; a non-self-closed p:sldId entry
    // must be captured and replayed intact.
    let xml = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="rId7"></p:sldId><p:sldId id="257" r:id="rId8"></p:sldId><p:sldId id="258" r:id="rId9"/></p:sldIdLst><p:extLst><p:ext uri="{521415D9-36F7-43E2-AB2F-B90AF26B5E84}"><p14:sectionLst><p14:section name="Exec" id="{5AFF34B2-A757-4D2D-B8CD-91A579060DDC}"><p14:sldIdLst xmlns:q="http://schemas.openxmlformats.org/presentationml/2006/main"><p14:sldId id="256"></p14:sldId><p14:sldId id="257"/><q:sldIdLst><q:sldId id="258"/></q:sldIdLst></p14:sldIdLst></p14:section></p14:sectionLst></p:ext></p:extLst></p:presentation>"#;

    let (rewritten, count) = reorder_slide_ids(xml, &[2, 1, 0]).unwrap();
    let rewritten = String::from_utf8(rewritten).unwrap();

    assert_eq!(count, 1);
    // The root list is reordered, self-closed and paired entries alike.
    let list = rewritten.split("</p:sldIdLst>").next().unwrap().to_string();
    let position_258 = list.find("id=\"258\"").unwrap();
    let position_257 = list.find("id=\"257\"").unwrap();
    let position_256 = list.find("id=\"256\"").unwrap();
    assert!(position_258 < position_257 && position_257 < position_256);
    // The non-self-closed entry keeps its paired tag and relationship.
    assert!(list.contains(r#"<p:sldId id="256" r:id="rId7"></p:sldId>"#));
    // The section extension passes through untouched: the p14 entries
    // and the locally prefixed presentation-namespace list keep their
    // document order and are not collected as presentation slides.
    assert!(rewritten.contains(r#"<p14:sldId id="256"></p14:sldId>"#));
    assert!(rewritten.contains("<p14:sldId id=\"257\"/>"));
    assert!(rewritten.contains("<q:sldIdLst><q:sldId id=\"258\"/></q:sldIdLst>"));
    assert_eq!(
        rewritten.matches("id=\"256\"").count(),
        std::str::from_utf8(xml)
            .unwrap()
            .matches("id=\"256\"")
            .count()
    );
}
