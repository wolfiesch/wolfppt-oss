fn is_slide_part(name: &str) -> bool {
    let Some(rest) = name.strip_prefix("ppt/slides/slide") else {
        return false;
    };
    let Some(number) = rest.strip_suffix(".xml") else {
        return false;
    };
    !number.is_empty() && number.chars().all(|ch| ch.is_ascii_digit())
}

fn xml_text_content(event: &BytesText<'_>) -> Option<String> {
    let text = event.xml10_content();
    (!text.is_empty()).then(|| text.into_owned())
}

fn xml_reference_content(event: &BytesRef<'_>) -> Option<String> {
    if let Ok(Some(ch)) = event.resolve_char_ref() {
        return Some(ch.to_string());
    }

    let name = event.as_ref();
    let text = quick_xml::escape::resolve_xml_entity(name)
        .map(str::to_owned)
        .unwrap_or_else(|| format!("&{name};"));
    Some(text)
}

const MC_NAMESPACE: &str = "http://schemas.openxmlformats.org/markup-compatibility/2006";
const MC_SUPPORTED_NAMESPACE_URIS: &[&str] = &[
    "http://schemas.openxmlformats.org/presentationml/2006/main",
    "http://schemas.openxmlformats.org/drawingml/2006/main",
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "http://purl.oclc.org/ooxml/presentationml/main",
    "http://purl.oclc.org/ooxml/drawingml/main",
    "http://purl.oclc.org/ooxml/officeDocument/relationships",
    "http://schemas.openxmlformats.org/drawingml/2006/chart",
];

#[derive(Clone)]
enum McXmlNode {
    Element(McXmlElement),
    Event(Event<'static>),
}

#[derive(Clone)]
struct McXmlElement {
    start: BytesStart<'static>,
    end: BytesEnd<'static>,
    namespaces: BTreeMap<String, String>,
    namespace_declarations: Vec<(String, String)>,
    children: Vec<McXmlNode>,
}

/// Resolves `mc:AlternateContent` blocks to their selected branch.
///
/// Without an `AlternateContent` element the result is the parsed tree written
/// back unchanged, so inputs on which that round trip is the identity are
/// returned as-is without being parsed (see [`mc_round_trip_is_identity`]).
fn effective_mc_xml(xml: &[u8]) -> std::borrow::Cow<'_, [u8]> {
    if mc_round_trip_is_identity(xml) {
        return std::borrow::Cow::Borrowed(xml);
    }
    resolved_mc_xml(xml)
}

fn resolved_mc_xml(xml: &[u8]) -> std::borrow::Cow<'_, [u8]> {
    let Some(nodes) = parse_mc_xml(xml) else {
        return std::borrow::Cow::Borrowed(xml);
    };
    let mut writer = Writer::new(Vec::with_capacity(xml.len()));
    if nodes
        .iter()
        .try_for_each(|node| write_effective_mc_node(&mut writer, node))
        .is_err()
    {
        return std::borrow::Cow::Borrowed(xml);
    }
    std::borrow::Cow::Owned(writer.into_inner())
}

/// True when [`resolved_mc_xml`] would reproduce `xml` byte for byte.
///
/// Only an `AlternateContent` element changes the tree; otherwise every event
/// is written back from its raw bytes except where quick-xml normalizes while
/// reading: a leading byte-order mark is dropped (any input that could carry
/// one, or be UTF-16, is excluded), whitespace after a closing tag's name is
/// trimmed, and a DOCTYPE keyword and its following whitespace are respelled.
/// Inputs with any of those take the full path.
fn mc_round_trip_is_identity(xml: &[u8]) -> bool {
    const NEEDLE: &[u8] = b"AlternateContent";
    if xml.iter().take(2).any(|byte| matches!(byte, 0x00 | 0xEF | 0xFE | 0xFF))
        || xml
            .windows(NEEDLE.len())
            .any(|window| window[0] == NEEDLE[0] && window == NEEDLE)
    {
        return false;
    }
    let mut offset = 0;
    while let Some(relative) = xml[offset..].iter().position(|&byte| byte == b'<') {
        let start = offset + relative + 1;
        match xml.get(start) {
            Some(b'!') => {
                let keyword = xml.get(start + 1..start + 8);
                if keyword.is_some_and(|keyword| keyword.eq_ignore_ascii_case(b"DOCTYPE")) {
                    return false;
                }
            }
            Some(b'/') => {
                let name = &xml[start + 1..];
                let end = name.iter().position(|&byte| byte == b'>').unwrap_or(name.len());
                if name[..end].iter().any(u8::is_ascii_whitespace) {
                    return false;
                }
            }
            _ => {}
        }
        offset = start;
    }
    true
}

