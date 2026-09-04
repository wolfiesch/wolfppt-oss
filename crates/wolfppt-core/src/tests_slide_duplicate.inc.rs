#[test]
fn duplicates_slide_sharing_layout_and_image_parts() {
    let source = "../../fixtures/pptx/media/png_picture.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");
    let original = inspect_package(source).unwrap();

    let summary = duplicate_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let presentation = summarize_presentation(&out).unwrap();
    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide2.xml.rels");
    let source_rels = read_zip_text(source, "ppt/slides/_rels/slide1.xml.rels");

    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);
    assert_eq!(summary.slide_id, 257);
    assert_eq!(presentation.slides.len(), 2);
    assert_eq!(
        presentation.slides[0].part,
        presentation.slides[1].part.replace("slide2", "slide1")
    );
    assert_eq!(duplicate_rels, source_rels);
    assert!(duplicate_rels.contains("../media/image1.png"));
    assert_eq!(rewritten.parts.len(), original.parts.len() + 2);
    for part in &original.parts {
        assert!(
            part.name == "[Content_Types].xml"
                || part.name == "ppt/_rels/presentation.xml.rels"
                || part.name == "ppt/presentation.xml"
                || rewritten.parts.contains(part),
            "missing original part {}",
            part.name
        );
    }
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/slides/slide2.xml"));
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/slides/_rels/slide2.xml.rels"));
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/media/image1.png"));
}

#[test]
fn rejects_unknown_source_slide_part_for_duplication() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");

    let err = duplicate_slide(source, &out, "ppt/slides/slide9.xml").unwrap_err();

    assert!(err
        .to_string()
        .contains("source slide part ppt/slides/slide9.xml was not found"));
}

#[test]
fn duplicates_slide_with_chart_and_embedded_data() {
    let source = "../../fixtures/pptx/charts/bar_chart.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");
    let original = inspect_package(source).unwrap();

    let summary = duplicate_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let presentation = summarize_presentation(&out).unwrap();
    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide2.xml.rels");
    let chart_rels = read_zip_text(&out, "ppt/charts/_rels/chart2.xml.rels");

    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);
    assert_eq!(presentation.slides.len(), 2);
    assert!(duplicate_rels.contains("../charts/chart2.xml"));
    assert!(chart_rels.contains("../embeddings/Microsoft_Excel_Sheet2.xlsx"));
    assert_eq!(rewritten.parts.len(), original.parts.len() + 5);
    for part in &original.parts {
        assert!(
            part.name == "[Content_Types].xml"
                || part.name == "ppt/_rels/presentation.xml.rels"
                || part.name == "ppt/presentation.xml"
                || rewritten.parts.contains(part),
            "missing original part {}",
            part.name
        );
    }
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/charts/chart2.xml"));
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/charts/_rels/chart2.xml.rels"));
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/embeddings/Microsoft_Excel_Sheet2.xlsx"));
}

#[test]
fn duplicates_slide_with_chart_style_and_color_parts() {
    let source = "../../fixtures/pptx/charts/styled_bar_chart.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");
    let original = inspect_package(source).unwrap();

    let summary = duplicate_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let presentation = summarize_presentation(&out).unwrap();
    let chart_rels = read_zip_text(&out, "ppt/charts/_rels/chart2.xml.rels");

    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(presentation.slides.len(), 2);
    assert!(chart_rels.contains("Target=\"style2.xml\""));
    assert!(chart_rels.contains("Target=\"colors2.xml\""));
    assert!(chart_rels.contains("/chartStyle\""));
    assert!(chart_rels.contains("/chartColorStyle\""));
    assert_eq!(rewritten.parts.len(), original.parts.len() + 7);
    for name in [
        "ppt/charts/chart2.xml",
        "ppt/charts/_rels/chart2.xml.rels",
        "ppt/charts/style2.xml",
        "ppt/charts/colors2.xml",
        "ppt/embeddings/Microsoft_Excel_Sheet2.xlsx",
    ] {
        assert!(
            rewritten.parts.iter().any(|part| part.name == name),
            "missing duplicated part {name}"
        );
    }
    let content_types = read_zip_text(&out, "[Content_Types].xml");
    assert!(content_types.contains("/ppt/charts/style2.xml"));
    assert!(content_types.contains("/ppt/charts/colors2.xml"));
    assert!(content_types.contains("chartcolorstyle+xml"));
    assert!(content_types.contains("chartstyle+xml"));
}

