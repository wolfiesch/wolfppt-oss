"""Synthetic board and management pack builders for corpus fixtures."""

from __future__ import annotations

from io import BytesIO

from .corpus_slide_helpers import add_textbox as _add_textbox
from .corpus_slide_helpers import png_1x1 as _png_1x1


def _add_large_real_world_deck(prs, slide) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    _add_textbox(
        slide,
        "Operating Review Pack",
        Inches(0.5),
        Inches(0.35),
        Inches(8.8),
        Inches(0.6),
    )
    _add_textbox(
        slide,
        "Board-style deck with recurring KPI, chart, risk, and action sections.",
        Inches(0.7),
        Inches(1.1),
        Inches(8.2),
        Inches(0.8),
    )
    slide.shapes.add_picture(
        BytesIO(_png_1x1()),
        Inches(8.9),
        Inches(0.35),
        Inches(0.35),
        Inches(0.35),
    )
    slide.notes_slide.notes_text_frame.text = "Use this deck as the large real-corpus sentinel."

    sections = [
        ("Revenue", (12.0, 13.4, 15.1, 17.2), "$17.2m", "Pipeline conversion"),
        ("Margin", (5.8, 6.4, 7.2, 8.1), "47.1%", "Vendor price pressure"),
        ("Retention", (90.0, 91.5, 93.0, 94.0), "94.0%", "Renewal timing"),
        ("Bookings", (10.2, 12.8, 14.6, 18.5), "$18.5m", "Enterprise slippage"),
    ]
    for idx, (name, values, headline, risk) in enumerate(sections, start=1):
        table_slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_textbox(
            table_slide,
            f"{idx}. {name} KPI Detail",
            Inches(0.5),
            Inches(0.35),
            Inches(8.8),
            Inches(0.6),
        )
        table_shape = table_slide.shapes.add_table(
            5,
            5,
            Inches(0.6),
            Inches(1.1),
            Inches(8.8),
            Inches(2.5),
        )
        rows = [
            ["Metric", "Q1", "Q2", "Q3", "Q4"],
            [name, *[str(value) for value in values]],
            ["Target", "10.0", "12.0", "14.0", "16.0"],
            ["Variance", "+2.0", "+1.4", "+1.1", "+1.2"],
            ["Owner", "Ops", "Finance", "Sales", "GM"],
        ]
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                table_shape.table.cell(row_idx, col_idx).text = value
        table_slide.notes_slide.notes_text_frame.text = (
            f"{name} detail: call out headline {headline} and owner follow-up."
        )

        chart_slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_textbox(
            chart_slide,
            f"{idx}. {name} Trend",
            Inches(0.5),
            Inches(0.35),
            Inches(8.8),
            Inches(0.6),
        )
        chart_data = CategoryChartData()
        chart_data.categories = ["Q1", "Q2", "Q3", "Q4"]
        chart_data.add_series(name, values)
        chart_data.add_series("Plan", (10.0, 12.0, 14.0, 16.0))
        chart_slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.7),
            Inches(1.0),
            Inches(8.4),
            Inches(4.0),
            chart_data,
        )

        risk_slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_textbox(
            risk_slide,
            f"{idx}. {name} Risk and Actions",
            Inches(0.5),
            Inches(0.35),
            Inches(8.8),
            Inches(0.6),
        )
        for risk_idx, label in enumerate((risk, "Data quality", "Decision required")):
            shape = risk_slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(0.8),
                Inches(1.1 + risk_idx * 1.0),
                Inches(5.2),
                Inches(0.65),
            )
            shape.text = label
        risk_slide.notes_slide.notes_text_frame.text = (
            f"{name} risk slide should preserve notes and rounded-rectangle shapes."
        )


