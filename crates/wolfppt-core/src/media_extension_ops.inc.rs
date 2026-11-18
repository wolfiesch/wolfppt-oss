/// Surgical media deltas. JSON decoding lives in the host binding so the core
/// keeps its existing dependency surface; absent fields never overwrite XML.
#[derive(Debug, Default, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MediaControls {
    pub r#loop: Option<bool>,
    pub play_across_slides: Option<bool>,
    pub volume: Option<u8>,
    pub auto_play: Option<bool>,
    pub mute: Option<bool>,
    pub show_when_stopped: Option<bool>,
    pub trim_start: Option<f64>,
    pub trim_end: Option<f64>,
    pub fade_in: Option<f64>,
    pub fade_out: Option<f64>,
    pub bookmarks: Option<Vec<MediaControlBookmark>>,
    pub triggers: Option<Vec<MediaControlTrigger>>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MediaControlBookmark {
    pub name: String,
    pub time: f64,
}

#[derive(Debug, serde::Deserialize)]
#[serde(untagged)]
pub enum MediaControlId {
    Text(String),
    Number(u64),
}

impl MediaControlId {
    fn id(&self) -> Result<u64, WolfPptError> {
        let value = match self {
            Self::Text(value) => value
                .parse::<u64>()
                .ok()
                .filter(|id| value == &id.to_string()),
            Self::Number(value) => Some(*value),
        };
        value
            .filter(|value| *value > 0 && *value <= u64::from(u32::MAX))
            .ok_or_else(|| {
                media_control_refusal(
                    "shape and time-node ids must be canonical positive uint32 integers",
                )
            })
    }
}

#[derive(Debug, serde::Deserialize)]
#[serde(untagged)]
pub enum MediaControlDelay {
    Text(String),
    Number(f64),
}

impl MediaControlDelay {
    fn milliseconds(&self) -> Result<f64, WolfPptError> {
        let value = match self {
            Self::Text(value) => value.parse::<f64>().ok(),
            Self::Number(value) => Some(*value),
        };
        media_control_milliseconds(value.unwrap_or(f64::NAN))
    }
}

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MediaControlTrigger {
    pub event: Option<String>,
    pub delay: Option<MediaControlDelay>,
    pub node_id: Option<MediaControlId>,
    pub shape_id: Option<MediaControlId>,
    pub bookmark: Option<String>,
    pub time_node: Option<MediaControlId>,
}

fn media_control_refusal(message: impl std::fmt::Display) -> WolfPptError {
    WolfPptError::InvalidInput(format!("MediaControlRefusalError: {message}"))
}

fn media_control_milliseconds(value: f64) -> Result<f64, WolfPptError> {
    if !value.is_finite() || value < 0.0 {
        return Err(media_control_refusal(
            "milliseconds must be finite and nonnegative",
        ));
    }
    Ok(value)
}

const MEDIA_CONTROL_P_NS: &str = "http://schemas.openxmlformats.org/presentationml/2006/main";
const MEDIA_CONTROL_A_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/main";
const MEDIA_CONTROL_R_NS: &str =
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

fn media_control_bookmark_name(name: &str) -> Result<String, WolfPptError> {
    if name.is_empty()
        || name.chars().any(|ch| {
            !matches!(ch, '\t' | '\n' | '\r' | '\u{20}'..='\u{d7ff}'
            | '\u{e000}'..='\u{fffd}' | '\u{10000}'..='\u{10ffff}')
        })
    {
        return Err(media_control_refusal(
            "bookmark names must contain valid XML characters",
        ));
    }
    Ok(xml_attr(name)
        .replace('\t', "&#9;")
        .replace('\n', "&#10;")
        .replace('\r', "&#13;"))
}
const MEDIA_CONTROL_P14_NS: &str = "http://schemas.microsoft.com/office/powerpoint/2010/main";

// Byte spans come from the namespace-aware parser, never from matching target
// substrings. Only requested spans are replaced; unknown package/XML data stays.
struct MediaControlNode {
    name: String,
    namespace: String,
    qname: String,
    attributes: BTreeMap<String, String>,
    parent: Option<usize>,
    start: usize,
    open_end: usize,
    close_start: usize,
    end: usize,
    empty: bool,
}

impl MediaControlNode {
    fn is(&self, namespace: &str, name: &str) -> bool {
        self.namespace == namespace && self.name == name
    }

    fn attr(&self, name: &str) -> Option<&str> {
        self.attributes.get(name).map(String::as_str)
    }
}

