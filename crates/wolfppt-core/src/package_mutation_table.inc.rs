#[allow(clippy::too_many_arguments)]
pub fn add_slide_table(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
) -> Result<TableAddSummary, WolfPptError> {
    add_slide_table_impl(
        input_path,
        output_path,
        slide_index,
        rows,
        cols,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        &[],
    )
}
pub fn add_slide_table_with_cell_texts(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    cell_texts: &[(usize, usize, String)],
) -> Result<TableAddSummary, WolfPptError> {
    add_slide_table_impl(
        input_path,
        output_path,
        slide_index,
        rows,
        cols,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        cell_texts,
    )
}
fn add_slide_table_impl(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    rows: usize,
    cols: usize,
    x_emu: u64,
    y_emu: u64,
    cx_emu: u64,
    cy_emu: u64,
    cell_texts: &[(usize, usize, String)],
) -> Result<TableAddSummary, WolfPptError> {
    if rows == 0 || cols == 0 {
        return Err(WolfPptError::InvalidInput(
            "table rows and columns must be greater than zero".to_string(),
        ));
    }
    for (row_index, col_index, _text) in cell_texts {
        if *row_index >= rows || *col_index >= cols {
            return Err(WolfPptError::InvalidInput(format!(
                "table cell {row_index},{col_index} is outside {rows}x{cols} table"
            )));
        }
    }
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let mut slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let table_index = extract_tables(slide_xml.as_bytes()).len();
    let shape_id = max_cnvpr_id(&slide_xml) + 1;
    slide_xml = add_table_to_slide_xml(
        &slide_xml, shape_id, rows, cols, x_emu, y_emu, cx_emu, cy_emu, cell_texts,
    )?;

    let (part_count, has_vba) = write_package_with_replaced_part(
        &mut archive,
        output_path,
        &slide_part,
        slide_xml.as_bytes(),
    )?;
    Ok(TableAddSummary {
        path: output_path.to_path_buf(),
        slide_index,
        slide_part,
        table_index,
        shape_id,
        rows,
        cols,
        part_count,
        has_vba,
    })
}

pub fn insert_table_row(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    table_index: usize,
    row_index: usize,
) -> Result<TableMutationSummary, WolfPptError> {
    mutate_table_in_package(input_path, output_path, slide_index, table_index, |xml| {
        insert_table_row_in_slide(xml, table_index, row_index)
    })
}

pub fn delete_table_row(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    table_index: usize,
    row_index: usize,
) -> Result<TableMutationSummary, WolfPptError> {
    mutate_table_in_package(input_path, output_path, slide_index, table_index, |xml| {
        delete_table_row_in_slide(xml, table_index, row_index)
    })
}

pub fn insert_table_column(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    table_index: usize,
    col_index: usize,
) -> Result<TableMutationSummary, WolfPptError> {
    mutate_table_in_package(input_path, output_path, slide_index, table_index, |xml| {
        insert_table_column_in_slide(xml, table_index, col_index)
    })
}

pub fn delete_table_column(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    table_index: usize,
    col_index: usize,
) -> Result<TableMutationSummary, WolfPptError> {
    mutate_table_in_package(input_path, output_path, slide_index, table_index, |xml| {
        delete_table_column_in_slide(xml, table_index, col_index)
    })
}

fn mutate_table_in_package(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    table_index: usize,
    mutation: impl FnOnce(&[u8]) -> Result<(Vec<u8>, usize), WolfPptError>,
) -> Result<TableMutationSummary, WolfPptError> {
    let input_path = input_path.as_ref();
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let input = File::open(input_path)?;
    let mut archive = ZipArchive::new(input)?;
    let Some(slide_part) = slide_part_at_index(&mut archive, slide_index)? else {
        return Err(WolfPptError::InvalidInput(format!(
            "slide index {slide_index} was not found"
        )));
    };
    let slide_xml = read_archive_text(&mut archive, &slide_part)?.ok_or_else(|| {
        WolfPptError::InvalidInput(format!("slide part {slide_part} was not found"))
    })?;
    let (rewritten, _count) = mutation(slide_xml.as_bytes())?;
    let (part_count, has_vba) =
        write_package_with_replaced_part(&mut archive, output_path, &slide_part, &rewritten)?;
    Ok(TableMutationSummary {
        path: output_path.to_path_buf(),
        slide_index,
        table_index,
        part_count,
        has_vba,
    })
}

