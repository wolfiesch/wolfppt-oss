#[test]
fn test_table_row_insert_start_middle_end() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("row-inserts.pptx");

    let edits = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 0,
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 4,
        },
    ];

    let result = apply_edit_batch(source, &out, &edits).unwrap();
    assert_eq!(result.edits, 3);

    let summary = summarize_presentation(&out).unwrap();
    let table = &summary.slides[0].tables[0];
    assert_eq!(table.row_count, 5);
    assert_eq!(table.col_count, 2);
    assert_eq!(table.rows[0], vec!["".to_string(), "".to_string()]);
    assert_eq!(
        table.rows[1],
        vec!["Metric".to_string(), "Value".to_string()]
    );
    assert_eq!(table.rows[2], vec!["".to_string(), "".to_string()]);
    assert_eq!(table.rows[3], vec!["Slides".to_string(), "1".to_string()]);
    assert_eq!(table.rows[4], vec!["".to_string(), "".to_string()]);
}

#[test]
fn test_table_row_delete_single_and_multiple() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out1 = dir.path().join("row-insert-del.pptx");

    // Insert at 1, then delete at 1 -> should be back to original 2 rows
    let edits1 = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 1,
        },
        EditOperation::DeleteTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 1,
        },
    ];
    apply_edit_batch(source, &out1, &edits1).unwrap();
    let summary1 = summarize_presentation(&out1).unwrap();
    let table1 = &summary1.slides[0].tables[0];
    assert_eq!(table1.row_count, 2);
    assert_eq!(
        table1.rows[0],
        vec!["Metric".to_string(), "Value".to_string()]
    );
    assert_eq!(table1.rows[1], vec!["Slides".to_string(), "1".to_string()]);

    // Delete row 0 -> 1 row left
    let out2 = dir.path().join("row-del-first.pptx");
    let edits2 = vec![EditOperation::DeleteTableRow {
        slide_index: 0,
        table_index: 0,
        row_index: 0,
    }];
    apply_edit_batch(source, &out2, &edits2).unwrap();
    let summary2 = summarize_presentation(&out2).unwrap();
    let table2 = &summary2.slides[0].tables[0];
    assert_eq!(table2.row_count, 1);
    assert_eq!(table2.rows[0], vec!["Slides".to_string(), "1".to_string()]);
}

#[test]
fn test_table_column_insert_start_middle_end() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("col-inserts.pptx");

    let edits = vec![
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 0,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 4,
        },
    ];

    let result = apply_edit_batch(source, &out, &edits).unwrap();
    assert_eq!(result.edits, 3);

    let summary = summarize_presentation(&out).unwrap();
    let table = &summary.slides[0].tables[0];
    assert_eq!(table.row_count, 2);
    assert_eq!(table.col_count, 5);
    assert_eq!(
        table.rows[0],
        vec![
            "".to_string(),
            "Metric".to_string(),
            "".to_string(),
            "Value".to_string(),
            "".to_string(),
        ]
    );
    assert_eq!(
        table.rows[1],
        vec![
            "".to_string(),
            "Slides".to_string(),
            "".to_string(),
            "1".to_string(),
            "".to_string(),
        ]
    );
}

#[test]
fn test_table_column_delete_single_and_multiple() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out1 = dir.path().join("col-insert-del.pptx");

    // Insert at 1, then delete at 1 -> should be back to original 2 columns
    let edits1 = vec![
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 1,
        },
        EditOperation::DeleteTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 1,
        },
    ];
    apply_edit_batch(source, &out1, &edits1).unwrap();
    let summary1 = summarize_presentation(&out1).unwrap();
    let table1 = &summary1.slides[0].tables[0];
    assert_eq!(table1.col_count, 2);
    assert_eq!(
        table1.rows[0],
        vec!["Metric".to_string(), "Value".to_string()]
    );
    assert_eq!(table1.rows[1], vec!["Slides".to_string(), "1".to_string()]);

    // Delete col 0 -> 1 column left
    let out2 = dir.path().join("col-del-first.pptx");
    let edits2 = vec![EditOperation::DeleteTableColumn {
        slide_index: 0,
        table_index: 0,
        col_index: 0,
    }];
    apply_edit_batch(source, &out2, &edits2).unwrap();
    let summary2 = summarize_presentation(&out2).unwrap();
    let table2 = &summary2.slides[0].tables[0];
    assert_eq!(table2.col_count, 1);
    assert_eq!(table2.rows[0], vec!["Value".to_string()]);
    assert_eq!(table2.rows[1], vec!["1".to_string()]);
}

