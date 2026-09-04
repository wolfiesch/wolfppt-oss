"""Adapter discovery for optional PPTX tooling."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import asdict, dataclass

from ..native import native_available
from .apache_poi import (
    apache_poi_roundtrip_available,
    apache_poi_roundtrip_unavailable_reason,
)
from .aspose_slides import (
    aspose_slides_roundtrip_available,
    aspose_slides_roundtrip_unavailable_reason,
)
from .aspose_docker import (
    aspose_docker_roundtrip_available,
    aspose_docker_roundtrip_unavailable_reason,
)
from .external_command import (
    EXTERNAL_ROUNDTRIP_ENV,
    external_command_roundtrip_available,
    external_command_roundtrip_unavailable_reason,
)
from .openxml import VALIDATOR_PROJECT
from .openxml_sdk import openxml_sdk_roundtrip_available
from .powerpoint import powerpoint_available
from .pptxgenjs import pptxgenjs_available
from .rust_core import rust_cli_available
from .spire_presentation import (
    spire_presentation_roundtrip_available,
    spire_presentation_roundtrip_unavailable_reason,
)
from .syncfusion import (
    syncfusion_roundtrip_available,
    syncfusion_roundtrip_unavailable_reason,
)
from .toolchain import dotnet_command


@dataclass(frozen=True)
class ToolInfo:
    name: str
    available: bool
    role: str
    detail: str
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def available_tools() -> list[ToolInfo]:
    return [
        ToolInfo(
            name="stdlib-extractor",
            available=True,
            role="semantic oracle",
            detail="Built into WolfPPT; no external dependencies.",
        ),
        ToolInfo(
            name="python-pptx",
            available=importlib.util.find_spec("pptx") is not None,
            role="API baseline",
            detail="Optional python-pptx adapter for API comparison and round-trip probes.",
        ),
        ToolInfo(
            name="dotnet",
            available=dotnet_command() is not None and VALIDATOR_PROJECT.exists(),
            role="Open XML SDK validation host",
            detail="Runs the bundled DocumentFormat.OpenXml validator project.",
        ),
        ToolInfo(
            name="openxml-sdk-roundtrip",
            available=openxml_sdk_roundtrip_available(),
            role="official .NET Open XML SDK baseline",
            detail="Opens and saves copied PPTX/PPTM packages through DocumentFormat.OpenXml.",
        ),
        ToolInfo(
            name="pptxgenjs-generate",
            available=pptxgenjs_available(),
            role="JavaScript generation baseline",
            detail="Generates PPTX files through PptxGenJS; this is not an existing-deck round-trip lane.",
        ),
        ToolInfo(
            name="apache-poi-roundtrip",
            available=apache_poi_roundtrip_available(),
            role="Java Apache POI baseline",
            detail="Opens and writes existing PPTX files through Apache POI XSLF when Maven is installed.",
            unavailable_reason=apache_poi_roundtrip_unavailable_reason(),
        ),
        ToolInfo(
            name="aspose-slides-roundtrip",
            available=aspose_slides_roundtrip_available(),
            role="commercial Aspose.Slides baseline",
            detail="Opens and writes existing PPTX/PPTM files through Aspose.Slides for Python when installed.",
            unavailable_reason=aspose_slides_roundtrip_unavailable_reason(),
        ),
        ToolInfo(
            name="aspose-docker-roundtrip",
            available=aspose_docker_roundtrip_available(),
            role="commercial Aspose.Slides Docker baseline",
            detail=(
                "Opens and writes existing PPTX/PPTM files through "
                "Aspose.Slides inside a pinned Docker runtime."
            ),
            unavailable_reason=aspose_docker_roundtrip_unavailable_reason(),
        ),
        ToolInfo(
            name="spire-presentation-roundtrip",
            available=spire_presentation_roundtrip_available(),
            role="commercial Spire.Presentation baseline",
            detail=(
                "Opens and writes existing PPTX/PPTM files through "
                "Spire.Presentation for Python after a blank-save runtime probe."
            ),
            unavailable_reason=spire_presentation_roundtrip_unavailable_reason(),
        ),
        ToolInfo(
            name="syncfusion-roundtrip",
            available=syncfusion_roundtrip_available(),
            role="commercial Syncfusion baseline",
            detail=(
                "Opens and writes existing PPTX/PPTM files through the "
                "bundled Syncfusion .NET example when licensed."
            ),
            unavailable_reason=syncfusion_roundtrip_unavailable_reason(),
        ),
        ToolInfo(
            name="external-command-roundtrip",
            available=external_command_roundtrip_available(),
            role="custom external SDK baseline",
            detail=(
                "Runs the command configured in "
                f"{EXTERNAL_ROUNDTRIP_ENV} with {{input}} and {{output}} placeholders."
            ),
            unavailable_reason=external_command_roundtrip_unavailable_reason(),
        ),
        ToolInfo(
            name="libreoffice",
            available=_which_any("soffice", "libreoffice") is not None,
            role="non-authoritative render smoke",
            detail="Used for optional headless PDF/image export.",
        ),
        ToolInfo(
            name="microsoft-powerpoint",
            available=powerpoint_available(),
            role="gold visual oracle",
            detail="Optional local PowerPoint render lane using PDF export plus PNG conversion.",
        ),
        ToolInfo(
            name="wolfppt-rust-cli",
            available=rust_cli_available(),
            role="Rust core package reader/writer",
            detail="Runs wolfppt-cli inspect, roundtrip, add-slide, add-image, add-table, replace-text, replace-text-run, replace-image, and replace-table-cell through cargo.",
        ),
        ToolInfo(
            name="wolfppt-native",
            available=native_available(),
            role="Native Python binding",
            detail="Imports wolfppt_native built by maturin for inspect, summary, roundtrip, add-slide, add-image, add-table, add-connector, replace-text, replace-text-run, replace-image, and replace-table-cell.",
        ),
    ]


def _which_any(*names: str) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None