struct TableInspection {
    col_count: usize,
    col_widths: Vec<u64>,
    row_count: usize,
    row_heights: Vec<u64>,
    cells: Vec<Vec<CellMergeFlags>>,
}

struct CellMergeFlags {
    row_span: usize,
    v_merge: bool,
    grid_span: usize,
    h_merge: bool,
}

fn extract_u64_attr(event: &BytesStart, attr_name: &[u8]) -> Option<u64> {
    for attr in event.attributes().flatten() {
        if attr.key.as_ref() == attr_name {
            if let Ok(value_str) = std::str::from_utf8(&attr.value) {
                return value_str.parse().ok();
            }
        }
    }
    None
}

fn extract_cell_merge_flags(event: &BytesStart) -> CellMergeFlags {
    let mut row_span = 1;
    let mut v_merge = false;
    let mut grid_span = 1;
    let mut h_merge = false;
    for attr in event.attributes().flatten() {
        match attr.key.as_ref() {
            b"rowSpan" => {
                if let Ok(s) = std::str::from_utf8(&attr.value) {
                    row_span = s.parse().unwrap_or(1);
                }
            }
            b"vMerge" => {
                if let Ok(s) = std::str::from_utf8(&attr.value) {
                    v_merge = s == "1" || s == "true";
                }
            }
            b"gridSpan" => {
                if let Ok(s) = std::str::from_utf8(&attr.value) {
                    grid_span = s.parse().unwrap_or(1);
                }
            }
            b"hMerge" => {
                if let Ok(s) = std::str::from_utf8(&attr.value) {
                    h_merge = s == "1" || s == "true";
                }
            }
            _ => {}
        }
    }
    CellMergeFlags {
        row_span,
        v_merge,
        grid_span,
        h_merge,
    }
}

fn inspect_slide_table(
    xml: &[u8],
    target_table_index: usize,
) -> Result<TableInspection, WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut table_index = 0;
    let mut in_target_table = false;
    let mut in_grid = false;
    let mut in_row = false;
    let mut col_widths = Vec::new();
    let mut row_heights = Vec::new();
    let mut rows: Vec<Vec<CellMergeFlags>> = Vec::new();
    let mut current_row_cells: Vec<CellMergeFlags> = Vec::new();
    let mut found = false;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    if table_index == target_table_index {
                        in_target_table = true;
                        found = true;
                    }
                    table_index += 1;
                } else if in_target_table && name == b"tblGrid" {
                    in_grid = true;
                } else if in_target_table && in_grid && name == b"gridCol" {
                    let w = extract_u64_attr(&event, b"w").unwrap_or(0);
                    col_widths.push(w);
                } else if in_target_table && name == b"tr" {
                    in_row = true;
                    current_row_cells.clear();
                    let h = extract_u64_attr(&event, b"h").unwrap_or(0);
                    row_heights.push(h);
                } else if in_target_table && in_row && name == b"tc" {
                    current_row_cells.push(extract_cell_merge_flags(&event));
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && in_grid && name == b"gridCol" {
                    let w = extract_u64_attr(&event, b"w").unwrap_or(0);
                    col_widths.push(w);
                } else if in_target_table && in_row && name == b"tc" {
                    current_row_cells.push(extract_cell_merge_flags(&event));
                }
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && name == b"tblGrid" {
                    in_grid = false;
                } else if in_target_table && name == b"tr" {
                    in_row = false;
                    rows.push(std::mem::take(&mut current_row_cells));
                } else if in_target_table && name == b"tbl" {
                    break;
                }
            }
            Event::Eof => break,
            _ => {}
        }
    }

    if !found {
        return Err(WolfPptError::InvalidInput(format!(
            "table index {target_table_index} was not found"
        )));
    }

    let col_count = col_widths.len();
    let row_count = row_heights.len();
    Ok(TableInspection {
        col_count,
        col_widths,
        row_count,
        row_heights,
        cells: rows,
    })
}

