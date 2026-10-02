/// Write cell values into one worksheet of an XLSX package in place.
///
/// Every other part, cell, row, style reference and attribute is kept, and
/// untouched ZIP entries are copied without recompression. Updated cells keep
/// their style (`s`) and placement; missing rows and cells are inserted in
/// sheet order, and the sheet dimension and row spans grow to cover them.
/// Strings go to the shared string table when the workbook has one.
/// [`WorkbookCellValue::Empty`] clears an existing cell and never adds one.
///
/// Chart data replacement uses this to keep a chart's embedded workbook in
/// step with its caches without regenerating the workbook. A cell that holds
/// a formula is refused instead of being turned into a constant.
pub fn update_workbook_cells(
    xlsx: &[u8],
    sheet_name: &str,
    updates: &[WorkbookCellUpdate],
) -> Result<Vec<u8>, WolfPptError> {
    let mut cells = BTreeMap::new();
    let mut cleared = BTreeSet::new();
    for update in updates {
        let position = parse_cell_reference(&update.reference).ok_or_else(|| {
            WolfPptError::InvalidInput(format!("invalid cell reference: {}", update.reference))
        })?;
        if let WorkbookCellValue::Number(number) = &update.value {
            if !number.parse::<f64>().is_ok_and(f64::is_finite) {
                return Err(WolfPptError::InvalidInput(format!(
                    "cell {} value is not a finite number: {number}",
                    update.reference
                )));
            }
        }
        if matches!(update.value, WorkbookCellValue::Empty) {
            cells.remove(&position);
            cleared.insert(position);
        } else {
            cleared.remove(&position);
            cells.insert(position, &update.value);
        }
    }
    let cells: Vec<((u32, u32), &WorkbookCellValue)> = cells.into_iter().collect();

    let mut archive = ZipArchive::new(Cursor::new(xlsx))?;
    let workbook_part = read_relationships(&mut archive, "")?
        .into_iter()
        .find(|rel| rel.relationship_type.ends_with("/officeDocument"))
        .map(|rel| resolve_target("", &rel.target))
        .ok_or_else(|| WolfPptError::InvalidInput("workbook part is missing".to_string()))?;
    let workbook_xml = read_archive_bytes(&mut archive, &workbook_part)?
        .ok_or_else(|| WolfPptError::InvalidInput("workbook part is missing".to_string()))?;
    let sheet_relationship_id = workbook_sheet_relationship_id(&workbook_xml, sheet_name)?
        .ok_or_else(|| WolfPptError::InvalidInput(format!("sheet {sheet_name} was not found")))?;
    let workbook_relationships = read_relationships(&mut archive, &workbook_part)?;
    let sheet_part = workbook_relationships
        .iter()
        .find(|rel| rel.id == sheet_relationship_id)
        .map(|rel| resolve_target(&workbook_part, &rel.target))
        .ok_or_else(|| {
            WolfPptError::InvalidInput(format!("sheet {sheet_name} relationship is missing"))
        })?;
    let shared_strings_part = workbook_relationships
        .iter()
        .find(|rel| rel.relationship_type.ends_with("/sharedStrings"))
        .map(|rel| resolve_target(&workbook_part, &rel.target));

    let sheet_xml = read_archive_bytes(&mut archive, &sheet_part)?
        .ok_or_else(|| WolfPptError::InvalidInput(format!("sheet part {sheet_part} is missing")))?;
    let shared_strings_xml = match &shared_strings_part {
        Some(part) => read_archive_bytes(&mut archive, part)?,
        None => None,
    };
    let mut shared_strings = shared_strings_xml
        .as_deref()
        .map(SharedStringTable::parse)
        .transpose()?;

    let mut rewriter = WorksheetCellRewriter {
        writer: Writer::new(Vec::with_capacity(sheet_xml.len() + cells.len() * 32)),
        cells,
        cleared,
        next: 0,
        prefix: String::new(),
        shared_strings: shared_strings.as_mut(),
        string_refs_written: 0,
        string_refs_replaced: 0,
    };
    rewriter.rewrite(&sheet_xml)?;
    let string_refs_written = rewriter.string_refs_written;
    let string_refs_replaced = rewriter.string_refs_replaced;
    let mut replacements = BTreeMap::new();
    replacements.insert(sheet_part, rewriter.writer.into_inner());
    if let (Some(part), Some(xml), Some(table)) =
        (shared_strings_part, shared_strings_xml, shared_strings)
    {
        if !table.appended.is_empty() || string_refs_written != string_refs_replaced {
            let rewritten =
                table.rewrite(&xml, string_refs_written as i64 - string_refs_replaced as i64)?;
            replacements.insert(part, rewritten);
        }
    }

    let mut writer = zip::ZipWriter::new(Cursor::new(Vec::with_capacity(xlsx.len() + 1024)));
    for index in 0..archive.len() {
        let file = archive.by_index_raw(index)?;
        let Some(payload) = replacements.get(file.name()) else {
            writer.raw_copy_file(file)?;
            continue;
        };
        let mut options = SimpleFileOptions::default().compression_method(file.compression());
        if let Some(modified) = file.last_modified() {
            options = options.last_modified_time(modified);
        }
        let name = file.name().to_string();
        drop(file);
        writer.start_file(name, options)?;
        std::io::Write::write_all(&mut writer, payload)?;
    }
    Ok(writer.finish()?.into_inner())
}