#[test]
fn test_table_delete_with_merged_cells_rejected() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out1 = dir.path().join("merge-del-row.pptx");

    let edits1 = vec![
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 0,
            col_min: 0,
            col_max: 1,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::DeleteTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 0,
        },
    ];
    let err1 = apply_edit_batch(source, &out1, &edits1).unwrap_err();
    assert!(err1.to_string().contains("merged"));

    let out2 = dir.path().join("merge-del-col.pptx");
    let edits2 = vec![
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 0,
            col_min: 0,
            col_max: 1,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::DeleteTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 0,
        },
    ];
    let err2 = apply_edit_batch(source, &out2, &edits2).unwrap_err();
    assert!(err2.to_string().contains("merged"));
}

#[test]
fn test_table_delete_sole_row_or_col_rejected() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out1 = dir.path().join("del-sole-row.pptx");

    let edits1 = vec![
        EditOperation::DeleteTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 0,
        },
        EditOperation::DeleteTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 0,
        },
    ];
    let err1 = apply_edit_batch(source, &out1, &edits1).unwrap_err();
    assert!(err1.to_string().contains("only row"));

    let out2 = dir.path().join("del-sole-col.pptx");
    let edits2 = vec![
        EditOperation::DeleteTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 0,
        },
        EditOperation::DeleteTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 0,
        },
    ];
    let err2 = apply_edit_batch(source, &out2, &edits2).unwrap_err();
    assert!(err2.to_string().contains("only column"));
}

#[test]
fn test_table_row_insert_through_vertical_merge_rejected() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();

    let out1 = dir.path().join("reject-row-1.pptx");
    let edits1 = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 2,
            col_min: 0,
            col_max: 0,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 1,
        },
    ];
    let err1 = apply_edit_batch(source, &out1, &edits1).unwrap_err();
    assert!(err1
        .to_string()
        .contains("cannot insert row 1 through merged cells"));

    let out2 = dir.path().join("reject-row-2.pptx");
    let edits2 = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 2,
            col_min: 0,
            col_max: 0,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
    ];
    let err2 = apply_edit_batch(source, &out2, &edits2).unwrap_err();
    assert!(err2
        .to_string()
        .contains("cannot insert row 2 through merged cells"));
}

#[test]
fn test_table_row_insert_at_vertical_merge_boundaries_valid() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("row-merge-boundaries.pptx");

    let edits = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 1,
            row_max: 2,
            col_min: 0,
            col_max: 0,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        // Boundary insert before merge origin (row 1)
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 1,
        },
        // Boundary insert after merge end (now at row 4)
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 4,
        },
        // Insert before merge at start
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 0,
        },
    ];
    apply_edit_batch(source, &out, &edits).unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let table = &summary.slides[0].tables[0];
    assert_eq!(table.row_count, 6);
}

#[test]
fn test_table_column_insert_through_horizontal_merge_rejected() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();

    let out1 = dir.path().join("reject-col-1.pptx");
    let edits1 = vec![
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 0,
            col_min: 0,
            col_max: 2,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 1,
        },
    ];
    let err1 = apply_edit_batch(source, &out1, &edits1).unwrap_err();
    assert!(err1
        .to_string()
        .contains("cannot insert column 1 through merged cells"));

    let out2 = dir.path().join("reject-col-2.pptx");
    let edits2 = vec![
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 0,
            col_min: 0,
            col_max: 2,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
    ];
    let err2 = apply_edit_batch(source, &out2, &edits2).unwrap_err();
    assert!(err2
        .to_string()
        .contains("cannot insert column 2 through merged cells"));
}