fn row_insertion_intersects_merge(info: &TableInspection, row_index: usize) -> bool {
    info.cells.iter().enumerate().any(|(origin_row, row)| {
        row.iter().any(|cell| {
            (cell.row_span > 1
                && origin_row < row_index
                && row_index < origin_row.saturating_add(cell.row_span))
                || (origin_row == row_index && cell.v_merge)
        })
    })
}

fn column_insertion_intersects_merge(info: &TableInspection, col_index: usize) -> bool {
    info.cells.iter().any(|row| {
        row.iter().enumerate().any(|(origin_col, cell)| {
            (cell.grid_span > 1
                && origin_col < col_index
                && col_index < origin_col.saturating_add(cell.grid_span))
                || (origin_col == col_index && cell.h_merge)
        })
    })
}

fn write_empty_table_cell(writer: &mut Writer<Vec<u8>>) -> Result<(), WolfPptError> {
    writer.write_event(Event::Start(BytesStart::new("a:tc")))?;
    writer.write_event(Event::Start(BytesStart::new("a:txBody")))?;
    writer.write_event(Event::Empty(BytesStart::new("a:bodyPr")))?;
    writer.write_event(Event::Empty(BytesStart::new("a:lstStyle")))?;
    writer.write_event(Event::Start(BytesStart::new("a:p")))?;
    writer.write_event(Event::Start(BytesStart::new("a:r")))?;
    writer.write_event(Event::Start(BytesStart::new("a:t")))?;
    writer.write_event(Event::Text(BytesText::new("")))?;
    writer.write_event(Event::End(BytesEnd::new("a:t")))?;
    writer.write_event(Event::End(BytesEnd::new("a:r")))?;
    writer.write_event(Event::End(BytesEnd::new("a:p")))?;
    writer.write_event(Event::End(BytesEnd::new("a:txBody")))?;
    writer.write_event(Event::Empty(BytesStart::new("a:tcPr")))?;
    writer.write_event(Event::End(BytesEnd::new("a:tc")))?;
    Ok(())
}

fn write_empty_table_row(
    writer: &mut Writer<Vec<u8>>,
    height: u64,
    col_count: usize,
) -> Result<(), WolfPptError> {
    let mut tr = BytesStart::new("a:tr");
    let h_str = height.to_string();
    tr.push_attribute(("h", h_str.as_str()));
    writer.write_event(Event::Start(tr))?;
    for _ in 0..col_count {
        write_empty_table_cell(writer)?;
    }
    writer.write_event(Event::End(BytesEnd::new("a:tr")))?;
    Ok(())
}

fn write_grid_column(writer: &mut Writer<Vec<u8>>, width: u64) -> Result<(), WolfPptError> {
    let mut col = BytesStart::new("a:gridCol");
    let w_str = width.to_string();
    col.push_attribute(("w", w_str.as_str()));
    writer.write_event(Event::Empty(col))?;
    Ok(())
}

fn insert_table_row_in_slide(
    xml: &[u8],
    target_table_index: usize,
    target_row_index: usize,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let info = inspect_slide_table(xml, target_table_index)?;
    if target_row_index > info.row_count {
        return Err(WolfPptError::InvalidInput(format!(
            "table row index {target_row_index} out of range (table has {} rows)",
            info.row_count
        )));
    }
    if row_insertion_intersects_merge(&info, target_row_index) {
        return Err(WolfPptError::InvalidInput(format!(
            "cannot insert row {target_row_index} through merged cells"
        )));
    }
    let height = if target_row_index > 0 && target_row_index - 1 < info.row_heights.len() {
        info.row_heights[target_row_index - 1]
    } else if !info.row_heights.is_empty() {
        info.row_heights[0]
    } else {
        370840
    };
    let col_count = info.col_count;

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len() + 1024));
    let mut table_index = 0;
    let mut in_target_table = false;
    let mut current_row = 0;
    let mut wrote_new_row = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    if table_index == target_table_index {
                        in_target_table = true;
                    }
                    table_index += 1;
                } else if in_target_table && name == b"tr" {
                    if current_row == target_row_index && !wrote_new_row {
                        write_empty_table_row(&mut writer, height, col_count)?;
                        wrote_new_row = true;
                        replacements += 1;
                    }
                    current_row += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && name == b"tbl" {
                    if !wrote_new_row && current_row == target_row_index {
                        write_empty_table_row(&mut writer, height, col_count)?;
                        wrote_new_row = true;
                        replacements += 1;
                    }
                    in_target_table = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }
    Ok((writer.into_inner(), replacements))
}