def _add_portfolio_ops_review_deck(prs, slide) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    _add_textbox(
        slide,
        "Portfolio Operations Review",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    _add_textbox(
        slide,
        "KPI roll-forward, concentration, initiatives, risks, and appendix evidence.",
        Inches(0.7),
        Inches(1.05),
        Inches(8.4),
        Inches(0.8),
    )
    slide.shapes.add_picture(
        BytesIO(_png_1x1()),
        Inches(8.85),
        Inches(0.35),
        Inches(0.4),
        Inches(0.4),
    )
    slide.notes_slide.notes_text_frame.text = (
        "Use this deck to pressure-test portfolio review preservation."
    )

    kpi_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        kpi_slide,
        "Portfolio KPI Roll-forward",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    table_shape = kpi_slide.shapes.add_table(
        7,
        5,
        Inches(0.5),
        Inches(1.0),
        Inches(9.0),
        Inches(3.4),
    )
    rows = [
        ["Company", "Revenue", "EBITDA", "Rule of 40", "Status"],
        ["Northwind", "$24.2m", "$5.1m", "42%", "Green"],
        ["Contoso", "$18.6m", "$3.2m", "36%", "Yellow"],
        ["Fabrikam", "$31.4m", "$6.8m", "48%", "Green"],
        ["Adventure", "$12.8m", "$1.1m", "25%", "Red"],
        ["Tailwind", "$9.7m", "$2.0m", "39%", "Yellow"],
        ["Total", "$96.7m", "$18.2m", "40%", "Review"],
    ]
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            table_shape.table.cell(row_idx, col_idx).text = value
    kpi_slide.notes_slide.notes_text_frame.text = (
        "Confirm each KPI ties to the latest portfolio workbook."
    )

    chart_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        chart_slide,
        "Revenue by Portfolio Company",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    chart_data = CategoryChartData()
    chart_data.categories = ["Northwind", "Contoso", "Fabrikam", "Adventure", "Tailwind"]
    chart_data.add_series("Actual", (24.2, 18.6, 31.4, 12.8, 9.7))
    chart_data.add_series("Plan", (22.0, 20.0, 29.0, 15.0, 11.0))
    chart_slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.7),
        Inches(1.0),
        Inches(8.4),
        Inches(4.0),
        chart_data,
    )

    concentration_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        concentration_slide,
        "Customer Concentration",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    concentration = concentration_slide.shapes.add_table(
        5,
        4,
        Inches(0.7),
        Inches(1.0),
        Inches(8.4),
        Inches(2.6),
    ).table
    for row_idx, row in enumerate(
        [
            ["Customer", "Portfolio Co.", "ARR", "% Revenue"],
            ["Acme", "Northwind", "$4.4m", "18%"],
            ["Globex", "Fabrikam", "$3.8m", "12%"],
            ["Initech", "Contoso", "$2.1m", "11%"],
            ["Umbrella", "Adventure", "$1.6m", "13%"],
        ]
    ):
        for col_idx, value in enumerate(row):
            concentration.cell(row_idx, col_idx).text = value

    roadmap_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        roadmap_slide,
        "Value Creation Roadmap",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    for idx, label in enumerate(
        ("Pricing cleanup", "Sales capacity", "Working capital", "Data room refresh")
    ):
        shape = roadmap_slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.8 + (idx % 2) * 4.4),
            Inches(1.1 + (idx // 2) * 1.3),
            Inches(3.6),
            Inches(0.75),
        )
        shape.text = label

    risk_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        risk_slide,
        "Risk Register and Required Decisions",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    body = _add_textbox(
        risk_slide,
        "Red: Adventure retention; Yellow: Contoso expansion slippage",
        Inches(0.75),
        Inches(1.0),
        Inches(8.2),
        Inches(1.2),
    )
    body.text_frame.add_paragraph().text = (
        "Decision: approve incremental sales hiring for Q3"
    )
    body.text_frame.add_paragraph().text = "Decision: require weekly cash bridge"
    risk_slide.notes_slide.notes_text_frame.text = (
        "Do not drop the risk notes or decision text during round-trip."
    )

    appendix_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        appendix_slide,
        "Appendix: Evidence Index",
        Inches(0.5),
        Inches(0.35),
        Inches(8.5),
        Inches(0.6),
    )
    appendix = appendix_slide.shapes.add_table(
        4,
        3,
        Inches(0.7),
        Inches(1.0),
        Inches(8.2),
        Inches(2.2),
    ).table
    for row_idx, row in enumerate(
        [
            ["Evidence", "Source", "Owner"],
            ["KPI workbook", "portfolio_kpi.xlsx", "Finance"],
            ["Revenue bridge", "qbr_export.xlsx", "Ops"],
            ["Customer list", "crm_snapshot.csv", "RevOps"],
        ]
    ):
        for col_idx, value in enumerate(row):
            appendix.cell(row_idx, col_idx).text = value