#[test]
fn duplicates_slide_with_notes_slide_and_rewrites_back_reference() {
    let source = "../../fixtures/pptx/notes/speaker_notes.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");
    let original = inspect_package(source).unwrap();

    let summary = duplicate_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let presentation = summarize_presentation(&out).unwrap();
    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide2.xml.rels");
    let notes_rels = read_zip_text(&out, "ppt/notesSlides/_rels/notesSlide2.xml.rels");

    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);
    assert_eq!(presentation.slides.len(), 2);
    assert!(duplicate_rels.contains("../notesSlides/notesSlide2.xml"));
    assert!(notes_rels.contains("../slides/slide2.xml"));
    assert!(notes_rels.contains("../notesMasters/notesMaster1.xml"));
    assert_eq!(rewritten.parts.len(), original.parts.len() + 4);
    for part in &original.parts {
        assert!(
            part.name == "[Content_Types].xml"
                || part.name == "ppt/_rels/presentation.xml.rels"
                || part.name == "ppt/presentation.xml"
                || rewritten.parts.contains(part),
            "missing original part {}",
            part.name
        );
    }
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/notesSlides/notesSlide2.xml"));
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/notesSlides/_rels/notesSlide2.xml.rels"));
}

#[test]
fn duplicates_slide_with_ole_object() {
    let source = "../../fixtures/pptx/package/ole_object.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");
    let original = inspect_package(source).unwrap();

    let summary = duplicate_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide2.xml.rels");

    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);
    assert!(duplicate_rels.contains("../embeddings/oleObject2.bin"));
    assert_eq!(rewritten.parts.len(), original.parts.len() + 3);
    for part in &original.parts {
        assert!(
            part.name == "[Content_Types].xml"
                || part.name == "ppt/_rels/presentation.xml.rels"
                || part.name == "ppt/presentation.xml"
                || rewritten.parts.contains(part),
            "missing original part {}",
            part.name
        );
    }
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/embeddings/oleObject2.bin"));
}

