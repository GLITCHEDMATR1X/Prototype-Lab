from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from game.runtime_paths import source_result_dir, user_data_dir
from game.save_profile import ProfileState


@dataclass(frozen=True)
class MissionResult:
    completed: bool
    return_to_lab: bool
    district_complete: bool
    buildings_captured: int
    memory_fragments: int
    gleebs_alarms: int
    clean_hacks: int
    noisy_hacks: int
    maximum_trace: float
    completion_time: float
    prototype_lab_points_awarded: int


def result_dir() -> Path:
    override = os.environ.get("GHOST_SIGNAL_RESULT_DIR")
    if override:
        return Path(override).expanduser()
    if getattr(sys, "frozen", False):
        return user_data_dir() / "results"
    return source_result_dir()


def calculate_lab_points(profile: ProfileState) -> int:
    stats = profile.statistics
    score = (
        len(profile.captured_buildings) * 180
        + len(profile.memory_fragments) * 80
        + len(profile.districts_completed) * 360
        + int(stats.get("clean_hacks", 0)) * 18
        - int(stats.get("noisy_hacks", 0)) * 7
        - int(stats.get("gleebs_alarms", 0)) * 35
    )
    return max(0, score)


def build_mission_result(profile: ProfileState, completion_time: float) -> MissionResult:
    stats = profile.statistics
    complete = "industrial_grid" in profile.districts_completed
    return MissionResult(
        completed=complete,
        return_to_lab=complete,
        district_complete=complete,
        buildings_captured=len(profile.captured_buildings),
        memory_fragments=len(profile.memory_fragments),
        gleebs_alarms=int(stats.get("gleebs_alarms", 0)),
        clean_hacks=int(stats.get("clean_hacks", 0)),
        noisy_hacks=int(stats.get("noisy_hacks", 0)),
        maximum_trace=round(float(stats.get("maximum_trace", 0)), 2),
        completion_time=round(max(0.0, completion_time), 2),
        prototype_lab_points_awarded=calculate_lab_points(profile),
    )


def write_result_packets(profile: ProfileState, completion_time: float, directory: Path | None = None) -> dict[str, Path]:
    directory = directory or result_dir()
    directory.mkdir(parents=True, exist_ok=True)
    mission = build_mission_result(profile, completion_time)
    mission_data = asdict(mission)
    game_data = {
        "project": "GHOST SIGNAL: UTOPIA",
        "result_version": 1,
        **mission_data,
        "captured_buildings": sorted(profile.captured_buildings),
        "districts_completed": sorted(profile.districts_completed),
        "memory_fragment_ids": list(profile.memory_fragments),
        "method_usage": dict(sorted(profile.method_usage.items())),
    }
    preview_data = {
        "project": "GHOST SIGNAL: UTOPIA",
        "prototype_lab_points_awarded": mission.prototype_lab_points_awarded,
        "district_complete": mission.district_complete,
        "buildings_captured": mission.buildings_captured,
        "memory_fragments": mission.memory_fragments,
        "return_to_lab": mission.return_to_lab,
    }
    outputs = {
        "mission_result": directory / "mission_result.json",
        "game_result": directory / "game_result.json",
        "profile_preview": directory / "profile_preview.json",
    }
    outputs["mission_result"].write_text(json.dumps(mission_data, indent=2) + "\n", encoding="utf-8")
    outputs["game_result"].write_text(json.dumps(game_data, indent=2) + "\n", encoding="utf-8")
    outputs["profile_preview"].write_text(json.dumps(preview_data, indent=2) + "\n", encoding="utf-8")
    return outputs
