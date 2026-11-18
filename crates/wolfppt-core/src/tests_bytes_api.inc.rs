#[test]
fn edit_batch_bytes_output_is_byte_identical_to_path_output() {
    let dir = tempfile::tempdir().unwrap();
    let cases: [(&str, Vec<EditOperation>); 3] = [
        (
            "../../fixtures/pptx/text_basic/title_body_bullets.pptx",
            Vec::new(),
        ),
        (
            "../../fixtures/pptx/slides/two_slide_text.pptx",
            vec![
                EditOperation::ReorderSlides {
                    slide_indices: vec![1, 0],
                },
                EditOperation::SetShapeText {
                    slide_index: 0,
                    shape_index: 0,
                    replacement: "Bytes parity".to_string(),
                },
            ],
        ),
        (
            "../../fixtures/pptx/text_basic/title_body_bullets.pptx",
            vec![EditOperation::DeleteShape {
                slide_index: 0,
                shape_index: 1,
            }],
        ),
    ];
    for (index, (source, edits)) in cases.iter().enumerate() {
        let out = dir.path().join(format!("path-{index}.pptx"));
        let path_summary = apply_edit_batch(source, &out, edits).unwrap();
        let input = std::fs::read(source).unwrap();
        let bytes = apply_edit_batch_bytes(Cursor::new(&input), edits).unwrap();

        assert_eq!(bytes.bytes, std::fs::read(&out).unwrap(), "case {index}");
        assert_eq!(bytes.edits, path_summary.edits);
        assert_eq!(bytes.replacements, path_summary.replacements);
        assert_eq!(bytes.part_count, path_summary.part_count);
        assert_eq!(bytes.has_vba, path_summary.has_vba);
    }
}

#[test]
fn rejected_edit_batch_never_creates_the_output_file() {
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("rejected.pptx");
    let error = apply_edit_batch(
        "../../fixtures/pptx/text_basic/title_body_bullets.pptx",
        &out,
        &[EditOperation::SetShapeText {
            slide_index: 99,
            shape_index: 0,
            replacement: "missing".to_string(),
        }],
    )
    .unwrap_err();

    assert!(matches!(error, WolfPptError::InvalidInput(_)));
    assert!(!out.exists());
}

#[test]
fn presentation_summary_from_bytes_matches_path_summary() {
    let source = "../../fixtures/pptx/workloads/mixed_real_world_deck.pptx";
    let mut from_path = summarize_presentation(source).unwrap();
    let from_bytes =
        summarize_presentation_bytes(Cursor::new(std::fs::read(source).unwrap())).unwrap();

    assert_eq!(from_bytes.path, PathBuf::new());
    from_path.path = PathBuf::new();
    assert_eq!(from_bytes, from_path);
}