#[test]
fn test_table_column_insert_at_horizontal_merge_boundaries_valid() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();
    let out = dir.path().join("col-merge-boundaries.pptx");

    let edits = vec![
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 0,
            col_min: 1,
            col_max: 2,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        // Boundary insert before merge origin (col 1)
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 1,
        },
        // Boundary insert after merge end (now at col 4)
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 4,
        },
        // Insert before merge at start
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 0,
        },
    ];
    apply_edit_batch(source, &out, &edits).unwrap();
    let summary = summarize_presentation(&out).unwrap();
    let table = &summary.slides[0].tables[0];
    assert_eq!(table.col_count, 6);
}

#[test]
fn test_table_cross_axis_insert_allowed() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();

    // Horizontal merge on row 0; insert row at 1 should succeed
    let out1 = dir.path().join("cross-axis-row.pptx");
    let edits1 = vec![
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 0,
            col_min: 0,
            col_max: 1,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 1,
        },
    ];
    apply_edit_batch(source, &out1, &edits1).unwrap();
    let summary1 = summarize_presentation(&out1).unwrap();
    assert_eq!(summary1.slides[0].tables[0].row_count, 3);

    // Vertical merge on col 0; insert column at 1 should succeed
    let out2 = dir.path().join("cross-axis-col.pptx");
    let edits2 = vec![
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 0,
            row_max: 1,
            col_min: 0,
            col_max: 0,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged".to_string()],
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 1,
        },
    ];
    apply_edit_batch(source, &out2, &edits2).unwrap();
    let summary2 = summarize_presentation(&out2).unwrap();
    assert_eq!(summary2.slides[0].tables[0].col_count, 3);
}

#[test]
fn test_table_2d_merge_insert_guards_and_boundaries() {
    let source = "../../fixtures/pptx/tables/simple_table.pptx";
    let dir = tempfile::tempdir().unwrap();

    // Reject row insert at 2
    let out1 = dir.path().join("reject-2d-row.pptx");
    let edits1 = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 1,
            row_max: 2,
            col_min: 1,
            col_max: 2,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged2D".to_string()],
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
    ];
    let err1 = apply_edit_batch(source, &out1, &edits1).unwrap_err();
    assert!(err1
        .to_string()
        .contains("cannot insert row 2 through merged cells"));

    // Reject col insert at 2
    let out2 = dir.path().join("reject-2d-col.pptx");
    let edits2 = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 1,
            row_max: 2,
            col_min: 1,
            col_max: 2,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged2D".to_string()],
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
    ];
    let err2 = apply_edit_batch(source, &out2, &edits2).unwrap_err();
    assert!(err2
        .to_string()
        .contains("cannot insert column 2 through merged cells"));

    // Boundary inserts at 1 and 0 succeed
    let out3 = dir.path().join("boundaries-2d.pptx");
    let edits3 = vec![
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 2,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 2,
        },
        EditOperation::SetTableCellMerge {
            slide_index: 0,
            table_index: 0,
            row_min: 1,
            row_max: 2,
            col_min: 1,
            col_max: 2,
            kind: "merge".to_string(),
            paragraphs: vec!["Merged2D".to_string()],
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 1,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 1,
        },
        EditOperation::InsertTableRow {
            slide_index: 0,
            table_index: 0,
            row_index: 0,
        },
        EditOperation::InsertTableColumn {
            slide_index: 0,
            table_index: 0,
            col_index: 0,
        },
    ];
    apply_edit_batch(source, &out3, &edits3).unwrap();
    let summary3 = summarize_presentation(&out3).unwrap();
    assert_eq!(summary3.slides[0].tables[0].row_count, 5);
    assert_eq!(summary3.slides[0].tables[0].col_count, 5);
}