fn media_control_nodes(xml: &str) -> Result<Vec<MediaControlNode>, WolfPptError> {
    let bom = utf8_bom_offset(xml.as_bytes());
    let mut reader = quick_xml::NsReader::from_str(xml);
    let mut nodes: Vec<MediaControlNode> = Vec::new();
    let mut stack = Vec::new();
    loop {
        let start = bom + reader.buffer_position() as usize;
        let (resolved, event) = reader
            .read_resolved_event()
            .map_err(media_control_refusal)?;
        let namespace = match resolved {
            quick_xml::name::ResolveResult::Bound(ns) => {
                String::from_utf8_lossy(ns.0.as_bytes()).into_owned()
            }
            quick_xml::name::ResolveResult::Unbound => String::new(),
            quick_xml::name::ResolveResult::Unknown(_) => {
                return Err(media_control_refusal("unbound XML namespace"))
            }
        };
        let empty = matches!(event, Event::Empty(_));
        match event {
            Event::Start(event) | Event::Empty(event) => {
                let mut attributes = BTreeMap::new();
                for attribute in event.attributes() {
                    let attribute = attribute.map_err(media_control_refusal)?;
                    let raw_key = attribute.key.as_ref().as_bytes();
                    let (resolved, local) = reader.resolver().resolve_attribute(attribute.key);
                    let key = if raw_key == b"xmlns" || raw_key.starts_with(b"xmlns:") {
                        String::from_utf8_lossy(raw_key).into_owned()
                    } else {
                        match resolved {
                            quick_xml::name::ResolveResult::Bound(ns) => format!(
                                "{{{}}}{}",
                                String::from_utf8_lossy(ns.0.as_bytes()),
                                String::from_utf8_lossy(local.as_ref().as_bytes())
                            ),
                            quick_xml::name::ResolveResult::Unbound => {
                                String::from_utf8_lossy(attribute.key.as_ref().as_bytes())
                                    .into_owned()
                            }
                            quick_xml::name::ResolveResult::Unknown(_) => {
                                return Err(media_control_refusal("unbound attribute namespace"))
                            }
                        }
                    };
                    let value = attribute
                        .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                        .map_err(media_control_refusal)?
                        .into_owned();
                    if attributes.insert(key, value).is_some() {
                        return Err(media_control_refusal("duplicate XML attribute"));
                    }
                }
                let open_end = bom + reader.buffer_position() as usize;
                nodes.push(MediaControlNode {
                    name: String::from_utf8_lossy(event.local_name().as_ref().as_bytes())
                        .into_owned(),
                    namespace,
                    qname: String::from_utf8_lossy(event.name().as_ref().as_bytes()).into_owned(),
                    attributes,
                    parent: stack.last().copied(),
                    start,
                    open_end,
                    close_start: open_end,
                    end: open_end,
                    empty,
                });
                if !empty {
                    stack.push(nodes.len() - 1);
                }
            }
            Event::End(_) => {
                let index = stack
                    .pop()
                    .ok_or_else(|| media_control_refusal("invalid XML nesting"))?;
                nodes[index].close_start = start;
                nodes[index].end = bom + reader.buffer_position() as usize;
            }
            Event::DocType(_) => return Err(media_control_refusal("DTD media XML is unsupported")),
            Event::Eof => break,
            _ => {}
        }
    }
    if !stack.is_empty()
        || nodes.iter().filter(|node| node.parent.is_none()).count() != 1
        || nodes
            .first()
            .is_none_or(|node| !node.is(MEDIA_CONTROL_P_NS, "sld"))
    {
        return Err(media_control_refusal(
            "only complete Transitional slide XML is writable",
        ));
    }
    Ok(nodes)
}

fn media_control_descendant(nodes: &[MediaControlNode], child: usize, parent: usize) -> bool {
    let mut current = Some(child);
    while let Some(index) = current {
        if index == parent {
            return true;
        }
        current = nodes[index].parent;
    }
    false
}

fn media_control_child(
    nodes: &[MediaControlNode],
    parent: usize,
    namespace: &str,
    name: &str,
) -> Result<Option<usize>, WolfPptError> {
    let mut children = nodes
        .iter()
        .enumerate()
        .filter(|(_, node)| node.parent == Some(parent) && node.is(namespace, name));
    let found = children.next().map(|(index, _)| index);
    if children.next().is_some() {
        return Err(media_control_refusal(format!(
            "duplicate {name} XML control"
        )));
    }
    Ok(found)
}

type MediaControlEdit = (usize, usize, String);

fn media_control_apply(
    xml: &str,
    mut edits: Vec<MediaControlEdit>,
) -> Result<String, WolfPptError> {
    edits.sort_by_key(|edit| (edit.0, edit.1));
    for pair in edits.windows(2) {
        if pair[0].1 > pair[1].0 {
            return Err(media_control_refusal("overlapping media controls"));
        }
    }
    let mut output = xml.to_string();
    for (start, end, replacement) in edits.into_iter().rev() {
        output.replace_range(start..end, &replacement);
    }
    Ok(output)
}

fn media_control_contents(xml: &str, node: &MediaControlNode, contents: &str) -> MediaControlEdit {
    if node.empty {
        (
            node.start,
            node.end,
            format!(
                "{}>{contents}</{}>",
                &xml[node.start..node.open_end - 2],
                node.qname
            ),
        )
    } else {
        (node.open_end, node.close_start, contents.to_string())
    }
}

fn media_control_append(xml: &str, node: &MediaControlNode, contents: &str) -> MediaControlEdit {
    if node.empty {
        media_control_contents(xml, node, contents)
    } else {
        (node.close_start, node.close_start, contents.to_string())
    }
}

fn media_control_attribute(
    xml: &str,
    node: &MediaControlNode,
    name: &str,
    value: Option<String>,
) -> Result<MediaControlEdit, WolfPptError> {
    // Scan the already validated start tag, retaining whitespace, quote style,
    // and every unrequested attribute byte.
    let bytes = xml.as_bytes();
    let mut cursor = node.start + 1 + node.qname.len();
    while cursor < node.open_end {
        let whitespace = cursor;
        while cursor < node.open_end && bytes[cursor].is_ascii_whitespace() {
            cursor += 1;
        }
        if matches!(bytes[cursor], b'/' | b'>') {
            break;
        }
        let key_start = cursor;
        while cursor < node.open_end
            && !bytes[cursor].is_ascii_whitespace()
            && bytes[cursor] != b'='
        {
            cursor += 1;
        }
        let key_end = cursor;
        while cursor < node.open_end && bytes[cursor] != b'=' {
            cursor += 1;
        }
        cursor += 1;
        while cursor < node.open_end && bytes[cursor].is_ascii_whitespace() {
            cursor += 1;
        }
        let quote = bytes[cursor];
        cursor += 1;
        while cursor < node.open_end && bytes[cursor] != quote {
            cursor += 1;
        }
        cursor += 1;
        if &xml[key_start..key_end] == name {
            return Ok((
                whitespace,
                cursor,
                value.map_or_else(String::new, |value| {
                    format!(" {name}=\"{}\"", xml_attr(&value))
                }),
            ));
        }
    }
    let at = node.open_end - if node.empty { 2 } else { 1 };
    Ok((
        at,
        at,
        value.map_or_else(String::new, |value| {
            format!(" {name}=\"{}\"", xml_attr(&value))
        }),
    ))
}