fn parse_mc_xml(xml: &[u8]) -> Option<Vec<McXmlNode>> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    let mut nodes = Vec::new();
    let namespaces = BTreeMap::new();

    loop {
        let event = reader.read_event().ok()?;
        match event {
            Event::Start(start) => nodes.push(McXmlNode::Element(parse_mc_xml_element(
                &mut reader,
                start.into_owned(),
                &namespaces,
            )?)),
            Event::Empty(empty) => nodes.push(McXmlNode::Event(Event::Empty(empty.into_owned()))),
            Event::End(_) => return None,
            Event::Eof => return Some(nodes),
            event => nodes.push(McXmlNode::Event(event.into_owned())),
        }
    }
}

fn parse_mc_xml_element(
    reader: &mut Reader<&[u8]>,
    start: BytesStart<'static>,
    parent_namespaces: &BTreeMap<String, String>,
) -> Option<McXmlElement> {
    let namespace_declarations = namespace_declarations(&start);
    let namespaces = namespace_scope(parent_namespaces, &namespace_declarations);
    let mut children = Vec::new();

    loop {
        let event = reader.read_event().ok()?;
        match event {
            Event::Start(child) => children.push(McXmlNode::Element(parse_mc_xml_element(
                reader,
                child.into_owned(),
                &namespaces,
            )?)),
            Event::Empty(empty) => children.push(McXmlNode::Event(Event::Empty(empty.into_owned()))),
            Event::End(end) => {
                return Some(McXmlElement {
                    start,
                    end: end.into_owned(),
                    namespaces,
                    namespace_declarations,
                    children,
                });
            }
            Event::Eof => return None,
            event => children.push(McXmlNode::Event(event.into_owned())),
        }
    }
}

fn namespace_declarations(start: &BytesStart<'_>) -> Vec<(String, String)> {
    start
        .attributes()
        .flatten()
        .filter_map(|attribute| {
            let key = attribute.key.as_ref();
            let prefix = if key == "xmlns" {
                Some("")
            } else {
                key.strip_prefix("xmlns:")
            }?;
            let uri = attribute
                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                .ok()?;
            Some((prefix.to_string(), uri.into_owned()))
        })
        .collect()
}

fn namespace_scope(
    parent_namespaces: &BTreeMap<String, String>,
    declarations: &[(String, String)],
) -> BTreeMap<String, String> {
    let mut namespaces = parent_namespaces.clone();
    for (prefix, uri) in declarations {
        namespaces.insert(prefix.clone(), uri.clone());
    }
    namespaces
}

fn write_effective_mc_node(
    writer: &mut Writer<Vec<u8>>,
    node: &McXmlNode,
) -> std::io::Result<()> {
    write_effective_mc_node_with_namespaces(writer, node, &[])
}

fn write_effective_mc_node_with_namespaces(
    writer: &mut Writer<Vec<u8>>,
    node: &McXmlNode,
    inherited_declarations: &[(String, String)],
) -> std::io::Result<()> {
    match node {
        McXmlNode::Event(event) => writer.write_event(event.clone()),
        McXmlNode::Element(element) if is_mc_element(element, b"AlternateContent") => {
            if let Some(branch) = selected_mc_branch(element) {
                let mut effective_declarations = BTreeMap::new();
                for (prefix, uri) in inherited_declarations
                    .iter()
                    .chain(branch.namespace_declarations.iter())
                {
                    effective_declarations.insert(prefix.clone(), uri.clone());
                }
                let branch_declarations = effective_declarations.into_iter().collect::<Vec<_>>();
                for child in &branch.children {
                    write_effective_mc_node_with_namespaces(
                        writer,
                        child,
                        &branch_declarations,
                    )?;
                }
            }
            Ok(())
        }
        McXmlNode::Element(element) => {
            writer.write_event(Event::Start(with_namespace_declarations(
                &element.start,
                inherited_declarations,
            )))?;
            for child in &element.children {
                write_effective_mc_node_with_namespaces(writer, child, &[])?;
            }
            writer.write_event(Event::End(element.end.clone()))
        }
    }
}