def _add_management_reporting_deck(prs, slide) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    _add_textbox(
        slide,
        "Management Reporting Pack",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    _add_textbox(
        slide,
        "Monthly close, segment KPIs, grouped dashboard visuals, and action owners.",
        Inches(0.7),
        Inches(1.05),
        Inches(8.4),
        Inches(0.8),
    )
    slide.shapes.add_picture(
        BytesIO(_png_1x1()),
        Inches(8.85),
        Inches(0.35),
        Inches(0.4),
        Inches(0.4),
    )
    slide.notes_slide.notes_text_frame.text = (
        "Use this pack to test management-reporting style preservation."
    )

    close_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        close_slide,
        "Close Dashboard",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    table = close_slide.shapes.add_table(
        6,
        5,
        Inches(0.45),
        Inches(1.0),
        Inches(9.1),
        Inches(3.0),
    ).table
    rows = [
        ["Area", "Owner", "Status", "Open items", "Due"],
        ["Revenue", "Controller", "Green", "1", "Day 2"],
        ["COGS", "Ops Finance", "Yellow", "4", "Day 3"],
        ["Payroll", "People", "Green", "0", "Day 2"],
        ["Deferred Rev", "RevOps", "Yellow", "3", "Day 4"],
        ["Cash", "Treasury", "Red", "5", "Day 1"],
    ]
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            table.cell(row_idx, col_idx).text = value
    close_slide.notes_slide.notes_text_frame.text = (
        "Preserve close table text and note context for management review."
    )

    dashboard_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        dashboard_slide,
        "Segment Dashboard",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    group = dashboard_slide.shapes.add_group_shape()
    for idx, (label, value) in enumerate(
        (("Enterprise", "$18.4m"), ("SMB", "$7.2m"), ("Services", "$3.9m"))
    ):
        tile = group.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.3 + idx * 2.1),
            Inches(0.4),
            Inches(1.75),
            Inches(0.8),
        )
        tile.text = f"{label}\n{value}"
    chart_data = CategoryChartData()
    chart_data.categories = ["Jan", "Feb", "Mar", "Apr"]
    chart_data.add_series("Enterprise", (15.2, 16.1, 17.3, 18.4))
    chart_data.add_series("SMB", (6.8, 7.0, 7.1, 7.2))
    group.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.35),
        Inches(1.45),
        Inches(5.9),
        Inches(2.6),
        chart_data,
    )
    dashboard_slide.notes_slide.notes_text_frame.text = (
        "Grouped dashboard tiles and chart must stay inside the group."
    )

    for idx, (title, actual, plan, owner) in enumerate(
        (
            ("Revenue Bridge", (24.0, 25.1, 26.6, 29.5), (23.5, 24.5, 26.0, 28.0), "FP&A"),
            ("Gross Margin", (56.0, 56.5, 57.2, 58.1), (55.0, 55.5, 56.5, 57.0), "Ops"),
            ("Cash Conversion", (42.0, 45.0, 43.5, 48.0), (40.0, 42.0, 44.0, 46.0), "Treasury"),
        ),
        start=1,
    ):
        chart_slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_textbox(
            chart_slide,
            f"{idx}. {title}",
            Inches(0.5),
            Inches(0.35),
            Inches(8.6),
            Inches(0.6),
        )
        chart_data = CategoryChartData()
        chart_data.categories = ["Jan", "Feb", "Mar", "Apr"]
        chart_data.add_series("Actual", actual)
        chart_data.add_series("Plan", plan)
        chart_slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.7),
            Inches(1.0),
            Inches(8.4),
            Inches(4.0),
            chart_data,
        )
        chart_slide.notes_slide.notes_text_frame.text = (
            f"{title} owner is {owner}; preserve chart workbook and notes."
        )

    actions_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        actions_slide,
        "Management Actions",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    for idx, label in enumerate(
        ("Resolve cash reconciling items", "Reforecast Q3 hiring", "Refresh pricing model")
    ):
        shape = actions_slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.75),
            Inches(1.05 + idx * 1.05),
            Inches(5.6),
            Inches(0.7),
        )
        shape.text = label
    actions_slide.notes_slide.notes_text_frame.text = (
        "Action-owner slide should retain rounded shapes and speaker notes."
    )

    appendix_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        appendix_slide,
        "Appendix: Reporting Sources",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    appendix = appendix_slide.shapes.add_table(
        5,
        3,
        Inches(0.7),
        Inches(1.0),
        Inches(8.2),
        Inches(2.6),
    ).table
    for row_idx, row in enumerate(
        [
            ["Artifact", "Source", "Owner"],
            ["Close tracker", "close_tracker.xlsx", "Controller"],
            ["Segment P&L", "segment_reporting.xlsx", "FP&A"],
            ["Cash bridge", "treasury_bridge.xlsx", "Treasury"],
            ["Board actions", "board_actions.docx", "CEO Staff"],
        ]
    ):
        for col_idx, value in enumerate(row):
            appendix.cell(row_idx, col_idx).text = value