struct MediaControlScope {
    shape: usize,
    nv_pr: usize,
    kind: &'static str,
    media: Option<usize>,
    own: Option<usize>,
    chain: Vec<usize>,
    shapes: BTreeMap<u64, usize>,
    times: BTreeMap<u64, usize>,
}

fn media_control_scope(
    nodes: &[MediaControlNode],
    shape_id: u64,
) -> Result<MediaControlScope, WolfPptError> {
    let mut shapes = BTreeMap::new();
    let mut times = BTreeMap::new();
    for (index, node) in nodes.iter().enumerate() {
        if node.is(MEDIA_CONTROL_P_NS, "cNvPr") || node.is(MEDIA_CONTROL_P_NS, "cTn") {
            let id = node
                .attr("id")
                .and_then(|id| id.parse::<u64>().ok())
                .filter(|id| {
                    *id <= u64::from(u32::MAX) && node.attr("id") == Some(id.to_string().as_str())
                })
                .ok_or_else(|| media_control_refusal("missing or noncanonical XML id"))?;
            let map = if node.name == "cTn" {
                &mut times
            } else {
                &mut shapes
            };
            if map.insert(id, index).is_some() {
                return Err(media_control_refusal("duplicate shape or time-node id"));
            }
        }
    }
    let properties = *shapes
        .get(&shape_id)
        .ok_or_else(|| media_control_refusal(format!("shape {shape_id} does not exist")))?;
    let shape = nodes[properties]
        .parent
        .and_then(|index| nodes[index].parent)
        .ok_or_else(|| media_control_refusal("media shape has no owner"))?;
    if !nodes[shape].is(MEDIA_CONTROL_P_NS, "pic") {
        return Err(media_control_refusal("target is not a media picture"));
    }
    let mut source = None;
    let mut extension = None;
    for (index, node) in nodes.iter().enumerate() {
        if !media_control_descendant(nodes, index, shape) {
            continue;
        }
        if node.namespace == MEDIA_CONTROL_A_NS
            && matches!(node.name.as_str(), "audioFile" | "videoFile")
            && source.replace(index).is_some()
        {
            return Err(media_control_refusal("ambiguous media source"));
        }
        if node.is(MEDIA_CONTROL_P14_NS, "media") && extension.replace(index).is_some() {
            return Err(media_control_refusal("duplicate p14 media control"));
        }
    }
    let source = source.ok_or_else(|| media_control_refusal("media source is missing"))?;
    let nv_pr = nodes[source]
        .parent
        .filter(|index| nodes[*index].is(MEDIA_CONTROL_P_NS, "nvPr"))
        .ok_or_else(|| media_control_refusal("media source is not owned by nvPr"))?;
    let kind = if nodes[source].name == "audioFile" {
        "audio"
    } else {
        "video"
    };
    let mut media = None;
    for (index, _) in nodes
        .iter()
        .enumerate()
        .filter(|(_, node)| node.is(MEDIA_CONTROL_P_NS, "cMediaNode"))
    {
        let target_el = media_control_child(nodes, index, MEDIA_CONTROL_P_NS, "tgtEl")?
            .ok_or_else(|| media_control_refusal("media timing target is missing"))?;
        let target = media_control_child(nodes, target_el, MEDIA_CONTROL_P_NS, "spTgt")?
            .ok_or_else(|| media_control_refusal("media timing target is missing"))?;
        if nodes
            .iter()
            .any(|child| child.parent == Some(target_el) && !child.is(MEDIA_CONTROL_P_NS, "spTgt"))
            || nodes.iter().any(|child| child.parent == Some(target))
        {
            return Err(media_control_refusal(
                "unsupported media timing target topology",
            ));
        }
        let target_id = nodes[target]
            .attr("spid")
            .and_then(|id| id.parse::<u64>().ok())
            .filter(|id| shapes.contains_key(id))
            .ok_or_else(|| media_control_refusal("media timing references a missing shape"))?;
        if target_id == shape_id {
            if media.replace(index).is_some() {
                return Err(media_control_refusal("duplicate media timing target"));
            }
            if nodes[index]
                .parent
                .is_none_or(|parent| !nodes[parent].is(MEDIA_CONTROL_P_NS, kind))
            {
                return Err(media_control_refusal(
                    "media timing kind disagrees with source",
                ));
            }
        }
    }
    let own = media
        .map(|index| media_control_child(nodes, index, MEDIA_CONTROL_P_NS, "cTn"))
        .transpose()?
        .flatten();
    if media.is_some() && own.is_none() {
        return Err(media_control_refusal("media timing cTn is missing"));
    }
    let mut chain = own.into_iter().collect::<Vec<_>>();
    let mut parent = media.and_then(|index| nodes[index].parent);
    while let Some(index) = parent {
        if nodes[index].is(MEDIA_CONTROL_P_NS, "cTn") {
            chain.push(index);
        }
        parent = nodes[index].parent;
    }
    Ok(MediaControlScope {
        shape,
        nv_pr,
        kind,
        media,
        own,
        chain,
        shapes,
        times,
    })
}

fn media_control_exclusive(nodes: &[MediaControlNode], wrapper: usize, media: usize) -> bool {
    // A condition on a wrapper starts every timing child, not merely media.
    // Refuse any other timed behavior, even one that targets the same shape.
    !nodes.iter().enumerate().any(|(index, node)| {
        media_control_descendant(nodes, index, wrapper)
            && !media_control_descendant(nodes, index, media)
            && (node.is(MEDIA_CONTROL_P_NS, "cMediaNode")
                || node.is(MEDIA_CONTROL_P_NS, "cBhvr")
                || (node.namespace == MEDIA_CONTROL_P_NS
                    && matches!(
                        node.name.as_str(),
                        "cmd"
                            | "anim"
                            | "animClr"
                            | "animEffect"
                            | "animMotion"
                            | "animRot"
                            | "animScale"
                            | "set"
                    )))
    })
}