fn with_namespace_declarations(
    start: &BytesStart<'_>,
    declarations: &[(String, String)],
) -> BytesStart<'static> {
    let mut rewritten = start.to_owned();
    for (prefix, uri) in declarations {
        let key = if prefix.is_empty() {
            "xmlns".to_string()
        } else {
            format!("xmlns:{prefix}")
        };
        if rewritten
            .attributes()
            .flatten()
            .any(|attribute| attribute.key.as_ref() == key.as_str())
        {
            continue;
        }
        rewritten.push_attribute((key.as_str(), uri.as_str()));
    }
    rewritten
}

fn selected_mc_branch(alternate: &McXmlElement) -> Option<&McXmlElement> {
    let choice_elements: Vec<&McXmlElement> = alternate
        .children
        .iter()
        .filter_map(|node| match node {
            McXmlNode::Element(element) => Some(element),
            McXmlNode::Event(_) => None,
        })
        .filter(|element| is_mc_element(element, b"Choice"))
        .collect();

    // If any Choice has undefined required namespaces, skip the entire AlternateContent
    if choice_elements
        .iter()
        .any(|choice| mc_choice_has_undefined_namespaces(choice))
    {
        return None;
    }

    // Find a supported Choice
    choice_elements
        .into_iter()
        .find(|element| mc_choice_is_supported(element))
        .or_else(|| {
            // Fall back to Fallback if no supported Choice
            alternate.children.iter().find_map(|node| match node {
                McXmlNode::Element(element) if is_mc_element(element, b"Fallback") => {
                    Some(element)
                }
                _ => None,
            })
        })
}

fn is_mc_element(element: &McXmlElement, local_name: &[u8]) -> bool {
    let qualified_name = element.start.name();
    let name = qualified_name.as_ref().as_bytes();
    let Some((prefix, local)) = split_qualified_name(name) else {
        return false;
    };
    local == local_name
        && element
            .namespaces
            .get(prefix)
            .is_some_and(|namespace| namespace == MC_NAMESPACE)
}

fn mc_choice_is_supported(choice: &McXmlElement) -> bool {
    let Some(requires) = choice
        .start
        .attributes()
        .flatten()
        .find(|attribute| attribute.key.as_ref() == "Requires")
        .and_then(|attribute| {
            attribute
                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                .ok()
        })
    else {
        return false;
    };
    requires.split_whitespace().all(|prefix| {
        choice
            .namespaces
            .get(prefix)
            .is_some_and(|namespace| MC_SUPPORTED_NAMESPACE_URIS.contains(&namespace.as_str()))
    })
}

fn mc_choice_has_undefined_namespaces(choice: &McXmlElement) -> bool {
    let Some(requires) = choice
        .start
        .attributes()
        .flatten()
        .find(|attribute| attribute.key.as_ref() == "Requires")
        .and_then(|attribute| {
            attribute
                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                .ok()
        })
    else {
        return false;
    };
    requires
        .split_whitespace()
        .any(|prefix| !choice.namespaces.contains_key(prefix))
}

fn split_qualified_name(name: &[u8]) -> Option<(&str, &[u8])> {
    match name.iter().position(|byte| *byte == b':') {
        Some(index) => std::str::from_utf8(&name[..index])
            .ok()
            .map(|prefix| (prefix, &name[index + 1..])),
        None => Some(("", name)),
    }
}

fn extract_text_runs(xml: &[u8]) -> Vec<String> {
    let effective_xml = effective_mc_xml(xml);
    extract_text_runs_from_effective(&effective_xml)
}

fn extract_text_runs_from_effective(xml: &[u8]) -> Vec<String> {
    extract_text_runs_and_elements(xml, []).0
}