fn delete_table_row_in_slide(
    xml: &[u8],
    target_table_index: usize,
    target_row_index: usize,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let info = inspect_slide_table(xml, target_table_index)?;
    if info.row_count <= 1 {
        return Err(WolfPptError::InvalidInput(
            "cannot delete the only row of a table".to_string(),
        ));
    }
    if target_row_index >= info.row_count {
        return Err(WolfPptError::InvalidInput(format!(
            "table row index {target_row_index} out of range (table has {} rows)",
            info.row_count
        )));
    }
    if let Some(row_cells) = info.cells.get(target_row_index) {
        for cell in row_cells {
            if cell.row_span > 1 || cell.v_merge || cell.grid_span > 1 || cell.h_merge {
                return Err(WolfPptError::InvalidInput(format!(
                    "cannot delete row {target_row_index} because it contains merged cells"
                )));
            }
        }
    }

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut table_index = 0;
    let mut in_target_table = false;
    let mut current_row = 0;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    if table_index == target_table_index {
                        in_target_table = true;
                    }
                    table_index += 1;
                    writer.write_event(Event::Start(event))?;
                } else if in_target_table && name == b"tr" {
                    if current_row == target_row_index {
                        skip_current_element(&mut reader)?;
                        current_row += 1;
                        replacements += 1;
                        continue;
                    }
                    current_row += 1;
                    writer.write_event(Event::Start(event))?;
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && name == b"tr" {
                    if current_row == target_row_index {
                        current_row += 1;
                        replacements += 1;
                        continue;
                    }
                    current_row += 1;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && name == b"tbl" {
                    in_target_table = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }
    Ok((writer.into_inner(), replacements))
}

fn insert_table_column_in_slide(
    xml: &[u8],
    target_table_index: usize,
    target_col_index: usize,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let info = inspect_slide_table(xml, target_table_index)?;
    if target_col_index > info.col_count {
        return Err(WolfPptError::InvalidInput(format!(
            "table column index {target_col_index} out of range (table has {} columns)",
            info.col_count
        )));
    }
    if column_insertion_intersects_merge(&info, target_col_index) {
        return Err(WolfPptError::InvalidInput(format!(
            "cannot insert column {target_col_index} through merged cells"
        )));
    }
    let width = if target_col_index > 0 && target_col_index - 1 < info.col_widths.len() {
        info.col_widths[target_col_index - 1]
    } else if !info.col_widths.is_empty() {
        info.col_widths[0]
    } else {
        2743200
    };

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len() + 1024));
    let mut table_index = 0;
    let mut in_target_table = false;
    let mut in_grid = false;
    let mut in_row = false;
    let mut grid_col_index = 0;
    let mut wrote_grid_col = false;
    let mut current_col = 0;
    let mut wrote_cell = false;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    if table_index == target_table_index {
                        in_target_table = true;
                    }
                    table_index += 1;
                } else if in_target_table && name == b"tblGrid" {
                    in_grid = true;
                    grid_col_index = 0;
                    wrote_grid_col = false;
                } else if in_target_table && in_grid && name == b"gridCol" {
                    if grid_col_index == target_col_index && !wrote_grid_col {
                        write_grid_column(&mut writer, width)?;
                        wrote_grid_col = true;
                        replacements += 1;
                    }
                    grid_col_index += 1;
                } else if in_target_table && name == b"tr" {
                    in_row = true;
                    current_col = 0;
                    wrote_cell = false;
                } else if in_target_table && in_row && name == b"tc" {
                    if current_col == target_col_index && !wrote_cell {
                        write_empty_table_cell(&mut writer)?;
                        wrote_cell = true;
                        replacements += 1;
                    }
                    current_col += 1;
                }
                writer.write_event(Event::Start(event))?;
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && in_grid && name == b"gridCol" {
                    if grid_col_index == target_col_index && !wrote_grid_col {
                        write_grid_column(&mut writer, width)?;
                        wrote_grid_col = true;
                        replacements += 1;
                    }
                    grid_col_index += 1;
                } else if in_target_table && in_row && name == b"tc" {
                    if current_col == target_col_index && !wrote_cell {
                        write_empty_table_cell(&mut writer)?;
                        wrote_cell = true;
                        replacements += 1;
                    }
                    current_col += 1;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && in_grid && name == b"tblGrid" {
                    if !wrote_grid_col && grid_col_index == target_col_index {
                        write_grid_column(&mut writer, width)?;
                        wrote_grid_col = true;
                        replacements += 1;
                    }
                    in_grid = false;
                } else if in_target_table && in_row && name == b"tr" {
                    if !wrote_cell && current_col == target_col_index {
                        write_empty_table_cell(&mut writer)?;
                        wrote_cell = true;
                        replacements += 1;
                    }
                    in_row = false;
                } else if in_target_table && name == b"tbl" {
                    in_target_table = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }
    Ok((writer.into_inner(), replacements))
}

