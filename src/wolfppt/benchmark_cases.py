"""Expected values shared by benchmark adapter cases."""

from __future__ import annotations

# Re-export chart expectations from the historical benchmark_cases import path.
# ruff: noqa: F401
from .benchmark_chart_cases import (
    ADD_CHART_EXPECTED_TRANSFORM,
    ADD_CHART_EXPECTED,
    ADD_HIERARCHICAL_CHART_EXPECTED,
    ADD_XY_SCATTER_CHART_EXPECTED,
    ADD_BUBBLE_CHART_EXPECTED,
    ADD_BUBBLE_3D_CHART_EXPECTED,
    CHART_TITLE_EXPECTED_TEXT,
    CHART_TITLE_TEXT_FRAME_EXPECTED,
    CHART_TITLE_TEXT_FRAME_FLOW_EXPECTED,
    CHART_TITLE_PARAGRAPH_FORMAT_EXPECTED,
    CHART_TITLE_PARAGRAPH_FONT_EXPECTED,
    CHART_TITLE_FORMAT_EXPECTED,
    CHART_LEGEND_EXPECTED,
    CHART_AXIS_TITLE_EXPECTED,
    CHART_AXIS_PROPERTY_EXPECTED,
    CHART_PLOT_PROPERTY_EXPECTED,
    CHART_DATA_LABEL_EXPECTED,
    CHART_DATA_LABEL_REMOVAL_EXPECTED,
    CHART_POINT_DATA_LABEL_EXPECTED,
    CHART_STYLE_EXPECTED,
    CHART_FORMAT_EXPECTED,
    MULTI_FORMAT_RUN_COUNT,
    CHART_READ_PROXY_EXPECTED,
    CHART_PART_EXPECTED,
    CHART_NO_LEGEND_FONT_EXPECTED,
    CHART_READ_EXPECTED_METADATA,
    CHART_DATA_EDIT_CASES,
    CHART_SPARSE_CATEGORY_DATA_EDIT_CASES,
    CHART_HIERARCHICAL_CATEGORY_DATA_EDIT_CASES,
    CHART_EMPTY_CATEGORY_DATA_EDIT_CASES,
    CHART_XY_DATA_EDIT_CASES,
    CHART_EMPTY_XY_DATA_EDIT_CASES,
    CHART_BUBBLE_DATA_EDIT_CASES,
    CHART_EMPTY_BUBBLE_DATA_EDIT_CASES,
)


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RICH_FORMATTING_SIZE = 304800  # python-pptx Pt(24) as an integer length.
RICH_FORMATTING_EXPECTED = {
    "bold": "1",
    "italic": "1",
    "underline": "sng",
    "size": "2400",
    "font_name": "Aptos",
    "color_rgb": "123456",
}
FONT_LANGUAGE_EXPECTED = "fr-FR"
FONT_FILL_EXPECTED = {
    "fill_type": "gradient",
    "color_rgb": None,
    "gradient_angle": "18900000",
    "gradient_stop_count": 2,
    "gradient_first_stop_position": "25000",
    "gradient_first_stop_rgb": "123456",
}
PARAGRAPH_ALIGNMENT_EXPECTED = "ctr"
PARAGRAPH_LEVEL_EXPECTED = 1
PARAGRAPH_SPACING_EXPECTED = {
    "space_before": 152400,
    "space_after": 76200,
    "line_spacing": 1.25,
}
PARAGRAPH_CLEAR_EXPECTED = ["", "Lossless first"]
PARAGRAPH_LINE_BREAK_EXPECTED = ["Fast PPTX\vAfter", "Lossless first"]
PARAGRAPH_FONT_EXPECTED = {
    "bold": "1",
    "italic": "1",
    "underline": "sng",
    "size": "1800",
    "language_id": "de-DE",
    "font_name": "Aptos",
    "color_rgb": "0C2238",
}
APPENDED_PARAGRAPH_TEXT = "Third"
REPLACED_PARAGRAPH_TEXT = "Second"
ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 914400,
    "cx": 12700,
    "cy": 12700,
}
ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 914400,
    "cx": 914400,
    "cy": 914400,
}
ADD_MOVIE_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 1828800,
    "cx": 2743200,
    "cy": 1828800,
}
ADD_OLE_OBJECT_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 1828800,
    "cx": 2743200,
    "cy": 914400,
}
CONNECTOR_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 914400,
    "cx": 2743200,
    "cy": 914400,
}
CONNECTOR_LINE_STYLE_EXPECTED = {
    "line_rgb": "654321",
    "line_width": 28575,
    "line_dash_style": "dash",
}
ADD_SHAPE_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 2743200,
    "cx": 3657600,
    "cy": 914400,
}
SHAPE_GEOMETRY_EXPECTED = {
    "x": 914400,
    "y": 1828800,
    "cx": 2743200,
    "cy": 914400,
}
GROUP_CHILD_GEOMETRY_EXPECTED = {
    "x": 91440,
    "y": 182880,
    "cx": 914400,
    "cy": 365760,
}
SHAPE_ADJUSTMENT_EXPECTED = 0.33
SHAPE_ADJUSTMENT_EXPECTED_XML = "33000"
ADD_SHAPE_EXPECTED_TEXT = "New Shape"
ADD_SHAPE_EXPECTED_PRESET = "roundRect"
ADD_TEXTBOX_EXPECTED_TEXT = "New Box"
ADD_TEXTBOX_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 2743200,
    "cx": 3657600,
    "cy": 914400,
}
ADD_TABLE_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 914400,
    "cx": 2743200,
    "cy": 914400,
}
ADD_TABLE_EXPECTED_ROWS = [["Metric", "", ""], ["", "", ""]]
ADD_TITLE_SLIDE_EXPECTED_TEXTS = ["Pipeline Review", "Risks and next steps"]
ADD_SLIDE_EXPECTED_ADDED_PARTS = [
    "ppt/slides/_rels/slide2.xml.rels",
    "ppt/slides/slide2.xml",
]
ADD_SLIDE_EXPECTED_CHANGED_PARTS = [
    "[Content_Types].xml",
    "ppt/_rels/presentation.xml.rels",
    "ppt/presentation.xml",
]
ADD_FREEFORM_EXPECTED_TRANSFORM = {
    "x": 914400,
    "y": 1828800,
    "cx": 914400,
    "cy": 914400,
}
ADD_FREEFORM_EXPECTED_TEXT = "Freeform"
PICTURE_CROP_EXPECTED = {"left": 0.125, "right": 0.25, "top": 0.5, "bottom": 0.0}
SHAPE_SHADOW_EXPECTED_INHERIT = False
SHAPE_HYPERLINK_EXPECTED_ADDRESS = "https://example.com/report"
SHAPE_TARGET_SLIDE_EXPECTED_ADDRESS = "slide2.xml"
TEXT_RUN_HYPERLINK_EXPECTED_ADDRESS = "https://example.com/run"
NOTES_PLACEHOLDER_HYPERLINK_EXPECTED_ADDRESS = "https://example.com/notes"
NOTES_RUN_HYPERLINK_EXPECTED_ADDRESS = "https://example.com/notes-run"
NOTES_TEXT_EXPECTED = "Updated speaker note"
NOTES_TEXT_FRAME_FLOW_EXPECTED = {
    "margin_left": 228600,
    "margin_right": 274320,
    "margin_top": 137160,
    "margin_bottom": 182880,
    "word_wrap": False,
    "word_wrap_xml": "none",
    "vertical_anchor": "MIDDLE",
    "vertical_anchor_xml": "ctr",
    "auto_size": "TEXT_TO_FIT_SHAPE",
    "auto_size_xml": "normAutofit",
}
NOTES_PARAGRAPH_RUN_EXPECTED = "Run note update appended\nSecond note"
SLIDE_NAME_EXPECTED = "Intro"
SLIDE_SIZE_EXPECTED_CX = 10058400
SLIDE_SIZE_EXPECTED_CY = 7772400
SLIDE_BACKGROUND_EXPECTED_RGB = "123456"
NOTES_BACKGROUND_EXPECTED_RGB = "336699"
TEMPLATE_BACKGROUND_EXPECTED_RGB = "654321"
NOTES_PLACEHOLDER_CLONE_EXPECTED = [
    {
        "name": "Slide Image Placeholder 1",
        "text": "",
        "placeholder_idx": 2,
        "placeholder_type": "SLIDE_IMAGE (101)",
    },
    {
        "name": "Notes Placeholder 2",
        "text": "Remember to mention preservation before rendering.",
        "placeholder_idx": 3,
        "placeholder_type": "BODY (2)",
    },
    {
        "name": "Slide Number Placeholder 3",
        "text": "",
        "placeholder_idx": 5,
        "placeholder_type": "SLIDE_NUMBER (13)",
    },
    {
        "name": "Slide Image Placeholder 4",
        "text": "",
        "placeholder_idx": 2,
        "placeholder_type": "SLIDE_IMAGE (101)",
    },
    {
        "name": "Notes Placeholder 5",
        "text": "",
        "placeholder_idx": 3,
        "placeholder_type": "BODY (2)",
    },
    {
        "name": "Slide Number Placeholder 6",
        "text": "",
        "placeholder_idx": 5,
        "placeholder_type": "SLIDE_NUMBER (13)",
    },
    {
        "name": "Header Placeholder 7",
        "text": "",
        "placeholder_idx": 0,
        "placeholder_type": "HEADER (14)",
    },
]
SHAPE_ROTATION_EXPECTED = 37.5
SHAPE_ROTATION_EXPECTED_XML = "2250000"
SHAPE_NAME_EXPECTED = "Revenue Box"
TEXT_FRAME_MARGIN_EXPECTED = {
    "margin_left": 228600,
    "margin_right": 114300,
    "margin_top": 12345,
    "margin_bottom": 0,
}
TABLE_CELL_TEXT_FRAME_EXPECTED = {
    "text": "Metric X",
    "cell_margins": {
        "margin_left": 91440,
        "margin_right": 274320,
        "margin_top": 91440,
        "margin_bottom": 45720,
    },
    "text_frame_margins": {
        "margin_left": 182880,
        "margin_right": 91440,
        "margin_top": 45720,
        "margin_bottom": 137160,
    },
    "cell_vertical_anchor": {"value": 4, "xml_value": "b"},
    "text_frame_vertical_anchor": {"value": 3, "xml_value": "ctr"},
}
TABLE_CELL_TEXT_FRAME_FLOW_EXPECTED = {
    "paragraphs": ["", "Second"],
    "text": "\nSecond",
    "word_wrap": True,
    "word_wrap_xml": True,
    "auto_size": "TEXT_TO_FIT_SHAPE",
    "auto_size_xml": True,
}
TABLE_CELL_PARAGRAPH_RUNS_EXPECTED = {
    "text": "Metric X",
    "runs": ["Metric ", "X"],
    "run_count": 2,
}
TABLE_CELL_PARAGRAPH_LINE_BREAK_EXPECTED = {
    "text": "Metric \vX",
    "runs": ["Metric ", "X"],
    "line_break_count": 1,
}
TABLE_CELL_RUN_FONT_EXPECTED = {
    "text": "Metric X",
    "runs": ["Metric ", "X"],
    "theme_run_fill_type": "SOLID",
    "theme_run_color": "ACCENT_2",
    "bold": True,
    "italic": True,
    "underline": True,
    "size": 177800,
    "language_id": "FRENCH",
    "font_name": "Aptos",
    "fill_type": "SOLID",
    "color_rgb": "123456",
    "xml": {
        "bold": True,
        "italic": True,
        "underline": True,
        "size": True,
        "language_id": True,
        "font_name": True,
        "theme_run_color": True,
        "color_rgb": True,
    },
}
TABLE_CELL_RUN_HYPERLINK_EXPECTED = {
    "text": "Metric X",
    "runs": ["Metric ", "X"],
    "run_hyperlink_address": TEXT_RUN_HYPERLINK_EXPECTED_ADDRESS,
    "hyperlink_xml": True,
}
TABLE_CELL_PARAGRAPH_FONT_EXPECTED = {
    "text": "Metric X",
    "bold": True,
    "italic": True,
    "underline": True,
    "size": 177800,
    "language_id": "FRENCH",
    "font_name": "Aptos",
    "fill_type": "SOLID",
    "theme_color": "ACCENT_3",
    "color_rgb": None,
    "xml": {
        "bold": True,
        "italic": True,
        "underline": True,
        "size": True,
        "language_id": True,
        "font_name": True,
        "theme_color": True,
    },
}
TABLE_CELL_FILL_EXPECTED = {
    "solid_cell": {"fill_type": "SOLID", "fill_rgb": "123456"},
    "theme_cell": {
        "fill_type": "PATTERNED",
        "pattern": "DIVOT",
        "fore_type": "SCHEME",
        "fill_theme_color": "ACCENT_3",
        "back_type": "SCHEME",
        "back_theme_color": "ACCENT_4",
    },
    "gradient_cell": {
        "fill_type": "GRADIENT",
        "gradient_angle": 45.0,
        "gradient_stop_count": 2,
        "first_stop_position": 0.25,
        "first_stop_rgb": "654321",
    },
    "background_cell": {"fill_type": "BACKGROUND", "fill_rgb": None},
}
TABLE_CELL_MERGE_EXPECTED = [
    {
        "cell": [0, 0],
        "text": "Metric\nValue\nSlides\n1",
        "is_merge_origin": True,
        "is_spanned": False,
        "span_width": 2,
        "span_height": 2,
    },
    {
        "cell": [0, 1],
        "text": "",
        "is_merge_origin": False,
        "is_spanned": True,
        "span_width": 1,
        "span_height": 2,
    },
    {
        "cell": [1, 0],
        "text": "",
        "is_merge_origin": False,
        "is_spanned": True,
        "span_width": 2,
        "span_height": 1,
    },
    {
        "cell": [1, 1],
        "text": "",
        "is_merge_origin": False,
        "is_spanned": True,
        "span_width": 1,
        "span_height": 1,
    },
]
TABLE_STYLE_FLAGS_EXPECTED = {
    "flags": {
        "first_col": True,
        "first_row": False,
        "horz_banding": False,
        "last_col": True,
        "last_row": True,
        "vert_banding": True,
    },
    "cells": ["Metric", "Value", "Slides", "1"],
}
TABLE_DIMENSIONS_EXPECTED = {
    "row_heights": [500000, 457200],
    "column_widths": [700000, 2743200],
}
TEXT_FRAME_WORD_WRAP_EXPECTED = True
TEXT_FRAME_VERTICAL_ANCHOR_EXPECTED = "ctr"
TEXT_FRAME_VERTICAL_ANCHOR_EXPECTED_NAME = "MIDDLE"
TEXT_FRAME_AUTO_SIZE_EXPECTED = "normAutofit"
TEXT_FRAME_AUTO_SIZE_EXPECTED_NAME = "TEXT_TO_FIT_SHAPE"
TEXT_FRAME_FIT_TEXT_FONT_FAMILIES = ("Arial", "DejaVu Sans", "Liberation Sans")
TEXT_FRAME_FIT_TEXT_EXPECTED = {
    "font_family": TEXT_FRAME_FIT_TEXT_FONT_FAMILIES[0],
    "size": 228600,
    "size_xml": "1800",
    "bold": True,
    "italic": True,
}
MIXED_WORKLOAD_EXPECTED = {
    "title": "Quarterly Business Review - Board Update",
    "table_revenue_q3": "$14.6m",
    "risk": "Data quality - mitigated",
    "actions": [
        "Validate source workbooks",
        "Reconcile management adjustments",
        "Prepare board appendix package",
    ],
    "chart_categories": ["Q1", "Q2", "Q3", "Q4"],
    "chart_series": [
        {"name": "Revenue", "values": [10.5, 12.9, 14.6, 16.8]},
        {"name": "Gross Margin", "values": [5.6, 7.2, 8.5, 10.0]},
    ],
    "notes": "Close with owners, dates, and benchmark evidence.",
}
CREATE_NOTES_SLIDE_EXPECTED = "Created speaker note"
MIXED_WORKLOAD_CHANGED_PARTS = [
    "ppt/charts/chart1.xml",
    "ppt/embeddings/Microsoft_Excel_Sheet1.xlsx",
    "ppt/notesSlides/notesSlide2.xml",
    "ppt/slides/slide1.xml",
    "ppt/slides/slide2.xml",
    "ppt/slides/slide4.xml",
    "ppt/slides/slide5.xml",
]
