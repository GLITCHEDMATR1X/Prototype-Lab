from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LEVEL_ID = "enceladus_ice"
LEVEL_NAME = "Enceladus Ice"
MIMAS_LEVEL_ID = "mimas_snowfield"
MIMAS_LEVEL_NAME = "Mimas Snowfield"
IAPETUS_LEVEL_ID = "iapetus_ridge"
IAPETUS_LEVEL_NAME = "Iapetus Ridge"
TITAN_LEVEL_ID = "titan_methane_coast"
TITAN_LEVEL_NAME = "Titan Methane Coast"
MARS_LEVEL_ID = "mars_snow_caps"
MARS_LEVEL_NAME = "Mars Snow Caps"
PLUTO_LEVEL_ID = "pluto_nitrogen_frontier"
PLUTO_LEVEL_NAME = "Pluto Nitrogen Frontier"
EUROPA_LEVEL_ID = "europa_depths"
EUROPA_LEVEL_NAME = "Europa Depths"
TRITON_LEVEL_ID = "triton_valleys"
TRITON_LEVEL_NAME = "Triton Valleys"
WORLD_LEVELS = {
    "enceladus": {"level_id": LEVEL_ID, "level_name": LEVEL_NAME, "objective_name": "Cryo Extraction Quota"},
    "mimas": {"level_id": MIMAS_LEVEL_ID, "level_name": MIMAS_LEVEL_NAME, "objective_name": "Crater Snowpack Survey"},
    "iapetus": {"level_id": IAPETUS_LEVEL_ID, "level_name": IAPETUS_LEVEL_NAME, "objective_name": "Equatorial Ridge Ascent"},
    "titan": {"level_id": TITAN_LEVEL_ID, "level_name": TITAN_LEVEL_NAME, "objective_name": "Methane Coast Recon"},
    "mars": {"level_id": MARS_LEVEL_ID, "level_name": MARS_LEVEL_NAME, "objective_name": "Snow Cap Channel Survey"},
    "pluto": {"level_id": PLUTO_LEVEL_ID, "level_name": PLUTO_LEVEL_NAME, "objective_name": "Nitrogen Frontier Survey"},
    "europa": {"level_id": EUROPA_LEVEL_ID, "level_name": EUROPA_LEVEL_NAME, "objective_name": "Ice-Iron Canyon Survey"},
    "triton": {"level_id": TRITON_LEVEL_ID, "level_name": TRITON_LEVEL_NAME, "objective_name": "Neptune Valley Frost Survey"},
}
VALID_LEVELS = {str(v["level_id"]): str(v["level_name"]) for v in WORLD_LEVELS.values()}
CONTRACT_VERSION = "operation-starfall-level-contract-v4-all-worlds"

DEFAULT_RESULT_PATH = Path("verification/reports/level_result.json")
DEFAULT_PROFILE_PREVIEW_PATH = Path("verification/reports/lab_profile_preview.json")
DEFAULT_PROFILE_SAVE_PATH = Path("saves/lab_profile.json")


@dataclass
class EnceladusRunStats:
    resources_collected: int = 0
    raw_cargo_collected: int = 0
    refined_resources: int = 0
    modules_placed: int = 0
    upgrades_installed: int = 0
    hotspots_completed: int = 0
    hazards_survived: int = 0
    failures: int = 0
    time_seconds: int = 0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "EnceladusRunStats":
        fields = {k: int(data.get(k, 0) or 0) for k in cls.__dataclass_fields__}
        return cls(**fields)