/// Parse an A1 reference such as `B12` or `$B$12` into (row, column), both
/// one-based.
fn parse_cell_reference(reference: &str) -> Option<(u32, u32)> {
    let reference = reference.replace('$', "");
    let split = reference.find(|ch: char| ch.is_ascii_digit())?;
    let (letters, digits) = reference.split_at(split);
    if letters.is_empty() || letters.len() > 3 || !letters.bytes().all(|b| b.is_ascii_alphabetic())
    {
        return None;
    }
    let column = letters.bytes().fold(0u32, |value, byte| {
        value * 26 + u32::from(byte.to_ascii_uppercase() - b'A') + 1
    });
    let row = digits.parse::<u32>().ok().filter(|row| *row > 0)?;
    Some((row, column))
}

fn cell_reference(row: u32, column: u32) -> String {
    let mut letters = Vec::new();
    let mut remaining = column;
    while remaining > 0 {
        let digit = (remaining - 1) % 26;
        letters.push(b'A' + digit as u8);
        remaining = (remaining - 1) / 26;
    }
    letters.reverse();
    format!("{}{row}", String::from_utf8(letters).unwrap_or_default())
}

fn workbook_sheet_relationship_id(
    xml: &[u8],
    sheet_name: &str,
) -> Result<Option<String>, WolfPptError> {
    let mut reader = Reader::from_reader(xml);
    loop {
        match reader.read_event()? {
            Event::Start(event) | Event::Empty(event)
                if local_name(event.name().as_ref()) == b"sheet" =>
            {
                let mut name = None;
                let mut relationship_id = None;
                for attr in event.attributes().flatten() {
                    let key = attr.key.as_ref();
                    let value = attr
                        .decode_and_unescape_value(reader.decoder())
                        .map(|value| value.into_owned())
                        .ok();
                    if key == b"name" {
                        name = value;
                    } else if key.contains(&b':') && local_name(key) == b"id" {
                        relationship_id = value;
                    }
                }
                if name.as_deref() == Some(sheet_name) {
                    return Ok(relationship_id);
                }
            }
            Event::Eof => return Ok(None),
            _ => {}
        }
    }
}

/// Copy a start tag, dropping `drop` attributes and replacing or appending
/// `set` attributes. Attribute values are copied as raw (escaped) bytes.
fn with_raw_attributes(
    event: &BytesStart<'_>,
    drop: &[&[u8]],
    set: &[(&[u8], String)],
) -> BytesStart<'static> {
    let mut rewritten =
        BytesStart::new(String::from_utf8_lossy(event.name().as_ref()).into_owned());
    let mut seen = vec![false; set.len()];
    for attr in event.attributes().with_checks(false).flatten() {
        let key = attr.key.as_ref();
        if drop.contains(&key) {
            continue;
        }
        if let Some(index) = set.iter().position(|(name, _)| *name == key) {
            if !seen[index] {
                rewritten.push_attribute((key, set[index].1.as_bytes()));
                seen[index] = true;
            }
            continue;
        }
        rewritten.push_attribute((key, attr.value.as_ref()));
    }
    for (index, (name, value)) in set.iter().enumerate() {
        if !seen[index] {
            rewritten.push_attribute((*name, value.as_bytes()));
        }
    }
    rewritten
}

