#[test]
fn deletes_first_slide_and_preserves_survivor_and_package_integrity() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("deleted_first.pptx");

    let summary = delete_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let presentation = summarize_presentation(&out).unwrap();
    let presentation_xml = read_zip_text(&out, "ppt/presentation.xml");
    let presentation_rels = read_zip_text(&out, "ppt/_rels/presentation.xml.rels");
    let content_types = read_zip_text(&out, "[Content_Types].xml");

    assert_eq!(summary.deleted_slide_parts, vec!["ppt/slides/slide1.xml"]);
    assert_eq!(summary.survivor_count, 1);
    assert_eq!(presentation.slides.len(), 1);
    assert_eq!(presentation.slides[0].part, "ppt/slides/slide2.xml");

    // slide1 parts must be removed
    assert!(!rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/slide1.xml"));
    assert!(!rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/_rels/slide1.xml.rels"));

    // slide2 parts must remain
    assert!(rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/slide2.xml"));

    // presentation.xml must not reference deleted slide relationship
    for rel_id in &summary.deleted_relationship_ids {
        assert!(!presentation_xml.contains(&format!(r#"r:id="{rel_id}""#)));
        assert!(!presentation_rels.contains(&format!(r#"Id="{rel_id}""#)));
    }
    assert!(!content_types.contains("/ppt/slides/slide1.xml"));
    assert!(content_types.contains("/ppt/slides/slide2.xml"));
}

#[test]
fn deletes_second_slide_and_preserves_first_slide() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("deleted_second.pptx");

    let summary = delete_slide(source, &out, "ppt/slides/slide2.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let presentation = summarize_presentation(&out).unwrap();
    let presentation_xml = read_zip_text(&out, "ppt/presentation.xml");
    let presentation_rels = read_zip_text(&out, "ppt/_rels/presentation.xml.rels");
    let content_types = read_zip_text(&out, "[Content_Types].xml");

    assert_eq!(summary.deleted_slide_parts, vec!["ppt/slides/slide2.xml"]);
    assert_eq!(summary.survivor_count, 1);
    assert_eq!(presentation.slides.len(), 1);
    assert_eq!(presentation.slides[0].part, "ppt/slides/slide1.xml");

    assert!(!rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/slide2.xml"));
    assert!(!rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/_rels/slide2.xml.rels"));
    assert!(rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/slide1.xml"));

    for rel_id in &summary.deleted_relationship_ids {
        assert!(!presentation_xml.contains(&format!(r#"r:id="{rel_id}""#)));
        assert!(!presentation_rels.contains(&format!(r#"Id="{rel_id}""#)));
    }
    assert!(!content_types.contains("/ppt/slides/slide2.xml"));
    assert!(content_types.contains("/ppt/slides/slide1.xml"));
}

#[test]
fn deletes_multiple_slides_and_reorders_survivors() {
    let source = "../../fixtures/pptx/workloads/customer_success_review_pack.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("deleted_multiple.pptx");

    // customer_success_review_pack has 6 slides
    let original = summarize_presentation(source).unwrap();
    assert_eq!(original.slides.len(), 6);

    let target_deletes = ["ppt/slides/slide2.xml", "ppt/slides/slide4.xml"];
    // Remaining slides are 1, 3, 5, 6. Let's reorder them to 6, 1, 5, 3!
    let survivor_order = [
        "ppt/slides/slide6.xml",
        "ppt/slides/slide1.xml",
        "ppt/slides/slide5.xml",
        "ppt/slides/slide3.xml",
    ];

    let summary = delete_slides(source, &out, &target_deletes, Some(&survivor_order)).unwrap();
    let presentation = summarize_presentation(&out).unwrap();

    assert_eq!(summary.survivor_count, 4);
    assert_eq!(presentation.slides.len(), 4);
    assert_eq!(presentation.slides[0].part, "ppt/slides/slide6.xml");
    assert_eq!(presentation.slides[1].part, "ppt/slides/slide1.xml");
    assert_eq!(presentation.slides[2].part, "ppt/slides/slide5.xml");
    assert_eq!(presentation.slides[3].part, "ppt/slides/slide3.xml");
}

#[test]
fn rejects_deleting_all_slides() {
    let source = "../../fixtures/pptx/text_basic/title_body_bullets.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("deleted_sole.pptx");

    let err = delete_slide(source, &out, "ppt/slides/slide1.xml").unwrap_err();
    assert!(err
        .to_string()
        .contains("cannot delete all slides; presentation must contain at least one slide"));
}

#[test]
fn rejects_unknown_target_slide_part_for_deletion() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("out.pptx");

    let err = delete_slide(source, &out, "ppt/slides/slide99.xml").unwrap_err();
    assert!(err
        .to_string()
        .contains("target slide part ppt/slides/slide99.xml was not found"));
}

#[test]
fn rejects_duplicate_target_slide_parts_for_deletion() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("out.pptx");

    let err = delete_slides(
        source,
        &out,
        &["ppt/slides/slide1.xml", "ppt/slides/slide1.xml"],
        None,
    )
    .unwrap_err();
    assert!(err
        .to_string()
        .contains("duplicate target slide part specified"));
}

#[test]
fn rejects_mismatched_survivor_parts_count() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("out.pptx");

    let err = delete_slides(
        source,
        &out,
        &["ppt/slides/slide1.xml"],
        Some(&["ppt/slides/slide2.xml", "ppt/slides/slide3.xml"]),
    )
    .unwrap_err();
    assert!(err
        .to_string()
        .contains("ordered survivor parts count (2) does not match surviving slides count (1)"));
}

#[test]
fn rejects_deleted_part_in_ordered_survivors() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("out.pptx");

    let err = delete_slides(
        source,
        &out,
        &["ppt/slides/slide1.xml"],
        Some(&["ppt/slides/slide1.xml"]),
    )
    .unwrap_err();
    assert!(err.to_string().contains(
        "deleted slide part ppt/slides/slide1.xml cannot be included in ordered survivors"
    ));
}

#[test]
fn rejects_duplicate_part_in_ordered_survivors() {
    let source = "../../fixtures/pptx/workloads/customer_success_review_pack.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("out.pptx");

    let err = delete_slides(
        source,
        &out,
        &["ppt/slides/slide2.xml"],
        Some(&[
            "ppt/slides/slide1.xml",
            "ppt/slides/slide1.xml",
            "ppt/slides/slide3.xml",
            "ppt/slides/slide4.xml",
            "ppt/slides/slide5.xml",
        ]),
    )
    .unwrap_err();
    assert!(err
        .to_string()
        .contains("duplicate survivor slide part in ordered survivors"));
}

#[test]
fn rejects_non_survivor_part_in_ordered_survivors() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("out.pptx");

    let err = delete_slides(
        source,
        &out,
        &["ppt/slides/slide1.xml"],
        Some(&["ppt/slides/slide99.xml"]),
    )
    .unwrap_err();
    assert!(err
        .to_string()
        .contains("survivor slide part ppt/slides/slide99.xml was not found"));
}

#[test]
fn preserves_transitive_media_on_surviving_slides() {
    let source = "../../fixtures/pptx/media/png_picture.pptx";
    let dir = tempfile::tempdir().unwrap();
    let duplicated = dir.path().join("duplicated.pptx");
    let deleted = dir.path().join("deleted.pptx");

    let dup_summary = duplicate_slide(source, &duplicated, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(dup_summary.slide_count, 2);

    let del_summary = delete_slide(&duplicated, &deleted, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(del_summary.survivor_count, 1);

    let rewritten = inspect_package(&deleted).unwrap();
    assert!(rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/media/image1.png"));
    assert!(rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/slides/slide2.xml"));
    let rels = read_zip_text(&deleted, "ppt/slides/_rels/slide2.xml.rels");
    assert!(rels.contains("../media/image1.png"));
}

#[test]
fn preserves_vba_macro_project_on_slide_deletion() {
    let source = "../../fixtures/pptx/package/macro_preservation.pptm";
    let dir = tempfile::tempdir().unwrap();
    let duplicated = dir.path().join("duplicated.pptm");
    let deleted = dir.path().join("deleted.pptm");

    // Duplicate slide 1 so we have 2 slides
    let dup_summary = duplicate_slide(source, &duplicated, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(dup_summary.slide_count, 2);
    assert!(dup_summary.has_vba);

    // Delete slide 2
    let del_summary = delete_slide(&duplicated, &deleted, "ppt/slides/slide2.xml").unwrap();
    assert_eq!(del_summary.survivor_count, 1);
    assert!(del_summary.has_vba);

    let rewritten = inspect_package(&deleted).unwrap();
    assert!(rewritten
        .parts
        .iter()
        .any(|p| p.name == "ppt/vbaProject.bin"));
}

#[test]
fn cleans_unreferenced_slide_parts_and_preserves_shared_parts() {
    let source = "../../fixtures/pptx/charts/bar_chart.pptx";
    let dir = tempfile::tempdir().unwrap();
    let duplicated = dir.path().join("duplicated.pptx");
    let deleted = dir.path().join("deleted.pptx");

    // Duplicate slide 1 to create slide 2 with chart2 and sheet2
    duplicate_slide(source, &duplicated, "ppt/slides/slide1.xml").unwrap();

    // Now delete slide 1. chart1 and sheet1 should be pruned; chart2 and sheet2 remain.
    delete_slide(&duplicated, &deleted, "ppt/slides/slide1.xml").unwrap();

    let rewritten = inspect_package(&deleted).unwrap();
    let part_names: Vec<&str> = rewritten.parts.iter().map(|p| p.name.as_str()).collect();

    // slide1, chart1, sheet1 pruned
    assert!(!part_names.contains(&"ppt/slides/slide1.xml"));
    assert!(!part_names.contains(&"ppt/slides/_rels/slide1.xml.rels"));
    assert!(!part_names.contains(&"ppt/charts/chart1.xml"));
    assert!(!part_names.contains(&"ppt/charts/_rels/chart1.xml.rels"));
    assert!(!part_names.contains(&"ppt/embeddings/Microsoft_Excel_Sheet1.xlsx"));

    // slide2, chart2, sheet2 preserved
    assert!(part_names.contains(&"ppt/slides/slide2.xml"));
    assert!(part_names.contains(&"ppt/charts/chart2.xml"));
    assert!(part_names.contains(&"ppt/embeddings/Microsoft_Excel_Sheet2.xlsx"));

    // Content types check
    let content_types = read_zip_text(&deleted, "[Content_Types].xml");
    assert!(!content_types.contains("/ppt/charts/chart1.xml"));
    assert!(content_types.contains("/ppt/charts/chart2.xml"));
}

#[test]
fn cleans_unreferenced_ole_object() {
    let source = "../../fixtures/pptx/package/ole_object.pptx";
    let dir = tempfile::tempdir().unwrap();
    let duplicated = dir.path().join("duplicated.pptx");
    let deleted = dir.path().join("deleted.pptx");

    duplicate_slide(source, &duplicated, "ppt/slides/slide1.xml").unwrap();
    delete_slide(&duplicated, &deleted, "ppt/slides/slide1.xml").unwrap();

    let rewritten = inspect_package(&deleted).unwrap();
    let part_names: Vec<&str> = rewritten.parts.iter().map(|p| p.name.as_str()).collect();

    assert!(!part_names.contains(&"ppt/embeddings/oleObject1.bin"));
    assert!(part_names.contains(&"ppt/embeddings/oleObject2.bin"));

    let content_types = read_zip_text(&deleted, "[Content_Types].xml");
    assert!(!content_types.contains("/ppt/embeddings/oleObject1.bin"));
    assert!(content_types.contains("/ppt/embeddings/oleObject2.bin"));
}

#[test]
fn preserves_unreferenced_unknown_binary_and_xml_parts() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected_source = dir.path().join("injected.pptx");
    let deleted_out = dir.path().join("deleted.pptx");

    let custom_bin_bytes = b"CUSTOM_UNKNOWN_BINARY_DATA_PAYLOAD_98765";
    let custom_xml_bytes = b"<customMeta><item val=\"preserved\"/></customMeta>";
    let custom_rels_bytes = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"#;

    // Create injected_source by copying source and adding custom parts + content types
    {
        let file_in = File::open(source).unwrap();
        let mut zip_in = ZipArchive::new(file_in).unwrap();
        let file_out = File::create(&injected_source).unwrap();
        let mut zip_out = zip::ZipWriter::new(file_out);

        for i in 0..zip_in.len() {
            let mut file = zip_in.by_index(i).unwrap();
            let name = file.name().to_string();
            let options = SimpleFileOptions::default().compression_method(file.compression());
            if name == "[Content_Types].xml" {
                let mut ct_text = String::new();
                file.read_to_string(&mut ct_text).unwrap();
                let injection = r#"<Override PartName="/custom/unknown_payload.bin" ContentType="application/octet-stream"/><Override PartName="/custom/unknown_meta.xml" ContentType="application/xml"/></Types>"#;
                let modified_ct = ct_text.replace("</Types>", injection);
                zip_out.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(modified_ct.as_bytes()), &mut zip_out).unwrap();
            } else {
                zip_out.start_file(name, options).unwrap();
                std::io::copy(&mut file, &mut zip_out).unwrap();
            }
        }

        let options = SimpleFileOptions::default();
        zip_out
            .start_file("custom/unknown_payload.bin", options)
            .unwrap();
        std::io::copy(&mut Cursor::new(custom_bin_bytes), &mut zip_out).unwrap();

        zip_out
            .start_file("custom/unknown_meta.xml", options)
            .unwrap();
        std::io::copy(&mut Cursor::new(custom_xml_bytes), &mut zip_out).unwrap();

        zip_out
            .start_file("custom/_rels/unknown_meta.xml.rels", options)
            .unwrap();
        std::io::copy(&mut Cursor::new(custom_rels_bytes), &mut zip_out).unwrap();

        zip_out.finish().unwrap();
    }

    // Delete slide1
    let summary = delete_slide(&injected_source, &deleted_out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.survivor_count, 1);

    let rewritten = inspect_package(&deleted_out).unwrap();
    let part_names: Vec<&str> = rewritten.parts.iter().map(|p| p.name.as_str()).collect();

    // Target slide removed, survivor preserved
    assert!(!part_names.contains(&"ppt/slides/slide1.xml"));
    assert!(part_names.contains(&"ppt/slides/slide2.xml"));

    // Unreferenced unknown parts MUST BE PRESERVED!
    assert!(part_names.contains(&"custom/unknown_payload.bin"));
    assert!(part_names.contains(&"custom/unknown_meta.xml"));
    assert!(part_names.contains(&"custom/_rels/unknown_meta.xml.rels"));

    // Verify exact bytes
    let read_bin = read_zip_bytes(&deleted_out, "custom/unknown_payload.bin");
    assert_eq!(read_bin, custom_bin_bytes);

    let read_xml = read_zip_bytes(&deleted_out, "custom/unknown_meta.xml");
    assert_eq!(read_xml, custom_xml_bytes);

    let read_rels = read_zip_bytes(&deleted_out, "custom/_rels/unknown_meta.xml.rels");
    assert_eq!(read_rels, custom_rels_bytes);

    // Verify Content Types overrides preserved
    let ct = read_zip_text(&deleted_out, "[Content_Types].xml");
    assert!(ct.contains(r#"PartName="/custom/unknown_payload.bin""#));
    assert!(ct.contains(r#"PartName="/custom/unknown_meta.xml""#));
    assert!(!ct.contains("/ppt/slides/slide1.xml"));
    assert!(ct.contains("/ppt/slides/slide2.xml"));
}
