"""Small helpers for recording third-party SDK versions in benchmark evidence."""

from __future__ import annotations

import importlib.metadata
import xml.etree.ElementTree as ET
from pathlib import Path


def installed_package_version(*distribution_names: str) -> str | None:
    for name in distribution_names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def maven_dependency_versions(pom_path: Path, artifacts: set[str]) -> dict[str, str]:
    if not pom_path.exists():
        return {}
    root = ET.parse(pom_path).getroot()
    namespace = _xml_namespace(root.tag)
    versions: dict[str, str] = {}
    for dependency in root.findall(f".//{namespace}dependency"):
        artifact = dependency.findtext(f"{namespace}artifactId")
        version = dependency.findtext(f"{namespace}version")
        if artifact in artifacts and version:
            versions[artifact] = version
    return versions


def dotnet_package_versions(project_path: Path, packages: set[str]) -> dict[str, str]:
    if not project_path.exists():
        return {}
    root = ET.parse(project_path).getroot()
    versions: dict[str, str] = {}
    for package in root.findall(".//PackageReference"):
        package_name = package.attrib.get("Include")
        version = package.attrib.get("Version")
        if package_name in packages and version:
            versions[package_name] = version
    return versions


def _xml_namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[0] + "}"
    return ""