fn raw_attribute(event: &BytesStart<'_>, name: &[u8]) -> Option<String> {
    event
        .attributes()
        .with_checks(false)
        .flatten()
        .find(|attr| attr.key.as_ref() == name)
        .map(|attr| String::from_utf8_lossy(attr.value.as_ref()).into_owned())
}

fn element_prefix(name: &[u8]) -> String {
    match name.iter().rposition(|byte| *byte == b':') {
        Some(index) => String::from_utf8_lossy(&name[..=index]).into_owned(),
        None => String::new(),
    }
}

struct SharedStringTable {
    /// Index of the first plain (single `t`, no runs) item for each text.
    plain: BTreeMap<String, usize>,
    unique: usize,
    appended: Vec<String>,
}

impl SharedStringTable {
    fn parse(xml: &[u8]) -> Result<Self, WolfPptError> {
        let mut reader = Reader::from_reader(xml);
        reader.config_mut().trim_text(false);
        let mut plain = BTreeMap::new();
        let mut unique = 0usize;
        let mut depth = 0usize;
        let mut in_text = false;
        let mut is_plain = true;
        let mut text_count = 0usize;
        let mut text = String::new();
        loop {
            match reader.read_event()? {
                Event::Start(event) => {
                    let name = local_name(event.name().as_ref()).to_vec();
                    if depth == 0 {
                        if name == b"si" {
                            depth = 1;
                            is_plain = true;
                            text_count = 0;
                            text.clear();
                        }
                        continue;
                    }
                    if depth == 1 {
                        if name == b"t" {
                            in_text = true;
                            text_count += 1;
                        } else {
                            is_plain = false;
                        }
                    }
                    depth += 1;
                }
                Event::Empty(event) => {
                    let name = local_name(event.name().as_ref()).to_vec();
                    if depth == 0 {
                        if name == b"si" {
                            unique += 1;
                        }
                    } else if depth == 1 {
                        if name == b"t" {
                            text_count += 1;
                        } else {
                            is_plain = false;
                        }
                    }
                }
                Event::End(_) if depth > 0 => {
                    depth -= 1;
                    if depth == 1 {
                        in_text = false;
                    } else if depth == 0 {
                        if is_plain && text_count == 1 {
                            plain.entry(std::mem::take(&mut text)).or_insert(unique);
                        }
                        unique += 1;
                    }
                }
                Event::Text(event) if in_text => {
                    if let Some(content) = xml_text_content(&event) {
                        text.push_str(&content);
                    }
                }
                Event::GeneralRef(event) if in_text => {
                    if let Some(content) = xml_reference_content(&event) {
                        text.push_str(&content);
                    }
                }
                Event::CData(event) if in_text => {
                    text.push_str(&String::from_utf8_lossy(&event));
                }
                Event::Eof => break,
                _ => {}
            }
        }
        Ok(Self {
            plain,
            unique,
            appended: Vec::new(),
        })
    }

    fn intern(&mut self, text: &str) -> usize {
        if let Some(index) = self.plain.get(text) {
            return *index;
        }
        let index = self.unique + self.appended.len();
        self.appended.push(text.to_string());
        self.plain.insert(text.to_string(), index);
        index
    }

    /// Append new items and update `count`/`uniqueCount` on the root.
    fn rewrite(&self, xml: &[u8], count_delta: i64) -> Result<Vec<u8>, WolfPptError> {
        let mut reader = Reader::from_reader(xml);
        reader.config_mut().trim_text(false);
        let mut writer = Writer::new(Vec::with_capacity(xml.len() + self.appended.len() * 32));
        let mut depth = 0usize;
        let mut prefix = String::new();
        loop {
            match reader.read_event()? {
                Event::Start(event) if depth == 0 => {
                    prefix = element_prefix(event.name().as_ref());
                    writer.write_event(Event::Start(self.root_start(&event, count_delta)))?;
                    depth = 1;
                }
                Event::Empty(event) if depth == 0 => {
                    prefix = element_prefix(event.name().as_ref());
                    let name = String::from_utf8_lossy(event.name().as_ref()).into_owned();
                    writer.write_event(Event::Start(self.root_start(&event, count_delta)))?;
                    self.write_appended(&mut writer, &prefix)?;
                    writer.write_event(Event::End(BytesEnd::new(name)))?;
                }
                Event::Start(event) => {
                    depth += 1;
                    writer.write_event(Event::Start(event))?;
                }
                Event::End(event) => {
                    depth -= 1;
                    if depth == 0 {
                        self.write_appended(&mut writer, &prefix)?;
                    }
                    writer.write_event(Event::End(event))?;
                }
                Event::Eof => break,
                event => writer.write_event(event)?,
            }
        }
        Ok(writer.into_inner())
    }