fn delete_table_column_in_slide(
    xml: &[u8],
    target_table_index: usize,
    target_col_index: usize,
) -> Result<(Vec<u8>, usize), WolfPptError> {
    let info = inspect_slide_table(xml, target_table_index)?;
    if info.col_count <= 1 {
        return Err(WolfPptError::InvalidInput(
            "cannot delete the only column of a table".to_string(),
        ));
    }
    if target_col_index >= info.col_count {
        return Err(WolfPptError::InvalidInput(format!(
            "table column index {target_col_index} out of range (table has {} columns)",
            info.col_count
        )));
    }
    for (row_idx, row_cells) in info.cells.iter().enumerate() {
        if let Some(cell) = row_cells.get(target_col_index) {
            if cell.grid_span > 1 || cell.h_merge || cell.row_span > 1 || cell.v_merge {
                return Err(WolfPptError::InvalidInput(format!(
                    "cannot delete column {target_col_index} because it contains merged cells at row {row_idx}"
                )));
            }
        }
    }

    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    let mut table_index = 0;
    let mut in_target_table = false;
    let mut in_grid = false;
    let mut in_row = false;
    let mut grid_col_index = 0;
    let mut current_col = 0;
    let mut replacements = 0;

    loop {
        match reader.read_event()? {
            Event::Start(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if name == b"tbl" {
                    if table_index == target_table_index {
                        in_target_table = true;
                    }
                    table_index += 1;
                    writer.write_event(Event::Start(event))?;
                } else if in_target_table && name == b"tblGrid" {
                    in_grid = true;
                    grid_col_index = 0;
                    writer.write_event(Event::Start(event))?;
                } else if in_target_table && in_grid && name == b"gridCol" {
                    if grid_col_index == target_col_index {
                        skip_current_element(&mut reader)?;
                        grid_col_index += 1;
                        replacements += 1;
                        continue;
                    }
                    grid_col_index += 1;
                    writer.write_event(Event::Start(event))?;
                } else if in_target_table && name == b"tr" {
                    in_row = true;
                    current_col = 0;
                    writer.write_event(Event::Start(event))?;
                } else if in_target_table && in_row && name == b"tc" {
                    if current_col == target_col_index {
                        skip_current_element(&mut reader)?;
                        current_col += 1;
                        replacements += 1;
                        continue;
                    }
                    current_col += 1;
                    writer.write_event(Event::Start(event))?;
                } else {
                    writer.write_event(Event::Start(event))?;
                }
            }
            Event::Empty(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && in_grid && name == b"gridCol" {
                    if grid_col_index == target_col_index {
                        grid_col_index += 1;
                        replacements += 1;
                        continue;
                    }
                    grid_col_index += 1;
                } else if in_target_table && in_row && name == b"tc" {
                    if current_col == target_col_index {
                        current_col += 1;
                        replacements += 1;
                        continue;
                    }
                    current_col += 1;
                }
                writer.write_event(Event::Empty(event))?;
            }
            Event::End(event) => {
                let name = local_name(event.name().as_ref()).to_vec();
                if in_target_table && in_grid && name == b"tblGrid" {
                    in_grid = false;
                } else if in_target_table && in_row && name == b"tr" {
                    in_row = false;
                } else if in_target_table && name == b"tbl" {
                    in_target_table = false;
                }
                writer.write_event(Event::End(event))?;
            }
            Event::Eof => break,
            event => writer.write_event(event)?,
        }
    }
    Ok((writer.into_inner(), replacements))
}
