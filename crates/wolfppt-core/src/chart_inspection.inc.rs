// Chart inspection: the per-slide chart query. Values are reported as stored
// in the chart part, with null where the element or attribute is absent.

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct SlideChartsSummary {
    pub index: usize,
    pub part: String,
    pub charts: Vec<ChartSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartSummary {
    pub chart_index: usize,
    pub relationship_id: String,
    pub part: String,
    pub content_type: Option<String>,
    pub embedded_workbook: Option<String>,
    pub sheet_name: Option<String>,
    pub legend: Option<ChartLegendSummary>,
    pub plots: Vec<ChartPlotSummary>,
    pub axes: Vec<ChartAxisSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartLegendSummary {
    pub position: Option<String>,
    pub overlay: Option<bool>,
    pub manual_layout: Option<ChartManualLayoutSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartManualLayoutSummary {
    pub target: Option<String>,
    pub x_mode: Option<String>,
    pub y_mode: Option<String>,
    pub width_mode: Option<String>,
    pub height_mode: Option<String>,
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub width: Option<f64>,
    pub height: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartPlotSummary {
    pub plot_index: usize,
    #[serde(rename = "type")]
    pub kind: String,
    pub axis_ids: Vec<i64>,
    pub bar_direction: Option<String>,
    pub bar_grouping: Option<String>,
    pub gap_width: Option<u32>,
    pub grouping: Option<String>,
    pub radar_style: Option<String>,
    pub scatter_style: Option<String>,
    pub series: Vec<ChartSeriesSummary>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartSeriesSummary {
    pub series_index: usize,
    pub index: Option<u64>,
    pub order: Option<u64>,
    pub title: Option<ChartTextSummary>,
    pub categories: Option<ChartDataSummary>,
    pub values: Option<ChartDataSummary>,
    pub explosion: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ChartTextSummary {
    pub text: Option<String>,
    pub reference: Option<String>,
}

/// `kind` is the data-source element (`strRef`, `numRef`, `strLit`,
/// `numLit`, `multiLvlStrRef`); `values` follow cached point indices, with
/// null for points the cache omits.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartDataSummary {
    pub kind: String,
    pub reference: Option<String>,
    pub format_code: Option<String>,
    pub values: Vec<Option<ChartPointValue>>,
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct ChartAxisSummary {
    pub id: i64,
    pub kind: String,
    pub position: Option<String>,
    pub orientation: Option<String>,
    pub visible: Option<bool>,
    pub cross_axis_id: Option<i64>,
    pub crosses: Option<String>,
    pub crosses_at: Option<f64>,
    pub cross_between: Option<String>,
    pub number_format: Option<ChartNumberFormatSummary>,
    pub major_tick_mark: Option<String>,
    pub minor_tick_mark: Option<String>,
    pub log_base: Option<f64>,
    pub minimum: Option<f64>,
    pub maximum: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ChartNumberFormatSummary {
    pub format_code: Option<String>,
    pub source_linked: Option<bool>,
}

fn chart_data_summary(owner: &ChartXmlElement) -> Option<ChartDataSummary> {
    let source = owner.elements().next()?;
    let kind = source.local().to_string();
    let (reference, cache) = match kind.as_str() {
        "strRef" | "numRef" | "multiLvlStrRef" => (
            source.child("f").map(ChartXmlElement::text),
            source
                .elements()
                .find(|element| element.local().ends_with("Cache")),
        ),
        "strLit" | "numLit" => (None, Some(source)),
        _ => (None, None),
    };
    let numeric = kind.starts_with("num");
    let mut values: Vec<Option<ChartPointValue>> = Vec::new();
    let mut format_code = None;
    if let Some(cache) = cache {
        format_code = cache.child("formatCode").map(ChartXmlElement::text);
        let count: usize = cache.child_number("ptCount").unwrap_or(0);
        values.resize(count, None);
        // Multi-level caches keep their points per level; report the first.
        let points = cache.child("lvl").unwrap_or(cache);
        for point in points.elements().filter(|element| element.local() == "pt") {
            let Some(index) = point
                .attribute("idx")
                .and_then(|idx| idx.trim().parse::<usize>().ok())
            else {
                continue;
            };
            let text = point
                .child("v")
                .map(ChartXmlElement::text)
                .unwrap_or_default();
            let value = match text.trim().parse::<f64>() {
                Ok(number) if numeric => ChartPointValue::Number(number),
                _ => ChartPointValue::Text(text),
            };
            if index >= values.len() {
                values.resize(index + 1, None);
            }
            values[index] = Some(value);
        }
    }
    Some(ChartDataSummary {
        kind,
        reference,
        format_code,
        values,
    })
}

fn chart_series_summary(
    series_index: usize,
    series: &ChartXmlElement,
    xy: bool,
) -> ChartSeriesSummary {
    let title = series.child("tx").map(|tx| match tx.child("strRef") {
        Some(reference) => ChartTextSummary {
            text: reference
                .child("strCache")
                .and_then(|cache| cache.elements().find(|element| element.local() == "pt"))
                .and_then(|point| point.child("v"))
                .map(ChartXmlElement::text),
            reference: reference.child("f").map(ChartXmlElement::text),
        },
        None => ChartTextSummary {
            text: tx.child("v").map(ChartXmlElement::text),
            reference: None,
        },
    });
    let (categories, values) = if xy { ("xVal", "yVal") } else { ("cat", "val") };
    ChartSeriesSummary {
        series_index,
        index: series.child_number("idx"),
        order: series.child_number("order"),
        title,
        categories: series.child(categories).and_then(chart_data_summary),
        values: series.child(values).and_then(chart_data_summary),
        explosion: series.child_number("explosion"),
    }
}

fn chart_plot_summary(plot_index: usize, plot: &ChartXmlElement) -> ChartPlotSummary {
    let kind = plot.local().to_string();
    let bar = CHART_BAR_PLOTS.contains(&kind.as_str());
    let xy = CHART_XY_PLOTS.contains(&kind.as_str());
    ChartPlotSummary {
        plot_index,
        axis_ids: plot
            .elements()
            .filter(|element| element.local() == "axId")
            .filter_map(|element| element.attribute("val")?.trim().parse().ok())
            .collect(),
        bar_direction: plot.child_val("barDir"),
        bar_grouping: if bar {
            plot.child_val("grouping")
        } else {
            None
        },
        gap_width: plot.child_number("gapWidth"),
        grouping: if bar {
            None
        } else {
            plot.child_val("grouping")
        },
        radar_style: plot.child_val("radarStyle"),
        scatter_style: plot.child_val("scatterStyle"),
        series: plot
            .elements()
            .filter(|element| element.local() == "ser")
            .enumerate()
            .map(|(index, series)| chart_series_summary(index, series, xy))
            .collect(),
        kind,
    }
}

fn chart_axis_summary(axis: &ChartXmlElement) -> Option<ChartAxisSummary> {
    let scaling = axis.child("scaling");
    let scaled = |local: &str| scaling.and_then(|scaling| scaling.child_number::<f64>(local));
    Some(ChartAxisSummary {
        id: axis.child_number("axId")?,
        kind: axis.local().to_string(),
        position: axis.child_val("axPos"),
        orientation: scaling.and_then(|scaling| scaling.child_val("orientation")),
        visible: axis.child_bool("delete").map(|deleted| !deleted),
        cross_axis_id: axis.child_number("crossAx"),
        crosses: axis.child_val("crosses"),
        crosses_at: axis.child_number("crossesAt"),
        cross_between: axis.child_val("crossBetween"),
        number_format: axis.child("numFmt").map(|format| ChartNumberFormatSummary {
            format_code: format.attribute("formatCode"),
            source_linked: format
                .attribute("sourceLinked")
                .map(|value| value == "1" || value == "true"),
        }),
        major_tick_mark: axis.child_val("majorTickMark"),
        minor_tick_mark: axis.child_val("minorTickMark"),
        log_base: scaled("logBase"),
        minimum: scaled("min"),
        maximum: scaled("max"),
    })
}

fn chart_legend_summary(legend: &ChartXmlElement) -> ChartLegendSummary {
    let manual = legend
        .child("layout")
        .and_then(|layout| layout.child("manualLayout"));
    ChartLegendSummary {
        position: legend.child_val("legendPos"),
        overlay: legend.child_bool("overlay"),
        manual_layout: manual.map(|manual| ChartManualLayoutSummary {
            target: manual.child_val("layoutTarget"),
            x_mode: manual.child_val("xMode"),
            y_mode: manual.child_val("yMode"),
            width_mode: manual.child_val("wMode"),
            height_mode: manual.child_val("hMode"),
            x: manual.child_number("x"),
            y: manual.child_number("y"),
            width: manual.child_number("w"),
            height: manual.child_number("h"),
        }),
    }
}

fn chart_summary<R: Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    content_types_xml: &str,
    chart_index: usize,
    relationship_id: String,
    part: String,
) -> Result<ChartSummary, WolfPptError> {
    let xml = read_archive_text(archive, &part)?
        .ok_or_else(|| chart_invalid(format!("chart part {part} was not found")))?;
    let document = chart_xml_parse(&xml)?;
    let (embedded_workbook, sheet_name) = match chart_sheet_name(archive, &part)? {
        Some((workbook, sheet)) => (Some(workbook), Some(sheet)),
        None => (chart_embedded_workbook_part(archive, &part)?, None),
    };
    let chart = document.root.child("chart");
    let plot_area = chart.and_then(|chart| chart.child("plotArea"));
    Ok(ChartSummary {
        chart_index,
        relationship_id,
        content_type: find_content_type_override(content_types_xml, &part),
        embedded_workbook,
        sheet_name,
        legend: chart
            .and_then(|chart| chart.child("legend"))
            .map(chart_legend_summary),
        plots: plot_area
            .map(|area| {
                area.elements()
                    .filter(|element| chart_is_plot(element))
                    .enumerate()
                    .map(|(index, plot)| chart_plot_summary(index, plot))
                    .collect()
            })
            .unwrap_or_default(),
        axes: plot_area
            .map(|area| {
                area.elements()
                    .filter(|element| CHART_AXIS_KINDS.contains(&element.local()))
                    .filter_map(chart_axis_summary)
                    .collect()
            })
            .unwrap_or_default(),
        part,
    })
}

/// Charts of every slide in presentation order. A slide's charts are its
/// chart graphic frames in document order; `chart_index` addresses them in
/// the chart authoring operations.
pub fn summarize_slide_charts_bytes(bytes: &[u8]) -> Result<Vec<SlideChartsSummary>, WolfPptError> {
    let mut archive = ZipArchive::new(Cursor::new(bytes))?;
    let content_types_xml =
        read_archive_text(&mut archive, "[Content_Types].xml")?.unwrap_or_default();
    let mut slides = Vec::new();
    for (index, part) in slide_parts(&mut archive)?.into_iter().enumerate() {
        let references = slide_chart_references(&mut archive, &part)?;
        let mut charts = Vec::with_capacity(references.len());
        for (chart_index, (relationship_id, chart_part)) in references.into_iter().enumerate() {
            charts.push(chart_summary(
                &mut archive,
                &content_types_xml,
                chart_index,
                relationship_id,
                chart_part,
            )?);
        }
        slides.push(SlideChartsSummary {
            index,
            part,
            charts,
        });
    }
    Ok(slides)
}