fn media_control_extensions(
    xml: &str,
    shape_id: u64,
    controls: &MediaControls,
    relationships: &[RelationshipSummary],
) -> Result<String, WolfPptError> {
    let nodes = media_control_nodes(xml)?;
    let scope = media_control_scope(&nodes, shape_id)?;
    let media = nodes
        .iter()
        .enumerate()
        .find(|(index, node)| {
            node.is(MEDIA_CONTROL_P14_NS, "media")
                && media_control_descendant(&nodes, *index, scope.shape)
        })
        .map(|(index, _)| index);
    if let Some(media) = media {
        for child in nodes.iter().filter(|node| node.parent == Some(media)) {
            if child.namespace == MEDIA_CONTROL_P14_NS
                && !matches!(child.name.as_str(), "trim" | "fade" | "bmkLst" | "extLst")
            {
                return Err(media_control_refusal("unknown p14 media control"));
            }
        }
        for name in ["trim", "fade", "bmkLst"] {
            if let Some(child) = media_control_child(&nodes, media, MEDIA_CONTROL_P14_NS, name)? {
                let allowed = match name {
                    "trim" => &["st", "end"][..],
                    "fade" => &["in", "out"][..],
                    _ => &[][..],
                };
                if name != "bmkLst" {
                    for (attribute, value) in &nodes[child].attributes {
                        if allowed.contains(&attribute.as_str()) {
                            media_control_milliseconds(value.parse().unwrap_or(f64::NAN))?;
                        } else if !attribute.starts_with('{') && !attribute.starts_with("xmlns") {
                            return Err(media_control_refusal("unknown trim or fade attribute"));
                        }
                    }
                } else if nodes.iter().any(|node| {
                    node.parent == Some(child)
                        && node.namespace == MEDIA_CONTROL_P14_NS
                        && !matches!(node.name.as_str(), "bmk" | "extLst")
                }) {
                    return Err(media_control_refusal("unknown bookmark control"));
                }
            }
        }
    }
    let wanted = controls.trim_start.is_some()
        || controls.trim_end.is_some()
        || controls.fade_in.is_some()
        || controls.fade_out.is_some()
        || controls.bookmarks.is_some();
    if !wanted {
        return Ok(xml.to_string());
    }
    if media.is_none() {
        let source = nodes
            .iter()
            .find(|node| {
                node.parent == Some(scope.nv_pr)
                    && node.namespace == MEDIA_CONTROL_A_NS
                    && matches!(node.name.as_str(), "audioFile" | "videoFile")
            })
            .ok_or_else(|| media_control_refusal("media source is missing"))?;
        let link = source
            .attr(&format!("{{{MEDIA_CONTROL_R_NS}}}link"))
            .ok_or_else(|| media_control_refusal("media source relationship is missing"))?;
        let mut sources = relationships
            .iter()
            .filter(|relationship| relationship.id == link);
        let source = sources
            .next()
            .ok_or_else(|| media_control_refusal("media relationship is missing"))?;
        if sources.next().is_some() {
            return Err(media_control_refusal("duplicate media relationship id"));
        }
        let mut matching = relationships.iter().filter(|relationship| {
            relationship.relationship_type.ends_with("/media")
                && relationship.target == source.target
                && relationship.target_mode == source.target_mode
        });
        let relationship = matching.next().unwrap_or(source);
        if matching.next().is_some() {
            return Err(media_control_refusal("ambiguous media relationships"));
        }
        let attribute = if relationship.target_mode.as_deref() == Some("External") {
            "link"
        } else {
            "embed"
        };
        let extension = format!(
            r#"<p:ext xmlns:p="{MEDIA_CONTROL_P_NS}" uri="{{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}}"><p14:media xmlns:p14="{MEDIA_CONTROL_P14_NS}" xmlns:r="{MEDIA_CONTROL_R_NS}" r:{attribute}="{}"/></p:ext>"#,
            xml_attr(&relationship.id)
        );
        let list = media_control_child(&nodes, scope.nv_pr, MEDIA_CONTROL_P_NS, "extLst")?;
        let edit = match list {
            Some(list) => media_control_append(xml, &nodes[list], &extension),
            None => media_control_append(
                xml,
                &nodes[scope.nv_pr],
                &format!(r#"<p:extLst xmlns:p="{MEDIA_CONTROL_P_NS}">{extension}</p:extLst>"#),
            ),
        };
        let with_media = media_control_apply(xml, vec![edit])?;
        return media_control_extensions(&with_media, shape_id, controls, relationships);
    }
    let media = media.unwrap();
    let mut edits = Vec::new();
    let mut additions = Vec::new();
    for (name, first, second, first_name, second_name) in [
        ("trim", controls.trim_start, controls.trim_end, "st", "end"),
        ("fade", controls.fade_in, controls.fade_out, "in", "out"),
    ] {
        if first.is_none() && second.is_none() {
            continue;
        }
        let child = media_control_child(&nodes, media, MEDIA_CONTROL_P14_NS, name)?;
        if let Some(child) = child {
            for (attribute, value) in [(first_name, first), (second_name, second)] {
                if let Some(value) = value {
                    edits.push(media_control_attribute(
                        xml,
                        &nodes[child],
                        attribute,
                        Some(media_control_milliseconds(value)?.to_string()),
                    )?);
                }
            }
        } else {
            additions.push((name, format!(
                r#"<p14:{name} xmlns:p14="{MEDIA_CONTROL_P14_NS}" {first_name}="{}" {second_name}="{}"/>"#,
                media_control_milliseconds(first.unwrap_or(0.0))?,
                media_control_milliseconds(second.unwrap_or(0.0))?
            )));
        }
    }
    if let Some(bookmarks) = &controls.bookmarks {
        let mut names = std::collections::BTreeSet::new();
        let mut contents = String::new();
        for bookmark in bookmarks {
            if bookmark.name.is_empty() || !names.insert(&bookmark.name) {
                return Err(media_control_refusal(
                    "bookmark names must be nonempty and unique",
                ));
            }
            contents.push_str(&format!(
                r#"<p14:bmk xmlns:p14="{MEDIA_CONTROL_P14_NS}" name="{}" time="{}"/>"#,
                media_control_bookmark_name(&bookmark.name)?,
                media_control_milliseconds(bookmark.time)?
            ));
        }
        let list = media_control_child(&nodes, media, MEDIA_CONTROL_P14_NS, "bmkLst")?;
        if let Some(list) = list {
            let mut replacement = String::new();
            // Only bmk children are replaced; retain vendor extension children.
            let mut at = nodes[list].open_end;
            for child in nodes.iter().filter(|node| node.parent == Some(list)) {
                if child.is(MEDIA_CONTROL_P14_NS, "bmk") {
                    replacement.push_str(&xml[at..child.start]);
                    at = child.end;
                }
            }
            if !nodes[list].empty {
                replacement.push_str(&xml[at..nodes[list].close_start]);
            }
            replacement.push_str(&contents);
            if bookmarks.is_empty()
                && !nodes
                    .iter()
                    .any(|node| node.parent == Some(list) && !node.is(MEDIA_CONTROL_P14_NS, "bmk"))
            {
                edits.push((nodes[list].start, nodes[list].end, replacement));
            } else {
                edits.push(media_control_contents(xml, &nodes[list], &replacement));
            }
        } else if !bookmarks.is_empty() {
            additions.push((
                "bmkLst",
                format!(
                    r#"<p14:bmkLst xmlns:p14="{MEDIA_CONTROL_P14_NS}">{contents}</p14:bmkLst>"#
                ),
            ));
        }
    }
    if nodes[media].empty && !additions.is_empty() {
        let contents = additions
            .into_iter()
            .map(|(_, value)| value)
            .collect::<String>();
        edits.push(media_control_append(xml, &nodes[media], &contents));
    } else {
        let rank = |name: &str| match name {
            "trim" => 0,
            "fade" => 1,
            "bmkLst" => 2,
            _ => 3,
        };
        for (name, contents) in additions {
            let at = nodes
                .iter()
                .filter(|node| node.parent == Some(media))
                .find(|node| {
                    node.namespace == MEDIA_CONTROL_P14_NS && rank(&node.name) > rank(name)
                })
                .map_or(nodes[media].close_start, |node| node.start);
            edits.push((at, at, contents));
        }
    }
    media_control_apply(xml, edits)
}

fn media_control_conditions(
    nodes: &[MediaControlNode],
    owner: usize,
) -> Result<Option<usize>, WolfPptError> {
    let list = media_control_child(nodes, owner, MEDIA_CONTROL_P_NS, "stCondLst")?;
    if let Some(list) = list {
        for (index, node) in nodes
            .iter()
            .enumerate()
            .filter(|(_, node)| node.parent == Some(list))
        {
            if !node.is(MEDIA_CONTROL_P_NS, "cond")
                || node.attributes.keys().any(|key| {
                    !matches!(key.as_str(), "evt" | "delay" | "xmlns")
                        && !key.starts_with("xmlns:")
                        && !key.starts_with("{http://www.w3.org/2000/xmlns/}")
                })
                || node
                    .attr("evt")
                    .is_some_and(|event| !matches!(event, "onClick" | "onBegin" | "onEnd"))
            {
                return Err(media_control_refusal("unknown media start condition"));
            }
            if let Some(delay) = node.attr("delay") {
                if delay != "indefinite" {
                    media_control_milliseconds(delay.parse().unwrap_or(f64::NAN))?;
                }
            }
            for child in nodes.iter().filter(|child| child.parent == Some(index)) {
                if child.namespace != MEDIA_CONTROL_P_NS
                    || !matches!(child.name.as_str(), "tgtEl" | "tn")
                {
                    return Err(media_control_refusal("unsupported media condition target"));
                }
            }
            if let Some(target_el) = media_control_child(nodes, index, MEDIA_CONTROL_P_NS, "tgtEl")?
            {
                let target = media_control_child(nodes, target_el, MEDIA_CONTROL_P_NS, "spTgt")?
                    .ok_or_else(|| media_control_refusal("unsupported condition shape target"))?;
                if nodes.iter().any(|child| {
                    child.parent == Some(target_el) && !child.is(MEDIA_CONTROL_P_NS, "spTgt")
                }) || nodes.iter().any(|child| child.parent == Some(target))
                {
                    return Err(media_control_refusal(
                        "unsupported condition target topology",
                    ));
                }
            }
            if media_control_child(nodes, index, MEDIA_CONTROL_P_NS, "tgtEl")?.is_some()
                && media_control_child(nodes, index, MEDIA_CONTROL_P_NS, "tn")?.is_some()
            {
                return Err(media_control_refusal("ambiguous media condition target"));
            }
        }
    }
    Ok(list)
}

fn media_control_trigger_edits(
    xml: &str,
    shape_id: u64,
    controls: &MediaControls,
) -> Result<String, WolfPptError> {
    let Some(triggers) = &controls.triggers else {
        return Ok(xml.to_string());
    };
    let nodes = media_control_nodes(xml)?;
    let scope = media_control_scope(&nodes, shape_id)?;
    let own = scope
        .own
        .ok_or_else(|| media_control_refusal("media timing is missing"))?;
    let media = scope.media.unwrap();
    let own_id = nodes[own]
        .attr("id")
        .unwrap()
        .parse::<u64>()
        .map_err(media_control_refusal)?;
    let mut requested: BTreeMap<u64, String> = BTreeMap::new();
    let mut new_ids = Vec::new();
    for trigger in triggers {
        let owner_id = trigger
            .node_id
            .as_ref()
            .map(MediaControlId::id)
            .transpose()?
            .unwrap_or(own_id);
        if let Some(owner) = scope.times.get(&owner_id) {
            if !scope.chain.contains(owner) {
                return Err(media_control_refusal(
                    "trigger node_id is not a media-governing cTn",
                ));
            }
            if *owner != own && !media_control_exclusive(&nodes, *owner, media) {
                return Err(media_control_refusal(
                    "trigger wrapper is shared with another timing behavior",
                ));
            }
        } else if !new_ids.contains(&owner_id) {
            new_ids.push(owner_id);
        }
        let event = trigger
            .event
            .as_deref()
            .ok_or_else(|| media_control_refusal("trigger event is required"))?;
        if !matches!(event, "onClick" | "onBegin" | "onEnd") {
            return Err(media_control_refusal("unsupported trigger event"));
        }
        let shape_target = trigger
            .shape_id
            .as_ref()
            .map(MediaControlId::id)
            .transpose()?;
        let time_target = trigger
            .time_node
            .as_ref()
            .map(MediaControlId::id)
            .transpose()?;
        if shape_target.is_some() == time_target.is_some()
            || (event == "onClick" && shape_target.is_none())
            || (trigger.bookmark.is_some() && shape_target.is_none())
        {
            return Err(media_control_refusal(
                "trigger requires one compatible target",
            ));
        }
        if let Some(target) = shape_target {
            if !scope.shapes.contains_key(&target)
                || (target == shape_id && event != "onClick" && trigger.bookmark.is_none())
            {
                return Err(media_control_refusal(
                    "missing or self-referential shape trigger target",
                ));
            }
        }
        if let Some(target) = time_target {
            let target_index = scope
                .times
                .get(&target)
                .ok_or_else(|| media_control_refusal("trigger references a missing time node"))?;
            if scope.chain.contains(target_index)
                || media_control_descendant(&nodes, *target_index, own)
            {
                return Err(media_control_refusal(
                    "self or ancestor timing trigger would create a cycle",
                ));
            }
        }
        let delay = match &trigger.delay {
            Some(delay) => {
                delay.milliseconds()?;
                let value = match delay {
                    MediaControlDelay::Text(value) => value.clone(),
                    MediaControlDelay::Number(value) => value.to_string(),
                };
                format!(r#" delay="{}""#, xml_attr(&value))
            }
            None => String::new(),
        };
        let target = if let Some(target) = shape_target {
            let bookmark = trigger
                .bookmark
                .as_ref()
                .map(|bookmark| {
                    media_control_bookmark_name(bookmark)
                        .map(|name| format!(r#" bmkName="{name}""#))
                })
                .transpose()?
                .unwrap_or_default();
            format!(r#"<p:tgtEl><p:spTgt spid="{target}"{bookmark}/></p:tgtEl>"#)
        } else {
            format!(r#"<p:tn val="{}"/>"#, time_target.unwrap())
        };
        requested.entry(owner_id).or_default().push_str(&format!(
            r#"<p:cond xmlns:p="{MEDIA_CONTROL_P_NS}" evt="{event}"{delay}>{target}</p:cond>"#
        ));
    }
    let mut edits = Vec::new();
    for owner in &scope.chain {
        let list = media_control_conditions(&nodes, *owner)?;
        let id = nodes[*owner]
            .attr("id")
            .unwrap()
            .parse::<u64>()
            .map_err(media_control_refusal)?;
        let replacement = requested.remove(&id);
        if *owner != own && !media_control_exclusive(&nodes, *owner, media) {
            if list.is_some_and(|list| nodes.iter().any(|node| node.parent == Some(list))) {
                return Err(media_control_refusal(
                    "cannot replace shared ancestor start conditions",
                ));
            }
            continue;
        }
        if let Some(list) = list {
            let mut contents = String::new();
            let mut at = nodes[list].open_end;
            for condition in nodes.iter().filter(|node| node.parent == Some(list)) {
                contents.push_str(&xml[at..condition.start]);
                at = condition.end;
            }
            if !nodes[list].empty {
                contents.push_str(&xml[at..nodes[list].close_start]);
            }
            contents.push_str(replacement.as_deref().unwrap_or(""));
            if replacement.is_none() {
                edits.push((nodes[list].start, nodes[list].end, contents));
            } else {
                edits.push(media_control_contents(xml, &nodes[list], &contents));
            }
        } else if let Some(replacement) = replacement {
            let contents = format!(
                r#"<p:stCondLst xmlns:p="{MEDIA_CONTROL_P_NS}">{replacement}</p:stCondLst>"#
            );
            if nodes[*owner].empty {
                edits.push(media_control_append(xml, &nodes[*owner], &contents));
            } else {
                edits.push((nodes[*owner].open_end, nodes[*owner].open_end, contents));
            }
        }
    }
    if !new_ids.is_empty() {
        let media_element = nodes[media].parent.unwrap();
        let mut inner = Vec::new();
        let mut outer = Vec::new();
        let start = nodes[media_element].start;
        let end = nodes[media_element].end;
        for (edit_start, edit_end, replacement) in edits {
            if edit_start >= start && edit_end <= end {
                inner.push((edit_start - start, edit_end - start, replacement));
            } else {
                outer.push((edit_start, edit_end, replacement));
            }
        }
        edits = outer;
        let mut wrapper = media_control_apply(&xml[start..end], inner)?;
        for id in new_ids {
            let contents = requested.remove(&id).unwrap_or_default();
            wrapper = format!(
                r#"<p:par xmlns:p="{MEDIA_CONTROL_P_NS}"><p:cTn id="{id}" fill="hold"><p:stCondLst>{contents}</p:stCondLst><p:childTnLst>{wrapper}</p:childTnLst></p:cTn></p:par>"#
            );
        }
        edits.push((start, end, wrapper));
    }
    media_control_apply(xml, edits)
}

fn media_control_validate_references(
    nodes: &[MediaControlNode],
    scope: &MediaControlScope,
) -> Result<(), WolfPptError> {
    let mut bookmarks: BTreeMap<u64, std::collections::BTreeSet<String>> = BTreeMap::new();
    for (id, properties) in &scope.shapes {
        let Some(shape) = nodes[*properties]
            .parent
            .and_then(|parent| nodes[parent].parent)
        else {
            continue;
        };
        if !nodes[shape].is(MEDIA_CONTROL_P_NS, "pic") {
            continue;
        }
        for (index, _) in nodes
            .iter()
            .enumerate()
            .filter(|(_, node)| node.is(MEDIA_CONTROL_P14_NS, "media"))
        {
            if !media_control_descendant(nodes, index, shape) {
                continue;
            }
            if let Some(list) = media_control_child(nodes, index, MEDIA_CONTROL_P14_NS, "bmkLst")? {
                for child in nodes.iter().filter(|node| {
                    node.parent == Some(list) && node.is(MEDIA_CONTROL_P14_NS, "bmk")
                }) {
                    let name = child
                        .attr("name")
                        .filter(|name| !name.is_empty())
                        .ok_or_else(|| media_control_refusal("invalid bookmark name"))?;
                    if !bookmarks.entry(*id).or_default().insert(name.to_string()) {
                        return Err(media_control_refusal("duplicate bookmark name"));
                    }
                    media_control_milliseconds(
                        child
                            .attr("time")
                            .and_then(|time| time.parse().ok())
                            .unwrap_or(f64::NAN),
                    )?;
                }
            }
        }
    }
    let mut edges: BTreeMap<u64, Vec<u64>> = BTreeMap::new();
    for (index, node) in nodes
        .iter()
        .enumerate()
        .filter(|(_, node)| node.is(MEDIA_CONTROL_P_NS, "cond"))
    {
        let owner = nodes[index]
            .parent
            .filter(|list| nodes[*list].is(MEDIA_CONTROL_P_NS, "stCondLst"))
            .and_then(|list| nodes[list].parent)
            .filter(|owner| nodes[*owner].is(MEDIA_CONTROL_P_NS, "cTn"));
        for target in nodes
            .iter()
            .filter(|target| target.parent == Some(index) && target.is(MEDIA_CONTROL_P_NS, "tn"))
        {
            let id = target
                .attr("val")
                .and_then(|value| value.parse::<u64>().ok())
                .filter(|id| scope.times.contains_key(id))
                .ok_or_else(|| media_control_refusal("condition references missing time node"))?;
            if let Some(owner) = owner {
                let owner_id = nodes[owner]
                    .attr("id")
                    .unwrap()
                    .parse::<u64>()
                    .map_err(media_control_refusal)?;
                edges.entry(owner_id).or_default().push(id);
            }
        }
        if let Some(target_el) = media_control_child(nodes, index, MEDIA_CONTROL_P_NS, "tgtEl")? {
            if let Some(target) =
                media_control_child(nodes, target_el, MEDIA_CONTROL_P_NS, "spTgt")?
            {
                let id = nodes[target]
                    .attr("spid")
                    .and_then(|value| value.parse::<u64>().ok())
                    .filter(|id| scope.shapes.contains_key(id))
                    .ok_or_else(|| media_control_refusal("condition references missing shape"))?;
                if let Some(bookmark) = nodes[target].attr("bmkName") {
                    if !bookmarks
                        .get(&id)
                        .is_some_and(|names| names.contains(bookmark))
                    {
                        return Err(media_control_refusal(
                            "condition references missing bookmark",
                        ));
                    }
                }
                if nodes[target].attr("bmkName").is_none()
                    && matches!(node.attr("evt"), Some("onBegin" | "onEnd"))
                {
                    if let Some(owner) = owner {
                        let owner_id = nodes[owner]
                            .attr("id")
                            .unwrap()
                            .parse::<u64>()
                            .map_err(media_control_refusal)?;
                        for (behavior, _) in nodes.iter().enumerate().filter(|(_, candidate)| {
                            candidate.is(MEDIA_CONTROL_P_NS, "cMediaNode")
                                || candidate.is(MEDIA_CONTROL_P_NS, "cBhvr")
                        }) {
                            let target_el =
                                media_control_child(nodes, behavior, MEDIA_CONTROL_P_NS, "tgtEl")?;
                            let own =
                                media_control_child(nodes, behavior, MEDIA_CONTROL_P_NS, "cTn")?;
                            if let (Some(target_el), Some(own)) = (target_el, own) {
                                if let Some(shape) = media_control_child(
                                    nodes,
                                    target_el,
                                    MEDIA_CONTROL_P_NS,
                                    "spTgt",
                                )? {
                                    if nodes[shape]
                                        .attr("spid")
                                        .and_then(|value| value.parse::<u64>().ok())
                                        == Some(id)
                                    {
                                        let dependency = nodes[own]
                                            .attr("id")
                                            .unwrap()
                                            .parse::<u64>()
                                            .map_err(media_control_refusal)?;
                                        edges.entry(owner_id).or_default().push(dependency);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    // Timing ownership also supplies dependency edges: a child cannot start
    // before its ancestor. Combining these with event edges catches indirect
    // cycles through newly created wrappers or unrelated timing nodes.
    for (id, index) in &scope.times {
        let mut parent = nodes[*index].parent;
        while let Some(ancestor) = parent {
            if nodes[ancestor].is(MEDIA_CONTROL_P_NS, "cTn") {
                let parent_id = nodes[ancestor]
                    .attr("id")
                    .unwrap()
                    .parse::<u64>()
                    .map_err(media_control_refusal)?;
                edges.entry(*id).or_default().push(parent_id);
                break;
            }
            parent = nodes[ancestor].parent;
        }
    }
    fn visit(
        id: u64,
        edges: &BTreeMap<u64, Vec<u64>>,
        visiting: &mut std::collections::BTreeSet<u64>,
        visited: &mut std::collections::BTreeSet<u64>,
    ) -> bool {
        if visited.contains(&id) {
            return true;
        }
        if !visiting.insert(id) {
            return false;
        }
        if edges.get(&id).is_some_and(|targets| {
            targets
                .iter()
                .any(|target| !visit(*target, edges, visiting, visited))
        }) {
            return false;
        }
        visiting.remove(&id);
        visited.insert(id);
        true
    }
    let mut visiting = std::collections::BTreeSet::new();
    let mut visited = std::collections::BTreeSet::new();
    for id in edges.keys() {
        if !visit(*id, &edges, &mut visiting, &mut visited) {
            return Err(media_control_refusal("cyclic timing trigger dependencies"));
        }
    }
    Ok(())
}

/// Apply validated deltas without rebuilding media timing or other ZIP parts.
/// All validation and XML construction finishes before creating the output.
pub fn set_slide_media_controls(
    input_path: impl AsRef<Path>,
    output_path: impl AsRef<Path>,
    slide_index: usize,
    shape_id: u64,
    controls: &MediaControls,
) -> Result<(), WolfPptError> {
    if controls.volume.is_some_and(|volume| volume > 100) {
        return Err(media_control_refusal(
            "media volume must be between 0 and 100",
        ));
    }
    if controls.auto_play == Some(true)
        && controls
            .triggers
            .as_ref()
            .is_some_and(|triggers| !triggers.is_empty())
    {
        return Err(media_control_refusal(
            "automatic playback conflicts with explicit start triggers",
        ));
    }
    if input_path.as_ref() == output_path.as_ref()
        || std::fs::canonicalize(output_path.as_ref())
            .ok()
            .is_some_and(|output| {
                std::fs::canonicalize(input_path.as_ref()).ok().as_ref() == Some(&output)
            })
    {
        return Err(media_control_refusal(
            "input and output must be distinct package paths",
        ));
    }
    let mut archive = ZipArchive::new(File::open(input_path.as_ref())?)?;
    let slide_part = slide_part_at_index(&mut archive, slide_index)?
        .ok_or_else(|| media_control_refusal("slide index was not found"))?;
    let xml = read_archive_text(&mut archive, &slide_part)?
        .ok_or_else(|| media_control_refusal("slide XML was not found"))?;
    let nodes = media_control_nodes(&xml)?;
    let scope = media_control_scope(&nodes, shape_id)?;
    for owner in &scope.chain {
        media_control_conditions(&nodes, *owner)?;
    }
    if scope.kind == "video" && controls.play_across_slides == Some(true) {
        return Err(media_control_refusal("play_across_slides is audio-only"));
    }
    let kind = scope.kind;
    let relationships = read_archive_text(&mut archive, &relationship_part_name(&slide_part))?
        .map(|xml| parse_relationships(xml.as_bytes()))
        .unwrap_or_default();
    let mut rewritten = media_control_extensions(&xml, shape_id, controls, &relationships)?;
    if scope.media.is_none() {
        rewritten =
            add_media_timing_to_slide_xml(&rewritten, shape_id, kind, false, false, 80, 1, None)
                .map_err(media_control_refusal)?;
    }
    let nodes = media_control_nodes(&rewritten)?;
    let scope = media_control_scope(&nodes, shape_id)?;
    let media = scope
        .media
        .ok_or_else(|| media_control_refusal("cannot create media timing in this topology"))?;
    let own = scope.own.unwrap();
    let across_slide_count = slide_parts(&mut archive)?
        .len()
        .saturating_sub(slide_index)
        .max(2);
    let mut edits = Vec::new();
    for (attribute, value) in [
        (
            "vol",
            controls
                .volume
                .map(|volume| (u32::from(volume) * 1000).to_string()),
        ),
        (
            "mute",
            controls.mute.map(|value| u8::from(value).to_string()),
        ),
        (
            "showWhenStopped",
            controls
                .show_when_stopped
                .map(|value| u8::from(value).to_string()),
        ),
    ] {
        if let Some(value) = value {
            edits.push(media_control_attribute(
                &rewritten,
                &nodes[media],
                attribute,
                Some(value),
            )?);
        }
    }
    if let Some(value) = controls.play_across_slides {
        edits.push(media_control_attribute(
            &rewritten,
            &nodes[media],
            "numSld",
            value.then(|| across_slide_count.to_string()),
        )?);
    }
    if let Some(value) = controls.r#loop {
        edits.push(media_control_attribute(
            &rewritten,
            &nodes[own],
            "repeatCount",
            value.then(|| "indefinite".to_string()),
        )?);
    }
    rewritten = media_control_apply(&rewritten, edits)?;
    rewritten = media_control_trigger_edits(&rewritten, shape_id, controls)?;
    if let Some(auto_play) = controls.auto_play {
        for owner in scope.chain.iter().filter(|owner| **owner != own) {
            if !media_control_exclusive(&nodes, *owner, media)
                && media_control_conditions(&nodes, *owner)?
                    .is_some_and(|list| nodes.iter().any(|node| node.parent == Some(list)))
            {
                return Err(media_control_refusal(
                    "auto_play would change shared ancestor timing",
                ));
            }
        }
        rewritten = set_media_auto_play_in_slide_xml(&rewritten, &shape_id.to_string(), auto_play);
        if auto_play
            && !media_play_call_effects(&rewritten, &shape_id.to_string())
                .iter()
                .any(|(_, _, node_type)| is_auto_media_call_node_type(node_type.as_deref()))
        {
            return Err(media_control_refusal(
                "auto_play is unsupported in this timing topology",
            ));
        }
    }
    let nodes = media_control_nodes(&rewritten)?;
    let scope = media_control_scope(&nodes, shape_id)?;
    media_control_validate_references(&nodes, &scope)?;
    let output_path = output_path.as_ref();
    if let Some(parent) = output_path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        std::fs::create_dir_all(parent)?;
    }
    let mut writer = zip::ZipWriter::new(File::create(output_path)?);
    for index in 0..archive.len() {
        let file = archive.by_index(index)?;
        let name = file.name()?.into_owned();
        if name == slide_part {
            let options = SimpleFileOptions::default().compression_method(file.compression());
            writer.start_file(name, options)?;
            std::io::copy(&mut Cursor::new(rewritten.as_bytes()), &mut writer)?;
        } else {
            writer.raw_copy_file(file)?;
        }
    }
    writer.finish()?;
    Ok(())
}