def _add_finance_board_pack(prs, slide) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    _add_textbox(
        slide,
        "Finance Board Pack",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    _add_textbox(
        slide,
        "Close status, liquidity, covenants, and operating actions for board review.",
        Inches(0.7),
        Inches(1.05),
        Inches(8.4),
        Inches(0.8),
    )
    slide.shapes.add_picture(
        BytesIO(_png_1x1()),
        Inches(8.85),
        Inches(0.35),
        Inches(0.4),
        Inches(0.4),
    )
    slide.notes_slide.notes_text_frame.text = (
        "Synthetic finance board pack for real-corpus preservation evidence."
    )

    dashboard_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        dashboard_slide,
        "Board KPI Dashboard",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    group = dashboard_slide.shapes.add_group_shape()
    for idx, (label, value) in enumerate(
        (("ARR", "$42.6m"), ("EBITDA", "$8.4m"), ("Cash", "$14.2m"), ("NWC", "$6.1m"))
    ):
        tile = group.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.25 + (idx % 2) * 2.4),
            Inches(0.25 + (idx // 2) * 1.0),
            Inches(2.0),
            Inches(0.72),
        )
        tile.text = f"{label}\n{value}"
    chart_data = CategoryChartData()
    chart_data.categories = ["Jan", "Feb", "Mar", "Apr"]
    chart_data.add_series("Actual", (38.1, 39.4, 40.8, 42.6))
    chart_data.add_series("Plan", (37.5, 39.0, 41.0, 43.0))
    group.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.35),
        Inches(2.35),
        Inches(5.9),
        Inches(2.25),
        chart_data,
    )
    dashboard_slide.notes_slide.notes_text_frame.text = (
        "Grouped KPI tiles and embedded dashboard chart must survive round-trip."
    )

    close_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        close_slide,
        "Close and Reporting Status",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    table = close_slide.shapes.add_table(
        7,
        5,
        Inches(0.45),
        Inches(1.0),
        Inches(9.1),
        Inches(3.35),
    ).table
    rows = [
        ["Workstream", "Owner", "Status", "Open", "Risk"],
        ["Revenue recognition", "Controller", "Yellow", "4", "Cutoff samples"],
        ["Deferred revenue", "RevOps", "Green", "1", "Low"],
        ["Payroll accrual", "People", "Green", "0", "Low"],
        ["Bank recs", "Treasury", "Red", "6", "Timing"],
        ["Tax provision", "Tax", "Yellow", "3", "External review"],
        ["Board package", "FP&A", "Green", "2", "Formatting"],
    ]
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            table.cell(row_idx, col_idx).text = value
    close_slide.notes_slide.notes_text_frame.text = (
        "Close status table carries operational risk commentary."
    )

    for title, actual, plan, owner in (
        (
            "Cash Bridge",
            (14.8, 13.9, 13.4, 14.2),
            (15.0, 14.5, 14.0, 14.0),
            "Treasury",
        ),
        (
            "Covenant Headroom",
            (3.4, 3.2, 3.0, 2.8),
            (3.5, 3.3, 3.1, 3.0),
            "CFO",
        ),
        (
            "Revenue Retention",
            (92.0, 93.5, 94.2, 95.1),
            (91.0, 92.0, 93.0, 94.0),
            "RevOps",
        ),
    ):
        chart_slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_textbox(
            chart_slide,
            title,
            Inches(0.5),
            Inches(0.35),
            Inches(8.6),
            Inches(0.6),
        )
        chart_data = CategoryChartData()
        chart_data.categories = ["Jan", "Feb", "Mar", "Apr"]
        chart_data.add_series("Actual", actual)
        chart_data.add_series("Plan", plan)
        chart_slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.7),
            Inches(1.0),
            Inches(8.4),
            Inches(4.0),
            chart_data,
        )
        chart_slide.notes_slide.notes_text_frame.text = (
            f"{title} owner is {owner}; preserve chart workbook and notes."
        )

    actions_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        actions_slide,
        "Board Actions and Decisions",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    for idx, label in enumerate(
        (
            "Approve bank covenant amendment",
            "Fund Q3 hiring plan",
            "Escalate collection plan",
        )
    ):
        shape = actions_slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.75),
            Inches(1.05 + idx * 1.05),
            Inches(5.9),
            Inches(0.7),
        )
        shape.text = label
    actions_slide.notes_slide.notes_text_frame.text = (
        "Decision slide should retain action text and rounded shapes."
    )

    appendix_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        appendix_slide,
        "Appendix: Finance Evidence Index",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    appendix = appendix_slide.shapes.add_table(
        5,
        3,
        Inches(0.7),
        Inches(1.0),
        Inches(8.2),
        Inches(2.6),
    ).table
    for row_idx, row in enumerate(
        [
            ["Artifact", "Source", "Owner"],
            ["Cash bridge", "treasury_bridge.xlsx", "Treasury"],
            ["Covenant model", "debt_covenants.xlsx", "CFO"],
            ["Revenue cohort", "retention_export.xlsx", "RevOps"],
            ["Close tracker", "close_status.xlsx", "Controller"],
        ]
    ):
        for col_idx, value in enumerate(row):
            appendix.cell(row_idx, col_idx).text = value