    fn root_start(&self, event: &BytesStart<'_>, count_delta: i64) -> BytesStart<'static> {
        let mut set: Vec<(&[u8], String)> = Vec::new();
        if let Some(count) = raw_attribute(event, b"count").and_then(|v| v.parse::<i64>().ok()) {
            set.push((b"count", (count + count_delta).max(0).to_string()));
        }
        if raw_attribute(event, b"uniqueCount").is_some() {
            set.push((b"uniqueCount", (self.unique + self.appended.len()).to_string()));
        }
        with_raw_attributes(event, &[], &set)
    }

    fn write_appended(&self, writer: &mut Writer<Vec<u8>>, prefix: &str) -> Result<(), WolfPptError> {
        for text in &self.appended {
            writer.write_event(Event::Start(BytesStart::new(format!("{prefix}si"))))?;
            write_text_element(writer, &format!("{prefix}t"), text)?;
            writer.write_event(Event::End(BytesEnd::new(format!("{prefix}si"))))?;
        }
        Ok(())
    }
}

fn write_text_element(
    writer: &mut Writer<Vec<u8>>,
    name: &str,
    text: &str,
) -> Result<(), WolfPptError> {
    let mut start = BytesStart::new(name.to_string());
    if text.trim() != text {
        start.push_attribute(("xml:space", "preserve"));
    }
    writer.write_event(Event::Start(start))?;
    writer.write_event(Event::Text(BytesText::new(text)))?;
    writer.write_event(Event::End(BytesEnd::new(name.to_string())))?;
    Ok(())
}

struct WorksheetCellRewriter<'u, 's> {
    writer: Writer<Vec<u8>>,
    /// Cells to write, sorted by (row, column).
    cells: Vec<((u32, u32), &'u WorkbookCellValue)>,
    /// First cell of `cells` not yet written.
    next: usize,
    /// Existing cells whose value is cleared.
    cleared: BTreeSet<(u32, u32)>,
    /// Namespace prefix of the worksheet elements, including the colon.
    prefix: String,
    shared_strings: Option<&'s mut SharedStringTable>,
    string_refs_written: usize,
    string_refs_replaced: usize,
}

impl WorksheetCellRewriter<'_, '_> {
    fn rewrite(&mut self, xml: &[u8]) -> Result<(), WolfPptError> {
        let mut reader = Reader::from_reader(xml);
        reader.config_mut().trim_text(false);
        let mut in_sheet_data = false;
        let mut current_row: Option<u32> = None;
        let mut skip_depth = 0usize;
        loop {
            let event = reader.read_event()?;
            if skip_depth > 0 {
                match &event {
                    Event::Start(start) | Event::Empty(start)
                        if local_name(start.name().as_ref()) == b"f" =>
                    {
                        return Err(WolfPptError::InvalidInput(
                            "worksheet cell to update holds a formula".to_string(),
                        ));
                    }
                    Event::Start(_) => skip_depth += 1,
                    Event::End(_) => skip_depth -= 1,
                    Event::Eof => break,
                    _ => {}
                }
                continue;
            }
            let (start, is_empty) = match event {
                Event::Start(start) => (start, false),
                Event::Empty(start) => (start, true),
                Event::End(end) => {
                    let name = local_name(end.name().as_ref()).to_vec();
                    if name == b"row" && in_sheet_data {
                        if let Some(row) = current_row.take() {
                            self.write_cells_in_row(row, None)?;
                        }
                    } else if name == b"sheetData" && in_sheet_data {
                        self.write_rows_before(None)?;
                        in_sheet_data = false;
                    }
                    self.writer.write_event(Event::End(end))?;
                    continue;
                }
                Event::Eof => break,
                event => {
                    self.writer.write_event(event)?;
                    continue;
                }
            };
            let name = local_name(start.name().as_ref()).to_vec();
            match name.as_slice() {
                b"dimension" if !in_sheet_data => {
                    let rewritten = self.dimension_start(&start);
                    self.write_start(rewritten, is_empty)?;
                }
                b"sheetData" => {
                    self.prefix = element_prefix(start.name().as_ref());
                    let end_name = String::from_utf8_lossy(start.name().as_ref()).into_owned();
                    self.writer.write_event(Event::Start(start))?;
                    if is_empty {
                        self.write_rows_before(None)?;
                        self.writer.write_event(Event::End(BytesEnd::new(end_name)))?;
                    } else {
                        in_sheet_data = true;
                    }
                }
                b"row" if in_sheet_data && current_row.is_none() => {
                    let row = raw_attribute(&start, b"r")
                        .and_then(|value| value.parse::<u32>().ok())
                        .ok_or_else(|| {
                            WolfPptError::InvalidInput("worksheet row has no index".to_string())
                        })?;
                    self.write_rows_before(Some(row))?;
                    let rewritten = self.row_start(&start, row);
                    if is_empty {
                        if self.has_cells_in_row(row) {
                            let end_name =
                                String::from_utf8_lossy(start.name().as_ref()).into_owned();
                            self.writer.write_event(Event::Start(rewritten))?;
                            self.write_cells_in_row(row, None)?;
                            self.writer.write_event(Event::End(BytesEnd::new(end_name)))?;
                        } else {
                            self.writer.write_event(Event::Empty(rewritten))?;
                        }
                    } else {
                        self.writer.write_event(Event::Start(rewritten))?;
                        current_row = Some(row);
                    }
                }
                b"c" if current_row.is_some() => {
                    let row = current_row.unwrap_or_default();
                    let (cell_row, column) = raw_attribute(&start, b"r")
                        .as_deref()
                        .and_then(parse_cell_reference)
                        .ok_or_else(|| {
                            WolfPptError::InvalidInput(
                                "worksheet cell has no reference".to_string(),
                            )
                        })?;
                    if cell_row != row {
                        return Err(WolfPptError::InvalidInput(
                            "worksheet cell reference is outside its row".to_string(),
                        ));
                    }
                    self.write_cells_in_row(row, Some(column))?;
                    let value = if self.next < self.cells.len()
                        && self.cells[self.next].0 == (row, column)
                    {
                        self.next += 1;
                        Some(self.cells[self.next - 1].1)
                    } else if self.cleared.contains(&(row, column)) {
                        Some(&WorkbookCellValue::Empty)
                    } else {
                        None
                    };
                    if let Some(value) = value {
                        if raw_attribute(&start, b"t").as_deref() == Some("s") {
                            self.string_refs_replaced += 1;
                        }
                        let base = with_raw_attributes(&start, &[b"t", b"vm", b"cm"], &[]);
                        self.write_cell(base, value)?;
                        if !is_empty {
                            skip_depth = 1;
                        }
                    } else {
                        self.write_start(start, is_empty)?;
                    }
                }
                _ => self.write_start(start, is_empty)?,
            }
        }
        if self.next < self.cells.len() {
            return Err(WolfPptError::InvalidInput(
                "worksheet has no sheetData".to_string(),
            ));
        }
        Ok(())
    }

