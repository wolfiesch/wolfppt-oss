"""Shared result models for corpus runner lanes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LaneResult:
    name: str
    status: str
    elapsed_ms: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FixtureRun:
    fixture_id: str
    path: str
    lanes: list[LaneResult]

    @property
    def status(self) -> str:
        return "pass" if all(lane.status in {"pass", "skip"} for lane in self.lanes) else "fail"


@dataclass(frozen=True)
class CorpusRun:
    run_id: str
    fixtures: list[FixtureRun]
    tool_availability: list[dict[str, Any]]
    required_lanes: tuple[str, ...] = ()
    min_powerpoint_exported_slides: int | None = None

    @property
    def status(self) -> str:
        if self.required_lane_failures:
            return "fail"
        if self.powerpoint_export_sample_failures:
            return "fail"
        return "pass" if all(fixture.status == "pass" for fixture in self.fixtures) else "fail"

    @property
    def powerpoint_exported_slide_count(self) -> int:
        return sum(
            len(lane.details.get("exported_files", []))
            for fixture in self.fixtures
            for lane in fixture.lanes
            if lane.name == "powerpoint-render" and lane.status == "pass"
        )

    @property
    def powerpoint_export_sample_failures(self) -> list[dict[str, int]]:
        if self.min_powerpoint_exported_slides is None:
            return []
        observed = self.powerpoint_exported_slide_count
        if observed >= self.min_powerpoint_exported_slides:
            return []
        return [
            {
                "observed_powerpoint_exported_slides": observed,
                "required_min_powerpoint_exported_slides": self.min_powerpoint_exported_slides,
            }
        ]

    @property
    def required_lane_failures(self) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []
        for required_lane in self.required_lanes:
            missing: list[str] = []
            skipped: list[str] = []
            failed: list[str] = []
            for fixture in self.fixtures:
                matching = [lane for lane in fixture.lanes if lane.name == required_lane]
                if not matching:
                    missing.append(fixture.fixture_id)
                    continue
                lane = matching[0]
                if lane.status == "skip":
                    skipped.append(fixture.fixture_id)
                elif lane.status == "fail":
                    failed.append(fixture.fixture_id)
            if missing or skipped or failed:
                failures.append(
                    {
                        "lane": required_lane,
                        "missing_count": len(missing),
                        "skipped_count": len(skipped),
                        "failed_count": len(failed),
                        "missing_fixtures": missing,
                        "skipped_fixtures": skipped,
                        "failed_fixtures": failed,
                    }
                )
        return failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "required_lanes": list(self.required_lanes),
            "required_lane_failures": self.required_lane_failures,
            "min_powerpoint_exported_slides": self.min_powerpoint_exported_slides,
            "powerpoint_exported_slide_count": self.powerpoint_exported_slide_count,
            "powerpoint_export_sample_failures": self.powerpoint_export_sample_failures,
            "tool_availability": self.tool_availability,
            "fixtures": [
                {
                    "fixture_id": fixture.fixture_id,
                    "path": fixture.path,
                    "status": fixture.status,
                    "lanes": [asdict(lane) for lane in fixture.lanes],
                }
                for fixture in self.fixtures
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# WolfPPT Corpus Run {self.run_id}",
            "",
            f"Status: **{self.status}**",
            "",
        ]
        if self.required_lanes:
            lines.extend(
                [
                    "## Required Lane Gates",
                    "",
                    "| lane | status | missing fixtures | skipped fixtures | failed fixtures |",
                    "|---|---|---:|---:|---:|",
                ]
            )
            failures_by_lane = {
                failure["lane"]: failure for failure in self.required_lane_failures
            }
            for lane in self.required_lanes:
                failure = failures_by_lane.get(lane)
                if failure is None:
                    lines.append(f"| `{lane}` | pass | 0 | 0 | 0 |")
                else:
                    lines.append(
                        "| `{lane}` | fail | {missing_count} | {skipped_count} | "
                        "{failed_count} |".format(**failure)
                    )
            lines.append("")
        if self.min_powerpoint_exported_slides is not None:
            lines.extend(
                [
                    "## PowerPoint Export Sample Gate",
                    "",
                    "| observed exported slide PNGs | required minimum | status |",
                    "|---:|---:|---|",
                    (
                        f"| {self.powerpoint_exported_slide_count} | "
                        f"{self.min_powerpoint_exported_slides} | {self._powerpoint_export_gate_status()} |"
                    ),
                    "",
                ]
            )
        lines.extend(
            [
                "## Fixtures",
                "",
                "| fixture | status | lanes |",
                "|---|---|---|",
            ]
        )
        for fixture in self.fixtures:
            lane_summary = ", ".join(f"{lane.name}:{lane.status}" for lane in fixture.lanes)
            lines.append(f"| `{fixture.fixture_id}` | {fixture.status} | {lane_summary} |")
        lines.extend(["", "## Tools", "", "| tool | available | role |", "|---|---:|---|"])
        for tool in self.tool_availability:
            lines.append(f"| {tool['name']} | {tool['available']} | {tool['role']} |")
        return "\n".join(lines) + "\n"

    def _powerpoint_export_gate_status(self) -> str:
        return "fail" if self.powerpoint_export_sample_failures else "pass"
