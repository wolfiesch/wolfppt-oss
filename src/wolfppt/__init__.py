"""WolfPPT compatibility harness."""

from __future__ import annotations

from ._native_import import NativeExtensionImportError
from .background_picture_requests import (
    BackgroundPictureRefusal,
    BackgroundPictureRequest,
    apply_background_picture_request,
    load_background_picture_request,
    parse_background_picture_request,
)
from .chart_data import BubbleChartData, CategoryChartData, XyChartData
from .chart_error_bars_facade import (
    ChartErrorBar,
    ChartErrorBars,
    ErrorBarEntry,
    ErrorBars3DPolicyError,
    ErrorBarsDuplicateAxisError,
    ErrorBarsRefusal,
    ErrorBarsSpec,
    ErrorBarsStaleHandleError,
    ErrorBarsUnsupportedError,
    ErrorBarsUnsupportedFamilyError,
)
from .editions import CommercialFeatureError
from .extended_properties import ExtendedProperties
from .extractor import extract_semantics
from .html_import import HtmlImportError, html_to_pptx
from .markup_import import import_markdown, markdown_to_pptx
from .presentation import Presentation
from .presentation_formats import PresentationFormat, inspect_presentation_format
from .sections import Section, SectionCollection, SectionRefusalError
from .shape_glow_edits import GlowSpec
from .shape_lock_edits import apply_shape_lock_edits
from .shape_locks import (
    ShapeLockRefusal,
    ShapeLocks,
    ShapeLockStaleTargetError,
    ShapeLockUnsupportedError,
)
from .shape_shadow_edits import OuterShadowSpec
from .text_autofit import TextAutofitScale

try:
    from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("wolfppt")
except _PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "BackgroundPictureRefusal",
    "BackgroundPictureRequest",
    "BubbleChartData",
    "CategoryChartData",
    "ChartErrorBar",
    "ChartErrorBars",
    "CommercialFeatureError",
    "ErrorBarEntry",
    "ErrorBars3DPolicyError",
    "ErrorBarsDuplicateAxisError",
    "ErrorBarsRefusal",
    "ErrorBarsSpec",
    "ErrorBarsStaleHandleError",
    "ErrorBarsUnsupportedError",
    "ErrorBarsUnsupportedFamilyError",
    "ExtendedProperties",
    "GlowSpec",
    "HtmlImportError",
    "NativeExtensionImportError",
    "OuterShadowSpec",
    "Presentation",
    "PresentationFormat",
    "Section",
    "SectionCollection",
    "SectionRefusalError",
    "ShapeLockRefusal",
    "ShapeLockStaleTargetError",
    "ShapeLockUnsupportedError",
    "ShapeLocks",
    "TextAutofitScale",
    "XyChartData",
    "__version__",
    "apply_background_picture_request",
    "apply_shape_lock_edits",
    "extract_semantics",
    "html_to_pptx",
    "import_markdown",
    "inspect_presentation_format",
    "load_background_picture_request",
    "markdown_to_pptx",
    "parse_background_picture_request",
]