#[test]
fn duplicates_slide_with_ole_object_when_source_lacks_bin_content_type_coverage() {
    let source = "../../fixtures/pptx/package/ole_object.pptx";
    let dir = tempfile::tempdir().unwrap();
    let stripped = dir.path().join("stripped_ole.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&stripped).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "[Content_Types].xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let cleaned = content
                    .replace(
                        r#"<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.presentationml.printerSettings"/>"#,
                        "",
                    )
                    .replace(
                        r#"<Override PartName="/ppt/embeddings/oleObject1.bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>"#,
                        "",
                    );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(cleaned.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&stripped, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);

    let content_types = read_zip_text(&out, "[Content_Types].xml");
    assert!(content_types.contains(r#"<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>"#));
    assert!(!content_types.contains("/ppt/embeddings/oleObject2.bin"));
}

#[test]
fn duplicates_slide_with_ole_object_relying_on_bin_default_content_type() {
    let source = "../../fixtures/pptx/package/ole_object.pptx";
    let dir = tempfile::tempdir().unwrap();
    let default_only = dir.path().join("default_only_ole.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&default_only).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "[Content_Types].xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let updated = content
                    .replace(
                        r#"<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.presentationml.printerSettings"/>"#,
                        r#"<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>"#,
                    )
                    .replace(
                        r#"<Override PartName="/ppt/embeddings/oleObject1.bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>"#,
                        "",
                    );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(updated.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&default_only, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);

    let content_types = read_zip_text(&out, "[Content_Types].xml");
    assert!(content_types.contains(r#"<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>"#));
    assert!(!content_types.contains("/ppt/embeddings/oleObject1.bin"));
    assert!(!content_types.contains("/ppt/embeddings/oleObject2.bin"));
}

#[test]
fn duplicates_slide_with_legacy_comments() {
    let source = "../../fixtures/pptx/side_parts/legacy_comments.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("duplicated.pptx");
    let original = inspect_package(source).unwrap();

    let summary = duplicate_slide(source, &out, "ppt/slides/slide1.xml").unwrap();
    let rewritten = inspect_package(&out).unwrap();
    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide2.xml.rels");

    assert_eq!(summary.slide_part, "ppt/slides/slide2.xml");
    assert_eq!(summary.slide_count, 2);
    assert!(duplicate_rels.contains("../comments/comment2.xml"));
    assert_eq!(rewritten.parts.len(), original.parts.len() + 3);
    for part in &original.parts {
        assert!(
            part.name == "[Content_Types].xml"
                || part.name == "ppt/_rels/presentation.xml.rels"
                || part.name == "ppt/presentation.xml"
                || rewritten.parts.contains(part),
            "missing original part {}",
            part.name
        );
    }
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/comments/comment2.xml"));
    assert!(rewritten
        .parts
        .iter()
        .any(|part| part.name == "ppt/commentAuthors.xml"));
}

#[test]
fn rejects_unsupported_relationships_without_copy_policy() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected = dir.path().join("injected.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&injected).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "ppt/slides/_rels/slide1.xml.rels" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Relationships>").unwrap();
                content.insert_str(
                    end,
                    r#"<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/unsupportedType" Target="../unsupported/part.xml"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.finish().unwrap();
    }

    let err = duplicate_slide(&injected, &out, "ppt/slides/slide1.xml").unwrap_err();

    assert!(err
        .to_string()
        .contains("cannot duplicate slide relationship type"));
    assert!(!out.exists());
}

#[test]
fn duplicates_slide_with_video_and_partnered_media_relationships() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected = dir.path().join("injected.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&injected).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "ppt/slides/_rels/slide1.xml.rels" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Relationships>").unwrap();
                content.insert_str(
                    end,
                    r#"<Relationship Id="rId10" Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/media1.mp4"/><Relationship Id="rId11" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/video" Target="../media/media1.mp4"/><Relationship Id="rId12" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else if name == "[Content_Types].xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Types>").unwrap();
                content.insert_str(
                    end,
                    r#"<Default Extension="mp4" ContentType="video/mp4"/><Default Extension="png" ContentType="image/png"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.start_file("ppt/media/media1.mp4", options).unwrap();
        std::io::copy(&mut Cursor::new(b"fake video payload"), &mut writer).unwrap();
        writer.start_file("ppt/media/image1.png", options).unwrap();
        std::io::copy(&mut Cursor::new(b"fake poster png payload"), &mut writer).unwrap();
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&injected, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide3.xml");
    assert_eq!(summary.slide_count, 3);

    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide3.xml.rels");
    assert!(duplicate_rels.contains(r#"Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/media1.mp4""#));
    assert!(duplicate_rels.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/video" Target="../media/media1.mp4""#));
    assert!(duplicate_rels.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png""#));

    let rewritten = inspect_package(&out).unwrap();
    assert!(rewritten.part_names().contains(&"ppt/media/media1.mp4"));
    assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
    assert!(!rewritten.part_names().contains(&"ppt/media/media2.mp4"));
    assert!(!rewritten.part_names().contains(&"ppt/media/image2.png"));

    let content_types = read_zip_text(&out, "[Content_Types].xml");
    assert!(content_types.contains(r#"<Default Extension="mp4" ContentType="video/mp4"/>"#));
    assert!(content_types.contains(r#"<Default Extension="png" ContentType="image/png"/>"#));
    assert!(!content_types.contains("/ppt/media/media1.mp4"));
}

#[test]
fn duplicates_slide_with_audio_relationship() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected = dir.path().join("injected.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&injected).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "ppt/slides/_rels/slide1.xml.rels" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Relationships>").unwrap();
                content.insert_str(
                    end,
                    r#"<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio" Target="../media/audio1.mp3"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else if name == "[Content_Types].xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Types>").unwrap();
                content.insert_str(
                    end,
                    r#"<Default Extension="mp3" ContentType="audio/mpeg"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.start_file("ppt/media/audio1.mp3", options).unwrap();
        std::io::copy(&mut Cursor::new(b"fake audio payload"), &mut writer).unwrap();
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&injected, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide3.xml");
    assert_eq!(summary.slide_count, 3);

    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide3.xml.rels");
    assert!(duplicate_rels.contains(r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio" Target="../media/audio1.mp3""#));

    let rewritten = inspect_package(&out).unwrap();
    assert!(rewritten.part_names().contains(&"ppt/media/audio1.mp3"));
    assert!(!rewritten.part_names().contains(&"ppt/media/audio2.mp3"));
}

#[test]
fn duplicates_slide_with_singular_comment_relationship() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected = dir.path().join("injected.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&injected).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "ppt/slides/_rels/slide1.xml.rels" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Relationships>").unwrap();
                content.insert_str(
                    end,
                    r#"<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comment" Target="../comments/comment1.xml"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else if name == "[Content_Types].xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Types>").unwrap();
                content.insert_str(
                    end,
                    r#"<Override PartName="/ppt/comments/comment1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer
            .start_file("ppt/comments/comment1.xml", options)
            .unwrap();
        std::io::copy(&mut Cursor::new(br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:cmLst xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cm authorId="0" dt="2026-05-13T00:00:00Z" idx="1"><p:pos x="0" y="0"/><p:text>Singular comment.</p:text></p:cm></p:cmLst>"#), &mut writer).unwrap();
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&injected, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide3.xml");
    assert_eq!(summary.slide_count, 3);

    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide3.xml.rels");
    assert!(duplicate_rels.contains("../comments/comment2.xml"));

    let rewritten = inspect_package(&out).unwrap();
    assert!(rewritten
        .part_names()
        .contains(&"ppt/comments/comment2.xml"));

    let content_types = read_zip_text(&out, "[Content_Types].xml");
    assert!(content_types.contains(r#"<Override PartName="/ppt/comments/comment2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>"#));
}

#[test]
fn duplicates_slide_with_external_hyperlink_relationship() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected = dir.path().join("injected.pptx");
    let out = dir.path().join("duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&injected).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "ppt/slides/_rels/slide1.xml.rels" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Relationships>").unwrap();
                content.insert_str(
                    end,
                    r#"<Relationship Id="rId20" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com" TargetMode="External"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else if name == "ppt/slides/slide1.xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</p:spTree>").unwrap();
                content.insert_str(
                    end,
                    r#"<p:sp><p:nvSpPr><p:cNvPr id="10" name="Link Shape"><a:hlinkClick r:id="rId20"/></p:cNvPr><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:p><a:r><a:t>Link</a:t></a:r></a:p></p:txBody></p:sp>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&injected, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide3.xml");
    assert_eq!(summary.slide_count, 3);

    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide3.xml.rels");
    assert!(duplicate_rels.contains(r#"Id="rId20""#));
    assert!(duplicate_rels.contains(
        r#"Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink""#
    ));
    assert!(duplicate_rels.contains(r#"Target="https://example.com""#));
    assert!(duplicate_rels.contains(r#"TargetMode="External""#));

    let duplicate_xml = read_zip_text(&out, "ppt/slides/slide3.xml");
    assert!(duplicate_xml.contains(r#"<a:hlinkClick r:id="rId20"/>"#));

    let rewritten = inspect_package(&out).unwrap();
    assert!(!rewritten.part_names().contains(&"https://example.com"));
    assert!(!rewritten.part_names().contains(&"example.com"));

    let presentation = summarize_presentation(&out).unwrap();
    assert_eq!(presentation.slides.len(), 3);
}

#[test]
fn duplicates_slide_with_mixed_external_image_and_comment_relationships() {
    let source = "../../fixtures/pptx/slides/two_slide_text.pptx";
    let dir = tempfile::tempdir().unwrap();
    let injected = dir.path().join("mixed_injected.pptx");
    let out = dir.path().join("mixed_duplicated.pptx");

    {
        let input = File::open(source).unwrap();
        let mut archive = ZipArchive::new(input).unwrap();
        let output = File::create(&injected).unwrap();
        let mut writer = zip::ZipWriter::new(output);
        let options = SimpleFileOptions::default();
        for i in 0..archive.len() {
            let mut file = archive.by_index(i).unwrap();
            let name = file.name().to_string();
            if name == "ppt/slides/_rels/slide1.xml.rels" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Relationships>").unwrap();
                content.insert_str(
                    end,
                    r#"<Relationship Id="rId20" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.org/docs" TargetMode="External"/><Relationship Id="rId21" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/><Relationship Id="rId22" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments/comment1.xml"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else if name == "ppt/slides/slide1.xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</p:spTree>").unwrap();
                content.insert_str(
                    end,
                    r#"<p:pic><p:nvPicPr><p:cNvPr id="20" name="Picture 1"><a:hlinkClick r:id="rId20"/></p:cNvPr><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId21"/></p:blipFill><p:spPr/></p:pic>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else if name == "[Content_Types].xml" {
                let mut content = String::new();
                file.read_to_string(&mut content).unwrap();
                let end = content.rfind("</Types>").unwrap();
                content.insert_str(
                    end,
                    r#"<Default Extension="png" ContentType="image/png"/><Override PartName="/ppt/comments/comment1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>"#,
                );
                writer.start_file(name, options).unwrap();
                std::io::copy(&mut Cursor::new(content.as_bytes()), &mut writer).unwrap();
            } else {
                writer.raw_copy_file(file).unwrap();
            }
        }
        writer.start_file("ppt/media/image1.png", options).unwrap();
        std::io::copy(&mut Cursor::new(b"fake image payload"), &mut writer).unwrap();
        writer
            .start_file("ppt/comments/comment1.xml", options)
            .unwrap();
        std::io::copy(&mut Cursor::new(br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:cmLst xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cm authorId="0" dt="2026-05-13T00:00:00Z" idx="1"><p:pos x="0" y="0"/><p:text>Comment</p:text></p:cm></p:cmLst>"#), &mut writer).unwrap();
        writer.finish().unwrap();
    }

    let summary = duplicate_slide(&injected, &out, "ppt/slides/slide1.xml").unwrap();
    assert_eq!(summary.slide_part, "ppt/slides/slide3.xml");
    assert_eq!(summary.slide_count, 3);

    let duplicate_rels = read_zip_text(&out, "ppt/slides/_rels/slide3.xml.rels");
    // External hyperlink passed through verbatim
    assert!(duplicate_rels.contains(r#"Id="rId20" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.org/docs" TargetMode="External""#));
    // Image shared
    assert!(duplicate_rels.contains(r#"Id="rId21" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png""#));
    // Comments copied with remapped target
    assert!(duplicate_rels.contains(r#"Id="rId22" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments/comment2.xml""#));

    let duplicate_xml = read_zip_text(&out, "ppt/slides/slide3.xml");
    assert!(duplicate_xml.contains(r#"<a:hlinkClick r:id="rId20"/>"#));
    assert!(duplicate_xml.contains(r#"<a:blip r:embed="rId21"/>"#));

    let rewritten = inspect_package(&out).unwrap();
    assert!(rewritten.part_names().contains(&"ppt/media/image1.png"));
    assert!(!rewritten.part_names().contains(&"ppt/media/image2.png"));
    assert!(rewritten
        .part_names()
        .contains(&"ppt/comments/comment1.xml"));
    assert!(rewritten
        .part_names()
        .contains(&"ppt/comments/comment2.xml"));

    let content_types = read_zip_text(&out, "[Content_Types].xml");
    assert!(content_types.contains(r#"<Override PartName="/ppt/comments/comment2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>"#));
}