/// Text runs of `xml` plus whether each of `names` is the local name of an
/// element (start or empty tag) opened before the end of input or the first
/// read error. One read serves the runs and every name; both stop at the same
/// error, so each result equals what a read of its own would produce.
fn extract_text_runs_and_elements<const N: usize>(
    xml: &[u8],
    names: [&[u8]; N],
) -> (Vec<String>, [bool; N]) {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    let mut found = [false; N];
    let mut in_text = false;
    let mut current_text = String::new();
    let mut texts = Vec::new();

    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => {
                let qualified_name = event.name();
                let qualified_name = qualified_name.as_ref();
                if N > 0 {
                    let name = local_name(qualified_name.as_bytes());
                    for (flag, wanted) in found.iter_mut().zip(names) {
                        *flag |= name == wanted;
                    }
                }
                in_text = qualified_name.ends_with(":t") || qualified_name == "t";
                if in_text {
                    current_text.clear();
                }
            }
            Ok(Event::Empty(event)) if N > 0 => {
                let qualified_name = event.name();
                let name = local_name(qualified_name.as_ref().as_bytes());
                for (flag, wanted) in found.iter_mut().zip(names) {
                    *flag |= name == wanted;
                }
            }
            Ok(Event::End(event)) => {
                if event.name().as_ref().ends_with(":t") || event.name().as_ref() == "t" {
                    if !current_text.is_empty() {
                        texts.push(std::mem::take(&mut current_text));
                    }
                    in_text = false;
                }
            }
            Ok(Event::Text(event)) if in_text => {
                current_text.push_str(&event.xml10_content());
            }
            Ok(Event::CData(event)) if in_text => {
                current_text.push_str(&event.xml10_content());
            }
            Ok(Event::GeneralRef(event)) if in_text => {
                if let Some(text) = xml_reference_content(&event) {
                    current_text.push_str(&text);
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }

    (texts, found)
}

/// Reads `xml` with the paragraph extractors' reader settings and hands every
/// event before the end of input or the first read error to `feed`.
fn for_each_paragraph_event(xml: &[u8], mut feed: impl FnMut(&Event<'_>)) {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(false);
    loop {
        match reader.read_event() {
            Ok(Event::Eof) | Err(_) => break,
            Ok(event) => feed(&event),
        }
    }
}

/// Paragraph-level fields of one shape. Each field keeps its own extractor
/// state machine; all of them consume one shared event stream.
struct ParagraphSummary {
    runs: Vec<Vec<String>>,
    line_breaks: Vec<Vec<usize>>,
    run_bold: Vec<Vec<Option<bool>>>,
    run_italic: Vec<Vec<Option<bool>>>,
    run_underline: Vec<Vec<Option<bool>>>,
    run_strike: Vec<Vec<Option<bool>>>,
    run_font_size: Vec<Vec<Option<i64>>>,
    run_font_name: Vec<Vec<Option<String>>>,
    run_color: Vec<Vec<Option<RunColorSummary>>>,
    texts: Vec<String>,
}

fn extract_paragraph_summary(xml: &[u8]) -> ParagraphSummary {
    let mut runs = ParagraphRuns::default();
    let mut texts = ParagraphTexts::default();
    let mut line_breaks = ParagraphLineBreaks::default();
    let mut attributes = ParagraphRunAttributes::default();
    for_each_paragraph_event(xml, |event| {
        runs.feed(event);
        texts.feed(event);
        line_breaks.feed(event);
        attributes.feed(event);
    });
    let attributes = attributes.paragraphs;
    ParagraphSummary {
        runs: runs.paragraphs,
        line_breaks: line_breaks.paragraphs,
        run_bold: map_run_attributes(&attributes, |run| bool_attribute(run.bold.as_deref())),
        run_italic: map_run_attributes(&attributes, |run| bool_attribute(run.italic.as_deref())),
        run_underline: map_run_attributes(&attributes, |run| match run.underline.as_deref() {
            Some("none") => Some(false),
            Some(_) => Some(true),
            None => None,
        }),
        run_strike: map_run_attributes(&attributes, |run| match run.strike.as_deref() {
            Some("noStrike") => Some(false),
            Some(_) => Some(true),
            None => None,
        }),
        run_font_size: map_run_attributes(&attributes, |run| {
            run.size
                .as_deref()
                .and_then(|value| value.parse::<i64>().ok())
                .map(|centipoints| centipoints * 127)
        }),
        run_font_name: map_run_attributes(&attributes, |run| run.typeface.clone()),
        run_color: map_run_attributes(&attributes, |run| run.color.clone()),
        texts: texts.paragraphs,
    }
}

#[derive(Default)]
struct ParagraphRuns {
    in_paragraph: bool,
    in_text: bool,
    current_text: String,
    current_runs: Vec<String>,
    paragraphs: Vec<Vec<String>>,
}

impl ParagraphRuns {
    fn feed(&mut self, event: &Event<'_>) {
        match event {
            Event::Start(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => {
                    self.in_paragraph = true;
                    self.current_runs.clear();
                }
                b"t" if self.in_paragraph => {
                    self.in_text = true;
                    self.current_text.clear();
                }
                _ => {}
            },
            Event::Empty(event) if local_name(event.name().as_ref().as_bytes()) == b"p" => {
                self.paragraphs.push(Vec::new());
            }
            Event::Empty(event)
                if self.in_paragraph && local_name(event.name().as_ref().as_bytes()) == b"t" =>
            {
                self.current_runs.push(String::new());
            }
            Event::End(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"t" => {
                    if self.in_paragraph && self.in_text {
                        self.current_runs
                            .push(std::mem::take(&mut self.current_text));
                    }
                    self.in_text = false;
                }
                b"p" if self.in_paragraph => {
                    self.paragraphs.push(std::mem::take(&mut self.current_runs));
                    self.in_paragraph = false;
                }
                _ => {}
            },
            Event::Text(event) if self.in_paragraph && self.in_text => {
                if let Some(text) = xml_text_content(event) {
                    self.current_text.push_str(&text);
                }
            }
            Event::CData(event) if self.in_paragraph && self.in_text => {
                let text = event.xml10_content();
                if !text.is_empty() {
                    self.current_text.push_str(&text);
                }
            }
            Event::GeneralRef(event) if self.in_paragraph && self.in_text => {
                if let Some(text) = xml_reference_content(event) {
                    self.current_text.push_str(&text);
                }
            }
            _ => {}
        }
    }
}

#[derive(Default)]
struct ParagraphTexts {
    in_paragraph: bool,
    in_text: bool,
    current_parts: Vec<String>,
    paragraphs: Vec<String>,
}

impl ParagraphTexts {
    fn feed(&mut self, event: &Event<'_>) {
        match event {
            Event::Start(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => {
                    self.in_paragraph = true;
                    self.current_parts.clear();
                }
                b"br" if self.in_paragraph => {
                    self.current_parts.push("\u{000b}".to_string());
                }
                b"t" if self.in_paragraph => {
                    self.in_text = true;
                }
                _ => {}
            },
            Event::Empty(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => self.paragraphs.push(String::new()),
                b"br" if self.in_paragraph => self.current_parts.push("\u{000b}".to_string()),
                _ => {}
            },
            Event::End(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"t" => {
                    self.in_text = false;
                }
                b"p" if self.in_paragraph => {
                    self.paragraphs
                        .push(std::mem::take(&mut self.current_parts).join(""));
                    self.in_paragraph = false;
                }
                _ => {}
            },
            Event::Text(event) if self.in_paragraph && self.in_text => {
                if let Some(text) = xml_text_content(event) {
                    self.current_parts.push(text);
                }
            }
            Event::CData(event) if self.in_paragraph && self.in_text => {
                let text = event.xml10_content();
                if !text.is_empty() {
                    self.current_parts.push(text.into_owned());
                }
            }
            Event::GeneralRef(event) if self.in_paragraph && self.in_text => {
                if let Some(text) = xml_reference_content(event) {
                    self.current_parts.push(text);
                }
            }
            _ => {}
        }
    }
}

#[derive(Default)]
struct ParagraphLineBreaks {
    in_paragraph: bool,
    in_run: bool,
    current_run_has_text: bool,
    current_run_count: usize,
    current_breaks: Vec<usize>,
    paragraphs: Vec<Vec<usize>>,
}

impl ParagraphLineBreaks {
    fn feed(&mut self, event: &Event<'_>) {
        match event {
            Event::Start(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => {
                    self.in_paragraph = true;
                    self.current_run_count = 0;
                    self.current_breaks.clear();
                }
                b"r" if self.in_paragraph => {
                    self.in_run = true;
                    self.current_run_has_text = false;
                }
                b"br" if self.in_paragraph => self.current_breaks.push(self.current_run_count),
                b"t" if self.in_run => self.current_run_has_text = true,
                _ => {}
            },
            Event::Empty(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => self.paragraphs.push(Vec::new()),
                b"br" if self.in_paragraph => self.current_breaks.push(self.current_run_count),
                b"t" if self.in_run => self.current_run_has_text = true,
                _ => {}
            },
            Event::End(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"r" if self.in_run => {
                    if self.current_run_has_text {
                        self.current_run_count += 1;
                    }
                    self.in_run = false;
                    self.current_run_has_text = false;
                }
                b"p" if self.in_paragraph => {
                    self.paragraphs
                        .push(std::mem::take(&mut self.current_breaks));
                    self.in_paragraph = false;
                }
                _ => {}
            },
            _ => {}
        }
    }
}

/// Raw run properties in effect at one text element of a run: the `rPr`
/// attributes, the `latin` typeface, and the `rPr/solidFill` colour.
#[derive(Clone, Default)]
struct RunAttributes {
    bold: Option<String>,
    italic: Option<String>,
    underline: Option<String>,
    strike: Option<String>,
    size: Option<String>,
    typeface: Option<String>,
    color: Option<RunColorSummary>,
}

#[derive(Default)]
struct ParagraphRunAttributes {
    in_paragraph: bool,
    in_run: bool,
    /// Element depth inside the current run's `rPr`; 1 = direct children.
    rpr_depth: usize,
    /// Inside a `solidFill` that is a direct child of the run's `rPr`.
    in_run_fill: bool,
    current: RunAttributes,
    current_runs: Vec<RunAttributes>,
    paragraphs: Vec<Vec<RunAttributes>>,
}

impl ParagraphRunAttributes {
    fn feed(&mut self, event: &Event<'_>) {
        if self.rpr_depth > 0 {
            self.feed_run_properties_child(event);
        }
        match event {
            Event::Start(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => {
                    self.in_paragraph = true;
                    self.current_runs.clear();
                }
                b"r" if self.in_paragraph => {
                    self.in_run = true;
                    self.rpr_depth = 0;
                    self.in_run_fill = false;
                    self.current = RunAttributes::default();
                }
                b"rPr" if self.in_run && self.rpr_depth == 0 => {
                    self.set_run_properties(event);
                    self.rpr_depth = 1;
                }
                b"latin" if self.in_run => {
                    self.current.typeface = drawingml_attribute(event, b"typeface");
                }
                _ => {}
            },
            Event::Empty(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"p" => self.paragraphs.push(Vec::new()),
                b"rPr" if self.in_run => self.set_run_properties(event),
                b"latin" if self.in_run => {
                    self.current.typeface = drawingml_attribute(event, b"typeface");
                }
                b"t" if self.in_run => self.current_runs.push(self.current.clone()),
                _ => {}
            },
            Event::End(event) => match local_name(event.name().as_ref().as_bytes()) {
                b"t" if self.in_run => self.current_runs.push(self.current.clone()),
                b"r" if self.in_run => {
                    self.in_run = false;
                    self.current = RunAttributes::default();
                }
                b"p" if self.in_paragraph => {
                    self.paragraphs.push(std::mem::take(&mut self.current_runs));
                    self.in_paragraph = false;
                }
                _ => {}
            },
            _ => {}
        }
    }

    /// Tracks depth inside the run `rPr` and records the colour element that
    /// is the direct child of its `solidFill`.
    fn feed_run_properties_child(&mut self, event: &Event<'_>) {
        match event {
            Event::Start(element) => {
                let qualified_name = element.name();
                let name = local_name(qualified_name.as_ref().as_bytes());
                if self.rpr_depth == 1 && name == b"solidFill" {
                    self.in_run_fill = true;
                } else if self.rpr_depth == 2 && self.in_run_fill {
                    self.current.color = run_color_summary(element);
                }
                self.rpr_depth += 1;
            }
            Event::Empty(element) if self.rpr_depth == 2 && self.in_run_fill => {
                self.current.color = run_color_summary(element);
            }
            Event::End(_) => {
                self.rpr_depth -= 1;
                if self.rpr_depth <= 1 {
                    self.in_run_fill = false;
                }
            }
            _ => {}
        }
    }

    fn set_run_properties(&mut self, properties: &BytesStart<'_>) {
        self.current.bold = drawingml_attribute(properties, b"b");
        self.current.italic = drawingml_attribute(properties, b"i");
        self.current.underline = drawingml_attribute(properties, b"u");
        self.current.strike = drawingml_attribute(properties, b"strike");
        self.current.size = drawingml_attribute(properties, b"sz");
    }
}

/// Summarizes a DrawingML colour element (`srgbClr`, `prstClr`, `sysClr`,
/// `scrgbClr`, `schemeClr`, `hslClr`); any other element yields `None`.
fn run_color_summary(element: &BytesStart<'_>) -> Option<RunColorSummary> {
    let upper = |value: Option<String>| value.map(|value| value.to_ascii_uppercase());
    let channel = |name: &[u8]| {
        drawingml_attribute(element, name).and_then(|value| value.parse::<i64>().ok())
    };
    let mut summary = RunColorSummary {
        kind: RunColorKind::Srgb,
        value: None,
        r: None,
        g: None,
        b: None,
        last_color: None,
        rgb_hex: None,
    };
    match local_name(element.name().as_ref().as_bytes()) {
        b"srgbClr" => {
            summary.value = upper(drawingml_attribute(element, b"val"));
            summary.rgb_hex = summary.value.clone();
        }
        b"prstClr" => {
            summary.kind = RunColorKind::Preset;
            summary.value = drawingml_attribute(element, b"val");
        }
        b"sysClr" => {
            summary.kind = RunColorKind::System;
            summary.value = drawingml_attribute(element, b"val");
            summary.last_color = upper(drawingml_attribute(element, b"lastClr"));
            summary.rgb_hex = summary.last_color.clone();
        }
        b"scrgbClr" => {
            summary.kind = RunColorKind::Scrgb;
            summary.r = channel(b"r");
            summary.g = channel(b"g");
            summary.b = channel(b"b");
            if let (Some(r), Some(g), Some(b)) = (summary.r, summary.g, summary.b) {
                summary.rgb_hex = Some(format!(
                    "{:02X}{:02X}{:02X}",
                    srgb_companded_byte(r),
                    srgb_companded_byte(g),
                    srgb_companded_byte(b)
                ));
            }
        }
        b"schemeClr" => {
            summary.kind = RunColorKind::Scheme;
            summary.value = drawingml_attribute(element, b"val");
        }
        b"hslClr" => summary.kind = RunColorKind::Hsl,
        _ => return None,
    }
    Some(summary)
}

/// IEC 61966-2-1 sRGB companding of a linear scRGB channel given in 1/1000
/// percent, as an 8-bit value.
fn srgb_companded_byte(channel: i64) -> u8 {
    let linear = (channel as f64 / 100_000.0).clamp(0.0, 1.0);
    let companded = if linear <= 0.003_130_8 {
        12.92 * linear
    } else {
        1.055 * linear.powf(1.0 / 2.4) - 0.055
    };
    (255.0 * companded).round().clamp(0.0, 255.0) as u8
}

fn map_run_attributes<T>(
    paragraphs: &[Vec<RunAttributes>],
    value: impl Fn(&RunAttributes) -> T,
) -> Vec<Vec<T>> {
    paragraphs
        .iter()
        .map(|runs| runs.iter().map(&value).collect())
        .collect()
}

fn bool_attribute(value: Option<&str>) -> Option<bool> {
    match value {
        Some("1") | Some("true") | Some("on") => Some(true),
        Some("0") | Some("false") | Some("off") => Some(false),
        _ => None,
    }
}

fn extract_paragraph_texts(xml: &[u8]) -> Vec<String> {
    let mut texts = ParagraphTexts::default();
    for_each_paragraph_event(xml, |event| texts.feed(event));
    texts.paragraphs
}

#[cfg(test)]
fn extract_paragraph_runs(xml: &[u8]) -> Vec<Vec<String>> {
    extract_paragraph_summary(xml).runs
}

#[cfg(test)]
fn extract_paragraph_line_breaks(xml: &[u8]) -> Vec<Vec<usize>> {
    extract_paragraph_summary(xml).line_breaks
}

#[cfg(test)]
fn extract_paragraph_run_bold(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    extract_paragraph_summary(xml).run_bold
}

#[cfg(test)]
fn extract_paragraph_run_italic(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    extract_paragraph_summary(xml).run_italic
}

#[cfg(test)]
fn extract_paragraph_run_underline(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    extract_paragraph_summary(xml).run_underline
}

#[cfg(test)]
fn extract_paragraph_run_strike(xml: &[u8]) -> Vec<Vec<Option<bool>>> {
    extract_paragraph_summary(xml).run_strike
}

#[cfg(test)]
fn extract_paragraph_run_font_size(xml: &[u8]) -> Vec<Vec<Option<i64>>> {
    extract_paragraph_summary(xml).run_font_size
}

#[cfg(test)]
fn extract_paragraph_run_font_name(xml: &[u8]) -> Vec<Vec<Option<String>>> {
    extract_paragraph_summary(xml).run_font_name
}

#[cfg(test)]
fn extract_paragraph_run_color(xml: &[u8]) -> Vec<Vec<Option<RunColorSummary>>> {
    extract_paragraph_summary(xml).run_color
}

#[cfg(test)]
mod mc_round_trip_tests {
    use super::*;

    #[test]
    fn identity_inputs_are_returned_without_parsing_and_match_the_round_trip() {
        let inputs: [&[u8]; 6] = [
            br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><p:cSld><a:t>A &amp; B &#x263A;</a:t><a:br />
<!-- note --><![CDATA[<x>]]><?pi data?><a:p/></p:cSld></p:sld>"#,
            b"<a:p xmlns:a=\"urn:a\">\r\n  <a:r><a:t xml:space='preserve'> x </a:t></a:r></a:p>",
            b"<root/>",
            b"",
            b"plain text",
            b"<a></b>",
        ];
        for input in inputs {
            assert!(mc_round_trip_is_identity(input), "{input:?}");
            assert!(matches!(
                effective_mc_xml(input),
                std::borrow::Cow::Borrowed(_)
            ));
            assert_eq!(resolved_mc_xml(input).as_ref(), input);
        }
    }

    #[test]
    fn inputs_quick_xml_would_normalize_take_the_resolving_path() {
        let normalized: [&[u8]; 5] = [
            b"\xEF\xBB\xBF<root></root>",
            b"<root></root >",
            b"<root></root\n>",
            b"<!DOCTYPE  root><root/>",
            b"<!doctype root><root/>",
        ];
        for input in normalized {
            assert!(!mc_round_trip_is_identity(input), "{input:?}");
            assert_ne!(resolved_mc_xml(input).as_ref(), input);
            assert_eq!(effective_mc_xml(input), resolved_mc_xml(input));
        }
        let alternate = br#"<p:sld xmlns:p="urn:p" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"><mc:AlternateContent><mc:Fallback><p:x/></mc:Fallback></mc:AlternateContent></p:sld>"#;
        assert!(!mc_round_trip_is_identity(alternate));
        assert_eq!(
            effective_mc_xml(alternate).as_ref(),
            br#"<p:sld xmlns:p="urn:p" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"><p:x/></p:sld>"#
        );
    }

    /// Every XML part of every PPTX fixture: wherever the fast path applies,
    /// the full round trip gives the same bytes.
    #[test]
    fn fixture_parts_on_the_fast_path_round_trip_unchanged() {
        fn pptx_files(dir: &Path, found: &mut Vec<PathBuf>) {
            let Ok(entries) = std::fs::read_dir(dir) else {
                return;
            };
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    pptx_files(&path, found);
                } else if path.extension().is_some_and(|ext| ext == "pptx") {
                    found.push(path);
                }
            }
        }
        let mut decks = Vec::new();
        pptx_files(Path::new("../../fixtures"), &mut decks);
        pptx_files(Path::new("../../tests"), &mut decks);
        let mut fast_path_parts = 0;
        for deck in &decks {
            let Ok(mut archive) = ZipArchive::new(File::open(deck).unwrap()) else {
                continue;
            };
            for index in 0..archive.len() {
                let mut entry = archive.by_index(index).unwrap();
                let entry_name = entry.name().unwrap().into_owned();
                if !entry_name.ends_with(".xml") {
                    continue;
                }
                let mut xml = Vec::new();
                entry.read_to_end(&mut xml).unwrap();
                if mc_round_trip_is_identity(&xml) {
                    fast_path_parts += 1;
                    assert_eq!(
                        resolved_mc_xml(&xml).as_ref(),
                        xml.as_slice(),
                        "{} {}",
                        deck.display(),
                        entry_name
                    );
                }
            }
        }
        assert!(
            fast_path_parts > 100,
            "{fast_path_parts} parts from {} decks",
            decks.len()
        );
    }
}