    fn write_start(&mut self, start: BytesStart<'_>, is_empty: bool) -> Result<(), WolfPptError> {
        if is_empty {
            self.writer.write_event(Event::Empty(start))?;
        } else {
            self.writer.write_event(Event::Start(start))?;
        }
        Ok(())
    }

    fn has_cells_in_row(&self, row: u32) -> bool {
        self.next < self.cells.len() && self.cells[self.next].0 .0 == row
    }

    /// Write new rows for pending cells whose row is before `limit`.
    fn write_rows_before(&mut self, limit: Option<u32>) -> Result<(), WolfPptError> {
        while self.next < self.cells.len() {
            let row = self.cells[self.next].0 .0;
            if limit.is_some_and(|limit| row >= limit) {
                break;
            }
            let name = format!("{}row", self.prefix);
            let mut start = BytesStart::new(name.clone());
            start.push_attribute(("r", row.to_string().as_str()));
            self.writer.write_event(Event::Start(start))?;
            self.write_cells_in_row(row, None)?;
            self.writer.write_event(Event::End(BytesEnd::new(name)))?;
        }
        Ok(())
    }

    /// Write new cells of `row` whose column is before `limit`.
    fn write_cells_in_row(&mut self, row: u32, limit: Option<u32>) -> Result<(), WolfPptError> {
        while self.next < self.cells.len() {
            let ((cell_row, column), value) = self.cells[self.next];
            if cell_row != row || limit.is_some_and(|limit| column >= limit) {
                break;
            }
            self.next += 1;
            let mut start = BytesStart::new(format!("{}c", self.prefix));
            start.push_attribute(("r", cell_reference(row, column).as_str()));
            self.write_cell(start, value)?;
        }
        Ok(())
    }

