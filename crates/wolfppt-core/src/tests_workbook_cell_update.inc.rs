    const WORKBOOK_ROOT_RELS: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>"#;

    fn workbook_package(
        sheet_xml: &str,
        shared_strings_xml: Option<&str>,
        prefix: &str,
    ) -> Vec<u8> {
        let ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
        let declaration = if prefix.is_empty() {
            format!(r#"xmlns="{ns}""#)
        } else {
            format!(r#"xmlns:{}="{ns}""#, prefix.trim_end_matches(':'))
        };
        let workbook = format!(
            r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><{prefix}workbook {declaration} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><{prefix}sheets><{prefix}sheet name="Notes &amp; Data" sheetId="1" r:id="rId9"/><{prefix}sheet name="Sheet1" sheetId="2" r:id="rId1"/></{prefix}sheets></{prefix}workbook>"#
        );
        let mut workbook_rels = String::from(
            r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/notes.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>"#,
        );
        if shared_strings_xml.is_some() {
            workbook_rels.push_str(r#"<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>"#);
        }
        workbook_rels.push_str("</Relationships>");

        let mut writer = zip::ZipWriter::new(Cursor::new(Vec::new()));
        let mut add = |name: &str, payload: &str| {
            writer
                .start_file(name, SimpleFileOptions::default())
                .unwrap();
            std::io::Write::write_all(&mut writer, payload.as_bytes()).unwrap();
        };
        add("[Content_Types].xml", "<Types/>");
        add("_rels/.rels", WORKBOOK_ROOT_RELS);
        add("xl/workbook.xml", &workbook);
        add("xl/_rels/workbook.xml.rels", &workbook_rels);
        add("xl/styles.xml", "<styleSheet>custom styles</styleSheet>");
        add("xl/worksheets/notes.xml", "<worksheet>untouched</worksheet>");
        add("xl/worksheets/sheet1.xml", sheet_xml);
        if let Some(shared) = shared_strings_xml {
            add("xl/sharedStrings.xml", shared);
        }
        writer.finish().unwrap().into_inner()
    }

    fn package_part(package: &[u8], name: &str) -> String {
        let mut archive = ZipArchive::new(Cursor::new(package)).unwrap();
        let mut part = archive.by_name(name).unwrap();
        let mut payload = String::new();
        part.read_to_string(&mut payload).unwrap();
        payload
    }

    fn number(reference: &str, value: &str) -> WorkbookCellUpdate {
        WorkbookCellUpdate {
            reference: reference.to_string(),
            value: WorkbookCellValue::Number(value.to_string()),
        }
    }

    fn text(reference: &str, value: &str) -> WorkbookCellUpdate {
        WorkbookCellUpdate {
            reference: reference.to_string(),
            value: WorkbookCellValue::Text(value.to_string()),
        }
    }

    #[test]
    fn updates_workbook_cells_in_place_keeping_styles_and_other_parts() {
        let sheet = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac" mc:Ignorable="x14ac"><dimension ref="A1:D3"/><cols><col min="1" max="1" width="10.7" customWidth="1"/></cols><sheetData><row r="1" spans="1:2" x14ac:dyDescent="0.25"><c r="B1" s="2" t="s"><v>0</v></c></row><row r="2" spans="1:2"><c r="A2" s="1" t="s"><v>1</v></c><c r="B2" s="1"><v>10</v></c></row><row r="3" spans="1:2 4:4"><c r="A3" s="1" t="s"><v>2</v></c><c r="B3" s="1"><v>20</v></c><c r="D3" s="3"><v>99</v></c></row></sheetData><pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/></worksheet>"#;
        let shared = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3"><si><t>Revenue</t></si><si><t>North</t></si><si><r><t>Sou</t></r><r><t>th</t></r></si></sst>"#;
        let package = workbook_package(sheet, Some(shared), "");

        let updated = update_workbook_cells(
            &package,
            "Sheet1",
            &[
                text("B1", "Revenue"),
                text("A2", "East & West"),
                number("B2", "42"),
                text("A3", "South"),
                number("B3", "84.5"),
                text("A4", "North"),
                number("B4", "126"),
                number("C3", "7"),
            ],
        )
        .unwrap();

        let sheet = package_part(&updated, "xl/worksheets/sheet1.xml");
        assert!(sheet.contains(r#"mc:Ignorable="x14ac""#));
        assert!(sheet.contains(r#"<dimension ref="A1:D4"/>"#));
        assert!(sheet.contains(r#"<col min="1" max="1" width="10.7" customWidth="1"/>"#));
        assert!(sheet.contains(
            r#"<row r="1" spans="1:2" x14ac:dyDescent="0.25"><c r="B1" s="2" t="s"><v>0</v></c></row>"#
        ));
        assert!(sheet.contains(
            r#"<row r="2" spans="1:2"><c r="A2" s="1" t="s"><v>3</v></c><c r="B2" s="1"><v>42</v></c></row>"#
        ));
        // The rich-text "South" item is not reused: a plain item is appended.
        assert!(sheet.contains(
            r#"<row r="3" spans="1:4"><c r="A3" s="1" t="s"><v>4</v></c><c r="B3" s="1"><v>84.5</v></c><c r="C3"><v>7</v></c><c r="D3" s="3"><v>99</v></c></row>"#
        ));
        assert!(sheet.contains(
            r#"<row r="4"><c r="A4" t="s"><v>1</v></c><c r="B4"><v>126</v></c></row></sheetData><pageMargins"#
        ));

        let shared = package_part(&updated, "xl/sharedStrings.xml");
        assert!(shared.contains(r#"count="4" uniqueCount="5""#));
        assert!(shared.ends_with(
            "<si><t>East &amp; West</t></si><si><t>South</t></si></sst>"
        ));

        for unchanged in ["xl/styles.xml", "xl/workbook.xml", "xl/worksheets/notes.xml"] {
            assert_eq!(
                package_part(&updated, unchanged),
                package_part(&package, unchanged)
            );
        }
    }

    #[test]
    fn updates_prefixed_workbook_without_shared_strings_inline() {
        let sheet = r#"<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:sheetData><x:row r="2"><x:c r="A2" s="4" t="inlineStr"><x:is><x:t>Old</x:t></x:is></x:c></x:row></x:sheetData></x:worksheet>"#;
        let package = workbook_package(sheet, None, "x:");

        let updated = update_workbook_cells(
            &package,
            "Sheet1",
            &[text("B1", " Name "), text("A2", "New"), number("B2", "1.5")],
        )
        .unwrap();

        assert_eq!(
            package_part(&updated, "xl/worksheets/sheet1.xml"),
            concat!(
                r#"<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:sheetData>"#,
                r#"<x:row r="1"><x:c r="B1" t="inlineStr"><x:is><x:t xml:space="preserve"> Name </x:t></x:is></x:c></x:row>"#,
                r#"<x:row r="2"><x:c r="A2" s="4" t="inlineStr"><x:is><x:t>New</x:t></x:is></x:c><x:c r="B2"><x:v>1.5</x:v></x:c></x:row>"#,
                r#"</x:sheetData></x:worksheet>"#
            )
        );
    }

    #[test]
    fn clears_existing_cells_keeping_style_and_never_adds_cleared_cells() {
        let sheet = r#"<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:B3"/><sheetData><row r="2"><c r="A2" s="1" t="s"><v>0</v></c><c r="B2" s="2"><v>10</v></c></row><row r="3"><c r="A3" t="s"><v>1</v></c><c r="B3"><v>20</v></c></row></sheetData></worksheet>"#;
        let shared = r#"<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2"><si><t>East</t></si><si><t>West</t></si></sst>"#;
        let package = workbook_package(sheet, Some(shared), "");
        let clear = |reference: &str| WorkbookCellUpdate {
            reference: reference.to_string(),
            value: WorkbookCellValue::Empty,
        };

        let updated = update_workbook_cells(
            &package,
            "Sheet1",
            &[number("B2", "5"), clear("A3"), clear("B3"), clear("D9")],
        )
        .unwrap();

        assert_eq!(
            package_part(&updated, "xl/worksheets/sheet1.xml"),
            concat!(
                r#"<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:B3"/><sheetData>"#,
                r#"<row r="2"><c r="A2" s="1" t="s"><v>0</v></c><c r="B2" s="2"><v>5</v></c></row>"#,
                r#"<row r="3"><c r="A3"/><c r="B3"/></row></sheetData></worksheet>"#
            )
        );
        assert!(package_part(&updated, "xl/sharedStrings.xml").contains(r#"count="1" uniqueCount="2""#));
    }

    #[test]
    fn refuses_workbook_updates_that_would_drop_formulas_or_miss_the_sheet() {
        let sheet = r#"<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="B2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>"#;
        let package = workbook_package(sheet, None, "");

        assert!(update_workbook_cells(&package, "Sheet1", &[number("B2", "5")]).is_err());
        assert!(update_workbook_cells(&package, "Missing", &[number("A1", "5")]).is_err());
        assert!(update_workbook_cells(&package, "Sheet1", &[number("A1", "NaN")]).is_err());
        assert!(update_workbook_cells(&package, "Sheet1", &[number("A1", "5")]).is_ok());
    }