@dataclass
class LevelResult:
    version: str
    level_id: str
    level_name: str
    completed: bool
    score: int
    lab_points_awarded: int
    time_seconds: int
    failures: int
    world_key: str = "enceladus"
    objective_name: str = "Cryo Extraction Quota"
    progress_percent: int = 0
    badges: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    return_to_lab: bool = True
    generated_at: float = field(default_factory=lambda: round(time.time(), 3))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LevelResult":
        return cls(
            version=str(data.get("version", CONTRACT_VERSION)),
            level_id=str(data.get("level_id", LEVEL_ID)),
            level_name=str(data.get("level_name", LEVEL_NAME)),
            completed=bool(data.get("completed", False)),
            score=int(data.get("score", 0) or 0),
            lab_points_awarded=int(data.get("lab_points_awarded", 0) or 0),
            time_seconds=int(data.get("time_seconds", 0) or 0),
            failures=int(data.get("failures", 0) or 0),
            world_key=str(data.get("world_key", "enceladus")),
            objective_name=str(data.get("objective_name", "Cryo Extraction Quota")),
            progress_percent=max(0, min(100, int(data.get("progress_percent", 0) or 0))),
            badges=[str(x) for x in data.get("badges", []) if str(x)],
            stats={str(k): int(v or 0) for k, v in dict(data.get("stats", {})).items()},
            return_to_lab=bool(data.get("return_to_lab", True)),
            generated_at=float(data.get("generated_at", round(time.time(), 3)) or 0.0),
        )


def calculate_score(stats: EnceladusRunStats, *, completed: bool) -> int:
    score = 0
    score += stats.resources_collected * 120
    score += stats.raw_cargo_collected * 45
    score += stats.refined_resources * 70
    score += stats.modules_placed * 95
    score += stats.upgrades_installed * 160
    score += stats.hotspots_completed * 180
    score += stats.hazards_survived * 35
    if completed:
        score += 550
    score -= stats.failures * 120
    if completed and stats.time_seconds > 0:
        score += max(0, 360 - min(stats.time_seconds, 360))
    return max(0, int(score))