def _add_investor_update_pack(prs, slide) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.util import Inches

    _add_textbox(
        slide,
        "Investor Update Pack",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    _add_textbox(
        slide,
        "Monthly investor narrative with growth, retention, runway, and execution risks.",
        Inches(0.7),
        Inches(1.05),
        Inches(8.2),
        Inches(0.8),
    )
    slide.shapes.add_picture(
        BytesIO(_png_1x1()),
        Inches(8.85),
        Inches(0.35),
        Inches(0.4),
        Inches(0.4),
    )
    slide.notes_slide.notes_text_frame.text = (
        "Synthetic investor update pack for real-corpus preservation evidence."
    )

    metrics_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        metrics_slide,
        "Growth and Retention Snapshot",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    table = metrics_slide.shapes.add_table(
        6,
        5,
        Inches(0.45),
        Inches(1.0),
        Inches(9.1),
        Inches(2.85),
    ).table
    rows = [
        ["Metric", "Jan", "Feb", "Mar", "Apr"],
        ["ARR", "$38.1m", "$39.6m", "$41.2m", "$42.9m"],
        ["NRR", "112%", "113%", "114%", "116%"],
        ["Gross churn", "1.8%", "1.7%", "1.5%", "1.4%"],
        ["Pipeline", "$11.2m", "$12.4m", "$13.7m", "$15.1m"],
        ["Runway", "21 mo", "20 mo", "20 mo", "19 mo"],
    ]
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            table.cell(row_idx, col_idx).text = value
    metrics_slide.notes_slide.notes_text_frame.text = (
        "Investor KPI table should keep exact text and table topology."
    )

    chart_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        chart_slide,
        "ARR and Pipeline Trend",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    chart_data = CategoryChartData()
    chart_data.categories = ["Jan", "Feb", "Mar", "Apr"]
    chart_data.add_series("ARR", (38.1, 39.6, 41.2, 42.9))
    chart_data.add_series("Pipeline", (11.2, 12.4, 13.7, 15.1))
    chart_slide.shapes.add_chart(
        XL_CHART_TYPE.LINE_MARKERS,
        Inches(0.7),
        Inches(1.0),
        Inches(8.4),
        Inches(4.0),
        chart_data,
    )
    chart_slide.notes_slide.notes_text_frame.text = (
        "Line chart workbook and notes must survive investor update round-trip."
    )

    runway_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        runway_slide,
        "Runway and Financing Plan",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    runway = runway_slide.shapes.add_table(
        5,
        4,
        Inches(0.7),
        Inches(1.0),
        Inches(8.2),
        Inches(2.35),
    ).table
    for row_idx, row in enumerate(
        [
            ["Scenario", "Cash", "Burn", "Runway"],
            ["Base", "$18.4m", "$0.92m", "20 months"],
            ["Hiring upside", "$18.4m", "$1.18m", "16 months"],
            ["Sales delay", "$16.9m", "$0.98m", "17 months"],
            ["Fundraise", "$30.0m", "$1.15m", "26 months"],
        ]
    ):
        for col_idx, value in enumerate(row):
            runway.cell(row_idx, col_idx).text = value
    runway_slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(1.0),
        Inches(3.9),
        Inches(8.4),
        Inches(3.9),
    )
    runway_slide.notes_slide.notes_text_frame.text = (
        "Runway scenario table and connector line should be preserved."
    )

    milestones_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        milestones_slide,
        "Product and GTM Milestones",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    group = milestones_slide.shapes.add_group_shape()
    for idx, (label, owner) in enumerate(
        (
            ("Enterprise SSO", "Platform"),
            ("Partner channel launch", "GTM"),
            ("Usage-based pricing", "Finance"),
            ("Security review", "Ops"),
        )
    ):
        tile = group.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.25 + (idx % 2) * 2.8),
            Inches(0.25 + (idx // 2) * 1.0),
            Inches(2.45),
            Inches(0.75),
        )
        tile.text = f"{label}\n{owner}"
    milestones_slide.notes_slide.notes_text_frame.text = (
        "Grouped milestone tiles should keep child text and transforms."
    )

    appendix_slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(
        appendix_slide,
        "Appendix: Investor Evidence Index",
        Inches(0.5),
        Inches(0.35),
        Inches(8.6),
        Inches(0.6),
    )
    appendix = appendix_slide.shapes.add_table(
        5,
        3,
        Inches(0.7),
        Inches(1.0),
        Inches(8.2),
        Inches(2.6),
    ).table
    for row_idx, row in enumerate(
        [
            ["Artifact", "Source", "Owner"],
            ["ARR bridge", "arr_bridge.xlsx", "Finance"],
            ["Pipeline export", "crm_pipeline.xlsx", "RevOps"],
            ["Runway model", "runway_plan.xlsx", "CFO"],
            ["Security tracker", "security_review.docx", "Ops"],
        ]
    ):
        for col_idx, value in enumerate(row):
            appendix.cell(row_idx, col_idx).text = value