    fn write_cell(
        &mut self,
        mut start: BytesStart<'static>,
        value: &WorkbookCellValue,
    ) -> Result<(), WolfPptError> {
        let cell_name = format!("{}c", self.prefix);
        let value_name = format!("{}v", self.prefix);
        match value {
            WorkbookCellValue::Empty => {
                self.writer.write_event(Event::Empty(start))?;
                return Ok(());
            }
            WorkbookCellValue::Number(number) => {
                self.writer.write_event(Event::Start(start))?;
                write_text_element(&mut self.writer, &value_name, number)?;
            }
            WorkbookCellValue::Text(text) => match self.shared_strings.as_deref_mut() {
                Some(table) => {
                    let index = table.intern(text);
                    self.string_refs_written += 1;
                    start.push_attribute(("t", "s"));
                    self.writer.write_event(Event::Start(start))?;
                    write_text_element(&mut self.writer, &value_name, &index.to_string())?;
                }
                None => {
                    start.push_attribute(("t", "inlineStr"));
                    self.writer.write_event(Event::Start(start))?;
                    let inline_name = format!("{}is", self.prefix);
                    self.writer
                        .write_event(Event::Start(BytesStart::new(inline_name.clone())))?;
                    write_text_element(&mut self.writer, &format!("{}t", self.prefix), text)?;
                    self.writer.write_event(Event::End(BytesEnd::new(inline_name)))?;
                }
            },
        }
        self.writer.write_event(Event::End(BytesEnd::new(cell_name)))?;
        Ok(())
    }

    /// Widen the row `spans` hint to cover the cells being written in it.
    fn row_start(&self, start: &BytesStart<'_>, row: u32) -> BytesStart<'static> {
        let Some(spans) = raw_attribute(start, b"spans") else {
            return start.to_owned();
        };
        let mut ranges: Vec<(u32, u32)> = Vec::new();
        for span in spans.split_whitespace() {
            let mut bounds = span.split(':').map(|value| value.parse::<u32>().ok());
            match (bounds.next().flatten(), bounds.next().flatten()) {
                (Some(first), Some(last)) => ranges.push((first, last)),
                _ => return start.to_owned(),
            }
        }
        let new_columns: Vec<u32> = self.cells[self.next..]
            .iter()
            .take_while(|((cell_row, _), _)| *cell_row == row)
            .map(|((_, column), _)| *column)
            .filter(|column| {
                !ranges
                    .iter()
                    .any(|(first, last)| first <= column && column <= last)
            })
            .collect();
        if new_columns.is_empty() {
            return start.to_owned();
        }
        let columns = ranges
            .iter()
            .flat_map(|(first, last)| [*first, *last])
            .chain(new_columns);
        let first = columns.clone().min().unwrap_or(1);
        let last = columns.max().unwrap_or(1);
        with_raw_attributes(start, &[], &[(b"spans", format!("{first}:{last}"))])
    }

    /// Widen the dimension `ref` to cover every cell being written.
    fn dimension_start(&self, start: &BytesStart<'_>) -> BytesStart<'static> {
        let Some(existing) = raw_attribute(start, b"ref") else {
            return start.to_owned();
        };
        let mut corners: Vec<(u32, u32)> = existing
            .split(':')
            .filter_map(parse_cell_reference)
            .collect();
        if corners.is_empty() || corners.len() != existing.split(':').count() {
            return start.to_owned();
        }
        corners.extend(self.cells.iter().map(|(position, _)| *position));
        let min_row = corners.iter().map(|(row, _)| *row).min().unwrap_or(1);
        let max_row = corners.iter().map(|(row, _)| *row).max().unwrap_or(1);
        let min_column = corners.iter().map(|(_, column)| *column).min().unwrap_or(1);
        let max_column = corners.iter().map(|(_, column)| *column).max().unwrap_or(1);
        let first = cell_reference(min_row, min_column);
        let last = cell_reference(max_row, max_column);
        let reference = if first == last {
            first
        } else {
            format!("{first}:{last}")
        };
        if reference == existing {
            return start.to_owned();
        }
        with_raw_attributes(start, &[], &[(b"ref", reference)])
    }
}