def calculate_lab_points(score: int, stats: EnceladusRunStats, *, completed: bool) -> int:
    if not completed:
        return max(0, min(45, score // 30))
    points = 80 + score // 18
    points += stats.hotspots_completed * 10
    points += stats.modules_placed * 8
    if stats.failures == 0:
        points += 35
    return max(0, min(500, int(points)))


def badges_for(stats: EnceladusRunStats, *, completed: bool) -> list[str]:
    badges: list[str] = []
    if completed:
        badges.append("level_complete")
    if stats.resources_collected > 0 or stats.raw_cargo_collected > 0:
        badges.append("first_extract")
    if stats.modules_placed > 0:
        badges.append("builder")
    if stats.hotspots_completed >= 3:
        badges.append("hotspot_quota")
    if stats.failures == 0 and completed:
        badges.append("clean_run")
    if stats.time_seconds and stats.time_seconds <= 300 and completed:
        badges.append("fast_return")
    return badges


def _world_key_from_level_id(level_id: str) -> str:
    for key, info in WORLD_LEVELS.items():
        if str(info.get("level_id")) == str(level_id):
            return key
    return "enceladus"


def build_moon_level_result(
    stats: EnceladusRunStats | dict[str, Any] | None = None,
    *,
    completed: bool = True,
    level_id: str = LEVEL_ID,
    level_name: str | None = None,
    world_key: str | None = None,
    objective_name: str | None = None,
) -> LevelResult:
    run_stats = stats if isinstance(stats, EnceladusRunStats) else EnceladusRunStats.from_mapping(dict(stats or {}))
    resolved_world_key = str(world_key or _world_key_from_level_id(level_id))
    world_info = WORLD_LEVELS.get(resolved_world_key, {})
    resolved_name = level_name or str(world_info.get("level_name") or VALID_LEVELS.get(level_id, level_id.replace("_", " ").title()))
    resolved_objective = objective_name or str(world_info.get("objective_name") or "Moon Operation")
    score = calculate_score(run_stats, completed=completed)
    points = calculate_lab_points(score, run_stats, completed=completed)
    progress = 100 if completed else max(0, min(99, int((run_stats.hotspots_completed * 28) + (run_stats.resources_collected * 7) - (run_stats.failures * 10))))
    return LevelResult(
        version=CONTRACT_VERSION,
        level_id=level_id,
        level_name=resolved_name,
        completed=bool(completed),
        score=score,
        lab_points_awarded=points,
        time_seconds=int(run_stats.time_seconds),
        failures=int(run_stats.failures),
        world_key=resolved_world_key,
        objective_name=resolved_objective,
        progress_percent=progress,
        badges=badges_for(run_stats, completed=completed),
        stats=asdict(run_stats),
        return_to_lab=True,
    )


def build_world_level_result(world_key: str, stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    key = str(world_key or "enceladus").strip().lower()
    info = WORLD_LEVELS.get(key, WORLD_LEVELS["enceladus"])
    return build_moon_level_result(
        stats,
        completed=completed,
        level_id=str(info["level_id"]),
        level_name=str(info["level_name"]),
        world_key=key if key in WORLD_LEVELS else "enceladus",
        objective_name=str(info.get("objective_name", "Moon Operation")),
    )


def build_enceladus_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("enceladus", stats, completed=completed)


def build_mimas_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("mimas", stats, completed=completed)


def build_iapetus_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("iapetus", stats, completed=completed)


def build_titan_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("titan", stats, completed=completed)


def build_mars_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("mars", stats, completed=completed)


def build_pluto_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("pluto", stats, completed=completed)


def build_europa_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("europa", stats, completed=completed)


def build_triton_level_result(stats: EnceladusRunStats | dict[str, Any] | None = None, *, completed: bool = True) -> LevelResult:
    return build_world_level_result("triton", stats, completed=completed)


def validate_level_result(result: LevelResult | dict[str, Any]) -> tuple[bool, list[str]]:
    r = result if isinstance(result, LevelResult) else LevelResult.from_dict(result)
    issues: list[str] = []
    if r.level_id not in VALID_LEVELS:
        issues.append("wrong_level_id")
    if r.world_key not in WORLD_LEVELS:
        issues.append("wrong_world_key")
    if not r.level_name:
        issues.append("missing_level_name")
    if not r.objective_name:
        issues.append("missing_objective_name")
    if not 0 <= int(r.progress_percent) <= 100:
        issues.append("bad_progress_percent")
    if r.completed and int(r.progress_percent) != 100:
        issues.append("completed_without_100_percent")
    if r.score < 0:
        issues.append("negative_score")
    if r.lab_points_awarded < 0:
        issues.append("negative_lab_points")
    if r.lab_points_awarded > 500:
        issues.append("lab_points_above_cap")
    if r.completed and not r.return_to_lab:
        issues.append("completed_without_return_to_lab")
    if "level_complete" not in r.badges and r.completed:
        issues.append("completed_missing_badge")
    return not issues, issues


class LabProfile:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {
            "version": "prototype-lab-profile-v1",
            "total_lab_points": 0,
            "levels": {},
            "unlocks": {},
        }
        self.data.setdefault("total_lab_points", 0)
        self.data.setdefault("levels", {})
        self.data.setdefault("unlocks", {})

    @classmethod
    def load(cls, path: Path) -> "LabProfile":
        if path.exists():
            return cls(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    def apply_result(self, result: LevelResult | dict[str, Any]) -> dict[str, Any]:
        r = result if isinstance(result, LevelResult) else LevelResult.from_dict(result)
        ok, issues = validate_level_result(r)
        if not ok:
            raise ValueError("invalid level result: " + ",".join(issues))
        levels = self.data.setdefault("levels", {})
        current = dict(levels.get(r.level_id, {}))
        previous_best = int(current.get("best_score", 0) or 0)
        previous_runs = int(current.get("runs", 0) or 0)
        current.update({
            "level_name": r.level_name,
            "world_key": r.world_key,
            "objective_name": r.objective_name,
            "completed": bool(current.get("completed", False) or r.completed),
            "best_score": max(previous_best, r.score),
            "last_score": r.score,
            "last_progress_percent": r.progress_percent,
            "last_lab_points_awarded": r.lab_points_awarded,
            "runs": previous_runs + 1,
            "badges": sorted(set(current.get("badges", [])) | set(r.badges)),
            "last_result": r.to_dict(),
        })
        levels[r.level_id] = current
        self.data["total_lab_points"] = int(self.data.get("total_lab_points", 0) or 0) + r.lab_points_awarded
        if r.completed:
            self.data.setdefault("unlocks", {}).setdefault("prototype_keys", [])
            keys = self.data["unlocks"]["prototype_keys"]
            if r.level_id not in keys:
                keys.append(r.level_id)
        return current

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


def write_level_result(result: LevelResult, path: Path = DEFAULT_RESULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    lines = [
        f"# {result.level_name} Level Result",
        "",
        f"World: {result.world_key}",
        f"Level: {result.level_name}",
        f"Objective: {result.objective_name}",
        f"Progress: {result.progress_percent}%",
        f"Completed: {result.completed}",
        f"Score: {result.score}",
        f"Lab points awarded: {result.lab_points_awarded}",
        f"Return to Lab: {result.return_to_lab}",
        f"Badges: {', '.join(result.badges) if result.badges else 'none'}",
        "",
        "## Stats",
    ]
    for key, value in result.stats.items():
        lines.append(f"- {key}: {value}")
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def preview_apply_result(result: LevelResult, path: Path = DEFAULT_PROFILE_PREVIEW_PATH) -> LabProfile:
    profile = LabProfile()
    profile.apply_result(result)
    profile.save(path)
    return profile


def _standard_stats_for_world(world_key: str) -> EnceladusRunStats:
    key = str(world_key or "enceladus").lower()
    presets = {
        "enceladus": dict(resources_collected=3, raw_cargo_collected=5, refined_resources=3, modules_placed=2, upgrades_installed=1, hotspots_completed=3, hazards_survived=2, failures=0, time_seconds=286),
        "mimas": dict(resources_collected=3, raw_cargo_collected=4, refined_resources=2, modules_placed=1, upgrades_installed=1, hotspots_completed=3, hazards_survived=1, failures=0, time_seconds=312),
        "iapetus": dict(resources_collected=4, raw_cargo_collected=3, refined_resources=2, modules_placed=1, upgrades_installed=1, hotspots_completed=2, hazards_survived=4, failures=0, time_seconds=338),
        "titan": dict(resources_collected=4, raw_cargo_collected=5, refined_resources=2, modules_placed=2, upgrades_installed=1, hotspots_completed=3, hazards_survived=3, failures=0, time_seconds=326),
        "mars": dict(resources_collected=4, raw_cargo_collected=4, refined_resources=2, modules_placed=1, upgrades_installed=1, hotspots_completed=3, hazards_survived=2, failures=0, time_seconds=318),
        "pluto": dict(resources_collected=3, raw_cargo_collected=4, refined_resources=2, modules_placed=1, upgrades_installed=1, hotspots_completed=3, hazards_survived=4, failures=0, time_seconds=352),
        "europa": dict(resources_collected=4, raw_cargo_collected=3, refined_resources=2, modules_placed=1, upgrades_installed=1, hotspots_completed=3, hazards_survived=5, failures=0, time_seconds=344),
        "triton": dict(resources_collected=4, raw_cargo_collected=4, refined_resources=2, modules_placed=1, upgrades_installed=1, hotspots_completed=3, hazards_survived=4, failures=0, time_seconds=336),
    }
    return EnceladusRunStats(**presets.get(key, presets["enceladus"]))


def standard_world_completion_result(world_key: str) -> LevelResult:
    return build_world_level_result(world_key, _standard_stats_for_world(world_key), completed=True)


def standard_completion_result() -> LevelResult:
    return standard_world_completion_result("enceladus")


def standard_mimas_completion_result() -> LevelResult:
    return standard_world_completion_result("mimas")


def standard_iapetus_completion_result() -> LevelResult:
    return standard_world_completion_result("iapetus")


def standard_titan_completion_result() -> LevelResult:
    return standard_world_completion_result("titan")


def standard_mars_completion_result() -> LevelResult:
    return standard_world_completion_result("mars")


def standard_pluto_completion_result() -> LevelResult:
    return standard_world_completion_result("pluto")


def standard_europa_completion_result() -> LevelResult:
    return standard_world_completion_result("europa")


def standard_triton_completion_result() -> LevelResult:
    return standard_world_completion_result("triton")


def standard_all_world_results() -> dict[str, LevelResult]:
    return {key: standard_world_completion_result(key) for key in WORLD_LEVELS}

def failed_probe_result() -> LevelResult:
    return build_enceladus_level_result(
        EnceladusRunStats(
            resources_collected=1,
            raw_cargo_collected=1,
            refined_resources=0,
            modules_placed=0,
            upgrades_installed=0,
            hotspots_completed=1,
            hazards_survived=0,
            failures=2,
            time_seconds=420,
        ),
        completed=False,
    )
